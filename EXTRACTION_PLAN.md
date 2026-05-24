# Handoff Plan — Bulk Extraction of St-Takla.org Free Coptic Books

**For:** the agent taking over bulk extraction.
**Goal:** Do what was done for the reference book *“أكلت بإرادتي / I Willingly Ate”*
— but **recursively, for the entire free Coptic books library**, starting from:

> https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01.html

Each extracted book must land in this repo as a clean, self-contained folder
(raw HTML pages + per-chapter dirs + cover + validated EPUB + `meta.json`), and
the catalog must be regenerated. **Read this whole file before writing code.**

---

## 0. TL;DR of the approach

1. **Discover** (crawl) the library tree → produce `tools/catalog.json` listing every book.
2. **Pause for human review** of `catalog.json` (scope/false positives) before mass extraction.
3. **Pilot**: extract 3–5 *structurally different* books, validate, fix the extractor.
4. **Extract** every book (resumable, idempotent, polite), committing in batches.
5. **Index**: run `python3 tools/make_views.py` and verify the catalogs/EPUBs.

Do **not** try to write one regex that fits every book. The library is
**heterogeneous** (see §4). Build a small framework: a crawler, a classifier, a
per-family extractor with fallbacks, and a shared EPUB builder.

---

## 1. Context you inherit (repo conventions — DO NOT break these)

Repo: `/home/jimmy/projects/coptic-library` (public: https://github.com/athanasius742/coptic-library, branch `main`).

- **Canonical layout (single source of truth):**
  `books/<source>/<author-slug>/<book-slug>/`
  For St-Takla, `<source>` = `st-takla.org`.
- **Each book folder contains:** `<slug>.epub`, `cover.jpg` (if any),
  `manifest.json` (walk order), `meta.json` (catalog metadata),
  `pages/` (raw walked HTML, `NN-slug.html`, `00-index.html`),
  `chapters/NN-slug/` (raw `<slug>.html` + cleaned `content.xhtml`),
  `README.md` (generated). **No `_epub_build/`** — it’s scratch, `.gitignore`d.
- **`meta.json` drives the catalog.** Schema (see the reference book for a full example):
  `slug, title, title_en, author, author_en, author_slug, source, source_url,
  topics[], series, series_en, description, description_en, keywords[], epub,
  cover, language`.
- **Catalog files are generated** by `tools/make_views.py` from `meta.json` +
  `manifest.json`: root `README.md`, `by-author.md`, `by-topic.md`, and each
  book’s `README.md`. **Never hand-edit generated files.** Symlink folders were
  tried and abandoned (don’t navigate on GitHub web / break on clones) — the
  catalog is markdown tables of links into the single `books/` copy.
- **Reference implementation:** `tools/sttakla_extract.py` already implements the
  *common* family end-to-end (walk via `<a id="next">`, clean `div#bodytext`,
  download cover + images, build RTL EPUB). Treat it as the starting point and
  **refactor it into reusable functions** the framework can call. It is
  “primitive” precisely because it assumes one structure — your job is to
  generalize it.
- **Git identity for this repo:** commits as `athanasius742 <athanasius742@gmail.com>`
  (already set repo-locally). Commit in batches; push when the user approves.

---

## 2. Validated facts about St-Takla.org (confirmed this session)

- **Encoding:** real content pages are **windows-1256**. Decode to UTF-8 on save
  **and rewrite the declared `charset`** (`windows-1256` → `utf-8`) or the saved
  file renders as mojibake when opened. (A page that decodes as `windows-1252`
  with title containing “404” is the **404 page** — treat as missing, not a real
  encoding.) Still: **detect per page** from the `<meta charset>` and fall back
  gracefully; a few pages (esp. English section) may differ.
- **Content container:** `<div id="bodytext">` holds the real content on book/TOC
  and chapter pages. Everything outside it (navbars, mega-menu, sidebars, footer)
  is site chrome — **ignore it.** The mega-menu links to ~50 books site-wide on
  *every* page; only ~5 links inside `bodytext` are real content. **Always scope
  link discovery to `div#bodytext`.** Have a fallback if `bodytext` is absent
  (largest text/link container).
- **Page navigation (chapter chain):** content pages carry `<a id="next" href="…">`
  (and `<a id="prev">`). The chain **loops back to `index.html`** on the last
  page — stop when `next` is `index.html` or an already-visited URL. Book **index
  pages have no `id="next"`** (they’re the TOC).
- **Cover:** the book index page’s `<meta property="og:image">` is the cover
  (high-res JPEG under `/Gallery/var/albums/…`). `og:title` ≈ book title.
- **Author line:** inside `bodytext`, the first `<h2>` is usually
  `كتاب <title> - <author>`; split on `" - "` for the author. The page `<title>`
  is `<chapter/book> - <book> | St-Takla.org`.
- **Noise to strip from `bodytext`** when cleaning for EPUB: `table.table-footer`
  (prev/next footer), `<a id="next|prev">`, images whose `src` contains `arrow`
  or `divider`, the breadcrumb `<span>` containing `المكتبة القبطية`, the
  redundant book-title `<h2>`, and any `script/style/ins/iframe`.
- **robots.txt:** allows `/books/` and `/Full-Free-Coptic-Books/` (good). Only
  admin/system paths and **`/Gallery/var/resizes/`** + `/Gallery/var/thumbs/` are
  `Disallow`ed. **Inline illustration images are often under
  `/Gallery/var/resizes/`** (robots-disallowed for bots). Be respectful: prefer
  the original under `/Gallery/var/albums/…` when derivable, throttle, and treat
  missing images as non-fatal. No `Crawl-delay` is set — **self-impose ≥1s**.

---

## 3. The crawl surface (the library is a tree, not a flat list)

The seed `…index-01.html` is a **hub**, not a book list. Its `bodytext` links to
**category sub-indexes**, which in turn list authors/books (sometimes nested
again). Known top-level category seeds (all returned **200**):

```
https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01.html            (hub)
https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01-a-Bishops.html  (by bishops)
https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01-b-Priests.html  (by priests & monks)
https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01-c-Laymen.html   (by researchers/laymen)
https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-01-d-Churches.html (by churches/orgs)
https://st-takla.org/Full-Free-Coptic-Books/St-Takla.org_Kotob-Keptya-index-02-Church-Books.html (liturgical/official)
https://st-takla.org/Full-Free-Coptic-Books/00-English-Christian-Books/Christian-Coptic-Library-00-index.html (English)
https://st-takla.org/Full-Free-Coptic-Books/His-Holiness-Pope-Shenouda-III-Books-Online/Pope-Shenoda-Books_.html (Pope Shenouda collection)
https://st-takla.org/Full-Free-Coptic-Books/patristics.html                                     (patristic books/sayings)
https://st-takla.org/books/various/index.html                                                   (various authors)
```

There are **two main book-URL families**:
- **Clean/modern:** `/books/<author-slug>/<book-slug>/index.html` (e.g.
  `/books/anba-bishoy/christ/index.html`). This is the reference family.
- **Legacy/nested:** `/Full-Free-Coptic-Books/Books/FreeCopticBooks-NNN-<Author>/<NN-translit>/<English-Name>__00-index.html`
  and `…/His-Holiness-Pope-Shenouda-III-Books-Online/<NN-Name>/<English>__00-index.html`.

**Crawl boundary:** stay on host `st-takla.org`, only follow `bodytext` links whose
path starts with `/books/` or `/Full-Free-Coptic-Books/`. **Exclude** other
sections that appear as cross-links (`/Coptic-History/`, `/FAQ-…/`,
`/Coptic-Faith-Creed-Dogma/`, `/articles/`, `/pub_Bible-Interpretations/`,
`/Holy-Bible_…`) unless the user later asks to include them.

---

## 4. Page classification (decide what each URL is)

Fetch → decode → take `div#bodytext` → classify:

| Type | Signals | Action |
|---|---|---|
| **HUB / CATEGORY index** | `bodytext` links point to **many different directories**; title contains `مكتبة` / “library” / `index-01-x`; links are themselves indexes | enqueue child links (stay in boundary), do **not** treat as a book |
| **BOOK index / TOC** | `bodytext` links mostly to **sibling `.html` in the same directory**; has `og:image` (cover); little prose; page title ≈ book title; filename `index.html` or `…00-index.html` | register a **book**; record its index URL + dir |
| **CONTENT (chapter) page** | has `div#bodytext` **and** `<a id="next">` (or lots of prose `<p>`, few outgoing links) | reached during a book walk, not during discovery |
| **NON-BOOK / out of scope** | path outside `/books/` or `/Full-Free-Coptic-Books/`; or a 404 (title has “404”) | skip |

Heuristic for “same-directory sibling”: compare the directory portion of the
resolved link URL to the current page’s directory. A TOC is dominated by
same-dir links; a hub is dominated by cross-dir links.

---

## 5. Recommended architecture (build this)

Keep the three concerns separate and **state-driven** so it’s resumable.

### `tools/crawl.py` — discovery → `tools/catalog.json`
- BFS from the §3 seeds. Visited-set on normalized URL. Politeness ≥1s, retry
  with backoff on timeout/5xx, treat 404 as skip.
- For each page, classify (§4). Enqueue child links from HUB/CATEGORY pages.
  When a BOOK index is found, append a record:
  ```json
  {
    "book_id": "st-takla.org/anba-raphael/i-willingly-ate",
    "index_url": "https://st-takla.org/books/anba-raphael/i-willingly-ate/index.html",
    "family": "clean",                // or "legacy"
    "author_slug": "anba-raphael",    // derived (see §6)
    "book_slug": "i-willingly-ate",
    "title_guess": "...", "author_guess": "...", "cover_url": "...",
    "dest": "books/st-takla.org/anba-raphael/i-willingly-ate",
    "status": "discovered"            // discovered → extracted → verified → failed
  }
  ```
- **Dedupe**: a book can be linked from several category indexes; key by the
  book directory (the index URL’s parent path).
- Print a summary: # categories, # books per family, # skipped. **Stop and let
  the user review `catalog.json` before extracting.**

### `tools/extract_book.py` — one book → folder + EPUB (refactor of the reference)
Input: a `catalog.json` record (or an index URL). Steps:
1. **Determine reading order** (robustly, in this priority):
   a. From the book index, find the first in-content chapter (first same-dir
      sibling `.html` in `bodytext`, not `index`), then **follow `<a id="next">`**
      until it loops to `index.html`/a visited page. (Authoritative — this is how
      the reference book worked.)
   b. **Fallback** (no `id="next"`): use the ordered list of same-dir sibling
      `.html` links in the index `bodytext` as the chapter list.
   c. **Single-page book**: if the index itself is the content (substantial prose,
      no chapter links), treat the index as the one and only chapter.
   Cross-check a vs b when both exist; log mismatches.
2. **Save raw pages** decoded to UTF-8 with charset rewritten → `pages/NN-slug.html`
   (+ `00-index.html`). Build `manifest.json` (order, slug, file, title, url).
3. **Per-chapter dirs** `chapters/NN-slug/` with raw `<slug>.html` + cleaned
   `content.xhtml`.
4. **Cover**: download `og:image` → `cover.jpg`. **Images**: download `bodytext`
   images except `arrow`/`divider`; resolve relative to page URL; localize `src`;
   missing image = drop it, don’t fail. (Mind the `/Gallery/var/resizes/` robots
   note — throttle, treat failures as non-fatal.)
5. **Clean** `bodytext` per §2 and build the **RTL EPUB** (reuse the reference’s
   EPUB writer: mimetype-first/stored zip, `content.opf` v3 + `toc.ncx`, `nav.xhtml`,
   `cover.xhtml` + `properties="cover-image"` + `<meta name="cover">`, per-chapter
   XHTML, `style.css`). For **English/LTR** books, set `dir="ltr"`, `lang="en"`.
6. **Write `meta.json`** (best effort): title/title_en from `og:title`/`<title>`;
   author/author_slug from the `<h2>` line or the URL/collection (see §6); topics
   `[]` (leave for human curation — see §7); description from the index’s intro
   paragraph; keywords from notable terms. `language` from detected charset/section.
7. Update the record `status` and write back `catalog.json`.
**Idempotent**: wipe & rebuild the book folder on re-run. **Validate** before
marking `verified` (see §8).

### Reuse `tools/make_views.py` unchanged
Run it after a batch to regenerate `README.md`, `by-author.md`, `by-topic.md`,
per-book `README.md`.

---

## 6. Deriving author/book slugs (per family)

- **Clean family** `/books/<author>/<book>/`: `author_slug` and `book_slug` are
  the path segments. Easy and reliable.
- **Legacy family** `FreeCopticBooks-NNN-<Author>/…/<English>__00-index.html`:
  derive `author_slug` from the `<Author>` part of the collection folder
  (slugify; e.g. `His-Grace-Bishop-Makarios` → `bishop-makarios`). `book_slug`
  from the English name segment (strip `__00-index`, slugify). Keep a small
  **hand-maintained mapping table** in `tools/authors_map.json` for messy/ambiguous
  collection names (Pope Shenouda, “Various-Authors”, churches) so authors group
  cleanly. When in doubt, prefer the author’s clean transliteration already used
  elsewhere in the repo.
- Always slugify to `[a-z0-9-]`, ASCII; keep Arabic names in `author`/`title`
  fields, not in paths.

---

## 7. Topics (`by-topic`) — leave for human curation

Topics cannot be reliably auto-derived. Options, in order of preference:
1. Set `topics: []` during bulk extraction and **flag books for the user to tag**
   (produce a `tools/untagged.md` checklist). The user assigns topics in each
   `meta.json`, then re-runs `make_views.py`.
2. Optionally seed obvious topics from the collection/section name or keywords
   (e.g. patristics → `church-fathers`, a book on `الخطية الجدية` → `original-sin`).
Keep a controlled vocabulary in `tools/topics.json` so topic slugs stay consistent.

---

## 8. Robustness & QA (non-negotiable)

- **Politeness:** ≥1s between requests, a descriptive User-Agent, exponential
  backoff on errors, cap concurrency at 1. This is a large crawl (dozens of
  authors, likely 100+ books, thousands of pages) — be a good citizen.
- **Resumable:** everything keyed off `catalog.json` status; re-running skips
  `verified` books. Never lose progress on crash.
- **Per-book validation** (mark `verified` only if all pass):
  - EPUB zip integrity OK; `mimetype` is the **first** entry and **stored**.
  - All XHTML/OPF/NCX **well-formed** (parse with `lxml`).
  - Every manifest/image/spine reference resolves inside the zip.
  - `manifest.json` has ≥1 content chapter; cleaned `bodytext` is non-empty.
  - No leftover chrome strings in chapters (`المكتبة القبطية`, `الصفحة التالية/السابقة`).
- **Logging:** write `tools/extract.log` and per-book status. Summarize failures
  at the end; keep going (don’t abort the batch on one bad book).
- **Sanity caps:** guard against runaway walks (e.g. max 500 pages/book) and
  redirect loops.

---

## 9. Variation / edge cases to expect (the core difficulty)

1. **No `id="next"` chain** → fall back to TOC sibling-link order (§5.1b).
2. **Single-page books** → index is the content (§5.1c).
3. **Multi-level TOC** (parts → chapters, or a collection index → many books):
   recurse; flatten chapters in reading order, or model parts as sections.
4. **Pope Shenouda “Books-Online”** is a **collection of many books**, each with
   its own `…00-index`. Treat each as a separate book under author `pope-shenouda-iii`.
5. **English section** → LTR/`lang=en`; don’t force RTL; titles already English.
6. **Patristic sayings** indexed both “by saint” and “by topic” = duplicate views
   of the same content → dedupe by directory; pick one canonical index.
7. **Missing/disallowed images** (`/Gallery/var/resizes/`) → non-fatal; try
   `/albums/` original; otherwise drop.
8. **404 / moved pages** → skip and log; some index links are stale.
9. **Mixed encodings / stray entities** → detect charset; decode with
   `errors="replace"`; re-balance HTML via `lxml` before serializing XHTML.
10. **Huge books / image-heavy manuscripts** → fine, but watch EPUB size and the
    page cap.

---

## 10. Workflow & deliverables

1. Branch: work on `main` (or a `bulk-extraction` branch if you prefer; ask).
2. Build `crawl.py`, run it, **commit `catalog.json`**, and ask the user to review
   scope (count + a sample list) before extracting.
3. **Pilot**: extract one book per family + one English + one Pope-Shenouda
   sub-book + one single-page book. Validate (§8). Fix the extractor. Commit.
4. **Batch-extract** the rest, committing every ~10–20 books with `make_views.py`
   re-run each batch. Push when the user approves.
5. Final: full `make_views.py`, verify root `README.md` counts, spot-check a few
   EPUBs in a reader, produce `tools/untagged.md` for topic curation.

### Acceptance criteria
- Every in-scope book from the §3 tree is either `verified` in `catalog.json` or
  listed in a failures report with a reason.
- Each verified book matches the repo layout (§1) and passes validation (§8).
- Catalogs (`README.md`, `by-author.md`, `by-topic.md`, per-book) regenerate
  cleanly and links resolve.
- Tools are documented in `tools/README.md`; no scratch (`_epub_build/`) committed.

---

## 11. Open questions to confirm with the user before/while running

- **Scope:** only the Arabic free-books library, or also the English section and
  the borderline sections (Bible interpretations, FAQ, history, articles)?
- **Topics:** auto-seed a few, or leave all empty for manual tagging?
- **Author grouping** for messy collections (Pope Shenouda, “various”, churches) —
  confirm the `authors_map.json` choices.
- **Push cadence:** push per batch or once at the end?

---

## Appendix — quick-start pointers

- Reference book (study its output): `books/st-takla.org/anba-raphael/i-willingly-ate/`
  and its `meta.json` / `manifest.json`.
- Reference extractor to refactor: `tools/sttakla_extract.py` (validated selectors,
  EPUB writer, charset fix). Catalog generator to reuse: `tools/make_views.py`.
- Validated selectors: content `div#bodytext`; next-link `a#next`; cover
  `meta[property=og:image]`; footer nav `table.table-footer`; noise imgs
  `src*=arrow|divider`.
- Deps: `python3`, `beautifulsoup4`, `lxml` (already used). EPUB built with stdlib
  `zipfile` (no external epub lib needed).
