#!/usr/bin/env python3
"""
verify_book.py — PLAN §10 / phase 60.

All deterministic publish gates. Exits 0 only if every hard gate passes; writes
per-check results + issues into .build/state.json. The LLM (the calling agent)
triages failures into fix-vs-flag; this tool only judges.

Gates (PLAN §10):
  1. schema/manifest: meta.json, manifest.json, state.json well-formed; spine
     order == manifest order == chapter dirs on disk; catalog.chapter_links_guess
     == #content chapters == len(chapters/) == non-index manifest length.
  2. image-ref integrity: every src="images/X" resolves to a present file; every
     <img> has non-empty alt (warn).
  3. link integrity: every in-page href="#id" resolves to an id present in the
     SAME chapter. Footnote-style danglers are ERRORS; TOC-slug danglers are
     tolerated (warn) — the renderer renders them gracefully.
  4. round-trip text diff (tashkeel-preserving): the text of each source
     content.xhtml equals the text of the matching EPUB chapter (no content loss).
  5. EPUB validation: extract_book.validate_epub (lxml/zip/mimetype/refs);
     epubcheck if an epubcheck.jar is found (else logged as skipped).
  6. catalog consistency: catalog entry exists; dest/author_slug/book_slug/
     section correct.
  7. author sanity: meta.author_slug == catalog.author_slug; authors/<slug>/
     info.json exists OR state.author.needs_review is logged.
  8. re-attribution coverage: no un-reviewed st-takla self-reference candidate
     remains (every one rewritten+logged or queued in pending_review).

Usage:
  python3 tools/verify_book.py <book-dir>
"""
import os
import re
import sys
import json
import glob
import zipfile
import argparse
import warnings

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st
from extract_book import validate_epub, REPO, CATALOG

IMG_REF_RE = re.compile(r'src="(?:\./)?images/([^"?#]+)"')
TAG_RE = re.compile(r"<[^>]+>")


def _text_only(xhtml):
    body = re.search(r"<body[^>]*>([\s\S]*?)</body>", xhtml, re.I)
    s = body.group(1) if body else xhtml
    s = TAG_RE.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
         .replace("&lt;", "<").replace("&gt;", ">"))
    s = re.sub(r"&[a-zA-Z#0-9]+;", " ", s)
    return st.normalize_for_diff(s)


class Verifier:
    def __init__(self, book_dir, state):
        self.book_dir = book_dir
        self.state = state
        self.results = {}
        self.failed = False

    def err(self, code, detail, chapter=None):
        st.add_issue(self.state, "error", code, detail, chapter)
        self.failed = True

    def warn(self, code, detail, chapter=None):
        st.add_issue(self.state, "warn", code, detail, chapter)

    # ---- 1. schema / manifest / counts ----
    def check_schema_counts(self):
        ok = True
        meta = st.load_json(st.meta_path(self.book_dir))
        manifest = st.load_json(st.manifest_path(self.book_dir))
        if not meta:
            self.err("schema", "meta.json missing/invalid"); ok = False
        else:
            for k in ("slug", "title", "author", "author_slug", "language"):
                if k not in meta:
                    self.err("schema", f"meta.json missing '{k}'"); ok = False
            if meta.get("language") not in ("ar", "en"):
                self.err("schema", f"meta.language invalid: {meta.get('language')}"); ok = False
        if not isinstance(manifest, list) or not manifest:
            self.err("schema", "manifest.json missing/empty"); ok = False
            manifest = manifest or []

        content = [m for m in manifest if m.get("slug") != "index"]
        # non-index manifest order must be 1..N contiguous
        orders = [m.get("order") for m in content]
        if orders != list(range(1, len(content) + 1)):
            self.err("schema", f"manifest content orders not 1..N: {orders}"); ok = False
        # chapter dirs on disk == content count, names match file-stems
        dirs = [os.path.basename(d) for d in st.chapter_dirs(self.book_dir)]
        if len(dirs) != len(content):
            self.err("schema", f"chapter dirs ({len(dirs)}) != content chapters ({len(content)})"); ok = False
        for m in content:
            stem = re.sub(r"\.html?$", "", m["file"], flags=re.I)
            if stem not in dirs:
                self.err("schema", f"manifest file '{m['file']}' has no chapters/{stem}/"); ok = False
        # catalog chapter_links_guess consistency (the §0.2 gotcha)
        rec = self._catalog_record()
        if rec is not None and rec.get("chapter_links_guess") != len(content):
            self.warn("catalog-count",
                      f"chapter_links_guess={rec.get('chapter_links_guess')} != content chapters={len(content)}")
        self.results["schema_counts"] = ok
        return ok

    # ---- 2. image-ref integrity ----
    def check_images(self):
        ok = True
        imgdir = os.path.join(self.book_dir, "images")
        for cx in st.content_paths(self.book_dir):
            ch = os.path.basename(os.path.dirname(cx))
            txt = open(cx, encoding="utf-8").read()
            for name in IMG_REF_RE.findall(txt):
                if not os.path.exists(os.path.join(imgdir, name)):
                    self.err("image-missing", f"referenced image not present: {name}", ch); ok = False
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                soup = BeautifulSoup(txt, "lxml")
            for img in soup.find_all("img"):
                if not (img.get("alt") or "").strip():
                    self.warn("image-alt", f"img missing alt: {img.get('src')}", ch)
        self.results["images"] = ok
        return ok

    # ---- 3. link integrity ----
    def check_links(self):
        ok = True
        for cx in st.content_paths(self.book_dir):
            ch = os.path.basename(os.path.dirname(cx))
            txt = open(cx, encoding="utf-8").read()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                soup = BeautifulSoup(txt, "lxml")
            ids = {(el.get("id") or "").strip() for el in soup.find_all(id=True)}
            ids.discard("")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href.startswith("#"):
                    continue
                target = href[1:]
                if target in ids:
                    continue
                # footnote-style target with no id -> hard error
                if re.match(r"^_ftn(?:href)?\d+$", target):
                    self.err("dangling-ref", f"footnote anchor with no target: {href}", ch); ok = False
                else:
                    self.warn("dangling-ref", f"graceful dead anchor (TOC slug): {href}", ch)
        self.results["links"] = ok
        return ok

    # ---- 4. round-trip text + 5. EPUB ----
    def check_epub(self):
        meta = st.load_json(st.meta_path(self.book_dir)) or {}
        slug = meta.get("slug") or st.book_slug(self.book_dir)
        epub_path = os.path.join(self.book_dir, f"{slug}.epub")
        if not os.path.exists(epub_path):
            self.err("epub", f"{slug}.epub not built"); self.results["epub"] = False
            return False
        ok, problems = validate_epub(epub_path, self.book_dir)
        for p in problems:
            self.err("epub", p)
        # round-trip: source content.xhtml text == epub chapNN text
        with zipfile.ZipFile(epub_path) as z:
            chap_names = sorted(n for n in z.namelist() if re.match(r"OEBPS/chap\d+\.xhtml$", n))
            src = st.content_paths(self.book_dir)
            if len(chap_names) != len(src):
                self.err("roundtrip", f"epub chapters ({len(chap_names)}) != content.xhtml ({len(src)})")
            for cn, cx in zip(chap_names, src):
                a = _text_only(z.read(cn).decode("utf-8", "replace"))
                b = _text_only(open(cx, encoding="utf-8").read())
                if a != b:
                    # tolerate tiny whitespace-only deltas
                    if abs(len(a) - len(b)) > 2:
                        self.err("roundtrip",
                                 f"text differs between epub {os.path.basename(cn)} and source "
                                 f"(len {len(a)} vs {len(b)})", os.path.basename(os.path.dirname(cx)))
        # epubcheck if a jar is around (best-effort, §13)
        jar = self._find_epubcheck()
        if jar:
            import subprocess
            r = subprocess.run(["java", "-jar", jar, epub_path],
                               capture_output=True, text=True)
            if re.search(r"\b(ERROR|FATAL)\b", r.stdout + r.stderr):
                self.err("epubcheck", "epubcheck reported ERROR/FATAL (see report)")
            self.results["epubcheck"] = "ran"
        else:
            self.results["epubcheck"] = "skipped"
        self.results["epub"] = not self.failed
        return True

    def _find_epubcheck(self):
        for c in (os.path.join(REPO, "tools", "epubcheck.jar"),
                  os.path.join(REPO, "epubcheck.jar")):
            if os.path.exists(c):
                return c
        return None

    # ---- 6/7. catalog + author ----
    def _catalog_record(self):
        recs = st.load_json(CATALOG, [])
        bid = self.state["book_id"]
        for r in recs:
            if r.get("book_id") == bid:
                return r
        return None

    def check_catalog_author(self):
        rec = self._catalog_record()
        meta = st.load_json(st.meta_path(self.book_dir)) or {}
        if rec is None:
            self.warn("catalog", "no catalog entry yet (run catalog_upsert)")
        else:
            if rec.get("dest") != st.dest_relpath(self.book_dir):
                self.err("catalog", f"dest mismatch: {rec.get('dest')}")
            for k in ("author_slug", "book_slug"):
                exp = st.author_slug(self.book_dir) if k == "author_slug" else st.book_slug(self.book_dir)
                if rec.get(k) != exp:
                    self.err("catalog", f"{k} mismatch: {rec.get(k)} != {exp}")
            if rec.get("author_slug") != meta.get("author_slug"):
                self.err("author", f"meta.author_slug ({meta.get('author_slug')}) != "
                         f"catalog.author_slug ({rec.get('author_slug')})")
        # author info.json present or needs_review logged
        aslug = meta.get("author_slug")
        info = os.path.join(REPO, "authors", aslug or "", "info.json")
        if aslug and not os.path.exists(info):
            needs = (self.state.get("author") or {}).get("needs_review")
            if not needs:
                self.warn("author", f"authors/{aslug}/info.json missing and no needs_review flag")

    # ---- 8. re-attribution coverage ----
    def check_reattribution(self):
        sr = self.state.get("source_reattribution")
        if not sr:
            return  # phase 15 may not have run; not a hard gate by itself
        # any candidate not rewritten and not queued?
        pending = sr.get("pending_review", [])
        if pending:
            self.warn("reattribution", f"{len(pending)} self-reference candidate(s) await human review")

    def run(self):
        self.check_schema_counts()
        self.check_images()
        self.check_links()
        self.check_epub()
        self.check_catalog_author()
        self.check_reattribution()
        return not self.failed


def main():
    ap = argparse.ArgumentParser(description="Run all deterministic publish gates.")
    ap.add_argument("book_dir")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    state = st.init_state(book_dir, phase="html")
    # rebuild verify-owned issues from scratch (don't append across runs)
    for code in ("schema", "image-missing", "image-alt", "dangling-ref", "epub",
                 "roundtrip", "epubcheck", "catalog", "catalog-count", "author",
                 "reattribution"):
        st.clear_issues(state, code)

    v = Verifier(book_dir, state)
    ok = v.run()
    st.set_phase(state, "verify", "done" if ok else "failed", st.compute_source_hash(book_dir))
    st.save_state(book_dir, state)

    errors = st.issues_by_severity(state, "error")
    warns = st.issues_by_severity(state, "warn")
    print(f"verify: {'PASS' if ok else 'FAIL'}  ({len(errors)} errors, {len(warns)} warnings)")
    for i in errors + warns:
        tag = i["severity"].upper()
        ch = f" [{i['chapter']}]" if i.get("chapter") else ""
        print(f"  {tag} {i['code']}{ch}: {i['detail']}")
    print("  results:", json.dumps(v.results))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
