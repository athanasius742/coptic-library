#!/usr/bin/env python3
"""
extract_book.py — Extract ONE St-Takla.org book into a self-contained folder
(raw pages + per-chapter dirs + cover + images + validated EPUB + meta.json),
generalised from the reference extractor (tools/sttakla_extract.py).

This is the Phase-2 framework piece. It handles the variation documented in
EXTRACTION_PLAN.md §9:

  Reading-order detection (in priority):
    a. a#next chain  — follow <a id="next"> from the first content page until it
       loops back to the index / a visited page  (clean family).
    b. TOC fallback  — if there is no a#next chain, use the ordered same-directory
       sibling .html links in the index bodytext  (legacy family — confirmed to
       have NO next chain).
    c. single page   — if the index itself is the content (prose, no chapters),
       treat the index as the only chapter.
    When both (a) and (b) are available they are cross-checked and mismatches are
    logged.

  Also: charset rewrite (windows-1256/1252 -> utf-8), 404 = skip, cover from
  og:image, inline image download (skip arrow/divider; missing image non-fatal),
  bodytext cleaning, RTL EPUB (LTR/lang=en for English books), meta.json with
  topics:[] left for human curation, idempotent rebuild, and per-book validation.

  "Defer the giants": --max-pages (default 200) aborts a book whose reading order
  exceeds the cap — partial output is discarded (no truncated EPUB) and the
  catalog status becomes "deferred". In --from-catalog all, records whose crawler
  chapter_links_guess >= 150 are pre-skipped (deferred) WITHOUT fetching (the ~37
  English ECF Ante/Post-Nicene Fathers volumes). Every deferred book is recorded
  in tools/deferred.md (idempotent).

Usage:
  python3 tools/extract_book.py <index-url> [--out DIR] [--delay 1.0] [--max-pages 200]
  python3 tools/extract_book.py --from-catalog <book_id|book_slug>   # uses tools/catalog.json
  python3 tools/extract_book.py --from-catalog all --limit 5         # first N discovered
  python3 tools/extract_book.py --dry-giants                         # report giant pre-skips

Exit status reflects validation (0 = verified/deferred, 1 = failed).
"""
import argparse, os, re, sys, json, time, html, shutil, hashlib, zipfile, datetime, warnings
import urllib.request, urllib.error
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from lxml import etree

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) CopticLibrary/1.0 (+book archival; contact athanasius742)"}
TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
CATALOG = os.path.join(TOOLS, "catalog.json")
DEFERRED_MD = os.path.join(TOOLS, "deferred.md")
MAX_PAGES = 12000                            # absolute runaway guard (infinite-loop safety only; the real per-book policy cap is --max-pages / DeferBook)

# "Defer the giants": batch extraction skips oversized sets so they don't stall
# the run. DEFAULT_MAX_PAGES caps a single book's reading order (chain > this =>
# deferred). GIANT_GUESS_CHAPTERS pre-skips a record before fetching when the
# crawler's chapter_links_guess is at least this big (the English ECF Ante/Post-
# Nicene Fathers volumes, 800-1500+ ch).
DEFAULT_MAX_PAGES = 200
GIANT_GUESS_CHAPTERS = 150

# Canonical author-slug merges (user merged duplicate slugs — keep in sync with
# crawl.py's CANONICAL_AUTHOR_MAP). Applied to the direct-URL path so a manual
# extract groups under the canonical author too; --from-catalog already carries
# the canonical slug baked into catalog.json.
CANONICAL_AUTHOR_MAP = {
    "father-tadros-yaacoub-malaty": "fr-tadros-malaty",
    "fr-tadros-yacoub": "fr-tadros-malaty",
    "father-athanasius-fahmy-george": "fr-athnasius-fahmy",
    "bishop-makarios": "anba-macarious",
    "bishop-metaos": "anba-metaos",
    "bishop-bemen": "anba-bimen",
    "yousef-habeeb": "youssef-habib",
    "bishop-youannes": "anba-yoannes",
    "father-botrous-el-baramousy": "fr-botros-elbaramosy",
}


def canonical_author(author_slug):
    return CANONICAL_AUTHOR_MAP.get(author_slug, author_slug)


class DeferBook(Exception):
    """Raised to abort a book cleanly when it exceeds the page cap (a giant)."""
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


# ----------------------------- networking -----------------------------
def fetch(url, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None
            last = e
        except Exception as e:
            last = e
        time.sleep(2 ** attempt)
    raise last


def fetch_html(url):
    raw = fetch(url)
    if raw is None:
        return None
    m = re.search(rb"charset=([\w-]+)", raw[:2048], re.I)
    declared = (m.group(1).decode("ascii", "ignore").lower() if m else "windows-1256")
    enc = declared if declared in ("windows-1256", "windows-1252", "utf-8", "iso-8859-1") else "windows-1256"
    text = raw.decode(enc, errors="replace")
    return re.sub(r"windows-125[26]|iso-8859-1", "utf-8", text, flags=re.I)


def is_404_soup(soup):
    t = (soup.title.get_text() if soup.title else "")
    return "404" in t


# ----------------------------- metadata --------------------------------
def clean_title(t):
    """Strip site chrome from a page <title>.
    Format is  '<title> - <author> | St-Takla.org'  (Arabic) or
    '<title>, book by <author> | St-Takla.org'  (English)."""
    t = (t or "").split("<")[0].split("|")[0].strip()
    # drop a leading 'الفهرس - ' / 'Index - ' (TOC marker that prefixes og:title)
    t = re.sub(r"^\s*(الفهرس|فهرس|Index)\s*[-–]\s*", "", t).strip()
    t = re.sub(r"^\s*كتاب\s+", "", t).strip()        # drop leading 'كتاب ' (= 'book')
    return re.sub(r"\s+", " ", t).strip()


def split_title_author(t):
    """From a cleaned page title, split off a trailing ' - <author>' /
    ', book by <author>'. Returns (title, author_or_None)."""
    t = clean_title(t)
    m = re.search(r",?\s*book by\s+(.+)$", t, re.I)
    if m:
        return t[:m.start()].rstrip(" ,").strip(), m.group(1).strip()
    if " - " in t:
        head, tail = t.rsplit(" - ", 1)
        # only treat the tail as an author if it is short (a name, not a subtitle)
        if 0 < len(tail) <= 60 and len(head) > 0:
            return head.strip(), tail.strip()
    return t, None


def chapter_title(page_title, book_title):
    """Chapter page <title> is '<chapter> - <book> | St-Takla.org'. Strip the
    trailing ' - <book>' so the chapter title is just the chapter name."""
    t = clean_title(page_title)
    bt = clean_title(book_title or "")
    if bt:
        # drop a trailing ' - <book>' (book may itself have been chrome-stripped)
        t = re.sub(r"\s*[-–]\s*(كتاب\s+)?" + re.escape(bt) + r"\s*$", "", t).strip()
        # also handle 'book by <book>' English form
        t = re.sub(r",?\s*book by\s+" + re.escape(bt) + r"\s*$", "", t, flags=re.I).strip()
    return t or clean_title(page_title)


def bodytext(soup):
    b = soup.find("div", id="bodytext")
    if b:
        return b
    best, best_len = None, 0
    for d in soup.find_all("div"):
        n = len(d.get_text(strip=True))
        if n > best_len:
            best, best_len = d, n
    return best or soup


def derive_meta(index_soup):
    # The plain <title> ('<title> - <author> | St-Takla.org') is the cleanest
    # source; og:title carries extra TOC/site chrome.
    title, author = None, None
    if index_soup.title:
        title, author = split_title_author(index_soup.title.get_text())
    if not title:
        og = index_soup.find("meta", property="og:title")
        if og and og.get("content"):
            title, a2 = split_title_author(og["content"])
            author = author or a2
    body = bodytext(index_soup)
    if not author:                              # fallback: bodytext heading 'كتاب X - author'
        h2 = body.find(["h1", "h2"]) if body else None
        if h2 and " - " in h2.get_text():
            cand = h2.get_text(" ", strip=True).rsplit(" - ", 1)[1].strip()
            if 0 < len(cand) <= 60:
                author = cand
    cover = None
    ogimg = index_soup.find("meta", property="og:image")
    if ogimg and ogimg.get("content"):
        cover = ogimg["content"]
    # Description: prefer the first substantial prose paragraph in the index
    # bodytext (the meta description is usually site chrome / a TOC echo).
    desc = None
    if body:
        for p in body.find_all("p"):
            txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
            if len(txt) < 60:
                continue
            low = txt
            if ("المكتبة القبطية" in low or "St-Takla" in low
                    or low.startswith(("صورة", "Image", "صوره"))      # figure captions
                    or "غلاف كتاب" in low[:30]):
                continue
            desc = txt[:600]
            break
    return title, author, cover, desc


# --------------------- reading-order detection -------------------------
def samedir_html_basename(href, base_url):
    """Resolve an href and return its basename IFF it is a real same-directory
    .html document link; otherwise return None.

    Guards against links whose resolved path has no trailing filename segment
    (bare host like 'https://st-takla.org', a directory link ending in '/', an
    anchor-only '#frag', or a 'mailto:'/'javascript:' / empty href). Such links
    would crash a blind  urlparse(full).path.rsplit('/',1)[1]  with IndexError
    (single-element list) or sneak an empty basename through. We skip them
    instead of indexing blindly, while keeping the legitimate ordering of valid
    same-dir chapter links untouched."""
    href = (href or "").strip()
    if not href:
        return None
    # anchors and non-document schemes never reference a chapter file
    if href.startswith(("#", "mailto:", "javascript:", "tel:", "data:")):
        return None
    full = urljoin(base_url, href)
    # off-site / non-http(s) resolved links can't be same-dir chapters
    if not full.startswith(("http://", "https://")):
        return None
    fdir = full.rsplit("/", 1)[0]
    if fdir != base_url.rstrip("/"):
        return None
    path = urlparse(full).path
    # empty path (bare host) or trailing-slash dir => no filename segment
    if not path or path.endswith("/"):
        return None
    fname = path.rsplit("/", 1)[-1]
    if not fname.endswith(".html") or "index" in fname.lower():
        return None
    return fname


def toc_chapter_files(index_soup, base_url):
    """Ordered list of (filename) same-dir sibling .html links in the index TOC."""
    body = bodytext(index_soup)
    out, seen = [], set()
    for a in body.find_all("a", href=True):
        fname = samedir_html_basename(a["href"], base_url)
        if not fname or fname in seen:
            continue
        seen.add(fname)
        out.append(fname)
    return out


def first_content_file(index_soup, base_url):
    files = toc_chapter_files(index_soup, base_url)
    return files[0] if files else None


def detect_order(index_soup, base_url, delay, log, page_cache, max_pages=DEFAULT_MAX_PAGES):
    """Return list of chapter filenames in reading order, plus the method used.
    Fetched chapter HTML is stored in page_cache (filename -> html) so walk()
    can reuse it instead of re-fetching (important for long next-chains).

    Raises DeferBook if the reading order exceeds max_pages — the caller discards
    any partial output and marks the book 'deferred' (a giant set)."""
    toc_files = toc_chapter_files(index_soup, base_url)
    if max_pages and len(toc_files) > max_pages:
        raise DeferBook(f"chain>{max_pages}")   # TOC already lists too many chapters
    start = toc_files[0] if toc_files else None

    # (a) try the a#next chain from the first content page
    next_chain = []
    if start:
        visited, current = set(), start
        while current and current not in visited and "index" not in current.lower():
            visited.add(current)
            next_chain.append(current)
            # giant guard: abort the walk as soon as the chain blows past the cap
            # (don't keep fetching hundreds more pages just to discard them).
            if max_pages and len(next_chain) > max_pages:
                raise DeferBook(f"chain>{max_pages}")
            if len(next_chain) >= MAX_PAGES:
                log.append("WARN: a#next chain hit MAX_PAGES guard")
                break
            url = urljoin(base_url, current)
            try:
                page = fetch_html(url)
            except Exception as e:
                log.append(f"WARN: next-walk fetch failed {url}: {e}")
                break
            if page is None:
                break
            page_cache[current] = page          # reuse in walk()
            soup = BeautifulSoup(page, "lxml")
            nxt = soup.find("a", id="next")
            nxt_href = nxt.get("href") if nxt else None
            if not nxt_href:
                break
            # only continue if the a#next target is a real same-dir .html doc;
            # a bare-host / directory / anchor href ends the chain (and would
            # otherwise crash a blind rsplit('/',1)[1]). Allow 'index' here so
            # the chain terminates naturally on the loop-back guard above.
            nxt_full = urljoin(base_url, nxt_href)
            nxt_path = urlparse(nxt_full).path
            if (nxt_full.rsplit("/", 1)[0] != base_url.rstrip("/")
                    or not nxt_path or nxt_path.endswith("/")
                    or not nxt_path.rsplit("/", 1)[-1].endswith(".html")):
                break
            current = nxt_path.rsplit("/", 1)[-1]
            time.sleep(delay)

    if len(next_chain) >= 2:
        # cross-check against TOC
        if toc_files and set(next_chain) != set(toc_files):
            log.append(f"NOTE: next-chain ({len(next_chain)}) vs TOC ({len(toc_files)}) differ; "
                       "using next-chain (authoritative).")
        return next_chain, "next-chain"

    if toc_files:
        return toc_files, "toc-fallback"

    # (c) single-page book: index is the content
    body = bodytext(index_soup)
    if body and len(body.get_text(strip=True)) > 400:
        return ["index.html"], "single-page"
    return [], "none"


# --------------------------- the walk ----------------------------------
def walk(base_url, index_url, idx_html, order, method, pages_dir, delay, log,
         book_title, page_cache):
    os.makedirs(pages_dir, exist_ok=True)
    manifest = []
    with open(os.path.join(pages_dir, "00-index.html"), "w", encoding="utf-8") as f:
        f.write(idx_html or "")
    idx_soup = BeautifulSoup(idx_html, "lxml") if idx_html else None
    manifest.append({"order": 0, "slug": "index", "file": "00-index.html",
                     "title": clean_title(idx_soup.title.get_text()) if idx_soup and idx_soup.title else "index",
                     "url": index_url})

    if method == "single-page":
        # the index itself is the only chapter; save a content copy
        with open(os.path.join(pages_dir, "01-content.html"), "w", encoding="utf-8") as f:
            f.write(idx_html or "")
        title = book_title or (clean_title(idx_soup.title.get_text()) if idx_soup and idx_soup.title else "content")
        manifest.append({"order": 1, "slug": "content", "file": "01-content.html",
                         "title": title, "url": index_url})
        return manifest

    order_n = 1
    for fname in order:
        if order_n > MAX_PAGES:
            log.append("WARN: page cap reached")
            break
        url = urljoin(base_url, fname)
        page = page_cache.get(fname)            # reuse trial-walk fetch if present
        if page is None:
            try:
                page = fetch_html(url)
            except Exception as e:
                log.append(f"WARN: chapter fetch failed {url}: {e}")
                continue
            if page is None:
                log.append(f"SKIP 404 chapter: {url}")
                continue
            time.sleep(delay)
        soup = BeautifulSoup(page, "lxml")
        if is_404_soup(soup):
            log.append(f"SKIP 404 chapter: {url}")
            continue
        slug = fname[:-5] if fname.endswith(".html") else fname
        slug = re.sub(r"[^a-zA-Z0-9_-]", "-", slug)
        out_name = f"{order_n:02d}-{slug}.html"
        with open(os.path.join(pages_dir, out_name), "w", encoding="utf-8") as f:
            f.write(page)
        title = chapter_title(soup.title.get_text() if soup.title else slug, book_title)
        manifest.append({"order": order_n, "slug": slug, "file": out_name,
                         "title": title, "url": url})
        order_n += 1
    return manifest


# --------------------------- content cleaning --------------------------
VOID = re.compile(r"<(img|br|hr)([^>]*?)\s*/?>", re.I)


def xhtmlify(frag):
    return VOID.sub(lambda m: f"<{m.group(1)}{m.group(2)}/>", frag)


NAV_CHROME = ("الصفحة التالية", "الصفحة السابقة", "next page", "previous page",
              "previous", "next")

# Visible nav-chrome strings. An element whose *entire* visible text (after
# whitespace normalisation) equals one of these is a navigation link/label, not
# prose — so it can be dropped wherever it appears. We must NOT match the phrase
# as a substring (it occurs verbatim inside real body sentences, e.g.
# "...وفي الصفحة التالية يوحي د. زيدان...").
NAV_TEXTS = ("الصفحة التالية", "الصفحة السابقة")

# MS-Word conditional comments (<!--[if ...]> ... <![endif]-->) and the leftover
# "mso-..." inline-style declarations Word emits. Stripped textually so the
# serialized XHTML never carries Office cruft.
MSO_COND_COMMENT = re.compile(r"<!--\[if[^\]]*\][\s\S]*?<!\[endif\]-->", re.I)
MSO_STYLE_DECL = re.compile(r"\s*mso-[\w-]+\s*:[^;\"']*;?", re.I)


def _norm_ws(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def _is_nav_text(el):
    """True iff the element's whole visible text is exactly a nav-chrome string
    (whitespace-normalised) — i.e. it is a standalone next/prev link or label,
    not prose that merely mentions the phrase."""
    return _norm_ws(el.get_text(" ", strip=True)) in NAV_TEXTS


def _strip_office_tags(body):
    """Make the fragment well-formed XML by neutralising Microsoft-Word /
    Office namespaced markup, which lxml's HTML parser keeps as tags whose name
    carries an undefined namespace prefix (e.g. <o:p>, <w:...>, <v:...>,
    <m:...>, <st1:...>). Such tags serialize verbatim and then fail XML parsing
    with 'Namespace prefix X on Y is not defined'.

    We *unwrap* any element whose tag name contains a ':' (preserving its inner
    text/children) and drop any attribute whose name carries a namespace prefix.
    General: matches every prefix, not just o:p."""
    # Unwrap namespaced elements innermost-first so a nested <o:p> inside an
    # <st1:foo> is handled even after its parent is unwrapped.
    while True:
        ns_el = next((el for el in body.find_all(True) if ":" in el.name), None)
        if ns_el is None:
            break
        ns_el.unwrap()
    # Drop namespaced attributes from whatever remains.
    for el in body.find_all(True):
        for a in [a for a in list(el.attrs) if ":" in a]:
            del el.attrs[a]

# Site-chrome breadcrumb phrases that only ever appear in the page chrome, never
# in legitimate prose. The bare "المكتبة القبطية" ("the Coptic library") DOES
# occur in real body text (e.g. "...وتدعيم المكتبة القبطية..."), so we must match
# the *full* breadcrumb tail / the breadcrumb line instead of that bare phrase.
BREADCRUMB_PHRASES = (
    "المكتبة القبطية الأرثوذكسية",   # ".. | كتب قبطية | المكتبة القبطية الأرثوذكسية"
    "مكتبة الكتب المسيحية",          # "مكتبة الكتب المسيحية | كتب قبطية | ..."
)


def _strip_breadcrumb(body):
    """Remove the leading site-chrome breadcrumb robustly, regardless of the
    element's length or exact tag. We find the *smallest* element that fully
    contains a breadcrumb phrase (so we drop the breadcrumb wrapper without
    nuking a large parent that also holds real prose) and decompose it."""
    for phrase in BREADCRUMB_PHRASES:
        while True:
            target = None
            for el in body.find_all(True):
                if phrase not in el.get_text(" ", strip=True):
                    continue
                # smallest container: no descendant element also holds the phrase
                if any(phrase in c.get_text(" ", strip=True) for c in el.find_all(True)):
                    continue
                target = el
                break
            if target is None:
                break
            # climb to the breadcrumb wrapper: an ancestor whose own text is
            # still essentially just the breadcrumb (short / a single line of
            # nav links), so we drop the <a>/<span>/<font> chrome as a unit but
            # stop before a parent that introduces unrelated body content.
            node = target
            parent = node.parent
            while parent is not None and parent is not body:
                ptxt = parent.get_text(" ", strip=True)
                # only climb while the parent is dominated by the breadcrumb
                if len(ptxt) <= len(target.get_text(" ", strip=True)) + 40:
                    node = parent
                    parent = node.parent
                else:
                    break
            node.decompose()


def _is_nav_image(img):
    """True if an <img> is a prev/next/divider navigation graphic — by src OR by
    its alt/title text (some next-arrows have non-'arrow' filenames)."""
    src = (img.get("src") or "").lower()
    if "arrow" in src or "divider" in src or "next" in src or "prev" in src:
        return True
    for attr in ("alt", "title"):
        v = (img.get(attr) or "").strip()
        if v in ("الصفحة التالية", "الصفحة السابقة", "Next", "Previous",
                 "Next Page", "Previous Page"):
            return True
    return False


def clean_chapter(page_file, page_url, imgdir, img_cache, delay):
    raw = open(page_file, encoding="utf-8").read()
    # Drop MS-Word conditional comments before parsing (their inner markup is
    # Office cruft, and lxml would otherwise resurrect parts of it).
    raw = MSO_COND_COMMENT.sub("", raw)
    soup = BeautifulSoup(raw, "lxml")
    body = bodytext(soup)
    for t in body.select("table.table-footer"):
        t.decompose()
    for a in body.find_all("a", id=True):
        a.decompose()
    # links wrapping a prev/next nav graphic (or whose visible text *is* nav
    # chrome). Match the whole text, not a substring, so prose that merely
    # mentions "الصفحة التالية" is left intact.
    for a in body.find_all("a"):
        if _is_nav_text(a) or any(_is_nav_image(i) for i in a.find_all("img")):
            (a.find_parent("table") or a).decompose()
    for img in body.find_all("img"):
        if _is_nav_image(img):
            (img.find_parent("table") or img).decompose()
    # Any remaining standalone nav-chrome label (a bare <span>/<td>/<p> whose
    # only text is the next/prev phrase), wherever it appears — not just inside
    # table.table-footer. Drop the smallest container so prose is untouched.
    for el in body.find_all(True):
        if el.parent is None:                     # already detached
            continue
        if _is_nav_text(el) and not any(_is_nav_text(c) for c in el.find_all(True)):
            (el.find_parent("table") or el).decompose()
    _strip_breadcrumb(body)
    for h2 in body.find_all("h2"):
        h2.decompose()
    for img in body.find_all("img"):
        src = img.get("src")
        if not src:
            img.decompose(); continue
        local = download_image(urljoin(page_url, src), imgdir, img_cache, delay)
        if local:
            img["src"] = "images/" + local
            alt = (img.get("alt") or "").strip()
            # don't carry nav-chrome alt text into the clean output
            if alt in ("الصفحة التالية", "الصفحة السابقة"):
                alt = ""
            img.attrs = {"src": img["src"], "alt": alt}
        else:
            img.decompose()
    for bad in body.find_all(["script", "style", "ins", "iframe", "noscript"]):
        bad.decompose()
    # Neutralise MS-Office namespaced tags/attrs so the fragment is well-formed
    # XML (no undefined namespace prefixes like o:/w:/v:/m:/st1:).
    _strip_office_tags(body)
    for tag in body.find_all(True):
        for a in list(tag.attrs):
            if a in ("href", "src", "alt", "colspan", "rowspan"):
                continue
            del tag.attrs[a]
    out = body.decode_contents()
    out = MSO_STYLE_DECL.sub("", out)             # drop leftover mso-* style cruft
    return xhtmlify(out)


def download_image(remote_url, imgdir, cache, delay):
    if remote_url in cache:
        return cache[remote_url]
    ext = os.path.splitext(remote_url.split("?")[0])[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        ext = ".jpg"
    name = "img_" + hashlib.md5(remote_url.encode()).hexdigest()[:12] + ext
    # robots: /Gallery/var/resizes|thumbs are disallowed; prefer the /albums/ original
    candidates = [remote_url]
    if "/Gallery/var/resizes/" in remote_url:
        candidates.insert(0, remote_url.replace("/Gallery/var/resizes/", "/Gallery/var/albums/"))
    if "/Gallery/var/thumbs/" in remote_url:
        candidates.insert(0, remote_url.replace("/Gallery/var/thumbs/", "/Gallery/var/albums/"))
    for cand in candidates:
        try:
            data = fetch(cand)
            if data is None:
                continue
            with open(os.path.join(imgdir, name), "wb") as f:
                f.write(data)
            cache[remote_url] = name
            time.sleep(delay)
            return name
        except Exception:
            continue
    print(f"    image FAIL {remote_url}", file=sys.stderr)
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

CSS_LTR = CSS.replace("direction:rtl;text-align:right;", "direction:ltr;text-align:left;")


def page_xhtml(title, body_html, lang, rtl):
    d = "rtl" if rtl else "ltr"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}" dir="{d}">
<head><meta charset="utf-8"/><title>{html.escape(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body dir="{d}"><h1>{html.escape(title)}</h1>
{body_html}
</body></html>"""


def build_epub(out_dir, manifest, meta, cover_path, delay, log):
    title, author, source = meta["title"], meta["author"], meta["source"]
    lang = meta.get("language", "ar")
    rtl = (lang != "en")
    build = os.path.join(out_dir, "_epub_build")
    oebps = os.path.join(build, "OEBPS")
    imgdir = os.path.join(oebps, "images")
    chapters_dir = os.path.join(out_dir, "chapters")
    if os.path.isdir(build):
        shutil.rmtree(build)
    if os.path.isdir(chapters_dir):
        shutil.rmtree(chapters_dir)
    for d in (oebps, imgdir, os.path.join(build, "META-INF"), chapters_dir):
        os.makedirs(d, exist_ok=True)

    img_cache, spine = {}, []
    content = [m for m in manifest if m["slug"] != "index"]
    for i, m in enumerate(content, 1):
        src_page = os.path.join(out_dir, "pages", m["file"])
        cdir = os.path.join(chapters_dir, f"{i:02d}-{m['slug']}")
        os.makedirs(cdir, exist_ok=True)
        shutil.copy(src_page, os.path.join(cdir, f"{m['slug']}.html"))
        cleaned = clean_chapter(src_page, m["url"], imgdir, img_cache, delay)
        xhtml = page_xhtml(m["title"], cleaned, lang, rtl)
        with open(os.path.join(oebps, f"chap{i:02d}.xhtml"), "w", encoding="utf-8") as f:
            f.write(xhtml)
        with open(os.path.join(cdir, "content.xhtml"), "w", encoding="utf-8") as f:
            f.write(xhtml)
        spine.append({"idx": i, "file": f"chap{i:02d}.xhtml", "title": m["title"]})

    with open(os.path.join(oebps, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS if rtl else CSS_LTR)

    have_cover = cover_path and os.path.exists(cover_path)
    d = "rtl" if rtl else "ltr"
    if have_cover:
        shutil.copy(cover_path, os.path.join(imgdir, "cover.jpg"))
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
    nav_items = "\n".join(f'      <li><a href="{s["file"]}">{html.escape(s["title"])}</a></li>' for s in spine)
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

    ppd = "rtl" if rtl else "ltr"
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
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{lang}" dir="{ppd}">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{bookid}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:creator>{html.escape(author)}</dc:creator>
    <dc:language>{lang}</dc:language>
    <dc:source>{html.escape(source)}</dc:source>
    <dc:publisher>St-Takla.org</dc:publisher>
    <dc:date>{today}</dc:date>
    <meta property="dcterms:modified">{today}T00:00:00Z</meta>
    <meta property="page-progression-direction">{ppd}</meta>{cover_meta}
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="css" href="style.css" media-type="text/css"/>
{cover_manifest}    <item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>
{chap_items}
{img_items}
  </manifest>
  <spine toc="ncx" page-progression-direction="{ppd}">
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
    shutil.rmtree(build)
    return epub_path, len(spine)


# ----------------------------- validation ------------------------------
# Use the *full* breadcrumb phrases (which never occur in legitimate prose)
# rather than the bare "المكتبة القبطية", which is a real Arabic phrase ("the
# Coptic library") that appears inside body text on some pages.
BREADCRUMB_CHROME = ("المكتبة القبطية الأرثوذكسية", "مكتبة الكتب المسيحية")
# Nav phrases occur verbatim inside real prose ("...وفي الصفحة التالية يوحي...")
# so a substring match here is a FALSE positive. Leftover nav chrome is a
# standalone link/label whose *whole* visible text is the phrase — checked
# structurally below, not by substring.
NAV_CHROME_TEXTS = ("الصفحة التالية", "الصفحة السابقة")
# Kept for backwards-compat / external references.
CHROME_STRINGS = list(BREADCRUMB_CHROME) + list(NAV_CHROME_TEXTS)


def _leftover_nav_chrome(xhtml_bytes):
    """Return the nav phrase that survives as a standalone link/label in this
    chapter XHTML, or None. We parse the markup and only flag a phrase when some
    element's *entire* visible text equals it (a real next/prev control), so the
    same phrase embedded in a sentence does not trip the validator."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")       # XHTML parsed by the HTML parser
            soup = BeautifulSoup(xhtml_bytes, "lxml")
    except Exception:
        return None
    for el in soup.find_all(True):
        if _norm_ws(el.get_text(" ", strip=True)) in NAV_CHROME_TEXTS:
            return _norm_ws(el.get_text(" ", strip=True))
    return None


def validate_epub(epub_path, book_dir):
    """Return (ok, [problems]) per plan §8."""
    problems = []
    if not os.path.exists(epub_path):
        return False, ["epub does not exist"]
    try:
        with zipfile.ZipFile(epub_path) as z:
            bad = z.testzip()
            if bad:
                problems.append(f"zip integrity: bad file {bad}")
            names = z.namelist()
            # mimetype first and stored
            if names[0] != "mimetype":
                problems.append("mimetype is not the first entry")
            else:
                info = z.getinfo("mimetype")
                if info.compress_type != zipfile.ZIP_STORED:
                    problems.append("mimetype is not stored (uncompressed)")
                if z.read("mimetype") != b"application/epub+zip":
                    problems.append("mimetype content wrong")
            # parse all xml/xhtml well-formed
            opf_name = next((n for n in names if n.endswith("content.opf")), None)
            if not opf_name:
                problems.append("no content.opf")
            xml_files = [n for n in names if n.endswith((".xhtml", ".opf", ".ncx"))]
            chap_count = 0
            for n in xml_files:
                data = z.read(n)
                try:
                    etree.fromstring(data)
                except Exception as e:
                    problems.append(f"not well-formed: {n}: {str(e)[:80]}")
                if re.match(r"OEBPS/chap\d+\.xhtml$", n):
                    chap_count += 1
                    txt = data.decode("utf-8", "replace")
                    leftover = next((cs for cs in BREADCRUMB_CHROME if cs in txt), None)
                    # nav phrases: only a standalone control counts, not prose
                    leftover = leftover or _leftover_nav_chrome(data)
                    if leftover:
                        problems.append(f"leftover chrome '{leftover}' in {n}")
            if chap_count < 1:
                problems.append("no content chapters (chapNN.xhtml)")
            # all manifest hrefs resolve inside the zip
            if opf_name:
                opf = etree.fromstring(z.read(opf_name))
                ns = {"opf": "http://www.idpf.org/2007/opf"}
                manifest_ids = {}
                opf_dir = os.path.dirname(opf_name)
                zset = set(names)
                for item in opf.findall(".//opf:manifest/opf:item", ns):
                    href = item.get("href")
                    iid = item.get("id")
                    manifest_ids[iid] = href
                    target = os.path.normpath(os.path.join(opf_dir, href)).replace("\\", "/")
                    if target not in zset:
                        problems.append(f"manifest href missing in zip: {href}")
                for ref in opf.findall(".//opf:spine/opf:itemref", ns):
                    idref = ref.get("idref")
                    if idref not in manifest_ids:
                        problems.append(f"spine idref not in manifest: {idref}")
                # image src refs inside chapters resolve
                for n in xml_files:
                    if not re.match(r"OEBPS/chap\d+\.xhtml$", n):
                        continue
                    txt = z.read(n).decode("utf-8", "replace")
                    for src in re.findall(r'src="(images/[^"]+)"', txt):
                        target = os.path.normpath(os.path.join("OEBPS", src)).replace("\\", "/")
                        if target not in zset:
                            problems.append(f"image ref missing in zip: {src} (in {n})")
    except zipfile.BadZipFile:
        return False, ["not a valid zip"]
    # cleaned bodytext non-empty
    return (len(problems) == 0), problems


# ------------------------------- meta ----------------------------------
def write_meta(out_dir, meta):
    full = {
        "slug": meta["slug"],
        "title": meta["title"],
        "title_en": meta.get("title_en", ""),
        "author": meta["author"],
        "author_en": meta.get("author_en", ""),
        "author_slug": meta["author_slug"],
        "source": "st-takla.org",
        "source_url": meta["source"],
        "topics": [],                          # left for human curation (plan §7)
        "series": meta.get("series", ""),
        "series_en": meta.get("series_en", ""),
        "description": meta.get("description", ""),
        "description_en": meta.get("description_en", ""),
        "keywords": meta.get("keywords", []),
        "epub": f"{meta['slug']}.epub",
        "cover": "cover.jpg" if meta.get("have_cover") else "",
        "language": meta.get("language", "ar"),
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)


# ------------------------------- extract -------------------------------
def extract_book(index_url, out_dir, author_slug, book_slug, family, section, delay,
                 max_pages=DEFAULT_MAX_PAGES):
    """Returns (ok, problems, epub_path, n_chap, deferred_reason).
    deferred_reason is None unless the book exceeded max_pages (a giant) — in
    which case partial output is discarded and ok is False."""
    log = []
    out_dir = os.path.expanduser(out_dir)
    # idempotent: wipe & rebuild
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    # Fetch the actual index URL (authoritative for both families). Do NOT guess
    # 'index.html' — legacy book indexes are '...00-index.html' / '..._Index.html',
    # and St-Takla serves a soft-404 page with HTTP 200 for a wrong guess.
    base = index_url if index_url.endswith("/") else index_url.rsplit("/", 1)[0] + "/"
    idx_html = fetch_html(index_url)
    if idx_html is None:
        return False, ["index page 404"], None, 0, None
    index_soup = BeautifulSoup(idx_html, "lxml")
    if is_404_soup(index_soup):
        return False, ["index page is 404"], None, 0, None

    title, author, cover_url, desc = derive_meta(index_soup)
    lang = "en" if section == "english" else "ar"
    title = title or book_slug
    author = author or author_slug.replace("-", " ").title()

    print(f"  Title : {title}\n  Author: {author}\n  Family: {family}  Section: {section}")
    page_cache = {}
    try:
        order, method = detect_order(index_soup, base, delay, log, page_cache, max_pages)
    except DeferBook as d:
        # giant set: discard the (empty) book folder; do NOT build a truncated EPUB
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir)
        print(f"  DEFER: reading order exceeds {max_pages} pages ({d.reason})")
        return False, [f"deferred: {d.reason}"], None, 0, d.reason
    print(f"  Reading order: {len(order)} item(s) via {method}")
    if not order:
        return False, ["could not determine reading order"], None, 0, None

    manifest = walk(base, index_url, idx_html, order, method,
                    os.path.join(out_dir, "pages"), delay, log, title, page_cache)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    cover_path = None
    have_cover = False
    if cover_url:
        cover_path = os.path.join(out_dir, "cover.jpg")
        try:
            data = fetch(cover_url)
            if data:
                with open(cover_path, "wb") as f:
                    f.write(data)
                have_cover = True
            else:
                cover_path = None
        except Exception as e:
            log.append(f"cover failed: {e}")
            cover_path = None

    meta = {
        "slug": book_slug, "title": title, "author": author,
        "author_slug": author_slug, "source": index_url,
        "description": desc or "", "language": lang, "have_cover": have_cover,
        "title_en": title if lang == "en" else "",
    }
    epub_path, n_chap = build_epub(out_dir, manifest, meta, cover_path, delay, log)
    write_meta(out_dir, meta)

    ok, problems = validate_epub(epub_path, out_dir)
    return ok, problems + log, epub_path, n_chap, None


# ------------------------------- catalog -------------------------------
def update_catalog_status(book_id, status):
    if not os.path.exists(CATALOG):
        return
    recs = json.load(open(CATALOG, encoding="utf-8"))
    for r in recs:
        if r["book_id"] == book_id:
            r["status"] = status
    json.dump(recs, open(CATALOG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def log_deferred(rec, reason):
    """Append a 'deferred giant' line to tools/deferred.md, idempotently (keyed on
    book_id so re-runs / re-skips don't double-list)."""
    book_id = rec["book_id"]
    header = ("# Deferred books (giants)\n\n"
              "Oversized sets skipped during bulk extraction (see extract_book.py:\n"
              "`--max-pages`, default 200, and the `chapter_links_guess >= 150` "
              "pre-skip). Extract these deliberately later, e.g. with a higher\n"
              "`--max-pages`. One line per book.\n\n"
              "| title | author | dest | index_url | reason |\n"
              "|---|---|---|---|---|\n")
    if not os.path.exists(DEFERRED_MD):
        with open(DEFERRED_MD, "w", encoding="utf-8") as f:
            f.write(header)
    existing = open(DEFERRED_MD, encoding="utf-8").read()
    if f"| {book_id} |" in existing or f"`{rec['index_url']}`" in existing:
        return                                  # already listed
    title = (rec.get("title_guess") or rec["book_slug"]).replace("|", "/").strip()
    author = (rec.get("author_guess") or rec["author_slug"]).replace("|", "/").strip()
    line = (f"| {title} | {author} | `{rec['dest']}` | {book_id} | "
            f"`{rec['index_url']}` | {reason} |\n")
    with open(DEFERRED_MD, "a", encoding="utf-8") as f:
        f.write(line)


def run_record(rec, delay, max_pages=DEFAULT_MAX_PAGES):
    print(f"\n=== {rec['book_id']} ===")
    out = os.path.join(REPO, rec["dest"])
    ok, problems, epub, n_chap, deferred = extract_book(
        rec["index_url"], out, rec["author_slug"], rec["book_slug"],
        rec["family"], rec.get("section", "arabic"), delay, max_pages)
    if deferred:
        update_catalog_status(rec["book_id"], "deferred")
        log_deferred(rec, deferred)
        print(f"  -> deferred ({deferred})")
        return ok, n_chap, 0, problems, True
    size_kb = (os.path.getsize(epub) // 1024) if epub and os.path.exists(epub) else 0
    status = "verified" if ok else "failed"
    update_catalog_status(rec["book_id"], status)
    print(f"  -> {status}: {n_chap} chapters, {size_kb} KB EPUB")
    if problems:
        for p in problems:
            print(f"     - {p}")
    return ok, n_chap, size_kb, problems, False


def preskip_giant(rec):
    """A record whose crawler chapter_links_guess is a giant (>= GIANT_GUESS_
    CHAPTERS) is deferred WITHOUT fetching (the ~37 English ECF Ante/Post-Nicene
    Fathers volumes). Returns True if it was pre-skipped."""
    guess = rec.get("chapter_links_guess") or 0
    if guess >= GIANT_GUESS_CHAPTERS:
        update_catalog_status(rec["book_id"], "deferred")
        log_deferred(rec, "guess>=150")
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Extract a St-Takla.org book to a folder + EPUB.")
    ap.add_argument("url", nargs="?", help="Book index URL")
    ap.add_argument("--out")
    ap.add_argument("--from-catalog", help="book_id / book_slug from catalog.json, or 'all'")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--author-slug"); ap.add_argument("--book-slug")
    ap.add_argument("--family", default="clean"); ap.add_argument("--section", default="arabic")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                    help="defer a book whose reading order exceeds this many pages "
                         f"(default {DEFAULT_MAX_PAGES}; 0 = no cap)")
    ap.add_argument("--dry-giants", action="store_true",
                    help="report how many catalog records the chapter_links_guess>="
                         f"{GIANT_GUESS_CHAPTERS} pre-skip rule would defer, then exit")
    args = ap.parse_args()

    if args.dry_giants:
        recs = json.load(open(CATALOG, encoding="utf-8"))
        giants = [r for r in recs if (r.get("chapter_links_guess") or 0) >= GIANT_GUESS_CHAPTERS]
        print(f"chapter_links_guess >= {GIANT_GUESS_CHAPTERS} pre-skip would defer "
              f"{len(giants)} of {len(recs)} records as giants:")
        for r in giants:
            print(f"  {r['chapter_links_guess']:5d} ch  {r['book_id']}  ({r.get('section')})")
        sys.exit(0)

    if args.from_catalog:
        recs = json.load(open(CATALOG, encoding="utf-8"))
        if args.from_catalog == "all":
            targets = recs[:args.limit] if args.limit else recs
        else:
            # prefer an exact book_id match; fall back to slug only if unambiguous
            exact = [r for r in recs if r["book_id"] == args.from_catalog
                     or r["book_id"].endswith("/" + args.from_catalog)]
            targets = exact or [r for r in recs if r["book_slug"] == args.from_catalog]
            if not targets:
                sys.exit(f"No catalog record matches '{args.from_catalog}'")
            if len(targets) > 1:
                ids = ", ".join(r["book_id"] for r in targets)
                sys.exit(f"Ambiguous '{args.from_catalog}' matches multiple books: {ids}\n"
                         f"Pass a full book_id (e.g. <author-slug>/<book-slug>).")
        results, preskipped = [], 0
        batch = (args.from_catalog == "all")
        for r in targets:
            # In the 'all' batch path, pre-skip giants by the crawler's guess
            # (no fetch). For a single named book, honour the explicit request.
            if batch and preskip_giant(r):
                preskipped += 1
                print(f"\n=== {r['book_id']} ===\n  -> deferred (guess>=150, pre-skip)")
                continue
            results.append((r["book_id"], *run_record(r, args.delay, args.max_pages)))
        print("\n--- batch summary ---")
        if preskipped:
            print(f"  pre-skipped giants (guess>={GIANT_GUESS_CHAPTERS}): {preskipped}")
        for bid, ok, n, kb, probs, deferred in results:
            tag = "DEFER" if deferred else ("PASS" if ok else "FAIL")
            print(f"  {tag}  {bid}  ({n} ch, {kb} KB)")
        sys.exit(0 if all(r[1] or r[5] for r in results) else 1)

    if not args.url:
        sys.exit("Provide a book index URL or --from-catalog.")
    slug = args.book_slug or [p for p in urlparse(args.url).path.split("/") if p][-2]
    aslug = canonical_author(args.author_slug or "unknown")
    out = args.out or os.path.join(REPO, "books", "st-takla.org", aslug, slug)
    ok, problems, epub, n_chap, deferred = extract_book(
        args.url, out, aslug, slug, args.family, args.section, args.delay, args.max_pages)
    tag = "DEFER" if deferred else ("PASS" if ok else "FAIL")
    print(f"\n{tag}: {n_chap} chapters")
    for p in problems:
        print(f"  - {p}")
    sys.exit(0 if (ok or deferred) else 1)


if __name__ == "__main__":
    main()
