#!/usr/bin/env python3
"""
resolve_refs.py — PLAN §8 / phase 20.

Two-pass, deterministic resolution of footnotes, in-page anchors, and a stable
ID/heading/anchor registry across a book's chapters. The LLM is NOT used here;
this is pure markup graph work.

The web renderer (apps/web/src/lib/render-content.tsx) pairs a footnote marker
with its note by `anchorKey`: two distinct `#` targets that collapse to the same
key form a footnote pair, and it renders them as <FootnoteRef>. St-Takla scrapes
are INCONSISTENT — `#(1)`/`#1` happen to collapse (both -> "1") and already
pair, but `#(501f)`/`#501h` collapse to "501f"/"501h" and DON'T, so those
footnotes are dead links. This tool normalizes every footnote marker/note pair
to the renderer-native, self-pairing convention with FROZEN, deterministic ids:

    marker:  <a href="#_ftn{N}"     id="_ftnhref{N}">(N)</a>   (inside <sup>)
    note:    <a href="#_ftnhref{N}" id="_ftn{N}">(N)</a>       (the return link)

`anchorKey("_ftn{N}") == anchorKey("_ftnhref{N}") == "ftn{N}"` (the renderer's
special case), so the pair is detected and FootnoteRef-rendered, while the
explicit ids make the jumps deterministic. The visible marker text `(N)` is
NEVER renumbered or altered (sacred-text rule); N is the footnote's own number.

It also: records the chapter/heading/anchor/footnote registries + a TOC into
.build/state.json (provenance + the §10 verify gates); leaves in-library /
cross-chapter st-takla links untouched (the renderer rewrites those); and
downgrades clearly-dangling footnote anchors (orphan marker or note, no pair) to
a <span> that preserves the visible text, logging a `dangling-ref` issue.
Non-footnote intra-page anchors (TOC slug links whose targets were stripped at
scrape time) are LEFT as graceful dead `#` links — the renderer tolerates them.

Usage:
  python3 tools/resolve_refs.py <book-dir> [--force]
"""
import os
import re
import sys
import argparse
import warnings

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st
from extract_book import xhtmlify, page_xhtml, MSO_STYLE_DECL

NUM_RE = re.compile(r"\d+")
# A footnote marker/note visible text: a number optionally wrapped in () or [],
# possibly with a trailing letter the scrape appended — e.g. "(501)", "[12]".
# Group 1 = an opening bracket (distinguishes co-existing series), group 2 = the
# footnote number.
FNTEXT_RE = re.compile(r"^([(\[])?\s*(\d+)\s*[a-zA-Z]?[)\]]?$")
RESOLVED_HREF_RE = re.compile(r"^#_ftn(?:href)?\d+$")

# Books mix footnote series — "(N)" parentheses and "[N]" square brackets — that
# reuse the same numbers. The web renderer only pairs PURELY-NUMERIC
# _ftn(h|href)<digits> anchors, so we namespace each series by a numeric offset
# to keep the internal token numeric AND collision-free across series.
SERIES_OFFSET = {"(": 0, None: 0, "[": 100000}


def _chapter_slug(chapter_dir):
    """chapters/03-faith -> 'faith' (strip the NN- content-order prefix)."""
    base = os.path.basename(chapter_dir)
    return re.sub(r"^\d+-", "", base)


def _heading_level(name):
    m = re.match(r"^h([1-6])$", name)
    return int(m.group(1)) if m else None


def resolve_chapter(raw, slug):
    """Return (new_xhtml, footnotes[], headings[], dangling[]) for one chapter."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        soup = BeautifulSoup(raw, "lxml")
    body = soup.body or soup

    title = ""
    if soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(strip=True)
    first_h1 = body.find("h1")
    if first_h1:
        if not title:
            title = first_h1.get_text(" ", strip=True)
        first_h1.extract()  # page_xhtml re-emits the title h1
    title = re.sub(r"\s+", " ", title).strip() or "بدون عنوان"

    lang_rtl = (soup.html and (soup.html.get("dir") == "rtl")) if soup.html else True

    # ---- headings registry (recorded, not injected; ids can't survive on hN) ----
    headings = []
    n = 0
    for h in body.find_all(re.compile(r"^h[1-6]$")):
        text = re.sub(r"\s+", " ", h.get_text(" ", strip=True))
        if not text:
            continue
        n += 1
        headings.append({"id": f"{slug}--sec-{n}", "level": _heading_level(h.name),
                         "text": text})

    # ---- collect intra-page footnote anchors, grouped by (series, number) ----
    # Each anchor records: element, under_sup, has 'ref' in href, doc-order index.
    groups = {}
    order = 0
    for a in body.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("#"):
            continue
        m = FNTEXT_RE.match(a.get_text(" ", strip=True))
        if not m:
            continue  # non-numeric (TOC slug) -> left graceful, handled below
        order += 1
        bracket, num = m.group(1), int(m.group(2))
        if bracket not in SERIES_OFFSET:
            continue
        key = (bracket if bracket in SERIES_OFFSET else None, num)
        groups.setdefault(key, []).append(
            {"a": a, "sup": a.find_parent("sup") is not None,
             "ref": "ref" in href.lower(), "ord": order})

    footnotes = []
    dangling = []
    for (bracket, num), anchors in sorted(groups.items(), key=lambda kv: (kv[0][1], str(kv[0][0]))):
        marker_label = f"[{num}]" if bracket == "[" else f"({num})"
        token = num + SERIES_OFFSET.get(bracket, 0)
        if len(anchors) >= 2:
            # marker = under <sup>, else href contains 'ref', else first in order
            anchors_sorted = sorted(anchors, key=lambda x: x["ord"])
            marker = next((x for x in anchors_sorted if x["sup"]), None)
            if marker is None:
                marker = next((x for x in anchors_sorted if x["ref"]), anchors_sorted[0])
            note = next((x for x in anchors_sorted if x is not marker), None)
            marker["a"]["href"] = f"#_ftn{token}"
            marker["a"]["id"] = f"_ftnhref{token}"
            note["a"]["href"] = f"#_ftnhref{token}"
            note["a"]["id"] = f"_ftn{token}"
            # Any extra anchors reusing the same number jump to the note too
            # (no id, so we never emit a duplicate id).
            for extra in anchors_sorted:
                if extra is marker or extra is note:
                    continue
                extra["a"]["href"] = f"#_ftn{token}"
                extra["a"].attrs.pop("id", None)
            footnotes.append({"id": f"_ftn{token}", "chapter": slug, "marker": marker_label,
                              "ref_anchor": f"_ftnhref{token}", "target_anchor": f"_ftn{token}",
                              "text": note["a"].get_text(" ", strip=True)[:200], "resolved": True})
        else:
            # Orphan marker or orphan note: a dead footnote link. Downgrade the
            # <a> to a <span> keeping the visible marker text; never delete.
            for x in anchors:
                span = soup.new_tag("span")
                span.string = x["a"].get_text(" ", strip=True)
                x["a"].replace_with(span)
            footnotes.append({"id": f"_ftn{token}", "chapter": slug, "marker": marker_label,
                              "ref_anchor": "", "target_anchor": "", "text": "",
                              "resolved": False})
            dangling.append(f"footnote {marker_label}")

    frag = body.decode_contents()
    frag = MSO_STYLE_DECL.sub("", frag)
    frag = xhtmlify(frag).strip()
    out = page_xhtml(title, frag, "ar" if lang_rtl else "en", lang_rtl)
    if not out.endswith("\n"):
        out += "\n"
    return out, footnotes, headings, dangling


def process_book(book_dir):
    manifest = st.load_json(st.manifest_path(book_dir), [])
    content = [m for m in manifest if m.get("slug") != "index"]
    # toc registry (chapter-level), derived from manifest order
    toc = []
    for i, m in enumerate(content, 1):
        toc.append({"order": i, "slug": m["slug"], "title": m.get("title", ""),
                    "id": f"ch-{i:02d}-{m['slug']}", "level": 1})

    all_fn, heading_map, anchor_registry = [], {}, {}
    dangling_all = []
    rewritten = 0
    for cdir in st.chapter_dirs(book_dir):
        cx = os.path.join(cdir, "content.xhtml")
        if not os.path.exists(cx):
            continue
        slug = _chapter_slug(cdir)
        before = open(cx, encoding="utf-8").read()
        # Converge to a fixpoint so a re-run is a true no-op.
        after = before
        for _ in range(4):
            nxt, fns, heads, dangs = resolve_chapter(after, slug)
            if nxt == after:
                break
            after = nxt
        # final registries from the converged content
        _, fns, heads, dangs = resolve_chapter(after, slug)
        all_fn.extend(fns)
        for h in heads:
            heading_map[h["id"]] = {"chapter": slug, "text": h["text"]}
        for f in fns:
            if f["resolved"]:
                anchor_registry[f["target_anchor"]] = {"chapter": slug, "kind": "footnote"}
                anchor_registry[f["ref_anchor"]] = {"chapter": slug, "kind": "footnote-ref"}
        dangling_all.extend((slug, d) for d in dangs)
        if after != before:
            st.atomic_write_text(cx, after)
            rewritten += 1
    return {"toc": toc, "footnotes": all_fn, "heading_map": heading_map,
            "anchor_registry": anchor_registry, "dangling": dangling_all,
            "rewritten": rewritten, "chapters": len(content)}


def main():
    ap = argparse.ArgumentParser(description="Resolve footnotes/anchors + build the ref registries.")
    ap.add_argument("book_dir")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    state = st.init_state(book_dir, phase="html")
    input_hash = st.compute_source_hash(book_dir)
    if not args.force and st.phase_is_current(state, "refs", input_hash):
        print("resolve_refs: up to date (hash-gated skip)")
        return

    r = process_book(book_dir)
    state["toc"] = r["toc"]
    state["heading_map"] = r["heading_map"]
    state["anchor_registry"] = r["anchor_registry"]
    state["footnote_registry"] = r["footnotes"]
    st.clear_issues(state, "dangling-ref")
    for slug, d in r["dangling"]:
        st.add_issue(state, "warn", "dangling-ref", f"downgraded dead {d} to text", slug)

    n_resolved = sum(1 for f in r["footnotes"] if f["resolved"])
    n_dangle = len(r["dangling"])
    print(f"resolve_refs: {r['rewritten']}/{r['chapters']} chapters rewritten; "
          f"{n_resolved} footnotes wired, {n_dangle} dangling downgraded")

    # refs rewrite content.xhtml -> source_hash changed; record under new hash.
    new_hash = st.compute_source_hash(book_dir)
    state["source_hash"] = new_hash
    st.set_phase(state, "refs", "done", new_hash)
    st.save_state(book_dir, state)


if __name__ == "__main__":
    main()
