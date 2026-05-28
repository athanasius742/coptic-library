# Renderer Spec — Book Chapter Content (Phase 2)

> Implementation contract for Phase 3 (`apps/web/src/lib/render-content.tsx` +
> `apps/web/src/components/content/*`). Replaces the regex pipeline in
> `apps/web/src/lib/chapter.ts` (`transformHtml`, `resolveHref`,
> `rewriteToInternal`, `plainTextExcerpt`). Renderer = **`html-react-parser`**;
> sanitizer = **`sanitize-html`**. Detection is **content/shape-based only** —
> the corpus has **zero `class`/`id`/`style`/`name`** attributes
> (FINDINGS.md §"Distinct meaningful class / id values").
>
> All rules below were validated against real `content.xhtml`:
> `adel-zekri/augustine-consentius-120/chapters/02-text`,
> `.../03-faith-seeking-understanding`, `amir-nasr/alex-rome/chapters/03-mark`,
> `anba-raphael/i-willingly-ate/chapters/07-liturgy`,
> `adel-zekri/augustine-faith/chapters/02-text`.

---

## 0. Order-of-operations pipeline — `renderChapterHtml(raw, ctx)`

`ctx = { chapterUrl: string; locale: Locale; bookKeys: Set<string> }`

1. **Extract `<body>`** — `raw.match(/<body[^>]*>([\s\S]*?)<\/body>/i)`; fall back
   to `raw`. (Same as today.)
2. **Re-anchor (STRING stage, pre-sanitize).** Run the anchor-reconstruction pass
   (§Re-anchoring) on the body string. This **injects `id="…"` attributes** onto
   the destination anchors. It runs *before* sanitize so the ids are real markup
   the sanitizer can be told to keep. (Rationale: doing it in `replace()` is hard —
   `replace()` visits nodes in isolation and you need a whole-document two-pass id
   map first. A single regex/`htmlparser2` pre-pass over the string is simplest and
   the only place the global pairing map is cheap to build.)
3. **`sanitize-html`** with the allowlist in §Sanitize. Force-drops the strip-list,
   `on*` handlers, `javascript:` hrefs, and `src="images/…"`. **`id` is allowed only
   on `a`** (the elements step 2 wrote ids to) so they survive.
4. **`parse(clean, { replace })`** — `replace()` maps shapes → components and ports
   link rewriting (`resolveHref`/`rewriteToInternal`). Returns `React.ReactNode`.

`chapterPlainText(raw)` is a **separate, lighter** path (§chapterPlainText) used for
metadata/excerpt — it does NOT need React/components, just body-extract + strip.

Both wrapped in `cache()` as today. Output is rendered inside the existing
`<div className="prose-coptic" dir={bookDir}>` wrapper (kept as the typographic base).

---

## 1. Re-anchoring (THE critical task — 15,134 broken-anchor files)

**Problem:** source links `<a href="#X">` survive, but the destination's `id`/`name`
was stripped during cleaning, so `#X` jumps nowhere. We must re-attach ids.

**Two real schemes observed (both are mutual-reference pairs):**

| scheme | body marker (href) | note/return link (href) | example file |
|---|---|---|---|
| Word footnotes | `<a href="#_ftnH1">[1]</a>` | `<a href="#_ftnHref1">[1]</a>` | augustine-consentius-120/02-text |
| paren footnotes | `<sup>(<a href="#(1)">1</a>)</sup>` | `<a href="#1">(1)</a>` | alex-rome/03-mark |

Each member links to the OTHER's intended id. So the destination for `#X` is the
**counterpart anchor** in the pair.

**Canonical-key pairing function** (validated — see commit research):

```ts
function anchorKey(target: string): string {
  const s = target.toLowerCase();
  const m = s.match(/^_ftn(?:h|href)(\d+)$/);   // _ftnH1 / _ftnHref1 -> "ftn1"
  if (m) return "ftn" + m[1];
  return s.replace(/[^0-9a-z؀-ۿ]/gi, ""); // (1)->"1", 1->"1", إنجيل_مارمرقس -> stripped
}
```

**Algorithm (whole-body, two pass):**

1. Collect every `<a href="#TARGET">` → list of `{ target, key: anchorKey(target) }`.
2. Group by `key`. For each group with **exactly two distinct targets** `A`, `B`
   (the normal footnote pair): the anchor whose href is `#A` is the destination for
   the *other* link, so it must carry `id="B"`; the anchor whose href is `#B` must
   carry `id="A"`. (Cross-assign: each anchor gets the id its partner is pointing at.)
3. Inject `id` onto the **anchor element itself** (the `<a>`), at the opening tag.
   Idempotent: never overwrite an existing `id`; never add a second.

**Slug/TOC targets with no counterpart** (e.g. `#إنجيل_مارمرقس` → section heading was
stripped to bare inline text): **best-effort, then graceful no-op.** Match a bare
`<a>` (no `href`) whose `anchorKey(textContent)` equals the slug key → give it the
`id` (observed: `<a>الحواشي والمراجع</a>` at line 438 is the destination for
`#الحواشي_والمراجع`). If no bare-anchor or heading match exists, **leave the link as
a dead `#` anchor** (do not crash, do not invent a target mid-prose). Document the
tradeoff: full TOC-slug recovery is unreliable because destinations were deleted; the
footnote pairs (the high-value, high-frequency case) recover deterministically.

**Result:** `<a href="#_ftnH1">` now also bears `id="_ftnHref1"` etc.; clicking the
marker scrolls to the note and the note's back-link scrolls to the marker.

---

## 2. Sanitize-html allowlist

```ts
const SANITIZE: sanitizeHtml.IOptions = {
  allowedTags: [
    "p","br","hr",
    "h1","h2","h3","h4","h5","h6",
    "strong","b","em","i","u","sup","sub",
    "a","span",
    "ul","ol","li",
    "table","thead","tbody","tr","td","th",
    "blockquote",
    // NOTE: font, center, div intentionally OMITTED -> sanitize-html drops the
    // tag but KEEPS children by default (we want unwrap, not removal).
  ],
  allowedAttributes: {
    a: ["href", "id"],            // id MUST survive (re-anchoring writes it here)
    td: ["colspan", "rowspan"],
    th: ["colspan", "rowspan"],
    "*": ["dir", "lang"],         // dir/lang are the only other real attrs in corpus
  },
  allowedSchemes: ["http", "https", "mailto"],   // drops javascript:
  allowedSchemesByTag: { a: ["http", "https", "mailto"] },
  disallowedTagsMode: "discard",  // unknown tags -> drop tag, keep text children
  // strip-list: tags whose CONTENT must also die, not just the tag wrapper:
  nonTextTags: ["script","style","iframe","button","input","form","nav",
                "link","meta","button-hide","textarea","select","option"],
  // image-wrapper / stray images: assets not in repo -> drop entirely.
  exclusiveFilter: (frame) =>
    frame.tag === "img" /* all imgs dropped */ ||
    (frame.tag === "table" && /src=["']?(?:\.\/)?images\//i.test(frame.text)),
  transformTags: {
    // on* handlers: sanitize-html drops any attr not in allowedAttributes, so
    // on* are removed automatically. No explicit transform needed.
  },
};
```

Notes:
- `img` is **always dropped** (assets absent) — both stray imgs and image-wrapper
  tables. The `exclusiveFilter` table clause is belt-and-suspenders; in practice the
  `<img>` tags inside die because `img` is not allowed, leaving an empty table that
  the `replace()` step (§Tables) discards when it has no real cell text.
- `font`, `center`, `div`, `basefont` are **not** in `allowedTags` → sanitize-html
  unwraps them (keeps children) under `disallowedTagsMode:"discard"`. Verify this is
  the actual sanitize-html behavior for non-`nonTextTags` disallowed tags; if a given
  version *removes* children, move `font/center/div` to `transformTags` →
  `{ tagName: false }` which is documented to unwrap. Pick whichever the installed
  version guarantees and pin it.
- `area`, `map`, `o`, `dir` (deprecated), `thead`/`tbody` survive structurally;
  `area/map/o/dir` are negligible noise and drop via not-allowed.

---

## 3. Structure catalog — matching rule → target → styling

`replace(domNode)` returns a React element to substitute, or `undefined` to let
html-react-parser render the default tag (which then picks up `.prose-coptic` CSS).

### 3.1 Leading chapter title `<h1>` — STRIP
- **Rule:** the FIRST `<h1>` that is a direct/early child of body (the page chrome
  already renders the title as its own `<h1>`). Today: `replace(/^\s*<h1…>…<\/h1>/)`.
  Implement as: track "have we passed the first top-level h1?"; drop occurrence #1.
- **Target:** strip (return `<></>`).

### 3.2 Decorative source-TOC heading shells — STRIP
- **Rule (a):** `<h1>` whose only content is `<span>N- <a>title</a></span>`
  (number-dash-link pattern) — matches today's
  `/<h1>\s*<span>\s*\d+[-–]\s*<a>…<\/a>\s*<\/span>\s*<\/h1>/`. Detect: h1 whose text
  matches `^\s*\d+\s*[-–]\s` and whose only element child is a single `<a>`.
- **Rule (b):** empty heading shells `<h3></h3>` (and any `<hN>` with no
  text after trimming) — drop.
- **Target:** strip.

### 3.3 In-body headings `h1`–`h6` — DEMOTE
- **Rule:** any remaining heading after 3.1/3.2. Map level → `Math.min(level+1, 6)`
  so the top in-body heading becomes `<h2>` (chrome owns `<h1>`). h1→h2, h2→h3,
  h3→h3/h4 etc. Keep it simple: render `h{min(n+1,6)}`.
- **Target:** plain element (emit `React.createElement("h"+lvl, …)`).
- **Styling:** kept in `.prose-coptic h1,h2,h3` (extend selector to h4–h6 with same
  treatment, or clamp visual size). No component.

### 3.4 Table of Contents tables — `ChapterToc`
- **Rule:** `<table>` whose **full text content** contains `محتويات` or
  (case-insensitive) `Contents`, AND it contains `<a href="#…">` intra-page links.
  Validated: alex-rome/03-mark table text starts `محتويات`.
- **Target:** `ChapterToc` (client component — collapsible). Receives the parsed list
  of `{ href, label }` (anchors already re-anchored in §1 so `#…` works).
- **Styling:** component-owned Tailwind (bordered card, `<details>`/`<summary>` or a
  state toggle, gold accent). Not `.prose-coptic table`.

### 3.5 Image-wrapper tables + stray images — STRIP
- **Rule:** `<table>` containing `<img src="images/…">` (validated:
  i-willingly-ate/07-liturgy). Any `<img>` at all (assets absent).
- **Target:** strip. (Mostly handled in sanitize via `exclusiveFilter` + img
  not-allowed; `replace()` additionally discards any `<table>` left with no
  non-whitespace cell text.)
- Keep-stripping decision retained per FINDINGS (no assets in repo). Follow-up:
  asset fetch would convert these to a `<Figure>` placeholder — out of scope.

### 3.6 Data tables — `ContentTable`
- **Rule:** `<table>` that is NOT a TOC (3.4) and NOT image-wrapper (3.5) and HAS
  real cell text (≥1 `<td>`/`<th>` with non-whitespace, non-link-only content).
  Validated: augustine-faith/02-text, augustine-consentius-120/02-text.
- **Target:** `ContentTable` (server) — wraps in an overflow-x scroll container for
  responsiveness; passes `colspan`/`rowspan` through.
- **Styling:** component Tailwind for the responsive wrapper + borders; may reuse the
  `.prose-coptic table td/th` border look. Move table CSS into component.

### 3.7 Scripture citations `<sup>` — `ScriptureCite`
- **Rule:** `<sup>` element. (FINDINGS §6: `<sup>` = citation parens like
  `(لو24:45)`, NOT footnotes — do NOT build a footnote popover off `<sup>`.) Note a
  `<sup>` may itself wrap a footnote `<a href="#(1)">` (alex-rome line 79); in that
  case the inner `<a>` is handled by 3.8 independently — `ScriptureCite` just styles
  the superscript shell.
- **Target:** `ScriptureCite` (server) — thin styled `<sup>`. Could also be "plain
  element" + `.prose-coptic sup` CSS. **Decision:** keep as plain `<sup>` styled by
  `.prose-coptic sup` (already gold, 0.75em) — a component adds no behavior. Only
  promote to a component if a future "show verse on hover" is wanted.

### 3.8 Footnotes — `FootnoteRef` (refs) + plain anchors
- **Rule:** `<a href="#X">` where `anchorKey(X)` participates in a 2-target pair
  (§1) — i.e. it is a footnote marker or return-link. Marker text is typically
  `[n]` / `(n)` / `n`.
- **Target:** `FootnoteRef` — renders `<a href={"#"+target} id={assignedId}>` with
  superscript bracket styling and `scroll-margin-top` so the jump isn't hidden under
  any sticky header. The id was injected in §1; `FootnoteRef` reads it from the node
  (it survived sanitize). No popover required for Phase 3 (footnote *body* stays
  inline at the bottom). Keep `FootnoteRef` **server** unless a hover-popover is
  added later (then isolate a client island).
- **Styling:** component Tailwind (small, gold, `scroll-margin-top`).

### 3.9 General links `<a href>` (inter/intra-book) — `ContentLink`
- **Rule:** any `<a>` not classified as 3.8. Port `resolveHref` + `rewriteToInternal`
  **exactly**:
  - `href` starts with `#` → keep as-is (in-page anchor; re-anchored in §1).
  - else resolve against `ctx.chapterUrl`; if it maps to a hosted book
    (`bookKeys.has("author/book")`) → internal route
    `/${locale}/books/${author}/${book}[/${chapter}]` (chapter = file basename,
    `index`→none), rendered with Next `<Link>`.
  - else absolute/other → `<a href target="_blank" rel="noopener noreferrer">`.
  - unresolvable href → drop the anchor, keep its inner text (today's behavior).
  - sanitize already removed `javascript:`; double-check in resolve.
- **Target:** `ContentLink` (server) — encapsulates the above branch logic. Internal
  links use `next/link`.
- **Styling:** kept in `.prose-coptic a` / `a:hover`.

### 3.10 Presentational inline soup — UNWRAP / map
- `font`, `center`, `basefont`, `div` → **unwrap** (handled by sanitize not-allowing
  them; children kept). `div` unwrap matches today's flattening.
- `span` → unwrap (no semantic value; corpus spans carry no attrs). Let
  html-react-parser render children; in `replace()` return `<>{children}</>` for
  `span`, OR simply leave `span` in allowedTags and let `.prose-coptic` ignore it
  (no style). **Decision:** keep `span` allowed and unstyled (cheaper than rewriting
  every span node); it is inert.
- `b` → `<strong>`; `i` → `<em>`; `u` → keep `<u>` (underline). Map via
  `transformTags` in sanitize (`b`→`strong`, `i`→`em`) so `replace()` stays simple.
- **Styling:** `.prose-coptic strong,b` and `em,i` kept.

### 3.11 Paragraphs / line breaks / hr — plain, with cleanup
- Empty `<p>` (only whitespace/`&nbsp;`) → drop (today's behavior). Detect in
  `replace()`: `<p>` whose text is empty after trim → return `<></>`.
- Stray `<br>` runs (≥3 consecutive) → collapse to one (avoid huge gaps).
- `<hr>` → plain element (`.prose-coptic hr` gold gradient kept).
- "← see other books" floating `<p>` (starts with `←`) → strip (today's behavior).
- **Target:** plain elements.

### 3.12 Poetry / verse — FOLD INTO PARAGRAPHS (no `Verse` component)
- **Decision (deviates from the hint's optional `Verse`):** do NOT build a `Verse`
  component. Signal is weak (FINDINGS §6: 639 paras/69 books, many false positives —
  Q&A lists, bullet runs). `<center>` already unwraps; multi-`<br>` paragraphs render
  their line breaks correctly as plain `<p>` with `<br>`. A heuristic `Verse` would
  mis-format more than it helps. **Tradeoff:** true hymn stanzas lose centered
  styling, but content + line breaks are 100% preserved and no prose is wrongly
  poeticized. Revisit only if a specific hymnal book is prioritized (the corpus's
  `<center>` is concentrated in `church-books/dafnar`).

### 3.13 Lists / blockquote — plain
- `ul/ol/li` → plain (`.prose-coptic ul,ol,li` kept).
- `blockquote` (only 3 in corpus) → plain (`.prose-coptic blockquote` kept).

---

## 4. `chapterPlainText(raw)` (replaces `plainTextExcerpt`)

Used for metadata/excerpt only — no React.
1. Extract `<body>` (same regex).
2. Strip all tags: `replace(/<[^>]+>/g, " ")`.
3. `&nbsp;`→space; collapse whitespace; trim. (Identical to today's `plainTextExcerpt`
   body.)
4. Optional `max` (default 200) → slice on word boundary + `…`.
- It should also skip image-wrapper table text and the bottom footnote block from the
  excerpt is NOT required (excerpt is just the lead) — keep behavior parity with today
  (today does not special-case those). Keep simple: do not over-engineer.

---

## 5. `.prose-coptic` CSS disposition

Keep `.prose-coptic` as the **typographic base wrapper** (RTL/LTR font, size,
line-height, indent, color, max-width — these MUST be preserved). Per-rule mapping:

| `.prose-coptic` rule | disposition |
|---|---|
| base (`font`, `font-size`, `line-height`, `color`, `max-width`, `margin-inline`) | **kept as-is** (wrapper) |
| `[dir="rtl"]` overrides (arabic font/size/leading/features) | **kept as-is** (wrapper) |
| `p` (`text-align:start`, `text-indent`) | **kept** |
| first-`p`/`h*+p` no-indent | **kept** (extend `h4–h6 + p` if demotion produces them) |
| `h1,h2,h3` style + sizes | **kept**; extend selector to `h4,h5,h6` |
| `a` / `a:hover` | **kept** (used by `ContentLink` output) |
| `strong,b` / `em,i` | **kept** |
| `blockquote` | **kept** |
| `img` | **removed/unused** (all imgs stripped) — may delete |
| `table` / `table td,th` | **moved to `ContentTable`** (responsive wrapper); base border look may stay as fallback |
| `sup,sub` | **kept** (used by `ScriptureCite`/inline sup) |
| `ul,ol` / `li` | **kept** |
| `hr` | **kept** |

New component styling (TOC card, ContentTable scroll wrapper, FootnoteRef
`scroll-margin-top`) lives in the components via Tailwind, not in `.prose-coptic`.

---

## 6. Component inventory (Phase 3) — `apps/web/src/components/content/`

| file | component | server/client | why |
|---|---|---|---|
| `ChapterToc.tsx` | `ChapterToc` | **client** | collapsible (details/toggle) |
| `ContentTable.tsx` | `ContentTable` | server | responsive overflow wrapper |
| `ContentLink.tsx` | `ContentLink` | server | internal vs external link branch (uses `next/link`) |
| `FootnoteRef.tsx` | `FootnoteRef` | server | styled `<a>` + id + scroll-margin (client only if popover added) |
| `ScriptureCite.tsx` | (optional) | server | only if promoting `<sup>` beyond CSS — **deferred**, use plain `<sup>` for now |
| `render-content.tsx` (lib) | `renderChapterHtml`, `chapterPlainText` | server | pipeline + `replace()` mapper + ported `resolveHref`/`rewriteToInternal` |

Minimum to build: `ChapterToc`, `ContentTable`, `ContentLink`, `FootnoteRef` +
the `render-content.tsx` lib. `ScriptureCite`/`Verse` intentionally NOT built
(see 3.7, 3.12).

---

## 7. Behavior-parity checklist vs old `transformHtml`

- [x] strip everything outside `<body>` — step 1
- [x] remove leading title `<h1>` — 3.1
- [x] unwrap `font/center/basefont` — 3.10 / sanitize
- [x] strip decorative source-TOC `<h1>`/empty `<h3>` shells — 3.2
- [x] strip `on*` handlers — sanitize (attr not allowed) + `javascript:` scheme
- [x] drop `images/…` tables and stray imgs — 3.5 / sanitize
- [x] strip "← other books" `<p>` — 3.11
- [x] anchor rewriting (internal route vs `_blank` vs keep `#`) — 3.9, plus NEW
      re-anchoring (3.1 fixes the dead-`#` regression) — §1
- [x] strip empty `<p>` — 3.11
- [x] strip `<link>` — sanitize (`nonTextTags`)
- [x] `plainTextExcerpt` → `chapterPlainText` — §4
- [x] NO `dangerouslySetInnerHTML` — output is React nodes
