# Phase 5 — Chapter Renderer Verification

Date: 2026-05-28. Branch: `feat/content-renderers`.

## Gates

- `pnpm --filter web exec tsc --noEmit` → **clean (exit 0)**.
- `pnpm --filter web build` → **success (exit 0)**. No fixes required.
  - One pre-existing, non-blocking warning unrelated to the renderer:
    `catalog.ts:107 bookDirAbsolute` produces an overly broad file-pattern
    (`/ROOT/books/st-takla.org/<dyn>/<dyn>`) — a Next.js bundling perf warning,
    not an error, and outside this phase's scope.

## Fixture chapters (locale = book language)

| # | Kind | URL |
|---|------|-----|
| a | Long Arabic, has محتويات TOC + `<sup>` markers | `/ar/books/anba-raphael/i-willingly-ate/sinned-in-adam` |
| b | Arabic footnotes (`_ftnH1`/`_ftnHref1` pair) + data table | `/ar/books/adel-zekri/augustine-consentius-120/text` |
| c | English book chapter (ecf, `meta.language=en`) | `/en/books/ecf/004/0040047` |
| d | Image-referencing Arabic (image-wrapper tables) | `/ar/books/anba-raphael/i-willingly-ate/foreword` |

## Smoke crawl

Script: `apps/web/scripts/smoke-crawl.mjs` (builds URLs from manifests across the
whole catalog, locale follows each book's language). Ran against a production
server (`pnpm --filter web start` on port 3100, isolated from a pre-existing
dev server on 3000 that was not ours).

- **50 URLs** crawled (4 fixtures + 46 spread across Arabic and English books).
- **All 200**, all with non-empty `<article>` bodies. 0 failures, 0 empties.
- **0 raw `images/` `<img>` leaks** anywhere.
- Server log: **no parser/runtime errors** during the crawl.

## Regression checks

| Check | Result |
|-------|--------|
| (a) internal book links → `/{locale}/books/...` | PASS (35 internal hrefs in fixture a, e.g. `/ar/books/anba-raphael/i-willingly-ate/foreword`) |
| (b) external links `target="_blank" rel="noopener noreferrer"` | PASS (125 in fixture a) |
| (c) footnote re-anchoring: ref + matching id in DOM | PASS — `<a href="#_ftnH1" id="_ftnHref1">` and `<a href="#_ftnHref1" id="_ftnH1">` (cross-assigned pair both present) |
| (d) no raw `images/` `<img>` leaks | PASS (0 in all 4 fixtures + 50-URL crawl) |
| (e) Arabic `dir="rtl"`, English `dir="ltr"` on prose wrapper | PASS — fixture a `<div class="prose-coptic" dir="rtl">`, fixture c `dir="ltr"` |
| (f) no content dropped vs source body text | PASS — Arabic fixture a ratio 1.03, English fixture c ratio 1.01 (rendered/source visible-text length) |

### Structure renderers confirmed in served HTML
- **TOC component**: fixture a renders the "محتويات" box with working `#anchor`
  links (e.g. `#شبه_جسد_الخطية`).
- **Demoted headings**: leading body `<h1>` stripped (page chrome owns the title —
  only one `<h1>` per article, the chrome title); second source `<h1>` demoted to
  `<h2>` (English fixture c shows `h2:1`, body `h1:0`).
- **Data tables**: render as `<table>` where the source has real tabular content
  (e.g. `/en/books/ecf/004/0040058` → 1 table; fixture b footnote chapter shows a
  section/page index table). Layout/image-wrapper tables are unwrapped/stripped.
- **Footnote markers**: `<sup>`/bracket refs render as gold superscript links.
- **Images**: image-wrapper tables stripped; caption text preserved (fixture d
  shows "St-Takla.org Image: …" captions, no broken images).

## Screenshots

Captured with system headless Chromium (`/usr/bin/chromium`, `--window-size=1440,1800`).
Saved under `apps/web/analysis/screenshots/`:

- `01-arabic-toc-sup.png` — RTL, TOC box, footnote superscripts, full prose.
- `02-arabic-footnotes.png` — RTL footnote marker `[1]`, data table, stripped image caption.
- `03-english-chapter.png` — LTR, demoted `<h2>`, footnote markers, full prose.
- `04-image-referencing.png` — RTL, image caption preserved as text, no broken image.

All four visually confirm headings, TOC, footnotes, tables, and RTL/LTR.

## Verdict

No `dangerouslySetInnerHTML` in the chapter path. tsc + build green, 50/50 smoke
URLs healthy, all 6 regression checks pass, 4 fixture screenshots verified. No
code fixes were needed.
