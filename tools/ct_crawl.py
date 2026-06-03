#!/usr/bin/env python3
"""
ct_crawl.py — Discover the coptic-treasures.com book library and produce
`tools/ct_catalog.json`, one record per book (metadata + Google-Drive file id).

Phase 1 of the coptic-treasures extraction (mirrors crawl.py for st-takla). It
does NOT download any PDFs — it only walks the site's book sitemaps, fetches
each book page, and records the metadata + download link(s). Review
`ct_catalog.json`, then run `ct_download.py` to pull the actual PDFs.

Why sitemaps, not pagination: the site exposes 6 `book-sitemap*.xml` files
(~5,364 book URLs total) — a complete, paginate-free index. The /sections/books/
listing is 671 pages of 8 books each; the sitemap is the same set, fetched once.

Each coptic-treasures book page is a WordPress (GeneratePress) `book` post with:
  * <article id="post-NNN" class="... book ... category-<slug> ...
    main-category-<id> ... author-speaker-<slug>">  — machine-readable taxonomy
  * a JSON-LD schema.org/Book block (author, genre, keywords, inLanguage, …)
  * a download <table>: <a class="download-button" href="<drive link>"> rows,
    each paired with a file-size <td>. Most links are
    drive.google.com/open?id=<ID> (also handles /file/d/<ID>/ and uc?id=<ID>).
  * og:image / JSON-LD image — the book cover.

Politeness: descriptive UA, configurable delay (default 0.6s), retry w/ backoff.
robots.txt allows `User-agent: *` (empty Disallow); we stay polite regardless.

Resumable: re-reads any existing ct_catalog.json and skips book URLs already
parsed OK. Saves incrementally every SAVE_EVERY records and on exit.

Usage:
  python3 tools/ct_crawl.py                  # full discovery -> tools/ct_catalog.json
  python3 tools/ct_crawl.py --max-books 30   # cap (testing)
  python3 tools/ct_crawl.py --delay 1.0
  python3 tools/ct_crawl.py --refetch-failed # re-attempt records with a fetch error
"""
import argparse, json, os, re, sys, time
import urllib.request, urllib.error
from urllib.parse import urlparse, unquote, parse_qs
from html import unescape
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) CopticLibrary/1.0 "
                    "(+book archival; contact athanasius742)"}
HOST = "coptic-treasures.com"
TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
CATALOG = os.path.join(TOOLS, "ct_catalog.json")
SITEMAP_INDEX = "https://coptic-treasures.com/sitemap_index.xml"
SAVE_EVERY = 25


# ----------------------------- networking -----------------------------
def fetch(url, retries=4, timeout=60):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None
            last = e
        except Exception as e:
            last = e
        time.sleep(min(2 ** attempt, 30))
    raise last


def fetch_text(url, **kw):
    raw = fetch(url, **kw)
    return None if raw is None else raw.decode("utf-8", "replace")


# ----------------------------- sitemap walk -----------------------------
def discover_book_urls():
    """Return the ordered, de-duplicated list of every book page URL."""
    idx = fetch_text(SITEMAP_INDEX)
    maps = [m for m in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", idx)
            if re.search(r"/book-sitemap\d*\.xml", m)]
    urls, seen = [], set()
    for sm in maps:
        body = fetch_text(sm)
        for loc in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", body):
            loc = loc.strip()
            # require a real slug after /book/ — skip the bare listing page
            if urlparse(loc).path.rstrip("/") in ("/book", ""):
                continue
            if "/book/" in loc and loc not in seen:
                seen.add(loc)
                urls.append(loc)
        time.sleep(0.3)
    return urls


# ----------------------------- parsing helpers -----------------------------
DRIVE_ID_RES = [
    re.compile(r"/file/d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"),
]


def drive_id(url):
    for rx in DRIVE_ID_RES:
        m = rx.search(url)
        if m:
            return m.group(1)
    return None


def slug_from_url(url):
    """Decoded last path segment, e.g. .../book/<slug>/ -> '<slug>' (Arabic kept)."""
    path = urlparse(url).path.rstrip("/")
    seg = path.rsplit("/", 1)[-1]
    seg = unquote(seg)
    # filesystem hygiene: kill separators/control chars, collapse whitespace
    seg = seg.replace("/", "-").replace("\\", "-").replace("\x00", "")
    seg = re.sub(r"\s+", " ", seg).strip().strip(".")
    return seg


def first_jsonld_book(soup):
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        cands = data if isinstance(data, list) else [data]
        for d in cands:
            if isinstance(d, dict) and d.get("@type") == "Book":
                return d
    return {}


def clean(s):
    return unescape(re.sub(r"\s+", " ", (s or "")).strip()) if s else ""


def person_name(node):
    if isinstance(node, dict):
        return clean(node.get("name", ""))
    return clean(node) if isinstance(node, str) else ""


def parse_book(url, html):
    soup = BeautifulSoup(html, "lxml")
    art = soup.find("article", class_="book") or soup.find("article")
    classes = art.get("class", []) if art else []
    classlist = " ".join(classes)

    post_id = ""
    m = re.search(r"post-(\d+)", classlist)
    if m:
        post_id = m.group(1)

    author_slugs = [c[len("author-speaker-"):] for c in classes
                    if c.startswith("author-speaker-")]
    category_slugs = [c[len("category-"):] for c in classes
                      if c.startswith("category-") and not c.startswith("main-category-")]
    main_category_ids = [c[len("main-category-"):] for c in classes
                         if c.startswith("main-category-")]

    ld = first_jsonld_book(soup)
    title = clean(ld.get("name")) or clean(
        (art.find("h1") if art else None) and art.find("h1").get_text())
    author = person_name(ld.get("author"))
    editor = person_name(ld.get("editor"))
    translator = person_name(ld.get("translator"))
    publisher = person_name(ld.get("publisher"))
    genre = clean(ld.get("genre"))
    language = clean(ld.get("inLanguage")) or "ar"
    number_of_pages = clean(str(ld.get("numberOfPages", "")))
    date_published = clean(str(ld.get("datePublished", "")))
    keywords = [clean(k) for k in (ld.get("keywords", "") or "").split(",") if clean(k)]
    cover_url = clean(ld.get("image"))
    if not cover_url:
        og = soup.find("meta", attrs={"property": "og:image"})
        cover_url = clean(og.get("content")) if og else ""

    # visible info-card extras (categories text, last-updated, rating)
    categories_text, last_updated, rating = [], "", ""
    box = soup.find(class_=re.compile(r"schema_book_microdata_container"))
    if box:
        rows = box.find_all("tr")
        for tr in rows:
            cells = [clean(td.get_text()) for td in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            label, val = cells[0], cells[1]
            if "التصنيف" in label:
                categories_text = [c.strip() for c in re.split(r"[,،]", val) if c.strip()]
            elif "تحديث" in label:
                last_updated = val
            elif "تقييم" in label:
                mm = re.search(r"(\d+(?:\.\d+)?)", val)
                rating = mm.group(1) if mm else val

    # download table: <a class="download-button"> paired with a size <td>
    downloads, seen = [], set()
    for a in soup.find_all("a", class_=re.compile(r"download-button")):
        href = clean(a.get("href"))
        if not href or href in seen:
            continue
        seen.add(href)
        size = ""
        tr = a.find_parent("tr")
        if tr:
            tds = tr.find_all("td")
            if len(tds) >= 2:
                size = clean(tds[-1].get_text())
        downloads.append({
            "url": href,
            "drive_id": drive_id(href),
            "size": size,
            "label": clean(a.get_text()),
        })

    author_slug = author_slugs[0] if author_slugs else "unknown-author"
    book_slug = slug_from_url(url)
    dest = os.path.join("books", HOST, author_slug, book_slug)

    return {
        "book_id": f"{HOST}/{author_slug}/{book_slug}",
        "post_id": post_id,
        "url": unquote(url),
        "url_encoded": url,
        "title": title,
        "author": author,
        "author_slug": author_slug,
        "author_slugs": author_slugs,
        "editor": editor,
        "translator": translator,
        "publisher": publisher,
        "categories": categories_text or ([genre] if genre else []),
        "category_slugs": category_slugs,
        "main_category_ids": main_category_ids,
        "genre": genre,
        "keywords": keywords,
        "language": language,
        "number_of_pages": number_of_pages,
        "date_published": date_published,
        "last_updated": last_updated,
        "rating": rating,
        "cover_url": cover_url,
        "book_slug": book_slug,
        "dest": dest,
        "source": HOST,
        "source_url": unquote(url),
        "downloads": downloads,
        "status": "discovered" if downloads else "no-file",
    }


# ----------------------------- catalog io -----------------------------
def load_catalog():
    if os.path.exists(CATALOG):
        with open(CATALOG, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_catalog(records):
    tmp = CATALOG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CATALOG)


# ----------------------------- main -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-books", type=int, default=0, help="cap for testing (0=all)")
    ap.add_argument("--delay", type=float, default=0.6, help="seconds between fetches")
    ap.add_argument("--refetch-failed", action="store_true",
                    help="re-attempt records whose status is a fetch error")
    args = ap.parse_args()

    records = load_catalog()
    by_url = {r["url_encoded"]: r for r in records}

    print("Discovering book URLs from sitemaps…", flush=True)
    urls = discover_book_urls()
    print(f"  {len(urls)} book URLs found", flush=True)

    todo = []
    for u in urls:
        r = by_url.get(u)
        if r is None:
            todo.append(u)
        elif args.refetch_failed and r.get("status") == "fetch-error":
            todo.append(u)
    if args.max_books:
        todo = todo[:args.max_books]
    print(f"  {len(todo)} to fetch ({len(by_url)} already in catalog)", flush=True)

    done = 0
    for i, u in enumerate(todo, 1):
        try:
            html = fetch_text(u)
            if html is None:
                rec = {"url_encoded": u, "url": unquote(u), "source": HOST,
                       "status": "gone-404"}
            else:
                rec = parse_book(u, html)
        except Exception as e:
            rec = {"url_encoded": u, "url": unquote(u), "source": HOST,
                   "status": "fetch-error", "error": str(e)[:200]}

        if u in by_url:
            records[records.index(by_url[u])] = rec
        else:
            records.append(rec)
        by_url[u] = rec
        done += 1

        if done % SAVE_EVERY == 0:
            save_catalog(records)
            print(f"  [{i}/{len(todo)}] saved · last: "
                  f"{rec.get('title','?')[:50]} [{rec.get('status')}]", flush=True)
        time.sleep(args.delay)

    save_catalog(records)

    # summary
    from collections import Counter
    stat = Counter(r.get("status") for r in records)
    nfiles = sum(len(r.get("downloads", [])) for r in records)
    ndrive = sum(1 for r in records for d in r.get("downloads", []) if d.get("drive_id"))
    print(f"\nDone. {len(records)} records in ct_catalog.json")
    print("  status:", dict(stat))
    print(f"  download links: {nfiles} ({ndrive} google-drive)")


if __name__ == "__main__":
    main()
