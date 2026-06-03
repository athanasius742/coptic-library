# Tools

Scripts for extracting books into this archive and maintaining its structure.

Requires Python 3 with `beautifulsoup4` and `lxml`:

```bash
pip install beautifulsoup4 lxml
```

## Bulk-extraction workflow (St-Takla.org library)

The library is a tree of category indexes, not a flat list. Bulk extraction is
two stages — see `../EXTRACTION_PLAN.md` for the full plan.

1. **Discover** the tree → `crawl.py` writes `catalog.json` (one record per book).
   Review `catalog.json` before extracting.
2. **Extract** a book (or a batch) → `extract_book.py` reads a catalog record,
   walks the book, builds the EPUB, validates it, and marks the record
   `verified` / `failed`.
3. Re-run `make_views.py` to regenerate the catalog markdown.

### `crawl.py` — discover books → `catalog.json`

BFS from the known category seeds, scoped to `div#bodytext` and the
`/books/` + `/Full-Free-Coptic-Books/` boundary on host `st-takla.org`. Each page
is classified as a BOOK index, a CATEGORY/hub (recursed into), or skipped (404 /
out of scope). Books are deduped by directory. Polite (≥1s, backoff, descriptive
UA). The 404 page is detected by its `<title>` (not by charset — the English
section legitimately declares `windows-1252`).

```bash
python3 tools/crawl.py                  # full discovery -> tools/catalog.json
python3 tools/crawl.py --max-pages 50   # cap fetches (testing)
python3 tools/crawl.py --delay 1.5
```

Classification signal: a **book** is dominated by same-directory sibling `.html`
chapter links and has no child-directory index links; a **category** links into
child-directory `*index*.html` pages (author hubs, collection hubs, multi-section
hubs) — those get enqueued. Each record carries `family` (clean/legacy), derived
`author_slug`/`book_slug`, `index_url`, `cover_url`, `title_guess`,
`author_guess`, `dest`, `section` (arabic/english), and `status:"discovered"`.
Messy legacy collection names map to clean author slugs via the
`COLLECTION_AUTHOR_MAP` table at the top of `crawl.py` (extend as needed).

**Author-slug merges:** the same author sometimes appears under several slugs
(a clean `/books/<author>/` form and a legacy `FreeCopticBooks-NNN-…` form, or an
English variant). Confirmed duplicates are collapsed onto ONE canonical slug per
author via `CANONICAL_AUTHOR_MAP` in `crawl.py` (mirrored in `extract_book.py`),
applied at the end of slug derivation so all future crawls/extracts group
cleanly. The legacy `COLLECTION_AUTHOR_MAP` entries point straight at the
canonical slug. Current merges: `father-tadros-yaacoub-malaty`,
`fr-tadros-yacoub` → `fr-tadros-malaty`; `father-athanasius-fahmy-george` →
`fr-athnasius-fahmy`; `bishop-makarios` → `anba-macarious`; `bishop-metaos` →
`anba-metaos`; `bishop-bemen` → `anba-bimen`; `yousef-habeeb` → `youssef-habib`;
`bishop-youannes` → `anba-yoannes`; `father-botrous-el-baramousy` →
`fr-botros-elbaramosy`.

### `extract_book.py` — one book → folder + validated EPUB

A generalised refactor of `sttakla_extract.py` that handles the library's
structural variation:

- **Reading order** (priority): `<a id="next">` chain → ordered TOC sibling links
  (the **legacy** `FreeCopticBooks-NNN-…` family has no next-chain) → single-page
  (the index is the only content). The two methods are cross-checked when both
  exist; mismatches are logged.
- Charset rewrite (`windows-1256`/`1252` → `utf-8`); 404 chapters skipped.
- Cover from `og:image`; inline images downloaded (arrows/dividers dropped;
  `/Gallery/var/resizes|thumbs/` retried via the `/albums/` original; missing
  images are non-fatal).
- RTL EPUB for Arabic, **LTR/`lang=en`** for English-section books.
- `meta.json` written with `topics: []` left for human curation.
- **Idempotent** (wipes & rebuilds the book folder) and **self-validating**
  (zip integrity; mimetype first+stored; all XHTML/OPF/NCX well-formed via lxml;
  manifest/spine/image refs resolve; ≥1 chapter; no leftover chrome strings).
- **Defer the giants:** `--max-pages` (default **200**) aborts a book whose
  reading order exceeds the cap — partial output is discarded (no truncated EPUB)
  and the record's `status` becomes `"deferred"`. In `--from-catalog all`, any
  record whose crawler `chapter_links_guess >= 150` is **pre-skipped** (deferred
  without fetching) — these are the English ECF Ante/Post-Nicene Fathers volumes
  (800–1500+ ch). Every deferred book is appended (idempotently) to
  `tools/deferred.md` with title/author/dest/index_url/reason (`guess>=150` or
  `chain>200`). `--dry-giants` reports how many records the `>=150` rule would
  pre-skip and exits (read-only). Extract a deferred book deliberately later with
  a higher `--max-pages`.

```bash
# from a catalog record (preferred — sets author/family/section/status):
python3 tools/extract_book.py --from-catalog i-willingly-ate
python3 tools/extract_book.py --from-catalog all --limit 5      # first N
python3 tools/extract_book.py --from-catalog all                # batch (defers giants)
python3 tools/extract_book.py --dry-giants                      # count giant pre-skips

# or directly from an index URL:
python3 tools/extract_book.py \
    https://st-takla.org/books/anba-raphael/i-willingly-ate/index.html \
    --author-slug anba-raphael --book-slug i-willingly-ate
```

Exit status is 0 only if validation passes. Topics stay empty — tag them in each
`meta.json` and re-run `make_views.py`.

## `sttakla_extract.py` — extract a St-Takla.org book (single-structure)

The original validated extractor (clean family only); `extract_book.py`
supersedes it for bulk work but it is kept as the reference implementation.

Walks a book by following its `<a id="next">` chain, saves every page (decoded
from windows-1256 to UTF-8), organizes per-chapter directories, downloads the
cover (`og:image`) and inline illustrations, and builds a right-to-left EPUB.

```bash
python3 tools/sttakla_extract.py \
    https://st-takla.org/books/anba-raphael/i-willingly-ate/index.html \
    --out books/st-takla.org/anba-raphael/i-willingly-ate
```

Title, author, cover and the first content page are auto-detected from the index
page; override with `--title`, `--author`, `--start`, `--slug`. Use `--no-epub`
to only fetch pages. Be polite: `--delay` defaults to 1s between requests.

After extracting, add a `meta.json` to the book folder (see existing books for
the schema — `slug`, `title`, `author_slug`, `source`, `topics`, `epub`, …) and
run `make_views.py`.

> This extractor targets the St-Takla.org page structure. Other sources need
> their own extractor; the EPUB builder inside is largely source-agnostic.

## `make_views.py` — regenerate the catalog

Rebuilds the markdown catalog from each book's `meta.json` (+ `manifest.json`):
the root `README.md`, the `by-author.md` and `by-topic.md` tables (links into the
single copy under `books/`), and a per-book `README.md`. Idempotent — run it
whenever you add a book or change metadata:

```bash
python3 tools/make_views.py
```

`README.md`, `by-author.md`, `by-topic.md` and per-book `README.md` files are
**generated** — don't edit them by hand; edit a book's `meta.json` and re-run.
Each book lives in exactly one place under `books/`; the catalogs are just tables
of links (no symlinks or duplicated copies).

## coptic-treasures.com import (`ct_crawl.py` + `ct_download.py`)

A second source: the [coptic-treasures.com](https://coptic-treasures.com) book
library (~5,300 books, each a PDF on Google Drive). Two phases, mirroring the
st-takla crawl→extract split. Output lands under `books/coptic-treasures.com/`
in the same directory convention (ascii `author-slug`, decoded-Arabic `book-slug`).

### `ct_crawl.py` — discover books → `ct_catalog.json`

Walks the 6 `book-sitemap*.xml` files, fetches each book page, and records one
catalog record per book: metadata from the `schema.org/Book` JSON-LD + the
`<article class="… category-<slug> main-category-<id> author-speaker-<slug>">`
taxonomy + the info-card, plus the Google-Drive download link(s) and file size.
Resumable; polite (descriptive UA, default 0.6s delay).

```bash
python3 tools/ct_crawl.py                 # full discovery -> tools/ct_catalog.json
python3 tools/ct_crawl.py --max-books 30  # cap (testing)
```

### `ct_download.py` — download PDFs + covers + `meta.json`

Reads `ct_catalog.json` and downloads each book's file(s) from Google Drive into
`books/coptic-treasures.com/<author>/<book>/` (`book.pdf` + `cover.jpg` +
st-takla-style `meta.json`). Handles Google's >100MB virus-scan confirm
interstitial; skips permanent 404/401 (dead/restricted files) without retrying.
Resumable/idempotent; writes status back to the catalog.

```bash
python3 tools/ct_download.py              # download everything pending
python3 tools/ct_download.py --retry-failed
```

**Access note:** ~93% of the Drive links are public; the rest are 401
(restricted) or 404 (deleted) at the source. Unavailable books are recorded in
`tools/ct_failed.json` (not kept on disk). Files exceeding GitHub's 100MB limit
are tracked via Git LFS (see `.gitattributes`) and listed in
`tools/ct_oversized.json`.
