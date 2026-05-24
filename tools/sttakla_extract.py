#!/usr/bin/env python3
"""
sttakla_extract.py — Extract a book from St-Takla.org into a self-contained
folder (raw pages + per-chapter dirs + cover) and build an EPUB.

St-Takla book pages share a structure this tool relies on:
  * content lives in   <div id="bodytext">
  * the "next page" is  <a id="next" href="...">   (the chain loops back to index)
  * pages are encoded in windows-1256
  * the cover is the index page's  <meta property="og:image">

Usage:
  python3 sttakla_extract.py <book-index-url> --out <output-dir> [options]

Example:
  python3 sttakla_extract.py \\
      https://st-takla.org/books/anba-raphael/i-willingly-ate/index.html \\
      --out ~/coptic-library/books/st-takla.org/anba-raphael/i-willingly-ate

Options:
  --title TEXT     Override book title (default: derived from page metadata)
  --author TEXT    Override author    (default: derived from the bodytext heading)
  --start FILE     First content page filename (default: auto-detected from the TOC)
  --slug NAME      Slug used for the .epub filename (default: from the URL path)
  --delay SECONDS  Politeness delay between requests (default: 1.0)
  --no-epub        Only walk + save pages/chapters, skip the EPUB build
"""
import argparse, os, re, sys, json, time, html, shutil, hashlib, zipfile, datetime
import urllib.request
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) CopticLibrary/1.0"}
ENC = "windows-1256"


# ----------------------------- networking -----------------------------
def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch_html(url):
    # Pages are windows-1256; decode to UTF-8 and fix the declared charset so the
    # saved file (now UTF-8 bytes) renders correctly when opened directly.
    text = fetch(url).decode(ENC, errors="replace")
    return re.sub(r"windows-1256", "utf-8", text, flags=re.I)


# ----------------------------- metadata --------------------------------
def clean_title(t):
    t = (t or "").split("|")[0].strip()
    if " - " in t:
        t = t.split(" - ")[0].strip()
    return t


def derive_meta(index_soup):
    """Return (title, author, cover_url) best-effort from the index page."""
    title = None
    og = index_soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = clean_title(og["content"])
    if not title and index_soup.title:
        title = clean_title(index_soup.title.get_text())

    author = None
    body = index_soup.find("div", id="bodytext")
    if body:
        h2 = body.find("h2")
        if h2 and " - " in h2.get_text():
            author = h2.get_text(" ", strip=True).split(" - ", 1)[1].strip()

    cover = None
    ogimg = index_soup.find("meta", property="og:image")
    if ogimg and ogimg.get("content"):
        cover = ogimg["content"]
    return title, author, cover


def find_start_page(index_soup):
    """First sibling .html link inside the TOC (skips index.html / absolute links)."""
    body = index_soup.find("div", id="bodytext") or index_soup
    for a in body.find_all("a", href=True):
        href = a["href"].strip()
        if (href.endswith(".html") and "/" not in href
                and not href.startswith(("http", "#")) and href != "index.html"):
            return href
    return None


# ----------------------------- the walk --------------------------------
def walk(base_url, start, pages_dir, delay):
    """Follow the <a id='next'> chain, saving each decoded page. Returns manifest."""
    os.makedirs(pages_dir, exist_ok=True)
    manifest = []
    # save index for reference
    idx_html = fetch_html(urljoin(base_url, "index.html"))
    with open(os.path.join(pages_dir, "00-index.html"), "w", encoding="utf-8") as f:
        f.write(idx_html)

    visited, current, order = set(), start, 1
    while current and current not in visited and current != "index.html":
        visited.add(current)
        url = urljoin(base_url, current)
        page = fetch_html(url)
        soup = BeautifulSoup(page, "lxml")
        slug = current[:-5] if current.endswith(".html") else current
        fname = f"{order:02d}-{slug}.html"
        with open(os.path.join(pages_dir, fname), "w", encoding="utf-8") as f:
            f.write(page)
        title = clean_title(soup.title.get_text() if soup.title else slug)
        manifest.append({"order": order, "slug": slug, "file": fname,
                         "title": title, "url": url})
        print(f"  [{order:02d}] {current:32s} -> {title}")
        nxt = soup.find("a", id="next")
        current = nxt.get("href") if nxt else None
        order += 1
        time.sleep(delay)
    return manifest


# --------------------------- content cleaning --------------------------
VOID = re.compile(r"<(img|br|hr)([^>]*?)\s*/?>", re.I)


def xhtmlify(frag):
    return VOID.sub(lambda m: f"<{m.group(1)}{m.group(2)}/>", frag)


def clean_chapter(page_file, page_url, imgdir, img_cache):
    soup = BeautifulSoup(open(page_file, encoding="utf-8").read(), "lxml")
    body = soup.find("div", id="bodytext")
    for t in body.select("table.table-footer"):       # footer prev/next nav
        t.decompose()
    for a in body.find_all("a", id=True):              # stray nav anchors
        a.decompose()
    for img in body.find_all("img"):                   # arrows + decorative dividers
        src = (img.get("src") or "").lower()
        if "arrow" in src or "divider" in src:
            (img.find_parent("table") or img).decompose()
    for sp in body.find_all(["span", "font"]):         # breadcrumb
        txt = sp.get_text(" ", strip=True)
        if "المكتبة القبطية" in txt and len(txt) < 80:
            sp.decompose()
    for h2 in body.find_all("h2"):                     # redundant book-title line
        h2.decompose()
    for img in body.find_all("img"):                   # download + localize content imgs
        src = img.get("src")
        if not src:
            img.decompose(); continue
        local = download_image(urljoin(page_url, src), imgdir, img_cache)
        if local:
            img["src"] = "images/" + local
            for a in ("width", "height", "border", "hspace", "vspace", "align", "style"):
                img.attrs.pop(a, None)
        else:
            img.decompose()
    for bad in body.find_all(["script", "style", "ins", "iframe"]):
        bad.decompose()
    for tag in body.find_all(True):
        for a in ("onclick", "onmouseover", "style", "width", "height",
                  "bgcolor", "border", "cellpadding", "cellspacing", "valign"):
            tag.attrs.pop(a, None)
    return xhtmlify(body.decode_contents())


def download_image(remote_url, imgdir, cache):
    if remote_url in cache:
        return cache[remote_url]
    ext = os.path.splitext(remote_url.split("?")[0])[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        ext = ".jpg"
    name = "img_" + hashlib.md5(remote_url.encode()).hexdigest()[:12] + ext
    try:
        data = fetch(remote_url)
        with open(os.path.join(imgdir, name), "wb") as f:
            f.write(data)
        cache[remote_url] = name
        return name
    except Exception as e:
        print(f"    image FAIL {remote_url}: {e}", file=sys.stderr)
        cache[remote_url] = None
        return None


# ----------------------------- epub build ------------------------------
CSS = """body{font-family:"Amiri","Scheherazade New","Noto Naskh Arabic",serif;
line-height:1.9;direction:rtl;text-align:right;margin:5% 6%;color:#1a1a1a;}
h1{font-size:1.5em;color:#5a2d0c;border-bottom:2px solid #c8a45c;padding-bottom:.3em;margin-bottom:1em;}
p{margin:.6em 0;}img{max-width:100%;height:auto;display:block;margin:1em auto;}
figcaption,.cap{font-size:.8em;color:#666;text-align:center;}
table{margin:1em auto;}hr{border:0;border-top:1px solid #ccc;margin:1.5em 0;}
a{color:#7a4a17;text-decoration:none;}"""


def page_xhtml(title, body_html, lang="ar"):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}" dir="rtl">
<head><meta charset="utf-8"/><title>{html.escape(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body dir="rtl"><h1>{html.escape(title)}</h1>
{body_html}
</body></html>"""


def build_epub(out_dir, manifest, meta, cover_path):
    title, author, source = meta["title"], meta["author"], meta["source"]
    build = os.path.join(out_dir, "_epub_build")
    oebps = os.path.join(build, "OEBPS")
    imgdir = os.path.join(oebps, "images")
    chapters_dir = os.path.join(out_dir, "chapters")
    if os.path.isdir(build):
        shutil.rmtree(build)
    for d in (oebps, imgdir, os.path.join(build, "META-INF"), chapters_dir):
        os.makedirs(d, exist_ok=True)

    img_cache, spine = {}, []
    content = [m for m in manifest if m["slug"] != "index"]
    for i, m in enumerate(content, 1):
        src_page = os.path.join(out_dir, "pages", m["file"])
        cdir = os.path.join(chapters_dir, f"{i:02d}-{m['slug']}")
        os.makedirs(cdir, exist_ok=True)
        shutil.copy(src_page, os.path.join(cdir, f"{m['slug']}.html"))
        cleaned = clean_chapter(src_page, m["url"], imgdir, img_cache)
        xhtml = page_xhtml(m["title"], cleaned)
        with open(os.path.join(oebps, f"chap{i:02d}.xhtml"), "w", encoding="utf-8") as f:
            f.write(xhtml)
        with open(os.path.join(cdir, "content.xhtml"), "w", encoding="utf-8") as f:
            f.write(xhtml)
        spine.append({"idx": i, "file": f"chap{i:02d}.xhtml", "title": m["title"]})

    with open(os.path.join(oebps, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)

    # cover
    have_cover = cover_path and os.path.exists(cover_path)
    if have_cover:
        shutil.copy(cover_path, os.path.join(imgdir, "cover.jpg"))
        with open(os.path.join(oebps, "cover.xhtml"), "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" dir="rtl">
<head><meta charset="utf-8"/><title>الغلاف</title>
<style type="text/css">html,body{margin:0;padding:0;height:100%;text-align:center;}
img{max-width:100%;max-height:100vh;object-fit:contain;}</style></head>
<body epub:type="cover"><img src="images/cover.jpg" alt="cover"/></body></html>""")

    # title page
    with open(os.path.join(oebps, "title.xhtml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ar" lang="ar" dir="rtl">
<head><meta charset="utf-8"/><title>{html.escape(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body dir="rtl" style="text-align:center;">
<h1 style="border:0;font-size:2em;">{html.escape(title)}</h1>
<p style="font-size:1.2em;">{html.escape(author)}</p>
<p style="font-size:.8em;color:#888;">المصدر: {html.escape(source)}</p>
</body></html>""")

    # nav + ncx
    nav_items = "\n".join(f'      <li><a href="{s["file"]}">{html.escape(s["title"])}</a></li>' for s in spine)
    with open(os.path.join(oebps, "nav.xhtml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ar" lang="ar" dir="rtl">
<head><meta charset="utf-8"/><title>الفهرس</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body dir="rtl"><nav epub:type="toc" id="toc"><h1>الفهرس</h1><ol>
{nav_items}
</ol></nav></body></html>""")

    bookid = "urn:uuid:" + hashlib.md5(source.encode()).hexdigest()
    navpoints = "\n".join(
        f'    <navPoint id="np{s["idx"]:02d}" playOrder="{s["idx"]}">'
        f'<navLabel><text>{html.escape(s["title"])}</text></navLabel>'
        f'<content src="{s["file"]}"/></navPoint>' for s in spine)
    with open(os.path.join(oebps, "toc.ncx"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="ar">
<head><meta name="dtb:uid" content="{bookid}"/><meta name="dtb:depth" content="1"/>
<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>
<docTitle><text>{html.escape(title)}</text></docTitle>
<docAuthor><text>{html.escape(author)}</text></docAuthor>
<navMap>
{navpoints}
</navMap></ncx>""")

    # opf
    img_items = "\n".join(
        f'    <item id="{fn}" href="images/{fn}" media-type="image/{"jpeg" if fn.endswith((".jpg",".jpeg")) else fn.split(".")[-1]}"'
        + (' properties="cover-image"' if fn == "cover.jpg" else "") + "/>"
        for fn in sorted(os.listdir(imgdir)))
    chap_items = "\n".join(f'    <item id="chap{s["idx"]:02d}" href="{s["file"]}" media-type="application/xhtml+xml"/>' for s in spine)
    spine_items = "\n".join(f'    <itemref idref="chap{s["idx"]:02d}"/>' for s in spine)
    today = datetime.date.today().isoformat()
    cover_meta = '\n    <meta name="cover" content="cover.jpg"/>' if have_cover else ""
    cover_manifest = '    <item id="coverpage" href="cover.xhtml" media-type="application/xhtml+xml"/>\n' if have_cover else ""
    cover_spine = '    <itemref idref="coverpage"/>\n' if have_cover else ""
    with open(os.path.join(oebps, "content.opf"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="ar" dir="rtl">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{bookid}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:creator>{html.escape(author)}</dc:creator>
    <dc:language>ar</dc:language>
    <dc:source>{html.escape(source)}</dc:source>
    <dc:publisher>St-Takla.org</dc:publisher>
    <dc:date>{today}</dc:date>
    <meta property="dcterms:modified">{today}T00:00:00Z</meta>
    <meta property="page-progression-direction">rtl</meta>{cover_meta}
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="css" href="style.css" media-type="text/css"/>
{cover_manifest}    <item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>
{chap_items}
{img_items}
  </manifest>
  <spine toc="ncx" page-progression-direction="rtl">
{cover_spine}    <itemref idref="title"/>
    <itemref idref="nav"/>
{spine_items}
  </spine>
</package>""")

    with open(os.path.join(build, "META-INF", "container.xml"), "w", encoding="utf-8") as f:
        f.write("""<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>""")

    slug = meta["slug"]
    epub_path = os.path.join(out_dir, f"{slug}.epub")
    if os.path.exists(epub_path):
        os.remove(epub_path)
    with zipfile.ZipFile(epub_path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for folder in ("META-INF", "OEBPS"):
            for dp, _, files in os.walk(os.path.join(build, folder)):
                for fn in files:
                    full = os.path.join(dp, fn)
                    z.write(full, os.path.relpath(full, build), compress_type=zipfile.ZIP_DEFLATED)
    shutil.rmtree(build)   # build is reproducible; keep the book dir clean
    return epub_path


# -------------------------------- main ---------------------------------
def main():
    ap = argparse.ArgumentParser(description="Extract a St-Takla.org book to a folder + EPUB.")
    ap.add_argument("url", help="Book index URL (…/index.html)")
    ap.add_argument("--out", required=True, help="Output directory for the book")
    ap.add_argument("--title"); ap.add_argument("--author"); ap.add_argument("--start")
    ap.add_argument("--slug"); ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--no-epub", action="store_true")
    args = ap.parse_args()

    out = os.path.expanduser(args.out)
    os.makedirs(out, exist_ok=True)
    base = args.url if args.url.endswith("/") else args.url.rsplit("/", 1)[0] + "/"

    index_soup = BeautifulSoup(fetch_html(urljoin(base, "index.html")), "lxml")
    d_title, d_author, cover_url = derive_meta(index_soup)
    title = args.title or d_title or "Untitled"
    author = args.author or d_author or "Unknown"
    slug = args.slug or [p for p in urlparse(args.url).path.split("/") if p][-2]
    start = args.start or find_start_page(index_soup)
    if not start:
        sys.exit("Could not auto-detect the first content page; pass --start FILE.")

    print(f"Title : {title}\nAuthor: {author}\nStart : {start}\nOut   : {out}\nWalking…")
    manifest = walk(base, start, os.path.join(out, "pages"), args.delay)
    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Walked {len(manifest)} pages.")

    cover_path = None
    if cover_url:
        cover_path = os.path.join(out, "cover.jpg")
        try:
            with open(cover_path, "wb") as f:
                f.write(fetch(cover_url))
            print(f"Cover saved: {cover_url}")
        except Exception as e:
            print(f"Cover download failed: {e}", file=sys.stderr); cover_path = None

    if not args.no_epub:
        meta = {"title": title, "author": author, "source": args.url, "slug": slug}
        epub = build_epub(out, manifest, meta, cover_path)
        print(f"EPUB: {epub} ({os.path.getsize(epub)//1024} KB)")


if __name__ == "__main__":
    main()
