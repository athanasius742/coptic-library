#!/usr/bin/env python3
"""
build_epub.py — PLAN §9 / phase 50.

Standalone EPUB builder that regenerates <book-slug>.epub as a PURE FUNCTION of
the canonical sources already on disk:
    chapters/<NN-slug>/content.xhtml  (the SAME file the web renderer consumes)
  + images/                            (chapter-local images)
  + meta.json + manifest.json          (titles, order, language, cover)

This decouples the EPUB from the scrape path: extract_book.py:build_epub re-reads
pages/* and re-runs clean_chapter (which hits the network). Here we read the
existing content.xhtml verbatim, so the EPUB reader and the web reader can never
drift, and the build needs NO network and NO LLM. Output is written atomically.

It reuses extract_book's proven primitives (page_xhtml envelope, CSS, the
validate_epub checks) and reproduces the repo's exact EPUB shape: mimetype first/
stored, META-INF/container.xml, OEBPS/{content.opf,nav.xhtml,toc.ncx,style.css,
title.xhtml,cover.xhtml,chapNN.xhtml,images/*}, with page-progression-direction.

Usage:
  python3 tools/build_epub.py <book-dir> [--force]
"""
import os
import re
import sys
import html
import shutil
import zipfile
import hashlib
import datetime
import argparse
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st
from extract_book import CSS, CSS_LTR, validate_epub

IMG_REF_RE = re.compile(r'src="(?:\./)?images/([^"?#]+)"')
IMG_EXT_MEDIA = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}


def _chapter_dir_for(book_dir, manifest_entry):
    """manifest file '01-foreword.html' -> chapters/01-foreword (PLAN §0.1)."""
    base = re.sub(r"\.html?$", "", manifest_entry["file"], flags=re.I)
    return os.path.join(book_dir, "chapters", base)


def _media_type(fn):
    ext = fn.rsplit(".", 1)[-1].lower()
    return "image/" + IMG_EXT_MEDIA.get(ext, ext)


def build(book_dir):
    meta = st.load_json(st.meta_path(book_dir))
    manifest = st.load_json(st.manifest_path(book_dir))
    if not meta or not manifest:
        raise SystemExit("build_epub: missing meta.json or manifest.json")

    title = meta["title"]
    author = meta.get("author", "")
    source = meta.get("source_url") or meta.get("source") or ""
    slug = meta["slug"]
    lang = meta.get("language", "ar")
    rtl = (lang != "en")
    d = "rtl" if rtl else "ltr"

    content = [m for m in manifest if m.get("slug") != "index"]
    if not content:
        raise SystemExit("build_epub: no content chapters in manifest")

    build_root = tempfile.mkdtemp(prefix=".epub-build-", dir=book_dir)
    try:
        oebps = os.path.join(build_root, "OEBPS")
        imgdir = os.path.join(oebps, "images")
        os.makedirs(imgdir, exist_ok=True)
        os.makedirs(os.path.join(build_root, "META-INF"), exist_ok=True)

        spine = []
        referenced = set()
        for i, m in enumerate(content, 1):
            cdir = _chapter_dir_for(book_dir, m)
            cx = os.path.join(cdir, "content.xhtml")
            if not os.path.exists(cx):
                raise SystemExit(f"build_epub: missing {cx}")
            xhtml = open(cx, encoding="utf-8").read()
            # content.xhtml already carries the canonical page_xhtml envelope
            # (RTL/LTR, style.css link, <h1> title) — use it verbatim as chapNN.
            with open(os.path.join(oebps, f"chap{i:02d}.xhtml"), "w", encoding="utf-8") as f:
                f.write(xhtml)
            referenced.update(IMG_REF_RE.findall(xhtml))
            spine.append({"idx": i, "file": f"chap{i:02d}.xhtml", "title": m["title"]})

        # Copy only the images actually referenced by the chapters.
        src_imgdir = os.path.join(book_dir, "images")
        missing_imgs = []
        for name in sorted(referenced):
            src = os.path.join(src_imgdir, name)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(imgdir, name))
            else:
                missing_imgs.append(name)

        with open(os.path.join(oebps, "style.css"), "w", encoding="utf-8") as f:
            f.write(CSS if rtl else CSS_LTR)

        cover_src = os.path.join(book_dir, meta.get("cover") or "cover.jpg")
        have_cover = bool(meta.get("cover")) and os.path.exists(cover_src)
        if have_cover:
            shutil.copy(cover_src, os.path.join(imgdir, "cover.jpg"))
            cover_label = "الغلاف" if rtl else "Cover"
            with open(os.path.join(oebps, "cover.xhtml"), "w", encoding="utf-8") as f:
                f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" dir="{d}">
<head><meta charset="utf-8"/><title>{cover_label}</title>
<style type="text/css">html,body{{margin:0;padding:0;height:100%;text-align:center;}}
img{{max-width:100%;max-height:100vh;object-fit:contain;}}</style></head>
<body epub:type="cover"><img src="images/cover.jpg" alt="cover"/></body></html>""")

        src_label = "المصدر" if rtl else "Source"
        with open(os.path.join(oebps, "title.xhtml"), "w", encoding="utf-8") as f:
            f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}" dir="{d}">
<head><meta charset="utf-8"/><title>{html.escape(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body dir="{d}" style="text-align:center;">
<h1 style="border:0;font-size:2em;">{html.escape(title)}</h1>
<p style="font-size:1.2em;">{html.escape(author)}</p>
<p style="font-size:.8em;color:#888;">{src_label}: {html.escape(source)}</p>
</body></html>""")

        toc_label = "الفهرس" if rtl else "Contents"
        nav_items = "\n".join(
            f'      <li><a href="{s["file"]}">{html.escape(s["title"])}</a></li>' for s in spine)
        with open(os.path.join(oebps, "nav.xhtml"), "w", encoding="utf-8") as f:
            f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}" dir="{d}">
<head><meta charset="utf-8"/><title>{toc_label}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body dir="{d}"><nav epub:type="toc" id="toc"><h1>{toc_label}</h1><ol>
{nav_items}
</ol></nav></body></html>""")

        bookid = "urn:uuid:" + hashlib.md5(source.encode()).hexdigest()
        navpoints = "\n".join(
            f'    <navPoint id="np{s["idx"]:02d}" playOrder="{s["idx"]}">'
            f'<navLabel><text>{html.escape(s["title"])}</text></navLabel>'
            f'<content src="{s["file"]}"/></navPoint>' for s in spine)
        with open(os.path.join(oebps, "toc.ncx"), "w", encoding="utf-8") as f:
            f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="{lang}">
<head><meta name="dtb:uid" content="{bookid}"/><meta name="dtb:depth" content="1"/>
<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>
<docTitle><text>{html.escape(title)}</text></docTitle>
<docAuthor><text>{html.escape(author)}</text></docAuthor>
<navMap>
{navpoints}
</navMap></ncx>""")

        img_items = "\n".join(
            f'    <item id="{fn}" href="images/{fn}" media-type="{_media_type(fn)}"'
            + (' properties="cover-image"' if fn == "cover.jpg" else "") + "/>"
            for fn in sorted(os.listdir(imgdir)))
        chap_items = "\n".join(
            f'    <item id="chap{s["idx"]:02d}" href="{s["file"]}" media-type="application/xhtml+xml"/>'
            for s in spine)
        spine_items = "\n".join(f'    <itemref idref="chap{s["idx"]:02d}"/>' for s in spine)
        today = datetime.date.today().isoformat()
        cover_meta = '\n    <meta name="cover" content="cover.jpg"/>' if have_cover else ""
        cover_manifest = ('    <item id="coverpage" href="cover.xhtml" '
                          'media-type="application/xhtml+xml"/>\n' if have_cover else "")
        cover_spine = '    <itemref idref="coverpage"/>\n' if have_cover else ""
        with open(os.path.join(oebps, "content.opf"), "w", encoding="utf-8") as f:
            f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{lang}" dir="{d}">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{bookid}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:creator>{html.escape(author)}</dc:creator>
    <dc:language>{lang}</dc:language>
    <dc:source>{html.escape(source)}</dc:source>
    <dc:publisher>St-Takla.org</dc:publisher>
    <dc:date>{today}</dc:date>
    <meta property="dcterms:modified">{today}T00:00:00Z</meta>
    <meta property="page-progression-direction">{d}</meta>{cover_meta}
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="css" href="style.css" media-type="text/css"/>
{cover_manifest}    <item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>
{chap_items}
{img_items}
  </manifest>
  <spine toc="ncx" page-progression-direction="{d}">
{cover_spine}    <itemref idref="title"/>
    <itemref idref="nav"/>
{spine_items}
  </spine>
</package>""")

        with open(os.path.join(build_root, "META-INF", "container.xml"), "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>""")

        # Zip to a temp epub, then os.replace atomically.
        tmp_epub = os.path.join(book_dir, f".{slug}.epub.tmp")
        with zipfile.ZipFile(tmp_epub, "w") as z:
            z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            for folder in ("META-INF", "OEBPS"):
                for dp, _, files in os.walk(os.path.join(build_root, folder)):
                    for fn in sorted(files):
                        full = os.path.join(dp, fn)
                        z.write(full, os.path.relpath(full, build_root),
                                compress_type=zipfile.ZIP_DEFLATED)
        epub_path = os.path.join(book_dir, f"{slug}.epub")
        os.replace(tmp_epub, epub_path)
        return epub_path, len(spine), missing_imgs
    finally:
        shutil.rmtree(build_root, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Build EPUB from canonical content.xhtml (no network).")
    ap.add_argument("book_dir")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    state = st.init_state(book_dir, phase="html")
    input_hash = st.compute_source_hash(book_dir)
    if not args.force and st.phase_is_current(state, "epub", input_hash):
        print("build_epub: up to date (hash-gated skip)")
        return

    epub_path, n_chap, missing_imgs = build(book_dir)
    ok, problems = validate_epub(epub_path, book_dir)
    size_kb = os.path.getsize(epub_path) // 1024
    print(f"build_epub: {'OK' if ok else 'INVALID'} -> {os.path.basename(epub_path)} "
          f"({n_chap} chapters, {size_kb} KB)")
    st.clear_issues(state, "epub")
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
        st.add_issue(state, "error", "epub", p)
    for m in missing_imgs:
        st.add_issue(state, "warn", "epub-image-missing",
                     f"referenced image not in images/: {m}")

    st.set_phase(state, "epub", "done" if ok else "failed", input_hash)
    st.save_state(book_dir, state)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
