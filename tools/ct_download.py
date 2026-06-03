#!/usr/bin/env python3
"""
ct_download.py — Phase 2 of the coptic-treasures extraction. Reads
`tools/ct_catalog.json` (produced by ct_crawl.py) and downloads every book's
raw file(s) from Google Drive into the st-takla directory convention:

    books/coptic-treasures.com/<author_slug>/<book_slug>/
        book.pdf            (or book-01.pdf, book-02.pdf, … for multi-file books;
                             extension follows the real file type if not a PDF)
        cover.jpg
        meta.json

meta.json mirrors the st-takla meta.json schema (slug/title/author/source/…)
plus coptic-treasures specifics (drive ids, file sizes, categories, rating).

Google Drive: a public file downloads from
    https://drive.google.com/uc?export=download&id=<ID>
Small files stream straight through. Large files first return an HTML
virus-scan interstitial — we carry cookies across the session and resubmit the
confirm form (handles both the legacy `confirm=<token>` cookie flow and the
newer drive.usercontent.google.com form). Non-Drive links (archive.org, direct
PDFs, …) are fetched as-is.

Resumable & idempotent: a book whose primary file already exists on disk
(non-empty) is skipped. Status is written back to ct_catalog.json
(downloaded / partial / failed / no-file). Safe to re-run; pass --retry-failed
to re-attempt failed/partial books.

Usage:
  python3 tools/ct_download.py                 # download everything pending
  python3 tools/ct_download.py --limit 20      # first 20 pending (sample)
  python3 tools/ct_download.py --author dr-bola-wagih
  python3 tools/ct_download.py --retry-failed
  python3 tools/ct_download.py --delay 1.0
"""
import argparse, json, os, re, sys, time
import urllib.request, urllib.error, urllib.parse
import http.cookiejar
from html import unescape

UA = "Mozilla/5.0 (X11; Linux x86_64) CopticLibrary/1.0 (+book archival; contact athanasius742)"
TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
CATALOG = os.path.join(TOOLS, "ct_catalog.json")
GD_BASE = "https://drive.google.com/uc?export=download&id="
SAVE_EVERY = 10
# HTTP codes that mean "this file is gone/restricted" — never retry these.
PERMANENT_HTTP = {400, 401, 403, 404, 410}


def _permanent(e):
    return isinstance(e, urllib.error.HTTPError) and e.code in PERMANENT_HTTP


# ----------------------------- catalog io -----------------------------
def load_catalog():
    with open(CATALOG, encoding="utf-8") as f:
        return json.load(f)


def save_catalog(records):
    tmp = CATALOG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CATALOG)


# ----------------------------- http session -----------------------------
def make_opener():
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", UA)]
    return op


def _filename_from_headers(resp):
    cd = resp.headers.get("Content-Disposition", "") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    if m:
        return urllib.parse.unquote(m.group(1).strip())
    return ""


def _ext_for(fname, head):
    if fname and "." in os.path.basename(fname):
        return os.path.splitext(fname)[1].lower()
    if head[:5] == b"%PDF-":
        return ".pdf"
    if head[:4] == b"PK\x03\x04":
        return ".zip"  # also docx/epub containers; .zip is a safe generic
    if head[:4] in (b"\xd0\xcf\x11\xe0",):
        return ".doc"
    if head[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def _is_html(resp, head):
    ct = (resp.headers.get("Content-Type", "") or "").lower()
    if "text/html" in ct:
        return True
    return head.lstrip()[:1] == b"<" and b"<html" in head[:512].lower()


def _drive_confirm_request(html_bytes, orig_url):
    """Build the follow-up Request that bypasses the virus-scan interstitial."""
    html = html_bytes.decode("utf-8", "replace")
    # Newer flow: a <form action="https://drive.usercontent.google.com/download">
    form = re.search(r'<form[^>]+action="([^"]+)"[^>]*>(.*?)</form>', html, re.S)
    if form:
        action = unescape(form.group(1))
        params = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', form.group(2)))
        params = {k: unescape(v) for k, v in params.items()}
        if action.startswith("http"):
            url = action + "?" + urllib.parse.urlencode(params)
            return urllib.request.Request(url, headers={"User-Agent": UA})
    # Legacy flow: confirm token embedded in a link/href
    m = re.search(r'confirm=([0-9A-Za-z_\-]+)', html)
    if m:
        sep = "&" if "?" in orig_url else "?"
        return urllib.request.Request(orig_url + sep + "confirm=" + m.group(1),
                                      headers={"User-Agent": UA})
    return None


def download_drive(opener, file_id, dest_path, retries=3):
    """Download a public Drive file to dest_path. Returns saved path or raises."""
    url = GD_BASE + file_id
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = opener.open(req, timeout=120)
            head = resp.read(8192)
            if _is_html(resp, head):
                # virus-scan interstitial — read the rest, build confirm request
                body = head + resp.read()
                creq = _drive_confirm_request(body, url)
                if creq is None:
                    raise RuntimeError("drive interstitial: no confirm token")
                resp = opener.open(creq, timeout=300)
                head = resp.read(8192)
                if _is_html(resp, head):
                    raise RuntimeError("drive: still HTML after confirm")
            # stream to disk
            base, _ = os.path.splitext(dest_path)
            ext = _ext_for(_filename_from_headers(resp), head)
            final = base + ext
            tmp = final + ".part"
            with open(tmp, "wb") as f:
                f.write(head)
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
            if os.path.getsize(tmp) == 0:
                raise RuntimeError("empty download")
            os.replace(tmp, final)
            return final
        except Exception as e:
            last = e
            if _permanent(e):
                break          # dead/restricted file — don't waste retries
            time.sleep(min(2 ** attempt, 20))
    raise last


def download_plain(opener, url, dest_path, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = opener.open(req, timeout=120)
            head = resp.read(8192)
            base, _ = os.path.splitext(dest_path)
            ext = _ext_for(_filename_from_headers(resp), head) or os.path.splitext(url)[1]
            final = base + (ext or ".bin")
            tmp = final + ".part"
            with open(tmp, "wb") as f:
                f.write(head)
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(tmp, final)
            return final
        except Exception as e:
            last = e
            if _permanent(e):
                break
            time.sleep(min(2 ** attempt, 20))
    raise last


# ----------------------------- meta.json -----------------------------
def write_meta(rec, saved_files, cover_name):
    meta = {
        "slug": rec.get("book_slug", ""),
        "title": rec.get("title", ""),
        "title_en": "",
        "author": rec.get("author", ""),
        "author_en": "",
        "author_slug": rec.get("author_slug", ""),
        "author_slugs": rec.get("author_slugs", []),
        "source": rec.get("source", "coptic-treasures.com"),
        "source_url": rec.get("source_url", rec.get("url", "")),
        "topics": rec.get("categories", []),
        "category_slugs": rec.get("category_slugs", []),
        "main_category_ids": rec.get("main_category_ids", []),
        "series": "",
        "description": "",
        "keywords": rec.get("keywords", []),
        "editor": rec.get("editor", ""),
        "translator": rec.get("translator", ""),
        "publisher": rec.get("publisher", ""),
        "number_of_pages": rec.get("number_of_pages", ""),
        "date_published": rec.get("date_published", ""),
        "last_updated": rec.get("last_updated", ""),
        "rating": rec.get("rating", ""),
        "post_id": rec.get("post_id", ""),
        "files": [
            {"name": os.path.basename(p), "drive_id": d.get("drive_id"),
             "size": d.get("size", ""), "url": d.get("url", "")}
            for p, d in saved_files
        ],
        "cover": cover_name,
        "language": rec.get("language", "ar"),
    }
    path = os.path.join(REPO, rec["dest"], "meta.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ----------------------------- per-book -----------------------------
def book_primary_exists(rec):
    d = os.path.join(REPO, rec["dest"])
    if not os.path.isdir(d):
        return False
    return any(fn.startswith("book") and not fn.endswith(".part")
               and os.path.getsize(os.path.join(d, fn)) > 0
               for fn in os.listdir(d))


def process_book(opener, rec, delay):
    dest = os.path.join(REPO, rec["dest"])
    os.makedirs(dest, exist_ok=True)
    downloads = rec.get("downloads", [])
    multi = len(downloads) > 1
    saved = []
    errors = []
    for i, d in enumerate(downloads, 1):
        stem = f"book-{i:02d}" if multi else "book"
        target = os.path.join(dest, stem + ".pdf")
        try:
            if d.get("drive_id"):
                final = download_drive(opener, d["drive_id"], target)
            elif d.get("url"):
                final = download_plain(opener, d["url"], target)
            else:
                continue
            saved.append((final, d))
        except Exception as e:
            errors.append(f"{d.get('url','?')}: {str(e)[:120]}")
        time.sleep(delay)

    # cover
    cover_name = ""
    cu = rec.get("cover_url", "")
    if cu:
        try:
            ext = os.path.splitext(urllib.parse.urlparse(cu).path)[1].lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                ext = ".jpg"
            cpath = os.path.join(dest, "cover" + ext)
            download_plain(opener, cu, cpath)
            # download_plain may pick a different ext from headers; find it
            for fn in os.listdir(dest):
                if fn.startswith("cover"):
                    cover_name = fn
                    break
        except Exception as e:
            errors.append(f"cover: {str(e)[:80]}")

    write_meta(rec, saved, cover_name)

    if saved and not errors:
        return "downloaded", errors
    if saved and errors:
        return "partial", errors
    return "failed", errors


# ----------------------------- main -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max books this run (0=all)")
    ap.add_argument("--author", default="", help="only this author_slug")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between files")
    ap.add_argument("--retry-failed", action="store_true",
                    help="re-attempt failed/partial books")
    args = ap.parse_args()

    records = load_catalog()
    opener = make_opener()

    def pending(r):
        if r.get("status") == "no-file" or not r.get("downloads"):
            return False
        if args.author and r.get("author_slug") != args.author:
            return False
        st = r.get("status")
        if st == "downloaded":
            return False
        if st in ("failed", "partial") and not args.retry_failed:
            return False
        if book_primary_exists(r) and st == "downloaded":
            return False
        return True

    todo = [r for r in records if pending(r)]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} books to download "
          f"({sum(1 for r in records if r.get('status')=='downloaded')} already done)",
          flush=True)

    n_ok = n_part = n_fail = 0
    for i, rec in enumerate(todo, 1):
        if book_primary_exists(rec) and rec.get("status") != "downloaded":
            rec["status"] = "downloaded"
        if rec.get("status") == "downloaded":
            continue
        status, errors = process_book(opener, rec, args.delay)
        rec["status"] = status
        if errors:
            rec["download_errors"] = errors
        else:
            rec.pop("download_errors", None)
        n_ok += status == "downloaded"
        n_part += status == "partial"
        n_fail += status == "failed"

        if i % SAVE_EVERY == 0:
            save_catalog(records)
            print(f"  [{i}/{len(todo)}] {status:10s} {rec.get('title','?')[:48]} "
                  f"· ok={n_ok} part={n_part} fail={n_fail}", flush=True)

    save_catalog(records)
    print(f"\nDone. downloaded={n_ok} partial={n_part} failed={n_fail}")


if __name__ == "__main__":
    main()
