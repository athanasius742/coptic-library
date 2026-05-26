#!/usr/bin/env python3
"""
crawl.py — Discover the St-Takla.org free Coptic books library and produce
`tools/catalog.json`, one record per book.

This is Phase 1 of the bulk-extraction plan (see EXTRACTION_PLAN.md). It does NOT
extract anything — it only walks the category tree (BFS), classifies each page,
and records every BOOK index it finds. Stop after this and review catalog.json
before mass extraction.

How it works (validated against the live site, see plan §2-§4):
  * Source pages are windows-1256 (English section may declare windows-1252).
    We decode best-effort and rewrite the declared charset to utf-8.
  * The 404 page is detected by its <title> containing "404" — NOT by charset.
  * Link discovery is scoped to <div id="bodytext"> (the mega-menu outside it
    links to ~50 books site-wide on every page and would explode the crawl).
  * Crawl boundary: host st-takla.org, path under /books/ or
    /Full-Free-Coptic-Books/. Other sections are out of scope.

Classification (per page, on its bodytext links):
  * BOOK index  — same-directory sibling .html links dominate AND there are no
                  links into child directories' index pages. These siblings are
                  the chapters (clean family also exposes an a#next walk chain;
                  legacy family has none — extract_book.py handles both).
  * CATEGORY    — has links into child-directory index pages, or links to many
                  different directories (a hub). Enqueue those links.
  * SKIP        — 404, out of boundary, or already visited.

Usage:
  python3 tools/crawl.py                 # full discovery -> tools/catalog.json
  python3 tools/crawl.py --max-pages 200 # cap fetches (testing)
  python3 tools/crawl.py --delay 1.5
"""
import argparse, json, os, re, sys, time, collections
import urllib.request, urllib.error
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) CopticLibrary/1.0 (+book archival; contact athanasius742)"}
HOST = "st-takla.org"
TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
CATALOG = os.path.join(TOOLS, "catalog.json")

SEEDS = [
    "https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01.html",
    "https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01-a-Bishops.html",
    "https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01-b-Priests.html",
    "https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01-c-Laymen.html",
    "https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01-d-Churches.html",
    "https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-02-Church-Books.html",
    "https://st-takla.org/Full-Free-Coptic-Books/00-English-Christian-Books/Christian-Coptic-Library-00-index.html",
    "https://st-takla.org/Full-Free-Coptic-Books/His-Holiness-Pope-Shenouda-III-Books-Online/Pope-Shenoda-Books_.html",
    "https://st-takla.org/Full-Free-Coptic-Books/patristics.html",
    "https://st-takla.org/books/various/index.html",
]

# Sections that show up as cross-links but are out of scope for the books library.
BOUNDARY_PREFIXES = ("/books/", "/Full-Free-Coptic-Books/")


# ----------------------------- networking -----------------------------
def fetch(url, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None, url            # gone — caller treats as skip
            last = e
        except Exception as e:
            last = e
        time.sleep(2 ** attempt)            # backoff: 1, 2, 4s
    raise last


def fetch_html(url):
    raw, final = fetch(url)
    if raw is None:
        return None, final
    # Decode: most pages are windows-1256; English may be windows-1252. Try the
    # declared charset first, then 1256, then utf-8 — all best-effort.
    m = re.search(rb"charset=([\w-]+)", raw[:2048], re.I)
    declared = (m.group(1).decode("ascii", "ignore").lower() if m else "windows-1256")
    enc = declared if declared in ("windows-1256", "windows-1252", "utf-8", "iso-8859-1") else "windows-1256"
    text = raw.decode(enc, errors="replace")
    text = re.sub(r"windows-125[26]|iso-8859-1", "utf-8", text, flags=re.I)
    return text, final


# ----------------------------- helpers --------------------------------
def in_boundary(url):
    p = urlparse(url)
    return p.netloc.endswith(HOST) and any(p.path.startswith(b) for b in BOUNDARY_PREFIXES)


def norm(url):
    """Normalize for the visited-set: drop fragment & trailing query."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


def is_404(soup):
    t = (soup.title.get_text() if soup.title else "")
    return "404" in t


def bodytext(soup):
    b = soup.find("div", id="bodytext")
    if b:
        return b
    # fallback: largest text/link container
    best, best_len = None, 0
    for d in soup.find_all("div"):
        n = len(d.get_text(strip=True))
        if n > best_len:
            best, best_len = d, n
    return best or soup


def slugify(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s or "").strip("-").lower()
    return re.sub(r"-{2,}", "-", s) or "x"


# author_slug overrides for messy legacy collection folders (plan §6). Extend as
# the user reviews catalog.json. Keys are matched against the collection folder.
# NOTE: where a legacy collection is the SAME author as a clean-family slug, this
# maps straight to the canonical clean slug (see CANONICAL_AUTHOR_MAP below).
COLLECTION_AUTHOR_MAP = {
    "His-Holiness-Pope-Shenouda-III-Books-Online": "pope-shenouda-iii",
    "FreeCopticBooks-006-His-Grace-Bishop-Makarios": "anba-macarious",
    "FreeCopticBooks-008-Anba-Metropolitan-Bishoy": "anba-bishoy",
    "FreeCopticBooks-009-Bishop-Moussa": "bishop-moussa",
    "FreeCopticBooks-010-Late-Bishop-Youannes": "anba-yoannes",
    "FreeCopticBooks-011-Late-Bishop-Bemen": "anba-bimen",
    "FreeCopticBooks-013-His-Grace-Bishop-Metaos": "anba-metaos",
    "FreeCopticBooks-017-Bishop-Yakobos": "bishop-yakobos",
    "FreeCopticBooks-029-Bishop-Isithoros-of-El-Baramous": "bishop-isithoros",
    "FreeCopticBooks-014-Various-Authors": "various-authors",
    "FreeCopticBooks-015-Church-Fathers-Sayings": "church-fathers",
    "FreeCopticBooks-018-Father-Athanasius-Fahmy-George": "fr-athnasius-fahmy",
    "FreeCopticBooks-020-Father-Tadros-Yaacoub-Malaty": "fr-tadros-malaty",
    "FreeCopticBooks-022-Yousef-Habeeb": "youssef-habib",
    "FreeCopticBooks-025-Father-Botrous-El-Baramousy": "fr-botros-elbaramosy",
}

# Canonical author-slug merges (the user merged duplicate slugs — see the merge
# report). Maps any non-canonical slug (clean OR legacy, after the slug is first
# derived from the URL) to ONE canonical slug per author so ALL future
# derivations group cleanly. The legacy-collection overrides above already point
# at the canonical slug; this catches the clean-family duplicates too
# (e.g. the English /books/en/fr-tadros-yacoub/ form).
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
    """Collapse a duplicate author slug onto its canonical form (user merge)."""
    return CANONICAL_AUTHOR_MAP.get(author_slug, author_slug)


def derive_ids(index_url):
    """Return (family, author_slug, book_slug, book_dir) from the index URL."""
    p = urlparse(index_url).path
    parts = [seg for seg in p.split("/") if seg]
    book_dir = p.rsplit("/", 1)[0] + "/"
    if "/books/" in p:
        # clean family: /books/<author>/<book>/index.html
        i = parts.index("books")
        rest = parts[i + 1:]
        # rest[-1] is the index file; book dir segment is rest[-2]
        if len(rest) >= 3:
            # e.g. en/<author>/<book>/index.html  OR  <author>/<book>/index.html
            author_slug = rest[-3] if rest[-3] not in ("en",) else (rest[-2] if len(rest) >= 4 else rest[-3])
            # handle /books/en/<author>/<book>/
            if rest[0] == "en" and len(rest) >= 4:
                author_slug, book_slug = rest[1], rest[-2]
            else:
                author_slug, book_slug = rest[-3], rest[-2]
        elif len(rest) == 2:
            author_slug, book_slug = rest[0], "book"
        else:
            author_slug, book_slug = "various", slugify(rest[-1].replace(".html", ""))
        return "clean", canonical_author(author_slug), book_slug, book_dir
    # legacy family: /Full-Free-Coptic-Books/<Collection>/<BookDir>/<x__00-index.html>
    ffc = parts.index("Full-Free-Coptic-Books")
    rest = parts[ffc + 1:]
    collection = rest[0] if rest else ""
    author_slug = COLLECTION_AUTHOR_MAP.get(collection, slugify(re.sub(r"^FreeCopticBooks-\d+-", "", collection)))
    if len(rest) >= 3:
        book_seg = rest[-2]                       # the book's own directory
    else:
        book_seg = rest[-1].replace(".html", "")  # collection-level index file
    book_slug = slugify(re.sub(r"^\d+[-_]", "", book_seg))
    return "legacy", canonical_author(author_slug), book_slug, book_dir


# ----------------------------- classification --------------------------
def classify(url, soup):
    """Return ('book'|'category'|'skip', child_urls, info)."""
    if is_404(soup):
        return "skip", [], {"reason": "404"}
    body = bodytext(soup)
    curdir = norm(url).rsplit("/", 1)[0]
    cur_file = urlparse(url).path.rsplit("/", 1)[1]

    raw_links = []
    for a in body.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        full = norm(urljoin(url, href))
        if not in_boundary(full):
            continue
        raw_links.append((full, a.get_text(" ", strip=True)))

    samedir_sibs, child_index, other = [], [], []
    seen = set()
    for full, text in raw_links:
        if full in seen:
            continue
        seen.add(full)
        ldir = full.rsplit("/", 1)[0]
        lfile = urlparse(full).path.rsplit("/", 1)[1]
        if full == norm(url):
            continue
        if ldir == curdir:
            if lfile.endswith(".html") and "index" not in lfile.lower():
                samedir_sibs.append((full, text))
        elif ldir.startswith(curdir + "/"):
            if "index" in lfile.lower():
                child_index.append((full, text))
            else:
                other.append((full, text))
        else:
            other.append((full, text))

    # CATEGORY: links into child directory indexes (author hub, collection hub,
    # or a multi-section hub). Enqueue those + any cross-directory index links.
    if child_index:
        children = [u for u, _ in child_index]
        # also enqueue cross-dir index-like links (e.g. hub -> /books/<author>/index.html
        # which appear in `other` as another directory's index)
        for u, _ in other:
            lf = urlparse(u).path.rsplit("/", 1)[1].lower()
            if "index" in lf or lf.endswith("_.html") or "books_" in lf:
                children.append(u)
        return "category", list(dict.fromkeys(children)), {"reason": "child-index links"}

    # BOOK: dominated by same-directory sibling content pages, has a cover, and
    # the file looks like a TOC (index.html / *00-index / *_Index).
    og = soup.find("meta", property="og:image")
    looks_index = bool(re.search(r"(^|[-_])index", cur_file, re.I)) or cur_file == "index.html"
    if samedir_sibs and (looks_index or og):
        return "book", [u for u, _ in samedir_sibs], {"reason": "same-dir siblings",
                                                       "chapters": len(samedir_sibs)}

    # Pure hub (many cross-dir links, no same-dir content): enqueue cross links
    # that look like indexes.
    hub_children = []
    for u, _ in other:
        lf = urlparse(u).path.rsplit("/", 1)[1].lower()
        if "index" in lf or lf.endswith("_.html") or "books_" in lf or "books-" in lf:
            hub_children.append(u)
    if hub_children:
        return "category", list(dict.fromkeys(hub_children)), {"reason": "hub cross-links"}

    return "skip", [], {"reason": "unclassified (no book signal)"}


def derive_book_meta(soup):
    title = author = cover = None
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].split("<")[0].split("|")[0].strip()
    if not title and soup.title:
        title = soup.title.get_text().split("|")[0].strip()
    body = bodytext(soup)
    h2 = body.find("h2") if body else None
    if h2 and " - " in h2.get_text():
        author = h2.get_text(" ", strip=True).split(" - ", 1)[1].strip()
    ogimg = soup.find("meta", property="og:image")
    if ogimg and ogimg.get("content"):
        cover = ogimg["content"]
    return title, author, cover


# ------------------------------- crawl ---------------------------------
def crawl(delay, max_pages):
    queue = collections.deque(norm(s) for s in SEEDS)
    visited = set()
    books = {}                              # book_dir -> record (dedupe key)
    counts = collections.Counter()
    fetched = 0

    while queue:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        if max_pages and fetched >= max_pages:
            print(f"  [cap] reached --max-pages {max_pages}; stopping discovery", file=sys.stderr)
            break
        try:
            html_text, final = fetch_html(url)
        except Exception as e:
            print(f"  FETCH FAIL {url}: {e}", file=sys.stderr)
            counts["fetch_fail"] += 1
            continue
        fetched += 1
        if html_text is None:
            counts["404"] += 1
            print(f"  [404] {url}")
            time.sleep(delay)
            continue
        soup = BeautifulSoup(html_text, "lxml")
        kind, children, info = classify(url, soup)
        counts[kind] += 1

        if kind == "category":
            new = 0
            for c in children:
                if c not in visited and c not in queue:
                    queue.append(c)
                    new += 1
            print(f"  [CAT ] {url.replace('https://st-takla.org','')}  (+{new} children)")
        elif kind == "book":
            family, author_slug, book_slug, book_dir = derive_ids(url)
            if book_dir in books:
                print(f"  [dup ] {book_dir} (already discovered)")
                counts["book"] -= 1
                counts["dup"] += 1
            else:
                title, author, cover = derive_book_meta(soup)
                english = "/books/en/" in url or "00-English-Christian-Books" in url or "/en/" in book_dir
                rec = {
                    "book_id": f"st-takla.org/{author_slug}/{book_slug}",
                    "index_url": url,
                    "family": family,
                    "author_slug": author_slug,
                    "book_slug": book_slug,
                    "title_guess": title,
                    "author_guess": author,
                    "cover_url": cover,
                    "dest": f"books/st-takla.org/{author_slug}/{book_slug}",
                    "section": "english" if english else "arabic",
                    "chapter_links_guess": info.get("chapters"),
                    "status": "discovered",
                }
                books[book_dir] = rec
                print(f"  [BOOK] {author_slug}/{book_slug}  ({info.get('chapters')} ch, {family})  {title}")
        else:
            print(f"  [skip] {url.replace('https://st-takla.org','')}  ({info.get('reason')})")
        time.sleep(delay)

    return list(books.values()), counts, len(visited), fetched


def main():
    ap = argparse.ArgumentParser(description="Discover St-Takla.org books -> tools/catalog.json")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--max-pages", type=int, default=0, help="cap fetches (0 = unlimited)")
    ap.add_argument("--out", default=CATALOG)
    args = ap.parse_args()

    print("Crawling St-Takla.org free Coptic books library…\n")
    records, counts, n_visited, fetched = crawl(args.delay, args.max_pages)

    # dedupe book_ids that collide (different dirs mapping to same author/slug)
    seen_ids = {}
    for r in records:
        bid = r["book_id"]
        if bid in seen_ids:
            seen_ids[bid] += 1
            r["book_slug"] = f"{r['book_slug']}-{seen_ids[bid]}"
            r["book_id"] = f"st-takla.org/{r['author_slug']}/{r['book_slug']}"
            r["dest"] = f"books/st-takla.org/{r['author_slug']}/{r['book_slug']}"
        else:
            seen_ids[bid] = 1

    records.sort(key=lambda r: (r["author_slug"], r["book_slug"]))
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # ----- summary -----
    by_family = collections.Counter(r["family"] for r in records)
    by_section = collections.Counter(r["section"] for r in records)
    by_author = collections.Counter(r["author_slug"] for r in records)
    print("\n" + "=" * 60)
    print(f"DISCOVERY SUMMARY  (catalog: {os.path.relpath(args.out, REPO)})")
    print("=" * 60)
    print(f"  Pages fetched          : {fetched}  (visited URLs: {n_visited})")
    print(f"  Categories/hubs        : {counts.get('category', 0)}")
    print(f"  Books discovered       : {len(records)}")
    print(f"  Skipped (incl. 404)    : {counts.get('skip', 0)} + 404s {counts.get('404', 0)}"
          f" + fetch-fail {counts.get('fetch_fail', 0)} + dup {counts.get('dup', 0)}")
    print(f"  By family              : clean={by_family.get('clean',0)}  legacy={by_family.get('legacy',0)}")
    print(f"  By section             : arabic={by_section.get('arabic',0)}  english={by_section.get('english',0)}")
    print(f"  Distinct authors       : {len(by_author)}")
    print("  Top authors by #books  :")
    for a, n in by_author.most_common(12):
        print(f"     {n:3d}  {a}")
    print("=" * 60)
    print("Review tools/catalog.json before extracting. Phase 2/3 use extract_book.py.")


if __name__ == "__main__":
    main()
