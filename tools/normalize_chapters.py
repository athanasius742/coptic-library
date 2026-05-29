#!/usr/bin/env python3
"""
normalize_chapters.py — PLAN §4.1 / phase 10.

Standalone, deterministic, no-network normalization of existing
chapters/<NN-slug>/content.xhtml to the renderer-compatible HTML subset
(prompts/lib/html-subset.md / render-content.tsx SANITIZE). This factors the
sanitizing half of extract_book.py:clean_chapter out as a re-runnable pass over
already-extracted content, so a book hardened by the pipeline conforms to the
exact subset the web renderer + EPUB builder consume.

What it does per chapter (mirrors the renderer's allowlist EXACTLY):
  * extract the inner <body>; the FIRST top-level <h1> is the chapter title
    (page chrome owns it) and is re-emitted by page_xhtml — so it is captured
    and not duplicated;
  * neutralise MS-Office namespaced tags/attrs (well-formed XML);
  * remove nonText tags entirely (script/style/iframe/form/...);
  * transform b->strong, i->em;
  * UNWRAP every tag not on the allowlist (font/center/div/... — children kept);
  * keep only chapter-local images (src ^(?:\\./)?images/<file>$); drop remote/
    data/empty <img>; preserve alt;
  * keep only safe <a> hrefs (http/https/mailto/relative/#fragment); unwrap an
    <a> with an unsupported scheme (keep its text); keep id-only destination
    anchors;
  * strip every attribute outside the allowlist (a:[href,id], img:[src,alt],
    td/th:[colspan,rowspan], *:[dir,lang]);
  * re-wrap with the canonical page_xhtml envelope (RTL for ar, LTR for en).

Idempotent: re-running on already-normalized content reproduces it byte-for-byte
(modulo a one-time cleanup of pre-existing cruft). Diff-safe: the sacred text is
never paraphrased; only markup is filtered.

Usage:
  python3 tools/normalize_chapters.py <book-dir> [--force] [--check]
"""
import os
import re
import sys
import argparse
import warnings

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st
from extract_book import (
    _strip_office_tags, xhtmlify, page_xhtml, MSO_COND_COMMENT, MSO_STYLE_DECL,
)

# The renderer's allowlist (apps/web/src/lib/render-content.tsx). b/i are kept
# only until the transform below renames them to strong/em.
ALLOWED_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "sup", "sub",
    "a", "span", "img",
    "ul", "ol", "li",
    "table", "thead", "tbody", "tr", "td", "th",
    "blockquote",
}
# Removed entirely (content dropped) — sanitize-html nonTextTags + clean_chapter's.
NONTEXT_TAGS = {
    "script", "style", "iframe", "button", "input", "form", "nav",
    "link", "meta", "textarea", "select", "option",
    "noscript", "ins", "object", "embed", "svg", "video", "audio", "head",
}
ALLOWED_ATTRS = {
    "a": {"href", "id"},
    "img": {"src", "alt"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
GLOBAL_ATTRS = {"dir", "lang"}
TRANSFORM = {"b": "strong", "i": "em"}

LOCAL_IMG_RE = re.compile(r"^(?:\./)?images/[^\"'?#]+$", re.I)
SAFE_SCHEME_RE = re.compile(r"^(?:https?:|mailto:)", re.I)


def _safe_href(href):
    """True if an <a> href is keepable: a #fragment, a relative ref, or an
    http/https/mailto absolute. javascript:/data:/tel:/etc are rejected."""
    href = (href or "").strip()
    if not href:
        return False
    if href.startswith("#"):
        return True
    if SAFE_SCHEME_RE.match(href):
        return True
    # has a scheme we don't allow?
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href):
        return False
    return True  # relative


def _clean_body(body):
    """Apply the allowlist to a parsed <body> subtree, in place."""
    # 1. MS-Office namespaced tags/attrs -> well-formed XML.
    _strip_office_tags(body)

    # 2. Remove nonText tags entirely.
    for el in body.find_all(lambda t: t.name in NONTEXT_TAGS):
        el.decompose()

    # 3. b->strong, i->em (rename in place, before the unwrap pass).
    for el in body.find_all(list(TRANSFORM.keys())):
        el.name = TRANSFORM[el.name]

    # 4. Unwrap every tag not on the allowlist (innermost-first so nested
    #    wrappers collapse fully). font/center/div/... lose their tag, keep kids.
    while True:
        bad = next((el for el in body.find_all(True)
                    if el.name not in ALLOWED_TAGS), None)
        if bad is None:
            break
        bad.unwrap()

    # 5. <img>: keep only chapter-local refs; drop the rest. Preserve alt.
    for img in body.find_all("img"):
        src = (img.get("src") or "").strip()
        if not LOCAL_IMG_RE.match(src):
            img.decompose()
            continue
        alt = (img.get("alt") or "").strip()
        img.attrs = {"src": src, "alt": alt}

    # 6. <a>: validate scheme; unwrap unsafe ones (keep text); drop empty-no-id.
    for a in body.find_all("a"):
        href = (a.get("href") or "").strip()
        has_id = bool((a.get("id") or "").strip())
        if not href:
            if not has_id:
                a.unwrap()
            continue
        if not _safe_href(href):
            a.unwrap()

    # 7. Strip all attributes outside the allowlist.
    for el in body.find_all(True):
        allowed = ALLOWED_ATTRS.get(el.name, set()) | GLOBAL_ATTRS
        for attr in list(el.attrs):
            if attr not in allowed:
                del el.attrs[attr]

    return body


def normalize_content(raw, lang):
    """Return normalized content.xhtml text for one chapter (title preserved)."""
    rtl = (lang != "en")
    raw = MSO_COND_COMMENT.sub("", raw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        soup = BeautifulSoup(raw, "lxml")

    # Title: prefer the <head><title>, else the first <h1> in the body.
    title = ""
    if soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(strip=True)
    body = soup.body or soup
    # The page_xhtml envelope put the chapter title in the first <h1>; remove it
    # so page_xhtml does not duplicate it. Capture its text as a title fallback.
    first_h1 = body.find("h1")
    if first_h1:
        if not title:
            title = first_h1.get_text(" ", strip=True)
        first_h1.decompose()
    title = re.sub(r"\s+", " ", title).strip() or "بدون عنوان"

    _clean_body(body)
    frag = body.decode_contents()
    frag = MSO_STYLE_DECL.sub("", frag)
    frag = xhtmlify(frag).strip()
    return page_xhtml(title, frag, lang, rtl)


def process_book(book_dir, force=False, check=False):
    lang = (st.load_json(st.meta_path(book_dir), {}) or {}).get("language", "ar")
    paths = st.content_paths(book_dir)
    summary = {"chapters": len(paths), "rewritten": 0, "unchanged": 0,
               "drift": [], "lang": lang}
    for p in paths:
        before = open(p, encoding="utf-8").read()
        # Apply repeatedly until a fixpoint: one pass can leave residue that a
        # re-parse collapses, so converge here to guarantee a true no-op re-run.
        after = before
        for _ in range(6):
            nxt = normalize_content(after, lang)
            if not nxt.endswith("\n"):
                nxt += "\n"
            if nxt == after:
                break
            after = nxt
        if before == after:
            summary["unchanged"] += 1
            continue
        # Round-trip text guard: normalized text (tags stripped, ws collapsed,
        # tashkeel KEPT) must equal the source's — markup may change, text must not.
        if _text_only(before) != _text_only(after):
            summary["drift"].append(os.path.basename(os.path.dirname(p)))
        if check:
            summary["rewritten"] += 1
            continue
        st.atomic_write_text(p, after)
        summary["rewritten"] += 1
    return summary


_TAG_RE = re.compile(r"<[^>]+>")
_ENT_RE = re.compile(r"&[a-zA-Z#0-9]+;")


def _text_only(xhtml):
    """Visible text with tags removed, entities neutralised, ws collapsed —
    KEEPS Arabic diacritics. Both sides of the sacred-text round-trip diff."""
    body = re.search(r"<body[^>]*>([\s\S]*?)</body>", xhtml, re.I)
    s = body.group(1) if body else xhtml
    s = _TAG_RE.sub(" ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    s = _ENT_RE.sub(" ", s)
    return st.normalize_for_diff(s)


def main():
    ap = argparse.ArgumentParser(description="Normalize chapter content.xhtml to the renderer subset.")
    ap.add_argument("book_dir")
    ap.add_argument("--force", action="store_true", help="re-run even if phase hash is current")
    ap.add_argument("--check", action="store_true", help="report changes without writing")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    state = st.init_state(book_dir, phase="html")
    input_hash = st.compute_source_hash(book_dir)
    if not args.force and not args.check and st.phase_is_current(state, "normalize", input_hash):
        print("normalize: up to date (hash-gated skip)")
        return

    summary = process_book(book_dir, force=args.force, check=args.check)
    print(f"normalize: {summary['rewritten']} rewritten, {summary['unchanged']} unchanged "
          f"of {summary['chapters']} chapters (lang={summary['lang']})")
    st.clear_issues(state, "normalize-text-drift")
    for ch in summary["drift"]:
        st.add_issue(state, "error", "normalize-text-drift",
                     "normalization changed visible text (tashkeel-preserving diff)", ch)
        print(f"  ERROR text drift in {ch}", file=sys.stderr)

    if not args.check:
        state["source_hash"] = st.compute_source_hash(book_dir)
        st.set_phase(state, "normalize",
                     "failed" if summary["drift"] else "done",
                     st.compute_source_hash(book_dir))
        st.save_state(book_dir, state)
    if summary["drift"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
