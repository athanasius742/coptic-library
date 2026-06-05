#!/usr/bin/env python3
"""
ct_ocr_batch.py — convert coptic-treasures PDFs into per-chapter
chapters/<NN-slug>/content.xhtml + a validated <book-slug>.epub, OCR'ing the
scanned / corrupt-text-layer pages with Claude vision via the **Anthropic Batch
API** (50% cheaper, async, and not subject to the Claude Code subagent throttle).

REQUIRES `ANTHROPIC_API_KEY` (see tools/README.md / .env.example) for any real
OCR. `--dry-run` does everything EXCEPT call the API (triage + rasterize + build
the batch request payloads + report counts/cost estimate) so the plumbing can be
validated offline.

Pipeline per book:
  1. TRIAGE (PyMuPDF, deterministic): per page classify digital | scanned | fake
     (corrupt text layer — high ratio of Arabic presentation forms / Latin / PUA
     glyphs inside Arabic, or no real Arabic). Genuine digital pages keep their
     text layer verbatim; everything else is rasterized (200 dpi) for OCR.
  2. OCR (Batch API): one request per page-image, shared cached system prompt
     ("transcribe EXACTLY, preserve tashkeel, RTL order, no translation"). The
     transcription is the SACRED source; uncertain spans are marked ⟦?⟧.
  3. ASSEMBLE (deterministic): merge digital + OCR text in page order, split into
     chapters (doc.get_toc() when present, else heading markers), write the
     html-subset content.xhtml + manifest.json, then build_epub.py + verify_book.py.

Resumable: a book with an .epub is skipped; per-book triage/plan and submitted
batch ids live under BOOK_DIR/.build/ so a re-run continues (re-OCR is avoided).

Usage:
  python3 tools/ct_ocr_batch.py --dry-run --limit 5     # offline: triage + payloads
  python3 tools/ct_ocr_batch.py --submit --limit 200    # build + submit batches
  python3 tools/ct_ocr_batch.py --collect               # poll + assemble finished batches
  python3 tools/ct_ocr_batch.py                          # submit + wait + collect (all pending)
"""
import argparse, base64, glob, json, os, re, subprocess, sys, time
from collections import Counter

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
CATALOG = os.path.join(THIS, "ct_catalog.json")
MODEL = "claude-opus-4-8"   # vision OCR; swap to a smaller model to cut cost
RASTER_DPI = 200
MAX_REQ_PER_BATCH = 1000

# build_epub.py / verify_book.py live on feat/publishing-pipeline; resolve from the
# repo tools dir first, else the staged pilot copy.
TOOLDIRS = [THIS, "/home/jimmy/coptic-pilot/tools"]


def tool(name):
    for d in TOOLDIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise SystemExit(f"{name} not found in {TOOLDIRS} (bring the publishing-pipeline tools onto this branch)")


# ----------------------------- triage -----------------------------
PRES_FORM = lambda c: 0xFB50 <= ord(c) <= 0xFEFF      # Arabic presentation forms
ARABIC = lambda c: 0x0600 <= ord(c) <= 0x06FF          # base Arabic block
PUA = lambda c: 0xE000 <= ord(c) <= 0xF8FF
LATIN = lambda c: ("A" <= c <= "Z") or ("a" <= c <= "z")


def classify_page(text, image_cover):
    """Return 'digital' | 'scanned' | 'fake'."""
    t = [c for c in text if not c.isspace()]
    n = len(t)
    if n < 20:
        return "scanned"
    pres = sum(PRES_FORM(c) for c in t)
    ara = sum(ARABIC(c) for c in t)
    pua = sum(PUA(c) for c in t)
    lat = sum(LATIN(c) for c in t)
    # corrupt layer signatures: presentation forms dominate, PUA present, or
    # almost no real base-Arabic letters in a page that clearly is Arabic text.
    if pua > n * 0.02:
        return "fake"
    if pres > (ara + pres) * 0.5 and (ara + pres) > 0.3 * n:
        return "fake"
    if ara < n * 0.15 and lat < n * 0.5:   # not Arabic, not Latin -> gibberish
        return "fake"
    return "digital"


def triage(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    pages = []
    for i, pg in enumerate(doc):
        text = pg.get_text("text")
        area = abs(pg.rect.width * pg.rect.height) or 1
        img_area = 0.0
        for blk in pg.get_text("dict").get("blocks", []):
            if blk.get("type") == 1:  # image block
                x0, y0, x1, y1 = blk["bbox"]
                img_area += abs((x1 - x0) * (y1 - y0))
        cls = classify_page(text, img_area / area)
        pages.append({"index": i, "cls": cls, "chars": len(text)})
    toc = [t for t in doc.get_toc() if len(t) >= 3]
    return doc, pages, toc


# ----------------------------- OCR prompt -----------------------------
OCR_SYSTEM = (
    "You transcribe a single scanned page of a Coptic-Orthodox Arabic book. Output ONLY the "
    "verbatim text of the page in natural right-to-left reading order. Preserve EVERY Arabic "
    "diacritic (tashkeel) exactly. Do NOT translate, summarize, correct, reorder, or add anything. "
    "Separate paragraphs with a blank line. Prefix a heading line with '## '. Wrap genuinely "
    "left-to-right runs (Latin/numbers-as-LTR) inline as normal text. Mark any illegible or "
    "uncertain span as ⟦?⟧. Exclude running headers/footers and bare page numbers. If the page "
    "has no body text (blank/figure-only), output an empty response."
)


def ocr_request(custom_id, png_path):
    b64 = base64.standard_b64encode(open(png_path, "rb").read()).decode()
    return {
        "custom_id": custom_id,
        "params": {
            "model": MODEL,
            "max_tokens": 8000,
            "system": [{"type": "text", "text": OCR_SYSTEM,
                        "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/png", "data": b64}},
                {"type": "text", "text": "Transcribe this page."},
            ]}],
        },
    }


# ----------------------------- plan (triage + rasterize) -----------------------------
def plan_book(book_dir):
    """Triage + rasterize OCR pages + extract digital text. Returns the plan dict."""
    import fitz
    pdf = os.path.join(book_dir, "book.pdf")
    build = os.path.join(book_dir, ".build")
    pdir = os.path.join(build, "pages")
    os.makedirs(pdir, exist_ok=True)
    doc, pages, toc = triage(pdf)
    plan = {"pages": [], "toc": toc, "counts": dict(Counter(p["cls"] for p in pages))}
    for p in pages:
        i = p["index"]
        rec = {"index": i, "cls": p["cls"]}
        if p["cls"] == "digital":
            rec["text"] = doc[i].get_text("text")
        else:
            png = os.path.join(pdir, f"p{i:04d}.png")
            if not os.path.exists(png):
                pix = doc[i].get_pixmap(dpi=RASTER_DPI)
                pix.save(png)
            rec["png"] = png
            rec["custom_id"] = f"p{i:04d}"
        plan["pages"].append(rec)
    doc.close()
    with open(os.path.join(build, "ocr_plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False)
    return plan


# ----------------------------- assemble -----------------------------
ENVELOPE = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ar" lang="ar" dir="rtl">\n'
            '<head><meta charset="utf-8"/><title>{title}</title>\n'
            '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            '<body dir="rtl"><h1>{title}</h1>\n{body}\n</body></html>\n')


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page_text_to_html(text):
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        para = para.strip()
        if not para:
            continue
        if para.startswith("## "):
            out.append(f"<h2>{esc(para[3:].strip())}</h2>")
        else:
            out.append("<p>" + esc(para).replace("\n", "<br/>") + "</p>")
    return "\n".join(out)


def assemble_book(book_dir, page_text):
    """page_text: {page_index: text}. Split into chapters by toc, write content.xhtml + manifest."""
    plan = json.load(open(os.path.join(book_dir, ".build", "ocr_plan.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(book_dir, "meta.json"), encoding="utf-8"))
    npages = len(plan["pages"])
    # chapter boundaries from toc page numbers (1-based in get_toc), else single chapter
    bounds = sorted({t[2] - 1 for t in plan["toc"] if 0 <= t[2] - 1 < npages})
    if not bounds or bounds[0] != 0:
        bounds = [0] + bounds
    titles = {}
    for t in plan["toc"]:
        if t[2] - 1 in range(npages):
            titles.setdefault(t[2] - 1, t[1])
    manifest = []
    for ci, start in enumerate(bounds, 1):
        end = bounds[ci] if ci < len(bounds) else npages
        body = "\n".join(page_text.get(i, "") for i in range(start, end)).strip()
        title = titles.get(start) or meta.get("title", "") or f"الفصل {ci}"
        slug = f"ch{ci:02d}"
        cdir = os.path.join(book_dir, "chapters", f"{ci:02d}-{slug}")
        os.makedirs(cdir, exist_ok=True)
        html = ENVELOPE.format(title=esc(title), body=page_text_to_html(body) or "<p></p>")
        with open(os.path.join(cdir, "content.xhtml"), "w", encoding="utf-8") as f:
            f.write(html)
        manifest.append({"order": ci, "slug": slug, "file": f"{ci:02d}-{slug}.html",
                         "title": title, "url": meta.get("source_url", "")})
    with open(os.path.join(book_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def build_and_verify(book_dir):
    py = sys.executable
    subprocess.run([py, tool("build_epub.py"), book_dir, "--force"], check=True)
    subprocess.run([py, tool("verify_book.py"), book_dir])


# ----------------------------- pending selection -----------------------------
def pending_books(limit, only):
    recs = json.load(open(CATALOG, encoding="utf-8"))
    out = []
    for x in recs:
        if x.get("status") not in ("downloaded", "partial"):
            continue
        d = os.path.join(REPO, x["dest"])
        if only and only not in d:
            continue
        if not os.path.exists(os.path.join(d, "book.pdf")):
            continue
        if glob.glob(os.path.join(d, "*.epub")):
            continue
        out.append(d)
        if limit and len(out) >= limit:
            break
    return out


# ----------------------------- main -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="triage + rasterize + payloads only, no API")
    ap.add_argument("--submit", action="store_true", help="submit batches and exit (poll later with --collect)")
    ap.add_argument("--collect", action="store_true", help="poll submitted batches and assemble")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--book", default="", help="substring filter on book dir")
    args = ap.parse_args()

    books = pending_books(args.limit, args.book)
    print(f"{len(books)} pending books", flush=True)

    # 1) plan all books (triage + rasterize) — no API
    digital_books, ocr_requests = [], []
    for d in books:
        plan = plan_book(d)
        print(f"  triage {os.path.basename(d)[:40]} -> {plan['counts']}", flush=True)
        if all(p["cls"] == "digital" for p in plan["pages"]):
            digital_books.append(d)
        for p in plan["pages"]:
            if p["cls"] != "digital":
                ocr_requests.append((d, p["custom_id"], p["png"]))

    n_ocr_pages = len(ocr_requests)
    print(f"\n{len(digital_books)} fully-digital books (no OCR) · {n_ocr_pages} pages need OCR "
          f"across {len(books)-len(digital_books)} books", flush=True)

    # assemble born-digital books immediately (no API needed)
    for d in digital_books:
        pt = {p["index"]: p.get("text", "") for p in
              json.load(open(os.path.join(d, ".build", "ocr_plan.json"), encoding="utf-8"))["pages"]}
        assemble_book(d, pt)
        build_and_verify(d)
        print(f"  built (digital) {os.path.basename(d)[:40]}", flush=True)

    if args.dry_run:
        # build payloads to validate structure + estimate, don't submit
        sample = ocr_request(*ocr_requests[0][1:]) if ocr_requests else None
        approx_mb = sum(os.path.getsize(p) for _, _, p in ocr_requests) * 1.37 / 1e6
        print(f"\n[dry-run] would submit {n_ocr_pages} OCR requests "
              f"(~{approx_mb:.0f} MB of base64 image data, "
              f"~{(n_ocr_pages+MAX_REQ_PER_BATCH-1)//MAX_REQ_PER_BATCH} batches). "
              f"Sample request custom_id={sample['custom_id'] if sample else None}.")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set — see tools/README.md / .env.example")
    import anthropic
    client = anthropic.Anthropic()

    # 2) submit OCR batches (custom_id namespaced by book index)
    bookidx = {d: i for i, d in enumerate(books)}
    reqs = [ocr_request(f"b{bookidx[d]}_{cid}", png) for d, cid, png in ocr_requests]
    batch_ids = []
    for i in range(0, len(reqs), MAX_REQ_PER_BATCH):
        chunk = reqs[i:i + MAX_REQ_PER_BATCH]
        b = client.messages.batches.create(requests=chunk)
        batch_ids.append(b.id)
        print(f"  submitted batch {b.id} ({len(chunk)} reqs)", flush=True)
    json.dump({"batch_ids": batch_ids, "books": books},
              open(os.path.join(THIS, "ct_ocr_state.json"), "w"), ensure_ascii=False, indent=2)
    if args.submit:
        print("submitted; run with --collect once batches end.")
        return

    # 3) collect (default path also falls through here)
    collect(client, batch_ids, books, bookidx)


def collect(client, batch_ids, books, bookidx):
    inv = {i: d for d, i in bookidx.items()}
    texts = {}  # (book_idx, page) -> text
    for bid in batch_ids:
        while True:
            b = client.messages.batches.retrieve(bid)
            if b.processing_status == "ended":
                break
            print(f"  batch {bid}: {b.processing_status} {b.request_counts}", flush=True)
            time.sleep(30)
        for r in client.messages.batches.results(bid):
            if r.result.type != "succeeded":
                continue
            m = re.match(r"b(\d+)_p(\d+)", r.custom_id)
            bi, pi = int(m.group(1)), int(m.group(2))
            txt = "".join(blk.text for blk in r.result.message.content if blk.type == "text")
            texts[(bi, pi)] = txt
    # assemble each OCR book (merge digital + OCR text)
    for d in books:
        bi = bookidx[d]
        planf = os.path.join(d, ".build", "ocr_plan.json")
        if not os.path.exists(planf):
            continue
        plan = json.load(open(planf, encoding="utf-8"))
        if all(p["cls"] == "digital" for p in plan["pages"]):
            continue  # already built
        pt = {}
        for p in plan["pages"]:
            pt[p["index"]] = p.get("text") if p["cls"] == "digital" else texts.get((bi, p["index"]), "")
        assemble_book(d, pt)
        build_and_verify(d)
        print(f"  built (ocr) {os.path.basename(d)[:40]}", flush=True)


if __name__ == "__main__":
    main()
