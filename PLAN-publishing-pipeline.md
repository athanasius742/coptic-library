# PLAN: LLM-Driven Book Publishing / Digitization Pipeline

**Purpose.** This document specifies a `prompts/` directory plus supporting Python tooling that lets a user tell an LLM coding agent *"read the publishing prompt and digitize this book,"* and have the agent scan a whole book, produce clean per-chapter `content.xhtml` + a valid EPUB, resolve images, resolve cross-references/footnotes/TOC, extract & research the author, dedup/link that author against the existing catalog (creating a new author record if needed), and store everything in the correct place in the repo — **idempotently, resumably, with provenance**. It must work for **Phase 1** (books already present as scraped HTML/EPUB) and, later, **Phase 2** (physical books delivered as PDF requiring extraction, Arabic OCR, and figure extraction).

> **Hand-off doc for a fresh-context implementing agent. Read top to bottom.** Every concrete path, field name, and tool name below is grounded in the real repo (recon brief `00-repo-brief.md`). Do not invent parallel conventions. Prefer reusing the existing `tools/*.py` over writing new code. Where a genuine human decision remains, it is parked in **§13 Open questions** — do not guess.

---

## §0. Context & ground truth (respect these exactly)

Repo root: `/home/jimmy/projects/coptic-library`. Monorepo (pnpm + turbo); one app `apps/web` (Next.js 16 / React 19); Python tooling in `tools/`. ~352 catalogued books (348 verified), 306 Arabic (RTL) / 46 English. ~60 author slugs.

### 0.1 Canonical book storage layout (single source of truth, no symlinks)

```
books/st-takla.org/<author-slug>/<book-slug>/
  meta.json              # per-book metadata (web reads this) — §0.3
  manifest.json          # ordered chapter list (web reads this) — §0.4
  cover.jpg              # served by /api/cover/<author>/<book>
  <book-slug>.epub       # validated EPUB, served by /api/epub/<author>/<book>
  README.md             # GENERATED per-book page (make_views.py) — docs only
  pages/                # raw scraped HTML, one per chapter (00-index.html .. NN-*.html)
  chapters/<NN-slug>/   # per-chapter dir, NN = 1-based CONTENT order (index excluded)
    content.xhtml       # CLEANED XHTML the web renderer consumes  ← KEY OUTPUT
    <slug>.html         # copy of the raw page (provenance/debug)
  images/               # web-servable images: img_<md5(remote_url)[:12]>.<ext>
    _missing.json       # OPTIONAL: referenced images absent from the epub
```

Rules that bite:
- `chapters/<NN-slug>/` number is the **1-based content order** (index page excluded), assigned in `extract_book.py:build_epub` via `f"{i:02d}-{m['slug']}"`.
- `pages/` keeps `00-index.html`; `chapters/` does **not** (no content extracted for the TOC page).
- The web maps a manifest entry to its chapter dir by `file.replace(/\.html?$/,"")` (`apps/web/src/lib/chapter.ts:orderSlugDirname`). So `file:"01-foreword.html"` ⇒ dir `chapters/01-foreword/`. **These must stay consistent.**
- Author metadata is NOT under `books/`; it lives in a top-level `authors/<slug>/` tree (§0.5).

### 0.2 The publish gate (how a book becomes visible)

The web app reads everything **at runtime from the filesystem** (`process.cwd()/../..` = repo root) via React `cache()`. A book is visible **iff** all of the following exist and `tools/catalog.json` has a matching entry with `status:"verified"` (`apps/web/src/lib/catalog.ts` filters `status === "verified"`):

1. `tools/catalog.json` entry: `book_id`, `index_url`, `family`, `author_slug`, `book_slug`, `title_guess`, `cover_url`, `dest`, `section` (`arabic`|`english`), `chapter_links_guess`, `status:"verified"`.
2. `books/st-takla.org/<author>/<book>/meta.json` (`BookMeta`).
3. `.../manifest.json` (ordered `Chapter[]`; the `order:0 slug:"index"` entry is filtered out of nav, optional).
4. `.../chapters/<NN-slug>/content.xhtml` per chapter.
5. `.../images/*` (relative-referenced).
6. `.../cover.jpg` and `.../<book-slug>.epub` (download button).
7. Optional: `authors/<slug>/info.json` + `portrait.jpg`.
8. Re-run `tools/make_views.py` for the markdown catalogs (docs only; web ignores them).

> **Gotcha:** `chapterCount` shown in the UI comes from `catalog.json.chapter_links_guess`, **not** `manifest.length` (`catalog.ts`). The pipeline MUST set `chapter_links_guess` = number of content chapters so the UI count is correct.

> **`status:"verified"` is the human-review flip.** Automation must never write `verified` until the §10 human review gate passes; use an intermediate status (`status:"draft"`) which the web app will not display.

### 0.3 `meta.json` (BookMeta — `apps/web/src/lib/types.ts`)

```json
{
  "slug": "i-willingly-ate",
  "title": "أكلت بإرادتي",
  "title_en": "",
  "author": "الأنبا رافائيل الأسقف العام لكنائس وسط القاهرة",
  "author_en": "",
  "author_slug": "anba-raphael",
  "source": "st-takla.org",
  "source_url": "https://st-takla.org/books/anba-raphael/i-willingly-ate/index.html",
  "topics": [], "series": "", "series_en": "",
  "description": "...", "description_en": "",
  "keywords": [],
  "epub": "i-willingly-ate.epub",
  "cover": "cover.jpg",
  "language": "ar"
}
```
`*_en` fields are optional with Arabic fallback (`bookDisplay`). `language` is `"ar"` or `"en"`. Written by `extract_book.py:write_meta`.

### 0.4 `manifest.json` (ordered `Chapter[]`)

```json
[
  {"order":0,"slug":"index","file":"00-index.html","title":"...","url":"https://st-takla.org/.../index.html"},
  {"order":1,"slug":"foreword","file":"01-foreword.html","title":"تقديم","url":"https://st-takla.org/.../foreword.html"}
]
```
`file` → chapter dir via `.html?$` strip (§0.1). `order:0/slug:"index"` filtered from nav.

### 0.5 Author model (`authors/<slug>/info.json` — `AuthorInfo`)

```json
{
  "slug": "anba-raphael",
  "kind": "person",                 // "person" | "collection" | "alias"
  "name_ar": "الأنبا رافائيل ...",
  "name_en": "H.G. Bishop Raphael",
  "bio_ar": "...", "bio_en": "...",
  "birth_year": 1958, "death_year": null,
  "portrait": "portrait.jpg",
  "portrait_source": "https://st-takla.org/Gallery/...jpg",
  "portrait_status": "ok",          // "ok"|"not_found"|"license_unclear"|"n/a"|null
  "wikipedia_ar": "https://ar.wikipedia.org/...",
  "wikipedia_en": null,
  "aliases_to": null                 // for kind:"alias", points at canonical slug
}
```
The author **list** is derived from books (`loadAuthors` groups `loadAllBooks` by `author_slug`). `info.json` is OPTIONAL enrichment; **no existing tool emits it** — this pipeline must own it (§6). Portrait served by `/api/portrait/<slug>` when `kind!="collection"` and `portrait_status==="ok"`; aliases followed one level.

### 0.6 The `content.xhtml` HTML subset the renderer accepts (HARD contract)

The same `content.xhtml` feeds BOTH the web renderer (`apps/web/src/lib/render-content.tsx`, via `html-react-parser` + `sanitize-html`, **no `dangerouslySetInnerHTML`**) and the EPUB. Emit the strictest-consumer subset (full contract in **Appendix D**):

- Renderer takes only inner `<body>…</body>`. The first top-level `<h1>` is the chapter title and is **stripped** (page chrome owns it). Every other heading is **demoted by one** (`hN→h(N+1)`, capped h6). So author `<h2>` shows as `h3`.
- **Allowed tags:** `p br hr h1 h2 h3 h4 h5 h6 strong b em i u sup sub a span img ul ol li table thead tbody tr td th blockquote`. `b→strong`, `i→em`. `font/center/div` are **unwrapped** (children kept). Everything else is **discarded**.
- **Allowed attributes:** `a:[href,id]`, `img:[src,alt]`, `td/th:[colspan,rowspan]`, `*:[dir,lang]`. All others (class/style/width/align/color/face) **stripped**.
- **Schemes:** `http https mailto`; relative + `#fragment` kept.
- **Images:** `<img>` survives **only** if `src` matches `^(?:\./)?images/<file>$` (`LOCAL_IMG_RE`). Naming: `images/img_<md5(remote_url)[:12]>.<ext>`. Resolved to `/book-images/<author>/<book>/<file>` and served by `apps/web/src/app/book-images/[author]/[book]/[file]/route.ts` (validates `^[A-Za-z0-9._-]+\.(jpe?g|png|gif|webp)$`).
- **Image-wrapper tables** → `ContentFigure`; **TOC tables** (contain "محتويات"/"Contents" + `#` anchors) → `ChapterToc`; data tables → `ContentTable`.
- **Footnotes:** in-body marker `<sup><b><a href="#(1)">(1)</a></b></sup>`; the note block uses `<a href="#1">(1)</a>` under an `<h6><a>الحواشي والمراجع</a></h6>` header + `_____` separator. Renderer pairs them by `anchorKey` (collapses `_ftnN`/`_ftnhrefN`) and re-attaches `id`s.
- **Cross-refs:** in-library st-takla URLs are rewritten to `/<locale>/books/<author>/<book>[/<chapter>]`; external kept; unresolved `#` kept as dead anchor (graceful).
- **RTL/lang:** `dir="rtl"` + `lang="ar"` for Arabic; `dir="ltr"` + `lang="en"` for English, on `<html>` and `<body>`.

### 0.7 Existing tools (reuse; do not rebuild)

Runtime: Python 3, deps `beautifulsoup4` + `lxml`. Image resize shells to ImageMagick `magick`. EPUB validation in-repo uses `lxml.etree`.

- `tools/crawl.py` — discovery → `tools/catalog.json` (`status:"discovered"`).
- `tools/extract_book.py` (the main extractor, 52 KB) — scrape+clean one book → `pages/`, `chapters/<NN-slug>/{content.xhtml,<slug>.html}`, `images/`, `meta.json`, `manifest.json`, `<slug>.epub`. Idempotent (wipes+rebuilds), self-validating (`validate_epub`, line 804). **Contains the only working EPUB builder: `build_epub` (line 624).** Key cleaning logic: `clean_chapter` (510–567) + `page_xhtml` (612). `write_meta` (880).
- `tools/extract_book_images.py` — NO network. Greps `src="images/<name>"` from `chapters/*/content.xhtml`, pulls matching `OEBPS/images/<name>` from the book `.epub`, resizes shrink-only `magick -resize 720x720> -strip -quality 82`, writes `images/_missing.json` for absent refs. Flags: `--all`, `--shard i/n`, `--force`, `--max-px`, `--quality`.
- `tools/make_views.py` — regenerates markdown catalogs from `meta.json`(+`manifest.json`). Docs only.
- `tools/sttakla_extract.py` — legacy/reference extractor.

### 0.8 Environment fact-check (verified on this machine)

| Capability | Present? | Note |
|---|---|---|
| `magick` (ImageMagick) | ✅ `/usr/bin/magick` | image resize convention |
| `ebook-convert` (Calibre) | ✅ `/usr/bin/ebook-convert` | EPUB fallback builder |
| `java` | ✅ | can run `epubcheck.jar` if downloaded |
| `python3`, `node` | ✅ | |
| `beautifulsoup4` + `lxml` | ✅ | |
| `pandoc` | ❌ not installed | **do NOT depend on it** |
| `epubcheck` | ❌ not installed | degrade gracefully; optional install |
| `ebooklib` (Python) | ❌ not installed | **do NOT depend on it** |
| `rapidfuzz` (Python) | ❌ not installed | author dedup needs it (§11) |
| `pymupdf`/`fitz` (Python) | ❌ not installed | Phase 2 only (§11) — deterministic PDF mechanics ONLY |
| Tesseract / OCRmyPDF / Surya / QARI / Docling | n/a | **not used.** A cloud vision-LLM does ALL OCR + structure for scans (§5.3/§5.4); no traditional/ML OCR or layout engine is a pipeline dependency. |

**Decisions forced by this table** (see §9): the canonical EPUB builder is a **refactor of `extract_book.py:build_epub`** (stdlib `zipfile` + `lxml` validation — already proven, already matches the repo's EPUB shape), **not** pandoc and **not** ebooklib. Calibre `ebook-convert` is the documented fallback. epubcheck is best-effort: run `java -jar epubcheck.jar` if a jar is present, else rely on the existing `validate_epub` lxml checks and log that strict validation was skipped.

---

## §1. Goals / non-goals / phases

**Goals.**
- A `prompts/` directory: one short master prompt that delegates to numbered phase prompts + a `lib/` of shared contracts (HTML subset, Arabic/RTL rules, JSON schemas, directory layout).
- Phase 1: turn an already-scraped book (HTML/EPUB) into a fully verified, catalog-wired publication — idempotently.
- Phase 2 (future): turn a PDF physical book into the **same** canonical shape, then rejoin Phase 1 from cross-reference resolution onward.
- Author extraction + research + dedup + idempotent upsert + book→author linking, for both phases.
- Every output is a pure function of canonical sources; re-runs converge; provenance/confidence logged; sacred text never silently altered.

**Non-goals.**
- No re-scraping of st-takla beyond what `extract_book.py` already does (Phase 1 reuses existing artifacts).
- No new web routes or renderer changes — emit to the existing contract (§0.6).
- No bulk re-processing of the 348 verified books (the pipeline targets one book at a time).
- Phase 2 OCR is decided to be a **cloud vision-LLM only** (no traditional/ML OCR or layout engine); only the specific model and budget are deferred to a human (§13).

**Phases.**
- **Phase 1 — HTML/EPUB intake** (§4). Highest value, no new infra. Build first.
- **Phase 2 — PDF intake** (§5). Future. Produces output identical in shape to Phase 1, then rejoins the shared pipeline.

---

## §2. Core architectural principle (state up front, apply everywhere)

> **Deterministic Python parses/converts/IDs/links. The LLM is used ONLY for judgment.** Code owns: body extraction & cleaning, heading demotion, table classification heuristics, stable ID allocation, footnote/xref graph matching, image manifest & integrity, EPUB OPF/nav/ncx/zip, all verification, the `match_key` recipe, dedup scoring, idempotent upserts, atomic writes. The LLM is used only for: structure inference on ambiguous heading soup, OCR cleanup / mojibake repair, missing-metadata guesses, fuzzy prose cross-reference disambiguation, author surface-form extraction, and triage of verification failures.

> **Every LLM edit to sacred text is gated by a round-trip diff that preserves Arabic tashkeel.** Normalize both sides (strip tags, collapse whitespace, **keep diacritics U+064B–U+0652 and shadda/superscript-alef**) and diff. Any delta beyond a near-zero tolerance ⇒ reject the LLM edit, keep the deterministic text, log an issue, STOP for human review. The LLM must never renumber footnotes or reorder content — IDs are frozen by code *before* any LLM step.

> **Idempotency + resumability + provenance are mandatory.** Content-addressed image names; deterministic IDs (a pure function of chapter slug + heading text + ordinal); rebuild registries from source (never append); write-temp-then-`os.replace`; per-phase input-hash gating (`make`-style); a confidence/method/timestamp recorded for every LLM-influenced decision.

---

## §3. The `prompts/` directory design

### 3.1 File tree

```
prompts/
  publish-book.md              # MASTER: role, invariants, output contract, phase order, STOP conditions
  phases/
    00-preflight.md            # detect inputs/tools; init or load .build/state.json; route Phase1 vs Phase2
    05-pdf-intake.md           # PHASE 2 ONLY: PyMuPDF triage/rasterize→vision-LLM OCR+structure+figure-bboxes→content.xhtml
    10-normalize-html.md       # clean/normalize body to the HTML subset; demote headings; classify tables
    15-reattribute-source.md   # rewrite st-takla self-referential asides to neutral 3rd-person external attribution (change-logged)
    20-resolve-references.md   # 2-pass deterministic anchor/footnote/TOC/xref resolution; stable IDs
    30-images.md               # extract_book_images.py + image_manifest + alt-text + integrity
    40-metadata.md             # fill meta.json gaps (LLM, schema-validated)
    45-resolve-author.md       # extract→normalize→research→dedup→upsert authors/<slug>/info.json
    50-build-epub.md           # standalone EPUB builder from canonical content.xhtml + images + meta
    60-verify.md               # deterministic gates: epubcheck/links/images/round-trip/consistency
    90-catalog-wire.md         # write/patch tools/catalog.json (status:"draft"); make_views.py
    99-report-and-gate.md      # REPORT.md; review:"pending"; human flips status:"verified"
  lib/
    html-subset.md             # Appendix D — the renderer-compatible HTML contract
    arabic-rtl.md              # Appendix D — Arabic/RTL gotchas + checklist
    directory-layout.md        # §0.1/§0.2 restated as a contract the agent can grep
    schemas/
      state.schema.json        # .build/state.json (Appendix C)
      image-manifest.schema.json
      author-info.schema.json  # authors/<slug>/info.json incl. pipeline additions
      author-extraction.schema.json
```

### 3.2 How prompts compose

- The **master** prompt (`publish-book.md`, Appendix A) is short: ROLE + non-negotiable invariants + INPUTS/PRECONDITIONS + OUTPUT CONTRACT + an ordered list "execute `phases/NN-*.md` in order; each is resumable via `.build/state.json`; STOP and report on any STOP condition." It also names the always-true rules: absolute paths, atomic writes, rebuild-don't-append, never hand-edit the EPUB's XHTML, never paraphrase/translate/reorder/drop source text, diff-gate every LLM text edit.
- Each **phase** prompt is self-contained and follows the same skeleton: *preconditions → exact command(s) to run (prefer `tools/*.py`) → expected artifact(s) → self-check → on-failure action*. A phase reads `.build/state.json` for what prior phases produced; it never relies on conversation memory.
- `lib/` files are referenced (not inlined) by phase prompts so the contract lives in one place. Phase prompts say e.g. "normalize to `prompts/lib/html-subset.md`" and "validate against `prompts/lib/schemas/state.schema.json`".
- The agent **uses on-disk state**: it writes manifests/registries to `.build/state.json` and re-reads them in the next phase. Structured state never lives only in the chat.

---

## §3a. On-disk pipeline state & idempotency model

A single per-book build-state file, **written by deterministic scripts, read by the agent for decisions.** Location: `books/st-takla.org/<author>/<book>/.build/state.json` (co-located with the book; `.build/` is pipeline scratch, not read by the web app). Full schema in **Appendix C**.

Contents:
- `book_id`, `schema_version`, `phase` ("html"|"pdf"), and per-phase status+input-hash map (`phases`).
- `source_hash` — sha256 over `manifest.json` + every `content.xhtml` (change detection / hash-gating).
- `toc` — derived from `manifest.json`: `[{order, slug, title, id, level}]` with stable `id` `ch-<NN>-<slug>`.
- `heading_map` — heading anchors `<chapter-slug>--sec-<n>` → `{chapter, text}`.
- `anchor_registry` — every `id` target → `{chapter, kind}`.
- `footnote_registry` — `[{id, chapter, marker, ref_anchor, target_anchor, text, resolved}]`.
- `image_manifest` — `[{name, referenced_in[], present, bytes, alt_present}]` (from `extract_book_images.py`).
- `source_reattribution` — the §4.1a result (`{count, rewrites:[{chapter, before, after, reason}], pending_review:[{chapter, context, note}]}`); every rewrite feeds `issues`/`review`.
- `author` — the §6 resolution result (`{slug, confidence, method, needs_review, authority, source_surface}`).
- `issues` — review queue `[{severity, code, detail, chapter?}]`.
- `review` — `"pending"|"approved"` (the §10 gate).

**Idempotency rules (mandatory).**
1. **Hash-gated phases.** Each phase records the hash of its inputs in `phases.<name>.input_hash`. Re-running skips a phase whose inputs are unchanged; a crash resumes at the first `pending`/`stale` phase.
2. **Deterministic IDs.** Anchor/footnote/chapter IDs are pure functions of (chapter slug + text/marker + ordinal) → regenerating yields identical IDs → no duplicates. **Never append to registries; always rebuild from source** so re-runs converge.
3. **Content-addressed images** (already true: `img_<md5(url)[:12]>`).
4. **Atomic writes.** Every generated file: write `*.tmp` then `os.replace`. No half-written `content.opf`/`.epub`.
5. **EPUB is a pure function** of canonical sources; rebuild overwrites atomically.
6. **Author upserts are keyed, never blind appends** (key = Wikidata QID else `match_key`; book-link key = `book_id`); merge-not-clobber; sticky `method:"manual"` (§6).

---

## §4. PHASE 1 pipeline (books already in HTML/EPUB form)

Input: an existing `books/st-takla.org/<author>/<book>/` directory (the common case — 348 verified books already have this shape; this pipeline re-publishes/hardens one, or finishes a `discovered`/`draft` one). Each step lists **owner (code/LLM)**, **inputs → outputs**, and **repo files touched**.

### 4.0 Preflight / triage — `phases/00-preflight.md`
- **Owner: code.** Assert `meta.json`, `manifest.json`, `chapters/*/content.xhtml` (or `pages/*` + `.epub` to (re)build them) exist. Detect tools (§0.8). Determine `phase:"html"`. Init/load `.build/state.json`; compute `source_hash`. If a PDF is the input instead → route to `phases/05-pdf-intake.md` (Phase 2). STOP precisely on missing preconditions; never guess paths.
- **Touched:** `.build/state.json` (create).

### 4.1 Normalize HTML to the allowed subset — `phases/10-normalize-html.md`
- **Owner: code** for the deterministic 95%; **LLM** only for ambiguous heading hierarchy & mojibake repair (each diff-gated, §2).
- **Inputs:** `chapters/*/content.xhtml` (or regenerate from `pages/*` using `extract_book.py:clean_chapter` logic). **Outputs:** rewritten `chapters/*/content.xhtml` conforming to Appendix D.
- Deterministic: extract `<body>`; unwrap `font/center/div`; drop disallowed tags/attrs to the §0.6 allowlist; ensure a single top-level `<h1>` title; leave other headings as authored (renderer demotes); ensure `dir`/`lang` on roots; verify image refs are `images/<file>`.
- LLM (diff-gated): only when heading levels are nonsensical (`h1/h3/h6` soup) or CP1256/mojibake remnants are detected by heuristic. Reject any LLM output failing the round-trip tashkeel diff.
- **Touched:** `books/.../chapters/*/content.xhtml`, `.build/state.json` (`phases.normalize`, `issues`).
- New helper script: `tools/normalize_chapters.py` (§11) factoring out `clean_chapter`'s sanitizing as a standalone pass over existing `content.xhtml`.

### 4.1a Re-attribute source self-references — `phases/15-reattribute-source.md`
- **Owner: code** for deterministic candidate detection; **LLM** only for the minimal in-span rewrite. Runs **after** normalize (4.1, operates on clean text) and **before** resolve-references (4.3, does not affect anchors/IDs).
- **Why.** st-takla.org editors inserted self-referential asides in a first-person voice that reads as if the reader is currently *on* the st-takla site (e.g. "وقد تكلمنا عن هذا الموضوع في موقع الأنبا تكلاهيمانوت", "كما ذكرنا في موقعنا", "اقرأ المزيد على موقعنا", inline "St-Takla.org" mentions framed as "we / our site"). Re-hosted here, those phrases wrongly imply this library **is** st-takla or speaks in its voice. This step rewrites them to refer to st-takla as a **separate, external website** (neutral third-person attribution) without deleting the author's content.
- **The sanctioned exception to verbatim/round-trip (§2).** This is the **one** intentional, surgical text edit allowed. The round-trip tashkeel diff is **replaced here by a change log**: every rewrite records `{chapter, before, after, reason}`, and the diff **MUST touch only the matched self-reference span** — all surrounding text (and its tashkeel) stays **byte-identical**. Any rewrite whose diff bleeds outside the flagged span is rejected and logged.
- **Inputs:** normalized `chapters/<NN-slug>/content.xhtml`. **Outputs:** rewritten `content.xhtml` for matched spans only; `source_reattribution` block in `.build/state.json`.
- **Deterministic detection (code, not LLM):** scan spans for st-takla self-reference markers — e.g. `موقع الأنبا تكلا`, `الأنبا تكلاهيمانوت`, `موقعنا`, `st-takla`, `St-Takla.org` — **combined with** first-person/"our-site" framing (`تكلمنا`, `ذكرنا`, `نشرنا`, `على موقعنا`, `في موقعنا`). Emit a candidate list with surrounding context.
- **LLM minimal rewrite (judgment):** for each candidate, rewrite **only** that span into neutral third-person external attribution (st-takla as a separate website, optionally with "(st-takla.org)"), preserving the author's meaning and the rest of the sentence. Must NOT touch anything outside the flagged span. Example: "وقد تكلمنا عن هذا الموضوع في موقع الأنبا تكلاهيمانوت" → "وقد ورد هذا الموضوع في موقع الأنبا تكلاهيمانوت (st-takla.org)".
- **Conservatism (no guessing).** Distinguish st-takla's **editorial self-promotion** asides from the **author's own** legitimate citations. Rewrite only clear first-person/"our-site" self-references; anything ambiguous (an author already citing st-takla in third person, or unclear voice) is **left as-is** and added to the review queue (`pending_review`) for a human — never guess.
- **Complement to the caption stripper.** The renderer already strips image-caption boilerplate ("St-Takla.org Image:" / "صورة في موقع الأنبا تكلا:"); this step handles **body prose** self-references, which the caption stripper does not.
- Every rewrite is surfaced at the §10 **human review gate** before `catalog.json status` flips to verified — these edits in particular must be human-approved since they alter sacred/authored text.
- **Touched:** `books/.../chapters/*/content.xhtml`, `.build/state.json` (`source_reattribution`, `issues`, `review`).
- New helper script: `tools/reattribute_source.py` (§11) — deterministic candidate scan + applies LLM-provided rewrites with span-bounded replacement + change log (reuses the same span-replacement safety as other text edits).

### 4.2 Resolve images — `phases/30-images.md`
- **Owner: code.** Run existing `tools/extract_book_images.py <book-dir>` (no network) to pull/resize images from the `.epub` into `images/`. Build `image_manifest` in `.build/state.json`; verify every `src="images/X"` in `content.xhtml` resolves to a present file; ensure each `<img>` has non-empty `alt` (preserve scraped bilingual alt).
- **LLM:** only to author `alt` text where genuinely missing (rare; log).
- **Missing images** → record in `image_manifest` + `images/_missing.json` + `issues`; **never silently drop** the `<img>`.
- **Touched:** `books/.../images/*`, `images/_missing.json`, `.build/state.json`.

### 4.3 Resolve cross-references / footnotes / TOC — `phases/20-resolve-references.md`
- **Owner: code** (two-pass, §8); **LLM** only for fuzzy prose "see chapter X".
- **Inputs:** all `content.xhtml`, `manifest.json`. **Outputs:** `content.xhtml` with stable IDs + wired footnote↔backref + resolved `#anchor`/cross-chapter links; `anchor_registry`/`footnote_registry`/`heading_map` in state.
- Dangling targets are **downgraded to text + logged**, never deleted (§8).
- **Touched:** `books/.../chapters/*/content.xhtml`, `.build/state.json`.
- New helper script: `tools/resolve_refs.py` (§11). **Run order note:** images (4.2) and refs (4.3) both rewrite `content.xhtml`; run images first, then refs, then recompute `source_hash`.

### 4.4 Metadata — `phases/40-metadata.md`
- **Owner: code** validates `meta.json` against the schema; **LLM** fills genuine gaps (`title_en`, `author_en`, `description_en`, `topics`, `keywords`, `series`).
- **Touched:** `books/.../meta.json` (merge-not-clobber existing human values), `.build/state.json`.

### 4.5 Author resolution + linking — `phases/45-resolve-author.md`
- See **§6**. Produces/merges `authors/<slug>/info.json`, sets `meta.json.author_slug` + `catalog.json.author_slug`, records `author` block + `needs_review` in state, appends to `tools/author-review-queue.json` when in the review band.
- **Touched:** `authors/<slug>/info.json`, optional `authors/<slug>/portrait.jpg`, `books/.../meta.json`, `tools/catalog.json`, `tools/author-review-queue.json`.

### 4.6 Build / validate EPUB — `phases/50-build-epub.md`
- See **§9**. **Owner: code.** Run the new standalone builder `tools/build_epub.py <book-dir>` which reads canonical `content.xhtml` + `images/` + `meta.json` + `manifest.json` and emits `<book-slug>.epub`, then validates (lxml well-formedness + zip/mimetype + ref resolution; epubcheck if available; Calibre fallback).
- **Touched:** `books/.../<book-slug>.epub`, `.build/state.json`.

### 4.7 Verification — `phases/60-verify.md`
- See **§10**. **Owner: code** for all checks; **LLM** triages failures into fix-vs-flag. All gates must pass.
- **Touched:** `.build/state.json` (`issues`, per-check results).

### 4.8 Catalog wiring — `phases/90-catalog-wire.md`
- **Owner: code.** Upsert the `tools/catalog.json` entry (keyed by `book_id`): set `dest`, `author_slug`, `book_slug`, `section`, `chapter_links_guess` = **content-chapter count** (the UI count source — §0.2), and `status:"draft"` (NOT verified yet). Run `tools/make_views.py`.
- **Touched:** `tools/catalog.json`, root markdown catalogs, `.build/state.json`.

### 4.9 Report + human review gate → flip to verified — `phases/99-report-and-gate.md`
- **Owner: code** writes `books/.../REPORT.md` (counts, issues, sample chapter links); set `review:"pending"`.
- **Human** reviews; on approval the agent (or a tiny `tools/publish.py --approve <book-id>`) flips `catalog.json.status` → `"verified"` and `state.review` → `"approved"`. Until then the book is invisible to the web app.
- **Touched:** `books/.../REPORT.md`, `tools/catalog.json` (status), `.build/state.json`.

---

## §5. PHASE 2 pipeline (physical book as PDF) — FUTURE

Goal: produce output **identical in shape to Phase 1** — `chapters/<NN-slug>/content.xhtml` (Appendix D subset) + `images/img_<hash>.<ext>` + `manifest.json` + `meta.json` + `cover.jpg` — then **rejoin Phase 1 at §4.3 (resolve-references)** so everything downstream (xref, EPUB, author, catalog, verify, gate) is shared and unchanged. Entry prompt: `phases/05-pdf-intake.md`. New tool: `tools/pdf_intake.py` (§11).

### 5.1 Triage (born-digital vs scanned vs fake-text) — code
- PyMuPDF (`fitz`) per **page**: char count, image-area coverage (`get_image_info`), and an **Arabic sanity check** (ratio of U+0600–U+06FF, presentation-form leakage U+FE70–FEFF, word-list hit rate). Thresholds: chars/page < ~50 or single image ≥95% page → scanned; chars present but failing the sanity check → "fake text layer", treat as scanned. Decide per page (books mix digital TOC + scanned body).

### 5.2 Text/structure extraction — code (deterministic) + vision-LLM (structure)
- Born-digital: PyMuPDF `get_text("dict")` blocks→lines→spans+bbox — **deterministic text-layer extraction** (no ML extractor). The existing text is the verbatim source; the vision-LLM infers structure (headings/reading-order/figures↔captions/tables) **from PyMuPDF's positioned text**, it does not re-OCR digital pages.
- Scanned: PyMuPDF renders 300 DPI page images (`page.get_pixmap(dpi=300)`) → vision-LLM OCR + structure (5.3/5.4).

### 5.3 Arabic OCR for scans — **cloud vision-LLM only**
- **Engine class is decided: a cloud multimodal vision-LLM (Claude or Gemini) does ALL OCR.** No traditional/ML OCR engine (Tesseract/OCRmyPDF/Surya/QARI/Docling) is used — not even as a fallback. (An offline/self-hosted OCR path exists in the wild but is explicitly **out of scope** here.) The specific model and budget are deferred to §13.
- **How:** PyMuPDF (5.2) rasterizes each scanned page to an image; deterministic code sends those page images to the vision-LLM with an instruction like: *transcribe the page EXACTLY; preserve all tashkeel/diacritics; do not hallucinate, summarize, translate, or reorder; return plain text in natural RTL reading order; mark any uncertain/illegible spans explicitly.* The LLM returns the verbatim transcription (plus the structure/regions in 5.4).
- **Deterministic guard (no blind trust).** The LLM's transcription is the **"source"** that everything downstream is held to: it is still subject to the §10 round-trip text checks (here the OCR text plays the role the scraped HTML plays in Phase 1), and any LLM edit to it after this point is diff-gated per §2. Recommended consistency safeguard: surface the LLM-flagged low-confidence/uncertain spans (and ideally a second-pass re-read disagreement) as `issues` for **human review** rather than trusting them blindly.
- Keep a two-text model: faithful `display_text` (with tashkeel, goes into `content.xhtml`) + optional normalized `search_text`. Normalization for `search_text` is **deterministic Arabic string folding** (e.g. `pyarabic` — string mechanics, NOT OCR); preserve display variants.

### 5.4 Layout / reading order + chapter segmentation — vision-LLM owns structure
- **The vision-LLM owns structure for scans.** In the same pass as 5.3 (or a structure-only follow-up over the page images) it returns: RTL-correct **reading order**, **region labels** (heading/body/footnote/caption/figure/page-header-footer), and **chapter boundaries**. No Python layout/ML model (Docling/Surya) is used.
- **Running headers/footers/page numbers** are dropped two ways: (1) by LLM instruction (label them `page-header-footer` / page-number and exclude them from body), reinforced by (2) a **deterministic repeated-line dedup** — lines that recur near-verbatim at the top/bottom across many pages are stripped by code.
- Chapter boundaries: the LLM proposes them (aided by Arabic ordinals الفصل الأول/الباب/المقالة); deterministic code prefers a born-digital PDF outline (`doc.get_toc()`) when present as a cross-check. The agreed boundaries + titles → `manifest.json`.

### 5.5 Image/figure extraction + caption linking — code (+ LLM for ambiguous links)
- Born-digital: PyMuPDF `extract_image(xref)` (keeps native format) or `pdfimages -all` — deterministic embedded-raster extraction. Scanned: the **vision-LLM returns figure bounding boxes + captions** (5.4); deterministic **PyMuPDF crops** those bboxes from the 300 DPI render; ImageMagick resizes. No Python layout/ML model does the cropping.
- Filter noise (tiny <~64 px / <0.5% page, near-uniform color, 1-bit rules). De-dup by perceptual/sha256 hash (drop furniture/watermarks recurring across pages).
- Caption: nearest text block below (figures) within a small gap, ideally label `caption`; Arabic captions often start شكل/صورة + number. LLM confirms ambiguous links.
- **Write to the repo convention:** `images/img_<md5(...)[:12]>.<ext>`, 720px q82 web derivative via `magick -resize '720x720>' -strip -quality 82` (§7). Optionally archive a full-res master under `.build/masters/` so EPUB/high-DPI isn't capped at 720px. Emit `image_manifest` entries (Appendix C) with `source_page`, `bbox`, `caption`, `hash`.

### 5.6 LLM structuring into the canonical shape — LLM (anchored, diff-aware)
- Input: cleaned text blocks (roles + reading order) + image manifest. Output: per-chapter `content.xhtml` in the Appendix D subset (`<h1>` title + `<h2>`+ sections, `<p>`, footnotes in the st-takla `<sup><a href="#(n)">`/`<a href="#n">` idiom, `<figure>`-equivalent image-wrapper or plain `<img images/...>`), bidi-correct (`dir="rtl"`, `<span dir="ltr">` for genuine LTR runs). The LLM is anchored to extracted text/boxes and instructed "do not invent text"; output is still subject to the §10 round-trip checks (here the "source" is the vision-LLM OCR / born-digital extracted text).

### 5.7 Metadata from title page — LLM, schema-validated
- PyMuPDF renders first ~3 + last ~2 pages → vision-LLM (same OCR engine as §5.3) → `meta.json` fields. Handle Arabic honorifics (القمص/الأنبا/القديس/الأب — capture separately), dual dating (Gregorian + Coptic/AM "للشهداء"), Eastern Arabic numerals (normalize Gregorian for catalog, keep display), edition (الطبعة الأولى). Cross-check `tools/catalog.json` to avoid duplicates.

### 5.8 Rejoin Phase 1
After 5.1–5.7, the directory is shape-identical to Phase 1. **Continue from §4.3** (resolve-references) → images integrity → metadata polish → **author resolution (§6, shared)** → EPUB → verify → catalog → gate. Nothing downstream knows or cares the source was a PDF.

---

## §6. Author identification, research & resolution (both phases) — `phases/45-resolve-author.md`

Pipeline: **extract → normalize → research → dedup (tiers) → idempotent upsert → link book.** All deterministic except the surface-form extraction and (optional) bio drafting. New tool: `tools/resolve_author.py` (§11).

### 6.1 Extraction (LLM, strict JSON — Appendix C `author-extraction.schema.json`)
Feed only high-signal regions: `catalog.json.title_guess` (already contains author+title+boilerplate), `meta.json.author`, title page / cover alt / colophon (Phase 2). Output **verbatim surface forms**, explicit roles, confidence:

```jsonc
{
  "title_ar": "string|null", "title_en": "string|null",
  "contributors": [{
    "surface_form": "string",          // exactly as printed, NO cleanup
    "role": "author|translator|editor|compiler|attributed",
    "honorific_surface": "string|null","name_core_surface": "string",
    "lang": "ar|en|other","confidence": 0.0 }],
  "is_anonymous": false, "is_collection": false, "attribution_uncertain": false,
  "series": "string|null", "evidence": "1-2 lines: where each field came from"
}
```
Rules: copy surface forms verbatim (normalization is Python's job); separate roles; **st-takla files under the Coptic compiler/translator** — keep that editorial convention when choosing the primary `author_slug`; "منسوب إلى"/attributed → `attribution_uncertain`+`role:"attributed"`, never auto-promote; anonymous/compiled/liturgical → `is_collection:true` → a `kind:"collection"` author (`church-fathers`, `various-authors`, `katamars`…), **never mint a person**; primary contributor confidence < 0.6 → no auto-link/auto-create, queue for review.

### 6.2 `match_key` recipe (deterministic Python; the dedup key, not display)
Run on the Arabic surface (and an EN variant separately). Aggressive-but-safe folding:
```python
import re, unicodedata
AR_HONORIFICS = ["قداسة","البابا","بابا","الانبا","انبا","نيافة","الاسقف","اسقف","المطران","مطران",
  "القمص","قمص","القس","الاب","ابونا","الراهب","القديس","قديس","مار","الشماس","دكتور","د","ا","است","الاستاذ"]
def normalize_ar(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[ً-ْٰـ]", "", s)            # tashkeel + tatweel
    s = re.sub(r"[إأآا]", "ا", s)
    s = s.replace("ة","ه").replace("ى","ي")
    s = re.sub(r"[ؤئء]", "", s)
    s = re.sub(r"\bال", "", s)               # leading definite article
    toks = [t for t in s.split() if t and t not in AR_HONORIFICS]
    return " ".join(toks).strip()
```
English: NFKC → lowercase → strip punctuation → drop EN honorifics (`hh hg st saint pope bishop metropolitan anba abba abouna father fr hegumen qommos mar mr dr prof rev the of`) → apply a small transliteration synonym table (`shenoute→shenouda, kyrillos→cyril, bishoy→pishoy, athanasios→athanasius, boulos/boles→paul, youhanna→john`) → **normalize regnal numerals to a kept comparable token** (`iii/3/الثالث → 3`). Store the AR+EN keys as a set. **Do not strip given/family-name tokens** (over-folding merges distinct people — §7 failure 3).

### 6.3 Research / authority lookups (verify + enrich)
Order, all anonymous HTTP/JSON, **set a descriptive User-Agent**:
1. **Wikidata** (primary, best Arabic): `wbsearchentities?search=<term>&language=ar&format=json&limit=5` → QID + labels/aliases; `Special:EntityData/<QID>.json` → ar/en labels, P569/P570 (birth/death), P39 (office), P18 (Commons portrait), sitelinks. Highest ROI.
2. **VIAF** AutoSuggest `https://viaf.org/viaf/AutoSuggest?query=<name>` + cluster `/<id>/viaf.json` for transliteration variants. **CAVEAT: VIAF returns 403 to default/bot UAs — send a real browser-like User-Agent** or use the OCLC API.
3. **LC** `id.loc.gov/authorities/names/suggest/?q=` (+ `didyoumean`) — Latin headings of saints/Fathers.
4. **Wikipedia REST** (ar+en) summary via the Wikidata **sitelink title** (avoid disambiguation hijack) → bio + thumbnail.
5. **st-takla.org** `/books/<slug>/` author page — authoritative AR spelling, the project's own slug, most existing portraits.
6. Fallback for the long tail (no global authority): thin record (`name_ar`, transliterated `name_en`, slug, `match_key`, rest `null`, `portrait_status:"missing"`) and/or an LLM bio flagged `bio_source:"llm-unverified"`, `reviewed:false`. **A thin record is fine; a wrong confident one is not.**

### 6.4 Dedup decision (confidence-tiered; uses `rapidfuzz`)
Build an in-memory `match_key → slug` index over `authors/*/info.json`. For the new contributor:
- **Tier 0 — authority ID exact:** new QID/VIAF already in some author's `authority` block → **auto-link** (beats all string heuristics).
- **Tier 1 — normalized exact:** new `match_key` ∈ existing set → **auto-link** (this collapses `anba-shenouda` vs `pope-shenouda-iii` → both fold to `شنوده 3`).
- **Tier 2 — fuzzy (RapidFuzz on normalized strings, AR↔AR & EN↔EN, take max):** `token_set_ratio` for dropped-middle-name cases, Jaro-Winkler for short transliterations, `WRatio` fallback.

| Score band | Action |
|---|---|
| `token_set_ratio ≥ 92` **or** Jaro-Winkler ≥ 0.93, **and** birth/death year agrees | **auto-link** |
| `82–92` (or year unknown, names close) | **queue for human review** — no write |
| `< 82` and no authority-ID match | **auto-create** |

Tie-breakers to merge: matching birth/death (±1), QID, office (P39), shared aliases. Blockers: different death years, different regnal numerals (Shenouda III ≠ I), different sees. **Always fuzzy-match on the normalized AR `match_key`, never raw Arabic.** Cross-script pairs (Bishoy/بيشوي) rely on the synonym table + authority-ID, not string distance.

### 6.5 Idempotent upsert + linking (Appendix C `author-info.schema.json`)
```
resolve_author(contributor):
  1. match_key(s) (§6.2)
  2. enrich via §6.3 -> QID, names, years, portrait, bio
  3. tiers (§6.4): Tier0/1/2≥92 -> existing slug auto-link;
                   82..92 -> review-needed (NO write, append review queue);
                   <82 -> create_author(...)
  4. follow aliases_to to terminal slug (links never point at a dup)
  5. link: meta.json.author_slug = slug; catalog.json[book].author_slug = slug
```
- `create_author` writes `authors/<slug>/info.json` **only if absent**; if present, **merge** (fill null fields, union `aliases_ar/aliases_en`) — never clobber human edits.
- A discovered duplicate dir is **not deleted**: set its `aliases_to:"<canonical>"` (the resolver follows one level). Old URLs keep working; dedup is reversible.
- Record a `resolution` provenance block (below). Emit `tools/author-review-queue.json` for every `needs_review` case (surface form, top candidates+scores, proposed action). A human flips `reviewed:true`/picks the slug; **`method:"manual"` is sticky and never overridden by automation.**

`info.json` written by the pipeline (existing fields from §0.5 plus additions):
```jsonc
{
  "slug": "pope-shenouda-iii", "kind": "person",
  "name_ar": "قداسة البابا شنودة الثالث", "name_en": "H.H. Pope Shenouda III",
  "bio_ar": null, "bio_en": null, "bio_source": "wikipedia-ar|llm-unverified|null",
  "birth_year": 1923, "death_year": 2012,
  "portrait": "portrait.jpg", "portrait_source": "https://...", "portrait_status": "ok",
  "portrait_license": "CC-BY-SA|PD|unknown|null",
  "wikipedia_ar": "https://ar.wikipedia.org/...", "wikipedia_en": null,
  "aliases_to": null,
  "match_key": ["شنوده 3","shenouda 3"],          // PIPELINE ADDITION
  "aliases_ar": ["..."], "aliases_en": ["..."],    // PIPELINE ADDITION
  "authority": { "wikidata": "Q87455", "viaf": null, "loc": null },  // ADDITION
  "resolution": {                                   // PIPELINE ADDITION
    "confidence": 0.97, "method": "wikidata-qid",   // qid|matchkey|fuzzy|created|manual
    "matched_slug": "pope-shenouda-iii",
    "source_surface": "قداسة البابا شنودة الثالث",
    "reviewed": false, "needs_review": false, "ts": "2026-05-29T..." }
}
```
**Compatibility:** the additive fields are ignored by the current web `AuthorInfo` reader; if TS strictness complains, mark them optional in `apps/web/src/lib/types.ts` (a one-line widening, listed in §11 / §13).

### 6.6 Portraits / licensing
Priority: Wikidata **P18** → Commons (read `extmetadata` license; store `portrait_license`) → st-takla Gallery (upstream, not openly licensed — keep `portrait_source` as the repo already does) → `portrait_status:"missing"`. Resize portrait to the repo convention; write `authors/<slug>/portrait.jpg`. Wikipedia text is CC-BY-SA (attribute); LLM bios carry `bio_source:"llm-unverified"`+`reviewed:false`.

---

## §7. Images (both phases) — `phases/30-images.md`

- **Phase 1 extraction:** existing `tools/extract_book_images.py <book-dir>` (no network) pulls `OEBPS/images/<name>` from the book `.epub` and resizes into `images/`. **Phase 2 extraction:** `tools/pdf_intake.py` (§5.5) extracts/crops from the PDF.
- **Resize convention (both):** ImageMagick, shrink-only, strip metadata, JPEG q82, max 720 px: `magick INPUT -resize '720x720>' -strip -quality 82 jpg:OUTPUT.jpg`.
- **Naming:** `images/img_<md5(source)[:12]>.<ext>` (content-addressed → idempotent + dedup-friendly). Phase 2 additionally content-hashes crops to drop furniture/watermarks.
- **Image manifest:** in `.build/state.json` (Appendix C) — `name`, `referenced_in[]`, `present`, `bytes`, `alt_present`, and (Phase 2) `source_page`, `bbox`, `caption`, `hash`, `master_path`.
- **Caption association:** Phase 1 captions come from the existing image-wrapper table markup (renderer turns it into `ContentFigure`); Phase 2 links nearest caption block (شكل/صورة + number), LLM confirms ambiguous.
- **Renderer serving:** `<img src="images/<file>">` (relative) → `imageUrl` → `/book-images/<author>/<book>/<file>`, served by `apps/web/src/app/book-images/[author]/[book]/[file]/route.ts` (extension allowlist, traversal-blocked, 1-yr immutable cache). The pipeline must emit only relative `images/<file>` refs (remote/data `<img>` are dropped by the sanitizer).

---

## §8. Cross-reference / footnote / TOC resolution — `phases/20-resolve-references.md`

New tool: `tools/resolve_refs.py`. **Two passes, deterministic; LLM only for fuzzy prose.**

**Pass 1 — collect (can be parallel, read-only).** Parse every `content.xhtml` with lxml/bs4. Record into the registries: targets (headings → section anchors, footnote bodies, TOC entries) and references (`<a href="#...">`, `<sup>` footnote markers in the st-takla pattern `<sup><b><a href="#(1)">(1)</a></b></sup>`, TOC links, and prose "see chapter X" flagged for the LLM).

**Pass 2 — resolve (deterministic match; sequential by `manifest.order` for stable numbering).**
- **Assign stable IDs first** (pure functions, idempotent): chapters `ch-<NN>-<slug>`; headings `<chapter-slug>--sec-<n>`; footnotes `<chapter-slug>--fn-<n>`; back-refs `<chapter-slug>--fnref-<n>`.
- Rewrite each reference `href` to the resolved ID. For footnotes, **match the existing repo markup conventions** (§0.6): in-body marker `<sup><b><a href="#…">(n)</a></b></sup>` and the bottom note block `<a href="#…">(n)</a>` under the `<h6><a>الحواشي والمراجع</a></h6>` header + `_____` separator, so the renderer's `anchorKey` pairing still works. Add reciprocal return links (ref↔note) but keep the surface text/markers exactly as authored.
- **Cross-chapter / inter-book refs** (`../../anba-bishoy/original-sin/index.html`) resolve against `manifest.json`/`catalog.json`; in-library → leave as a resolvable st-takla URL (the renderer rewrites to internal routes) or an internal `#`/file ref; unresolved → flag.
- **Dangling targets:** never crash, never delete visible text. Downgrade `<a href="#x">` with no target to a `<span>` preserving the marker text, and record a `dangling-ref` issue in `state.json` for §10 / the human. Lone TOC/slug anchors stay as graceful dead `#` (renderer already tolerates).
- LLM (judgment only): disambiguate fuzzy prose "see chapter X" to a chapter ID; never invent a target.

**Touched:** `books/.../chapters/*/content.xhtml`, `.build/state.json` (`anchor_registry`, `footnote_registry`, `heading_map`, `issues`). Recompute `source_hash` after.

---

## §9. EPUB building — `phases/50-build-epub.md`

**Recommendation: factor `extract_book.py:build_epub` (line 624) into a standalone `tools/build_epub.py` that regenerates the EPUB from the canonical `content.xhtml` + `images/` + `meta.json` + `manifest.json`** — so the web reader and the EPUB never drift.

**Why reuse, not pandoc/ebooklib:**
- `pandoc`, `ebooklib`, `epubcheck` are **not installed** (§0.8); `build_epub` already works, is pure stdlib (`zipfile`, `hashlib`, `datetime`) + `lxml` validation, and **already emits exactly the repo's EPUB shape** (`mimetype` first/stored, `META-INF/container.xml`, `OEBPS/content.opf` with `page-progression-direction`, `nav.xhtml`, `toc.ncx`, `chapNN.xhtml`, `cover.xhtml`, `title.xhtml`, `style.css`, RTL CSS const at line 601 + LTR variant). Adding pandoc/ebooklib means a new dependency for zero gain and a divergent output shape. **Tradeoff:** pandoc gives free auto-IDs/footnote back-links, but we resolve those ourselves in §8 (and must, since the web renderer consumes the same IDs) — so the builder's auto-magic is unwanted. Standardize on the refactored in-repo builder.

**The refactor (the one real code change to existing logic):** today `build_epub` re-reads `pages/*`, re-runs `clean_chapter` (which calls `download_image` → **network**) and writes both `content.xhtml` and `chapNN.xhtml` from the same fragment in one pass. **Decouple it:** `build_epub.py` must read the *existing canonical* `chapters/<NN-slug>/content.xhtml` (extract inner `<body>` + title), wrap each in the minimal XHTML envelope (reusing `page_xhtml`/`CSS`/`CSS_LTR`), copy referenced `images/*` into `OEBPS/images/`, and assemble OPF/nav/ncx/zip from `manifest.json`+`meta.json` — **no network, no LLM, atomic write**. This makes the EPUB a pure function of the canonical sources. Keep the original `build_epub` inside `extract_book.py` for the scrape path, or have `extract_book.py` call the new module after it writes `content.xhtml` (preferred: single source of truth).

**RTL:** keep `dir="rtl"`+`lang="ar"` on each XHTML root, `<spine page-progression-direction="rtl">`, generous `line-height` (~1.9, already in CSS) and a tashkeel-capable font stack (Amiri/Scheherazade/Noto Naskh — already in CSS). **Verify in a real reader** (Readium RTL blank-page bug exists), not just a validator.

**Validation (degrade gracefully):**
1. Always: the existing `validate_epub` checks (zip integrity, `mimetype` stored-first, all XHTML/OPF/NCX well-formed via lxml, manifest/spine/image refs resolve, ≥1 chapter, no leftover nav chrome).
2. If an `epubcheck.jar` is present (`java -jar epubcheck.jar <epub>`): treat FATAL/ERROR as build failure (STOP), WARNINGs → `REPORT.md`. If absent, log "epubcheck skipped" and rely on (1) + the §10 round-trip diff. (Installing epubcheck → §13.)
3. **Fallback builder:** if the in-repo builder ever fails, `ebook-convert <html> <epub> --epub-version 3 --language ar --cover cover.jpg ...` (Calibre, installed) can produce a degraded EPUB; flag it as fallback-built.

---

## §10. Verification & quality gates — `phases/60-verify.md`

Deterministic scripts (`tools/verify_book.py`); the LLM only triages failures into fix-vs-flag. **All must pass before the human gate.**

1. **Schema/manifest validation** — `meta.json`, `manifest.json`, `.build/state.json` validate against the Appendix C schemas. Spine order == `manifest.order` == files on disk. **chapterCount consistency:** `catalog.json.chapter_links_guess` == number of content chapters == `len(chapters/)` == non-index manifest length (the §0.2 gotcha).
2. **Image-reference integrity** — every `src="images/X"` resolves to an existing file (reuse `extract_book_images.py` referenced-vs-present logic); every `<img>` has non-empty `alt`. Missing → `state.json` issue + human flag, never silent drop.
3. **Link integrity (no dangling anchors)** — for every `href="#id"` (and cross-file `chapNN.xhtml#id` inside the EPUB), the target `id` exists. Zero dangling = pass; list offenders; danglers were already downgraded to text in §8.
4. **Round-trip text diff (tashkeel-preserving)** — normalize source `content.xhtml` and the built EPUB chapter (strip tags, collapse whitespace, **keep diacritics**), diff. Near-zero tolerance for text content; any large delta ⇒ normalize/cleanup dropped content ⇒ STOP. Primary guard against LLM content loss.
5. **EPUB validation** — §9 (lxml checks always; epubcheck 0 ERROR/FATAL if available).
6. **Manifest/catalog consistency** — `catalog.json` entry exists, `dest`/`author_slug`/`book_slug`/`section` correct, `status` still `"draft"` (not yet verified).
7. **Author resolution sanity** — `meta.json.author_slug` == `catalog.json.author_slug`, the `authors/<slug>/info.json` exists or `needs_review` is logged.
8. **Source re-attribution coverage (§4.1a)** — no un-reviewed self-reference candidates remain: every deterministically detected candidate was either rewritten + change-logged in `source_reattribution.rewrites` (with a span-bounded diff) **or** explicitly left with a `pending_review` note. Re-scanning finds no first-person/"our-site" st-takla marker that is neither logged nor queued.

**Arabic/RTL checklist** (`prompts/lib/arabic-rtl.md`, Appendix D): tashkeel preserved (diff #4); no mojibake/CP1256 remnants; bidi handled (`dir` roots, `<span dir="ltr">` for LTR runs — never manual reorder); `page-progression-direction="rtl"`; verified in a real reader; English books `dir="ltr"`/`lang="en"`.

**Human review gate (mandatory).** After all automated checks pass, set `state.review:"pending"` and write `REPORT.md`. A human approves before `catalog.json.status` flips to `"verified"`. **Every §4.1a source re-attribution rewrite (`{chapter, before, after}`) is listed in `REPORT.md` and MUST be human-approved** before verified, since it alters authored text; any `pending_review` self-reference is resolved by the human (rewrite or keep) at this gate. STOP conditions that halt + surface immediately: missing precondition; epubcheck ERROR/FATAL; round-trip diff over tolerance; unfixable mojibake; > K dangling refs; missing cover with no fallback; author primary confidence < 0.6.

---

## §11. New tools/scripts (under `tools/`) + what to reuse

| Tool | Purpose | CLI | In → Out | Reuse / notes |
|---|---|---|---|---|
| `tools/normalize_chapters.py` | NEW. Standalone normalize of existing `content.xhtml` to the §0.6 subset | `normalize_chapters.py <book-dir> [--force]` | `chapters/*/content.xhtml` → rewritten | factor `extract_book.py:clean_chapter` sanitizing (no network) |
| `tools/reattribute_source.py` | NEW. Deterministic st-takla self-reference candidate scan + applies LLM minimal rewrites with span-bounded replacement + change log (§4.1a) | `reattribute_source.py <book-dir>` | `content.xhtml` → rewritten matched spans + `source_reattribution` in state | reuses the same span-replacement safety as other text edits; conservative (ambiguous → review queue) |
| `tools/resolve_refs.py` | NEW. Two-pass xref/footnote/TOC resolver + stable IDs (§8) | `resolve_refs.py <book-dir>` | `content.xhtml`+`manifest.json` → rewritten + registries in state | bs4/lxml; mirror st-takla footnote markup |
| `tools/build_epub.py` | NEW. Standalone EPUB from canonical sources (§9) | `build_epub.py <book-dir>` | `content.xhtml`+`images`+`meta`+`manifest` → `<slug>.epub` | **factor `extract_book.py:build_epub`/`page_xhtml`/`CSS`/`validate_epub`** |
| `tools/resolve_author.py` | NEW. Extract→normalize→research→dedup→upsert (§6) | `resolve_author.py <book-dir> [--no-network]` | book → `authors/<slug>/info.json`, `meta`/`catalog` `author_slug`, review queue | needs `rapidfuzz`; uses Wikidata/VIAF(UA!)/LC/Wikipedia/st-takla |
| `tools/verify_book.py` | NEW. All §10 deterministic gates | `verify_book.py <book-dir>` | book → pass/fail + `issues` in state | reuse `extract_book_images.py` ref-integrity + `validate_epub` |
| `tools/catalog_upsert.py` | NEW. Idempotent `catalog.json` entry upsert (keyed by `book_id`) | `catalog_upsert.py <book-dir> --status draft\|verified` | book → patched `tools/catalog.json` | keep flat-list shape; set `chapter_links_guess` |
| `tools/publish.py` | NEW. State machine driver / approval flip | `publish.py <book-dir> [--approve]` | runs phases; `--approve` flips `status:"verified"` | optional thin orchestrator |
| `tools/pdf_intake.py` | NEW, **Phase 2 only**. PDF → canonical shape (§5) | `pdf_intake.py <book.pdf> --out <book-dir>` | PDF → `chapters/*/content.xhtml`+`images`+`manifest`+`meta` | needs `pymupdf` (deterministic mechanics ONLY: triage/text-layer/rasterize/embedded-image/crop) + a cloud vision-LLM (OCR + structure + figure bboxes) via API key. NO Tesseract/Surya/QARI/Docling/OCRmyPDF. |
| `tools/state.py` | NEW. Shared helpers: atomic write, hashing, state read/write | (library) | — | used by all the above |
| **reuse** `extract_book_images.py` | image extract/resize + ref integrity | (existing) | — | unchanged |
| **reuse** `make_views.py` | regenerate markdown catalogs | (existing) | — | unchanged |
| **reuse** `extract_book.py` | scrape path; source of `clean_chapter`/`build_epub`/`validate_epub`/`page_xhtml` | (existing) | — | factor shared bits into modules |

**Dependencies to install (document in `tools/README.md`):**
- Phase 1: `pip install rapidfuzz` (author dedup). Optional: download `epubcheck.jar` (run via the already-present `java`).
- Phase 2: `pip install pymupdf pyarabic` (PyMuPDF for deterministic PDF mechanics; `pyarabic` for deterministic Arabic string folding of `search_text`, NOT OCR) + a cloud vision-LLM (Claude or Gemini) via API key for ALL OCR + structure. **No traditional/ML OCR or layout engine** (Tesseract/OCRmyPDF/Surya/QARI/Docling/camel-tools).
- **Already present, rely on:** `magick` (ImageMagick), `ebook-convert` (Calibre), `java`, `beautifulsoup4`, `lxml`. **Absent, do NOT depend on:** `pandoc`, `ebooklib`.

---

## §12. Implementation checklist / milestones (ordered, each independently verifiable)

Build **Phase 1 first** (high value, no new infra); defer Phase 2.

**M0 — Scaffolding.**
- [ ] Create `prompts/` tree (§3.1) with Appendices A/B/C/D as the file contents.
- [ ] `tools/state.py` (atomic write, sha256, state read/write). Verify: unit round-trip.

**M1 — Normalize + verify on an existing book (no risk).**
- [ ] `tools/normalize_chapters.py`. Verify: run on `books/st-takla.org/anba-raphael/i-willingly-ate`; output still passes the renderer subset; round-trip tashkeel diff ≈ 0.
- [ ] `tools/reattribute_source.py` (§4.1a). Verify: deterministic scan flags first-person st-takla asides; an LLM rewrite changes ONLY the matched span (byte-identical outside it, tashkeel intact) and is change-logged in `source_reattribution`; an ambiguous third-person author citation is left as-is and queued for review; re-run is a no-op.
- [ ] `tools/resolve_refs.py`. Verify: footnotes still pair in the renderer; zero new danglers; IDs stable across two runs.

**M2 — Standalone EPUB builder (the key refactor).**
- [ ] `tools/build_epub.py` reading canonical `content.xhtml` (no network). Verify: rebuilt EPUB passes existing `validate_epub`; diff vs the committed `.epub` is structural-only; round-trip text diff ≈ 0.

**M3 — Verification gate.**
- [ ] `tools/verify_book.py` (all §10 checks). Verify: green on a known-good verified book; correctly red on an injected dangling ref / missing image.

**M4 — Author resolution.**
- [ ] `pip install rapidfuzz`; `tools/resolve_author.py`. Verify: re-running on `anba-raphael` is a no-op (idempotent), merges-not-clobbers; a synthetic `anba-shenouda` surface dedups to `pope-shenouda-iii` (match_key collision); a sub-0.6 case lands in `tools/author-review-queue.json`.
- [ ] If needed, widen `AuthorInfo` in `apps/web/src/lib/types.ts` to accept the additive fields (§6.5).

**M5 — Catalog wiring + gate.**
- [ ] `tools/catalog_upsert.py` (status:"draft"); `tools/publish.py --approve` (→ verified). Verify: a draft book stays invisible to the web app; after `--approve` it appears; `chapter_links_guess` matches content-chapter count.
- [ ] Run `make_views.py`; confirm markdown catalogs regenerate.

**M6 — End-to-end Phase 1.**
- [ ] `prompts/publish-book.md` drives 00→99 on one book unattended to the human gate. Verify: idempotent re-run changes nothing; `REPORT.md` lists counts/issues/samples.

**M7+ — Phase 2 (future, after §13 decisions).**
- [ ] `pip install pymupdf pyarabic`; `tools/pdf_intake.py` triage + born-digital path (PyMuPDF deterministic text-layer extraction) → canonical shape on a born-digital sample.
- [ ] Wire scanned-Arabic intake via the **cloud vision-LLM** (chosen model, §13): PyMuPDF rasterizes pages → vision-LLM does OCR + reading order/region labels + chapter boundaries + figure bboxes; PyMuPDF crops figures; rejoin Phase 1 at §4.3. No traditional/ML OCR or layout engine.

---

## §13. Open questions for the user (need a human decision)

1. **EPUB validation strictness:** install `epubcheck.jar` (run via existing `java`) for strict EPUB 3.3 validation, or accept the in-repo `lxml` checks + round-trip diff? (Recommendation: download the jar; no new runtime dep.)
2. **Author auto-create policy:** auto-create authors below the 82 fuzzy band, or always gate new persons for human review? (Recommendation: auto-create persons but mark `needs_review` until first human pass; always gate `collection` assignment.)
3. **Where research artifacts live:** `tools/author-review-queue.json` location/format; whether `.build/` is committed or gitignored; where Phase 2 full-res masters live (`.build/masters/`?).
4. **Phase 2 OCR model + budget:** the **engine class is settled** — a cloud multimodal vision-LLM does all OCR + structure (no traditional/ML OCR or layout engine). Remaining decision: **which model (Claude vs Gemini)** and **what budget/spend cap** for Phase 2 OCR (needs API key + spend approval). (Self-hosted/air-gapped OCR is out of scope.)
5. **Phase 2 dependencies:** OK to add `pymupdf` (deterministic PDF mechanics) and `pyarabic` (deterministic Arabic string folding for `search_text`)? No ML OCR/layout deps are requested.
6. **`AuthorInfo` widening:** approve adding optional `match_key`/`aliases_ar`/`aliases_en`/`authority`/`resolution`/`bio_source`/`portrait_license` to `apps/web/src/lib/types.ts`.
7. **Editorial primary-author rule:** confirm st-takla's "file under the Coptic compiler/translator" convention is the desired primary `author_slug` policy (vs. filing patristic works under the ancient Father).
8. **Status vocabulary:** is `status:"draft"` an acceptable new value in `catalog.json` for not-yet-verified books (web filters to `verified`), or prefer a different non-visible sentinel?
9. **Source re-attribution policy (§4.1a):** for purely *navigational* st-takla cross-promo asides ("اقرأ المزيد على موقعنا" with no authored content), do we **rewrite** them to neutral external attribution (default) or **remove** them entirely? (Recommendation: rewrite by default; only remove on explicit human approval at the §10 gate, since removal deletes authored-looking text.)

---

# APPENDIX A — `prompts/publish-book.md` (master prompt, ready to drop in)

```markdown
# ROLE
You are an autonomous publishing agent for a Coptic Orthodox digital library
(repo root /home/jimmy/projects/coptic-library). You digitize ONE book into clean
per-chapter content.xhtml + a valid EPUB3, resolve images and cross-references,
research and link the author, and wire the catalog — idempotently.

The text is SACRED. NON-NEGOTIABLE: never paraphrase, summarize, translate, reorder,
or drop source text. Preserve Arabic diacritics (tashkeel) EXACTLY. Convert
DETERMINISTICALLY with the tools/*.py scripts; use the LLM ONLY for judgment
(structure inference, OCR/mojibake cleanup, missing-metadata guesses, fuzzy reference
disambiguation, author surface extraction, failure triage). Gate EVERY LLM edit to
chapter text with a round-trip text diff that preserves tashkeel — on any delta beyond
near-zero, discard the LLM edit, keep the deterministic text, log an issue, and STOP.

# INPUTS / PRECONDITIONS
- BOOK_DIR (arg), absolute, under books/st-takla.org/<author-slug>/<book-slug>/.
  Phase 1 must contain: meta.json, manifest.json, chapters/<NN-slug>/content.xhtml
  (or pages/*.html + <slug>.epub to (re)build them), cover.jpg (or flag), images/.
  Phase 2: a PDF -> route to phases/05-pdf-intake.md first.
- Detect tools: magick, ebook-convert, java, python3, beautifulsoup4, lxml (present);
  rapidfuzz (install for author step); pandoc/ebooklib are ABSENT — never use them.
- If a precondition fails -> STOP with a precise message. Never guess paths.

# OUTPUT CONTRACT (write to disk, then re-read; validate vs prompts/lib/schemas/*)
- BOOK_DIR/.build/state.json     (Appendix C; written by scripts, read for decisions)
- BOOK_DIR/chapters/*/content.xhtml  (normalized to prompts/lib/html-subset.md)
- BOOK_DIR/meta.json, manifest.json  (validated/updated, merge-not-clobber)
- BOOK_DIR/images/*  (relative-referenced, 720px q82, content-addressed names)
- BOOK_DIR/<book-slug>.epub  (valid EPUB3, RTL, cover, nav, images embedded)
- authors/<slug>/info.json (+ portrait.jpg)  (idempotent upsert; aliases_to for dups)
- tools/catalog.json entry  (status:"draft" until the human gate; then "verified")
- BOOK_DIR/REPORT.md  (counts, issues, sample chapter links; review gate)

# PROCEDURE  (run phases in order; each is resumable via .build/state.json hash-gating)
1. phases/00-preflight.md      (-> Phase 2? run phases/05-pdf-intake.md, then continue at 15)
2. phases/10-normalize-html.md  3. phases/15-reattribute-source.md  4. phases/30-images.md
5. phases/20-resolve-references.md  6. phases/40-metadata.md  7. phases/45-resolve-author.md
8. phases/50-build-epub.md      9. phases/60-verify.md
10. phases/90-catalog-wire.md   11. phases/99-report-and-gate.md
Prefer running existing tools/*.py. Write new code only for a missing capability.

# TOOL-USE RULES
- All paths absolute. Atomic writes (tmp -> os.replace). Rebuild registries from source
  (never append). Image names stay content-addressed. NEVER hand-edit the EPUB's XHTML —
  regenerate via tools/build_epub.py from canonical content.xhtml. IDs are frozen by code
  before any LLM step. Author upserts are keyed (QID/match_key) and merge-not-clobber;
  method:"manual" is sticky.

# SELF-VERIFICATION CHECKLIST (phase 60 — all must pass before the human gate)
[ ] image integrity: every referenced image exists; every <img> has alt
[ ] link integrity: 0 dangling #anchors / cross-file refs (danglers downgraded to text)
[ ] round-trip text diff (WITH tashkeel) within tolerance for every chapter
[ ] EPUB: lxml well-formed + zip/mimetype + refs resolve; epubcheck 0 ERROR/FATAL if available
[ ] spine order == manifest order == files on disk; chapter_links_guess == content-chapter count
[ ] meta/manifest/state validate against prompts/lib/schemas/*
[ ] author: meta.author_slug == catalog.author_slug; info.json exists or needs_review logged
[ ] Arabic/RTL checklist (prompts/lib/arabic-rtl.md) passed

# IDEMPOTENCY / RESUMABILITY
- Hash inputs per phase; skip unchanged phases; resume at first pending/stale phase.
- Deterministic IDs -> re-runs reproduce identical output. Re-running converges.

# STOP CONDITIONS (halt, write REPORT.md, set review:"pending", surface to a human)
- Missing precondition; epubcheck ERROR/FATAL; round-trip diff over tolerance;
  unfixable mojibake; > K dangling refs; missing cover with no fallback;
  author primary confidence < 0.6. NEVER set catalog status:"verified" automatically.
```

---

# APPENDIX B — phase sub-prompts (ready to drop in)

### `prompts/phases/05-pdf-intake.md`
```markdown
# PHASE 05 — PDF intake (Phase 2 ONLY) -> canonical shape, then rejoin at phase 20
PRECONDITIONS: input is a PDF (routed here by phase 00); --out <BOOK_DIR> chosen.
GOAL: emit Phase-1-shaped chapters/<NN-slug>/content.xhtml + images/img_<hash>.<ext> +
  manifest.json + meta.json + cover.jpg, then CONTINUE at phase 20 (resolve-references).
ENGINE RULE (non-negotiable): a CLOUD VISION-LLM (Claude or Gemini) does ALL OCR AND
  ALL STRUCTURE for scans. PyMuPDF does DETERMINISTIC MECHANICS ONLY. There is NO
  Tesseract / OCRmyPDF / Surya / QARI / Docling anywhere in this phase.
RUN (deterministic plumbing, no network): python3 tools/pdf_intake.py <book.pdf> --out <BOOK_DIR>
  PyMuPDF (fitz) does ONLY:
    (a) TRIAGE per page: char count, image-area coverage, Arabic sanity check ->
        born-digital vs scanned vs fake-text-layer (§5.1);
    (b) BORN-DIGITAL: extract the existing text layer (get_text("dict"), positioned
        blocks/lines/spans+bbox) — verbatim source; no re-OCR;
    (c) SCANNED: rasterize pages to images (get_pixmap(dpi=300)) to feed the vision-LLM;
    (d) extract EMBEDDED raster images (extract_image(xref) / pdfimages -all);
    (e) CROP figure regions at the LLM-provided bounding boxes; ImageMagick resizes
        ('720x720>' -strip -quality 82) to images/img_<md5(...)[:12]>.<ext> (§7).
VISION-LLM (OCR + structure + judgment):
  - SCANNED OCR: send the rasterized page images; instruct: transcribe EXACTLY, preserve
    ALL tashkeel/diacritics, do NOT hallucinate/summarize/translate/reorder, return plain
    text in natural RTL reading order, MARK uncertain/illegible spans.
  - STRUCTURE: return RTL-correct reading order, region labels (heading/body/footnote/
    caption/figure/page-header-footer), chapter boundaries, and figure BOUNDING BOXES +
    captions. Running headers/footers/page numbers: labelled & excluded by the LLM, PLUS a
    deterministic repeated-line dedup strips recurring top/bottom lines.
  - BORN-DIGITAL: infer structure FROM PyMuPDF's positioned text (do NOT re-OCR digital pages).
  - STRUCTURE INTO content.xhtml: per-chapter Appendix D subset (<h1> title + <h2>+ sections,
    <p>, st-takla footnote idiom, image-wrapper/<img images/...>), dir="rtl" + <span dir="ltr">
    for genuine LTR runs; "do not invent text".
GUARD (no blind trust): the vision-LLM OCR text is the "source" for all §10 round-trip checks
  (it plays the role scraped HTML plays in Phase 1); any later LLM edit to it is diff-gated
  (§2). Surface LLM-flagged low-confidence/uncertain spans as state.issues for human review.
METADATA: rasterize first ~3 + last ~2 pages -> vision-LLM -> meta.json (honorifics, dual
  dating, Eastern-Arabic numerals, edition); cross-check catalog.json for duplicates (§5.7).
SELF-CHECK: directory is shape-identical to Phase 1; manifest.order == files on disk;
  every <img> ref is images/<file>; re-run is a no-op (content-addressed images, hash-gated).
ON FAILURE / STOP: illegible scan, no extractable text, or OCR consistency failure ->
  log state.issues and STOP for human review.
OUTPUT: chapters/*/content.xhtml + images/* + manifest.json + meta.json + cover.jpg;
  state.phase="pdf", phases.pdf_intake=done. NEXT: continue at phase 20 (§5.8).
```

### `prompts/phases/10-normalize-html.md`
```markdown
# PHASE 10 — Normalize chapter HTML to the renderer subset
PRECONDITIONS: .build/state.json exists (phase "html"); chapters/*/content.xhtml present.
GOAL: every content.xhtml conforms to prompts/lib/html-subset.md (Appendix D).
RUN (deterministic, no network):
  python3 tools/normalize_chapters.py <BOOK_DIR>
  - extract inner <body>; unwrap font/center/div; drop tags/attrs to the allowlist;
    ensure ONE top-level <h1> title; keep dir/lang on roots; ensure images are images/<file>.
LLM (ONLY if needed, each diff-gated):
  - ambiguous heading hierarchy (h1/h3/h6 soup) -> propose sane h2.. levels;
  - mojibake/CP1256 remnants -> repair. After any LLM edit, run the round-trip tashkeel
    diff; if delta > tolerance, DISCARD the edit, keep deterministic text, log issue, STOP.
SELF-CHECK: re-run is a no-op; sanitize-subset validator passes; diff ≈ 0.
ON FAILURE: log to state.issues and STOP.
OUTPUT: rewritten chapters/*/content.xhtml; state.phases.normalize=done (+input_hash).
```

### `prompts/phases/15-reattribute-source.md`
```markdown
# PHASE 15 — Re-attribute st-takla self-references (external, 3rd-person)
ROLE: rewrite ONLY st-takla editorial self-promotion asides (first-person "we / our site"
  voice that implies the reader is on st-takla) into NEUTRAL THIRD-PERSON attribution to
  st-takla as a SEPARATE, EXTERNAL website. This is THE sanctioned exception to the
  verbatim/round-trip rule (§2): a surgical, span-bounded edit, change-logged.
PRECONDITIONS: normalized content.xhtml (phase 10 done); runs BEFORE phase 20 (no anchors yet).
INPUTS: chapters/<NN-slug>/content.xhtml.  OUTPUTS: rewritten matched spans only;
  state.source_reattribution{count, rewrites[], pending_review[]}.
PROCEDURE:
  1. DETERMINISTIC SCAN (code, tools/reattribute_source.py): flag spans containing st-takla
     markers — موقع الأنبا تكلا / الأنبا تكلاهيمانوت / موقعنا / st-takla / St-Takla.org —
     COMBINED WITH first-person/"our-site" framing — تكلمنا / ذكرنا / نشرنا / على موقعنا /
     في موقعنا. Emit a candidate list with surrounding context.
  2. LLM MINIMAL REWRITE (judgment): for each candidate, rewrite ONLY the flagged span into
     neutral 3rd-person external attribution (st-takla as another site, optionally add
     "(st-takla.org)"), preserving the author's meaning and the rest of the sentence.
     Do NOT touch anything outside the span.
  3. CHANGE LOG (replaces the round-trip diff here): record {chapter, before, after, reason}
     for each rewrite. The applied diff MUST touch ONLY the matched span — all surrounding
     text and its tashkeel stay BYTE-IDENTICAL. Any rewrite bleeding outside the span ->
     reject, log issue, keep original.
  4. CONSERVATISM: only clear first-person/"our-site" self-references are rewritten.
     Ambiguous cases (author already citing st-takla in 3rd person, or unclear voice) are
     LEFT AS-IS and appended to pending_review[] for a human. NEVER guess.
NOTE (complement): the renderer already strips image-caption boilerplate
  ("St-Takla.org Image:" / "صورة في موقع الأنبا تكلا:"); THIS phase handles BODY PROSE only.
EXAMPLE:
  before: وقد تكلمنا عن هذا الموضوع في موقع الأنبا تكلاهيمانوت
  after:  وقد ورد هذا الموضوع في موقع الأنبا تكلاهيمانوت (st-takla.org)
SELF-CHECK: re-scan finds no first-person st-takla marker that is neither rewritten+logged
  nor in pending_review; every diff is span-bounded; re-run is a no-op.
STOP CONDITIONS: a rewrite's diff escapes the matched span; LLM alters tashkeel/text outside
  the span -> discard edit, log issue, STOP. (All rewrites are human-approved at phase 99.)
OUTPUT: rewritten chapters/*/content.xhtml; state.source_reattribution; state.issues/review.
```

### `prompts/phases/20-resolve-references.md`
```markdown
# PHASE 20 — Resolve cross-references, footnotes, TOC (stable IDs)
PRECONDITIONS: normalized content.xhtml; images already resolved (phase 30 ran).
RUN (deterministic, two-pass):
  python3 tools/resolve_refs.py <BOOK_DIR>
  Pass 1 collect: parse all chapters -> targets (headings, footnote bodies, TOC) and
    references (<a href="#..">, <sup><b><a href="#(n)">(n)</a></b></sup>, TOC links,
    prose "see chapter X").
  Pass 2 resolve (sequential by manifest.order):
    - assign stable IDs: ch-<NN>-<slug>, <slug>--sec-<n>, <slug>--fn-<n>, <slug>--fnref-<n>;
    - wire footnote<->backref in the st-takla markup (keep marker text verbatim;
      keep the <h6><a>الحواشي والمراجع</a></h6> + _____ block so renderer pairing works);
    - resolve #anchor / cross-chapter / inter-book refs against manifest.json/catalog.json;
    - DANGLING target -> downgrade <a> to <span> (keep text) + log dangling-ref. NEVER delete.
LLM: only to disambiguate fuzzy prose "see chapter X" to a chapter ID. Never invent a target.
SELF-CHECK: 0 new danglers; footnotes pair; IDs identical across two runs.
OUTPUT: rewritten content.xhtml; state.{anchor_registry,footnote_registry,heading_map};
        recompute source_hash.
```

### `prompts/phases/45-resolve-author.md`
```markdown
# PHASE 45 — Author extraction, research, dedup, idempotent link
PRECONDITIONS: meta.json present; rapidfuzz installed.
STEP 1 EXTRACT (LLM, strict JSON -> prompts/lib/schemas/author-extraction.schema.json):
  feed catalog.json.title_guess + meta.author + (Phase2: title page/colophon).
  Verbatim surface forms; explicit roles; is_collection/attribution flags; confidence.
STEP 2..5 (deterministic): python3 tools/resolve_author.py <BOOK_DIR>
  - match_key (AR+EN, §6.2 recipe);
  - research: Wikidata wbsearchentities(ar) + EntityData; VIAF AutoSuggest (REAL browser
    User-Agent — VIAF 403s bots); LC suggest/didyoumean; Wikipedia REST via sitelink title;
    st-takla /books/<slug>/; fallback thin record;
  - dedup tiers: Tier0 authority-QID -> link; Tier1 match_key== -> link;
    Tier2 RapidFuzz token_set_ratio>=92 or JaroWinkler>=0.93 (+year) -> link;
    82..92 -> append tools/author-review-queue.json, NO write; <82 -> create_author;
  - follow aliases_to to terminal slug; collections -> kind:"collection";
  - upsert authors/<slug>/info.json (create-if-absent / merge-not-clobber; union aliases;
    write resolution{confidence,method,reviewed,needs_review,ts}); honor sticky method:"manual";
  - set meta.json.author_slug AND catalog.json[book].author_slug.
SELF-CHECK: idempotent re-run = no-op; primary confidence<0.6 -> STOP (review).
OUTPUT: authors/<slug>/info.json (+portrait.jpg); state.author; review queue if needed.
```

### `prompts/phases/50-build-epub.md`
```markdown
# PHASE 50 — Build the EPUB from canonical sources (no drift)
PRECONDITIONS: normalized + ref-resolved content.xhtml; images/ present; meta+manifest valid.
RUN (deterministic, no network, atomic): python3 tools/build_epub.py <BOOK_DIR>
  - read EXISTING chapters/<NN-slug>/content.xhtml (inner <body> + <h1> title);
  - wrap via page_xhtml + style.css (RTL CSS for ar, LTR for en);
  - copy referenced images/* into OEBPS/images/; embed cover.jpg;
  - assemble content.opf (page-progression-direction from language), nav.xhtml, toc.ncx
    from manifest.order + meta; mimetype stored-first; zip atomically to <book-slug>.epub.
VALIDATE: always run the in-repo validate_epub (zip/mimetype/well-formed/refs/>=1 chapter/
  no nav chrome). If epubcheck.jar present: java -jar epubcheck.jar <epub> ; FATAL/ERROR=STOP,
  WARN -> REPORT.md. If absent: log "epubcheck skipped". Fallback: ebook-convert (Calibre),
  flagged as fallback-built.
SELF-CHECK: validate_epub passes; round-trip text diff (with tashkeel) ≈ 0 per chapter.
OUTPUT: <BOOK_DIR>/<book-slug>.epub; state.phases.epub=done.
```

### `prompts/phases/60-verify.md`
```markdown
# PHASE 60 — Verification & quality gates (all must pass)
RUN (deterministic): python3 tools/verify_book.py <BOOK_DIR>
  1. schemas valid (meta/manifest/state); spine==manifest==disk; chapter_links_guess==#chapters.
  2. image-ref integrity (referenced==present; every <img> has alt).
  3. link integrity: 0 dangling #anchors / cross-file refs.
  4. round-trip text diff WITH tashkeel within tolerance for every chapter.
  5. EPUB validation (lxml always; epubcheck 0 ERROR/FATAL if available).
  6. catalog consistency; status still "draft".
  7. author: meta.author_slug==catalog.author_slug; info.json exists or needs_review logged.
  8. Arabic/RTL checklist (prompts/lib/arabic-rtl.md).
LLM: triage any failure into auto-fixable (re-run prior phase) vs human-flag.
ON ANY HARD FAILURE OR STOP CONDITION: write REPORT.md, set review:"pending", STOP.
OUTPUT: state.issues + per-check results; pass -> proceed to phase 90.
```

---

# APPENDIX C — JSON schemas

### `prompts/lib/schemas/state.schema.json` (`.build/state.json`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "BookBuildState", "type": "object",
  "required": ["book_id","schema_version","phase","source_hash","phases"],
  "properties": {
    "book_id": {"type":"string"},
    "schema_version": {"type":"integer","const":1},
    "phase": {"type":"string","enum":["html","pdf"]},
    "source_hash": {"type":"string"},
    "phases": {"type":"object","additionalProperties":{
      "type":"object","properties":{
        "status":{"type":"string","enum":["pending","stale","done","failed"]},
        "input_hash":{"type":"string"}}}},
    "toc": {"type":"array","items":{"type":"object",
      "required":["order","slug","title","id","level"],
      "properties":{"order":{"type":"integer"},"slug":{"type":"string"},
        "title":{"type":"string"},"id":{"type":"string"},"level":{"type":"integer"}}}},
    "heading_map": {"type":"object","additionalProperties":{
      "type":"object","properties":{"chapter":{"type":"string"},"text":{"type":"string"}}}},
    "anchor_registry": {"type":"object","additionalProperties":{
      "type":"object","properties":{"chapter":{"type":"string"},"kind":{"type":"string"}}}},
    "footnote_registry": {"type":"array","items":{"type":"object",
      "required":["id","chapter","marker","resolved"],
      "properties":{"id":{"type":"string"},"chapter":{"type":"string"},
        "marker":{"type":"string"},"ref_anchor":{"type":"string"},
        "target_anchor":{"type":"string"},"text":{"type":"string"},
        "resolved":{"type":"boolean"}}}},
    "image_manifest": {"type":"array","items":{"$ref":"image-manifest.schema.json#/definitions/image"}},
    "author": {"type":"object","properties":{
      "slug":{"type":"string"},"confidence":{"type":"number"},
      "method":{"type":"string"},"needs_review":{"type":"boolean"},
      "authority":{"type":"object"},"source_surface":{"type":"string"}}},
    "issues": {"type":"array","items":{"type":"object",
      "required":["severity","code","detail"],
      "properties":{"severity":{"type":"string","enum":["info","warn","error"]},
        "code":{"type":"string"},"detail":{"type":"string"},"chapter":{"type":"string"}}}},
    "review": {"type":"string","enum":["pending","approved"]}
  }
}
```

### `prompts/lib/schemas/image-manifest.schema.json`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ImageManifest",
  "definitions": {
    "image": {
      "type": "object",
      "required": ["name","referenced_in","present"],
      "properties": {
        "name": {"type":"string","pattern":"^img_[0-9a-f]{12}\\.(jpe?g|png|gif|webp)$"},
        "referenced_in": {"type":"array","items":{"type":"string"}},
        "present": {"type":"boolean"},
        "bytes": {"type":"integer"},
        "alt_present": {"type":"boolean"},
        "source_page": {"type":["integer","null"]},
        "bbox": {"type":["array","null"],"items":{"type":"number"}},
        "caption": {"type":["string","null"]},
        "hash": {"type":["string","null"]},
        "master_path": {"type":["string","null"]}
      }
    }
  },
  "type": "array", "items": {"$ref": "#/definitions/image"}
}
```

### `prompts/lib/schemas/author-info.schema.json` (`authors/<slug>/info.json`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AuthorInfo", "type": "object",
  "required": ["slug","kind","name_ar","name_en"],
  "properties": {
    "slug": {"type":"string","pattern":"^[a-z0-9-]+$"},
    "kind": {"type":"string","enum":["person","collection","alias"]},
    "name_ar": {"type":"string"}, "name_en": {"type":"string"},
    "bio_ar": {"type":["string","null"]}, "bio_en": {"type":["string","null"]},
    "bio_source": {"type":["string","null"]},
    "birth_year": {"type":["integer","null"]}, "death_year": {"type":["integer","null"]},
    "portrait": {"type":["string","null"]},
    "portrait_source": {"type":["string","null"]},
    "portrait_status": {"type":["string","null"],
      "enum":["ok","not_found","license_unclear","n/a","missing",null]},
    "portrait_license": {"type":["string","null"]},
    "wikipedia_ar": {"type":["string","null"]}, "wikipedia_en": {"type":["string","null"]},
    "aliases_to": {"type":["string","null"]},
    "match_key": {"type":"array","items":{"type":"string"}},
    "aliases_ar": {"type":"array","items":{"type":"string"}},
    "aliases_en": {"type":"array","items":{"type":"string"}},
    "authority": {"type":"object","properties":{
      "wikidata":{"type":["string","null"]},"viaf":{"type":["string","null"]},
      "loc":{"type":["string","null"]}}},
    "resolution": {"type":"object","properties":{
      "confidence":{"type":"number"},"method":{"type":"string",
        "enum":["qid","matchkey","fuzzy","created","manual","wikidata-qid"]},
      "matched_slug":{"type":["string","null"]},
      "source_surface":{"type":"string"},
      "reviewed":{"type":"boolean"},"needs_review":{"type":"boolean"},
      "ts":{"type":"string"}}}
  }
}
```

### `prompts/lib/schemas/author-extraction.schema.json` (LLM output)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AuthorExtraction", "type": "object",
  "required": ["contributors","is_anonymous","is_collection","attribution_uncertain"],
  "properties": {
    "title_ar": {"type":["string","null"]}, "title_en": {"type":["string","null"]},
    "contributors": {"type":"array","items":{"type":"object",
      "required":["surface_form","role","name_core_surface","lang","confidence"],
      "properties":{
        "surface_form":{"type":"string"},
        "role":{"type":"string","enum":["author","translator","editor","compiler","attributed"]},
        "honorific_surface":{"type":["string","null"]},
        "name_core_surface":{"type":"string"},
        "lang":{"type":"string","enum":["ar","en","other"]},
        "confidence":{"type":"number","minimum":0,"maximum":1}}}},
    "is_anonymous": {"type":"boolean"}, "is_collection": {"type":"boolean"},
    "attribution_uncertain": {"type":"boolean"},
    "series": {"type":["string","null"]},
    "evidence": {"type":"string"}
  }
}
```

---

# APPENDIX D — Canonical HTML-subset + Arabic/RTL contract

### `prompts/lib/html-subset.md`
```markdown
# Renderer-compatible HTML subset (the strict contract for every content.xhtml)
The SAME content.xhtml feeds the web renderer (sanitize-html + html-react-parser, no
dangerouslySetInnerHTML) AND the EPUB builder. Emit only what the sanitizer keeps.

ENVELOPE (per chapter):
  <?xml version="1.0" encoding="utf-8"?>
  <!DOCTYPE html>
  <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ar" lang="ar" dir="rtl">
  <head><meta charset="utf-8"/><title>{chapter title}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/></head>
  <body dir="rtl"><h1>{chapter title}</h1> ...body... </body></html>
  (English: lang="en" dir="ltr" on both <html> and <body>.)

RENDERER BEHAVIOR TO DESIGN FOR:
- Only inner <body> is consumed. First top-level <h1> is the title and is STRIPPED
  (page chrome shows it). Every OTHER heading is DEMOTED one level (hN->h(N+1), cap h6):
  author <h2> renders as h3. So: ONE <h1> title, then use <h2>/<h3> for sections.

ALLOWED TAGS (everything else discarded; font/center/div unwrapped, children kept):
  p br hr h1 h2 h3 h4 h5 h6 strong b em i u sup sub a span img
  ul ol li table thead tbody tr td th blockquote
  (b->strong, i->em on transform.)

ALLOWED ATTRIBUTES (all others stripped — class/style/width/align/color/face are useless):
  a:[href,id]   img:[src,alt]   td:[colspan,rowspan]   th:[colspan,rowspan]   *:[dir,lang]
SCHEMES: http https mailto ; relative + #fragment kept.

IMAGES: relative ONLY. src MUST match ^(?:\./)?images/<file>$ where
  file = img_<md5(remote_url)[:12]>.<ext>  (jpg|jpeg|png|gif|webp).
  Any remote/data/empty <img> is DROPPED. Always include non-empty alt.
  Image-wrapper table (<table><tr><td><a href=gallery><img/></a></td></tr>
  <tr><td><div><p>caption</p></div></td></tr></table>) -> ContentFigure.

FOOTNOTES (keep these exact shapes so the renderer pairs them):
  in-body marker: <sup><b><a href="#(1)">(1)</a></b></sup>
  note block:     <a href="#1">(1)</a> ... under <h6><a>الحواشي والمراجع</a></h6> + "_____"
  The renderer collapses _ftnN/_ftnhrefN keys and re-attaches ids; preserve marker text.

CROSS-REFS: in-library st-takla URLs (absolute or ../..) are rewritten to internal routes;
  external kept; unresolved #anchor kept as a graceful dead link. Never delete visible text.

TOC TABLE: a table containing محتويات/Contents + intra-page # anchors -> ChapterToc.

FORBIDDEN: inline styles, classes, font/center, script/style/iframe/nav/form/input,
  on*=, javascript:, presentational attributes, non-images/* <img>.
```

### `prompts/lib/arabic-rtl.md`
```markdown
# Arabic / RTL contract + verification checklist
DATA INTEGRITY (the sacred-text guards):
- PRESERVE tashkeel/diacritics (U+064B..U+0652, shadda, superscript alef) EXACTLY.
  The round-trip text diff compares WITH diacritics; an LLM "cleanup" that strips them
  is the prime failure — discard it and STOP.
- Detect & fix mojibake / Windows-1256 remnants (heuristic: unexpected CP1256/Latin-1
  byte patterns in ar text; presentation-form leakage U+FE70..U+FEFF). Fix via LLM but
  diff-gate. Normalize to canonical Arabic block + NFC.
- NEVER normalize hamza/alef/taa-marbuta in DISPLAY text (variants carry meaning);
  normalization is for the author match_key / search index ONLY.

DIRECTION / BIDI:
- dir="rtl" + lang="ar" on <html> and <body> (English: dir="ltr" lang="en").
- Wrap genuinely LTR runs (Latin names, numbers, scripture refs) in <span dir="ltr">;
  rely on the Unicode bidi algorithm — NEVER manually reorder characters.
- EPUB spine: page-progression-direction="rtl". Verify in a REAL reader
  (Readium RTL blank-page bug exists), not just a validator.

RENDERING (style.css, already in repo): line-height ~1.9 so stacked diacritics don't clip;
  tashkeel-capable font stack (Amiri / Scheherazade New / Noto Naskh Arabic).

CHECKLIST (phase 60):
[ ] tashkeel preserved (round-trip diff with diacritics ≈ 0)
[ ] no mojibake / CP1256 / presentation-form leakage
[ ] dir/lang correct on roots; LTR runs wrapped; no manual reordering
[ ] page-progression-direction=rtl (ar) / ltr (en); checked in a real reader
[ ] display text keeps original hamza/alef/taa-marbuta variants
```
