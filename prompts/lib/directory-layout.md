# Canonical directory layout + publish gate (the contract an agent can grep)
Restated from §0.1 / §0.2 of the plan. Repo root: /home/jimmy/projects/coptic-library.
The web app reads everything AT RUNTIME from the filesystem (process.cwd()/../.. = repo root)
via React cache(). All paths are absolute in tooling; no symlinks; one source of truth.

## CANONICAL BOOK STORAGE LAYOUT (no symlinks)
  books/st-takla.org/<author-slug>/<book-slug>/
    meta.json              # per-book metadata (web reads this) — BookMeta
    manifest.json          # ordered chapter list (web reads this) — Chapter[]
    cover.jpg              # served by /api/cover/<author>/<book>
    <book-slug>.epub       # validated EPUB, served by /api/epub/<author>/<book>
    README.md             # GENERATED per-book page (make_views.py) — docs only
    pages/                # raw scraped HTML, one per chapter (00-index.html .. NN-*.html)
    chapters/<NN-slug>/   # per-chapter dir, NN = 1-based CONTENT order (index excluded)
      content.xhtml       # CLEANED XHTML the web renderer consumes  <- KEY OUTPUT
      <slug>.html         # copy of the raw page (provenance/debug)
    images/               # web-servable images: img_<md5(remote_url)[:12]>.<ext>
      _missing.json       # OPTIONAL: referenced images absent from the epub
    .build/               # pipeline scratch (state.json); NOT read by the web app
      state.json          # per-book build state (prompts/lib/schemas/state.schema.json)

## RULES THAT BITE (keep these consistent or the web breaks)
- chapters/<NN-slug>/ number is the 1-BASED CONTENT ORDER (index page excluded), assigned in
  extract_book.py:build_epub via f"{i:02d}-{m['slug']}".
- pages/ keeps 00-index.html; chapters/ does NOT (no content extracted for the TOC page).
- The web maps a manifest entry to its chapter dir by file.replace(/\.html?$/,"")
  (apps/web/src/lib/chapter.ts:orderSlugDirname). So file:"01-foreword.html" => dir
  chapters/01-foreword/. THESE MUST STAY CONSISTENT.
- Author metadata is NOT under books/; it lives in a top-level authors/<slug>/ tree:
    authors/<slug>/info.json      # AuthorInfo — OPTIONAL enrichment; this pipeline owns it
    authors/<slug>/portrait.jpg   # served by /api/portrait/<slug> when kind!="collection"
  No existing tool emits info.json; the pipeline must own it (phase 45 / §6).

## THE PUBLISH GATE (how a book becomes visible)
A book is visible IFF ALL of the following exist AND tools/catalog.json has a matching entry
with status:"verified" (apps/web/src/lib/catalog.ts filters status === "verified"):
1. tools/catalog.json entry: book_id, index_url, family, author_slug, book_slug, title_guess,
   cover_url, dest, section ("arabic"|"english"), chapter_links_guess, status:"verified".
2. books/st-takla.org/<author>/<book>/meta.json (BookMeta).
3. .../manifest.json (ordered Chapter[]; the order:0 slug:"index" entry is filtered out of
   nav, optional).
4. .../chapters/<NN-slug>/content.xhtml per chapter.
5. .../images/* (relative-referenced).
6. .../cover.jpg and .../<book-slug>.epub (download button).
7. Optional: authors/<slug>/info.json + portrait.jpg.
8. Re-run tools/make_views.py for the markdown catalogs (docs only; web ignores them).

## GOTCHAS (load-bearing)
- chapterCount shown in the UI comes from catalog.json.chapter_links_guess, NOT
  manifest.length (catalog.ts). The pipeline MUST set chapter_links_guess = number of
  CONTENT chapters so the UI count is correct.
- status:"verified" is the HUMAN-REVIEW flip. Automation must NEVER write "verified" until
  the §10 human review gate passes; use the intermediate status:"draft", which the web app
  will NOT display.
