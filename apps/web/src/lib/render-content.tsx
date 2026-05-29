import "server-only";

import { Fragment, createElement, type ReactNode } from "react";
import parse, {
  attributesToProps,
  domToReact,
  Element,
  type DOMNode,
  type HTMLReactParserOptions,
} from "html-react-parser";
import sanitizeHtml from "sanitize-html";

import {
  ChapterToc,
  ContentFigure,
  ContentImage,
  ContentLink,
  ContentTable,
  FootnoteRef,
  type ContentLinkKind,
  type TocEntry,
} from "@/components/content";
import type { Locale } from "./i18n";

export type RenderCtx = {
  chapterUrl: string;
  locale: Locale;
  bookKeys: Set<string>;
  authorSlug: string;
  bookSlug: string;
};

// ---------------------------------------------------------------------------
// 0. body extraction (shared)
// ---------------------------------------------------------------------------

function extractBody(raw: string): string {
  const bodyMatch = raw.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  return bodyMatch ? bodyMatch[1] : raw;
}

// ---------------------------------------------------------------------------
// 1. Re-anchoring (string pre-pass, before sanitize)
// ---------------------------------------------------------------------------

/**
 * Canonical key for an in-page anchor target. Footnote pairs collapse to a
 * shared `ftn<n>` key; everything else is lowercased with non-alphanumerics
 * stripped (Arabic letters kept).
 */
function anchorKey(target: string): string {
  const s = target.toLowerCase();
  const m = s.match(/^_ftn(?:h|href)(\d+)$/);
  if (m) return "ftn" + m[1];
  // Keep 0-9, a-z and the Arabic block (U+0600–U+06FF); strip the rest.
  return s.replace(/[^0-9a-z؀-ۿ]/gi, "");
}

const HREF_ATTR_RE = /href=(["'])#([^"']+)\1/i;

/**
 * Re-attach `id` attributes onto the destination anchors of mutual-reference
 * footnote pairs so the surviving `<a href="#X">` links jump somewhere.
 *
 * Two-pass over the body string:
 *  1. Collect every `<a href="#TARGET">`, grouped by `anchorKey(TARGET)`.
 *  2. For each group with exactly two distinct targets {A, B} (a footnote pair),
 *     the anchor pointing at `#A` must carry `id="B"` and vice versa
 *     (cross-assignment: each anchor gets the id its partner points at).
 *  3. Inject that id onto the `<a>` opening tag, never overwriting an existing
 *     id and never adding a second.
 *
 * TOC/slug targets with no counterpart are left as dead `#` anchors (their
 * destinations were deleted during scraping); recovering them reliably is not
 * possible, so this is a graceful no-op rather than inventing a target.
 */
function reAnchor(body: string): string {
  // Match each <a ...> opening tag (footnote markers never nest other tags in
  // their attributes).
  const openTagRe = /<a\b[^>]*>/gi;

  // Pass 1: collect href targets by canonical key.
  const targetsByKey = new Map<string, Set<string>>();
  for (const match of body.matchAll(openTagRe)) {
    const tag = match[0];
    const hrefMatch = tag.match(HREF_ATTR_RE);
    if (!hrefMatch) continue;
    const target = hrefMatch[2];
    const key = anchorKey(target);
    if (!key) continue;
    let set = targetsByKey.get(key);
    if (!set) {
      set = new Set();
      targetsByKey.set(key, set);
    }
    set.add(target);
  }

  // Build target -> id-to-assign map for the well-formed pairs only.
  const idForTarget = new Map<string, string>();
  for (const targets of targetsByKey.values()) {
    if (targets.size !== 2) continue; // only deterministic 2-member pairs
    const [a, b] = [...targets];
    // The anchor whose href is #a is the destination for the link pointing at
    // #b, so it must carry id="b"; and vice versa.
    idForTarget.set(a, b);
    idForTarget.set(b, a);
  }

  if (idForTarget.size === 0) return body;

  // Pass 2: rewrite opening tags, injecting the id where missing.
  return body.replace(openTagRe, (tag) => {
    if (/\sid=/i.test(tag)) return tag; // already has an id — leave it
    const hrefMatch = tag.match(HREF_ATTR_RE);
    if (!hrefMatch) return tag;
    const id = idForTarget.get(hrefMatch[2]);
    if (!id) return tag;
    // Insert id right after `<a`.
    return tag.replace(/^<a\b/i, `<a id="${id.replace(/"/g, "&quot;")}"`);
  });
}

// ---------------------------------------------------------------------------
// 2. sanitize-html allowlist
// ---------------------------------------------------------------------------

const SANITIZE: sanitizeHtml.IOptions = {
  allowedTags: [
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "sup", "sub",
    "a", "span", "img",
    "ul", "ol", "li",
    "table", "thead", "tbody", "tr", "td", "th",
    "blockquote",
    // font/center/div intentionally omitted -> unwrapped (children kept).
  ],
  allowedAttributes: {
    a: ["href", "id"],
    img: ["src", "alt"],
    td: ["colspan", "rowspan"],
    th: ["colspan", "rowspan"],
    "*": ["dir", "lang"],
  },
  allowedSchemes: ["http", "https", "mailto"],
  allowedSchemesByTag: { a: ["http", "https", "mailto"] },
  // Keep relative hrefs (chapter links resolve later) and in-page #anchors.
  allowProtocolRelative: false,
  allowedSchemesAppliedToAttributes: ["href", "src"],
  disallowedTagsMode: "discard",
  // b -> strong, i -> em so replace() stays simple.
  transformTags: {
    b: "strong",
    i: "em",
  },
  nonTextTags: [
    "script", "style", "iframe", "button", "input", "form", "nav",
    "link", "meta", "textarea", "select", "option",
  ],
  // Keep only local chapter images (src="images/..."); drop any remote/data/
  // empty <img>. Image-wrapper tables are now rendered (see replace()).
  exclusiveFilter: (frame) =>
    frame.tag === "img" && !LOCAL_IMG_RE.test(frame.attribs?.src ?? ""),
};

/** A chapter-local image reference, e.g. `images/img_abc.jpg` or `./images/…`. */
const LOCAL_IMG_RE = /^(?:\.\/)?images\/([^"'?#]+)$/i;

function sanitize(body: string): string {
  return sanitizeHtml(body, SANITIZE);
}

// ---------------------------------------------------------------------------
// 3. link rewriting (ported from chapter.ts — behavior-identical)
// ---------------------------------------------------------------------------

function resolveHref(href: string, chapterUrl: string): URL | null {
  try {
    return new URL(href, chapterUrl);
  } catch {
    return null;
  }
}

function rewriteToInternal(
  resolved: URL,
  bookKeys: Set<string>,
): { authorSlug: string; bookSlug: string; chapterSlug: string | null } | null {
  if (resolved.hostname !== "st-takla.org" && resolved.hostname !== "www.st-takla.org") {
    return null;
  }
  const parts = resolved.pathname.replace(/^\/+/, "").split("/");
  if (parts[0] !== "books") return null;
  let i = 1;
  if (parts[i] === "en") i += 1;
  const authorSlug = parts[i];
  const bookSlug = parts[i + 1];
  const file = parts[i + 2];
  if (!authorSlug || !bookSlug || !file) return null;
  if (!bookKeys.has(`${authorSlug}/${bookSlug}`)) return null;
  const fileBase = file.replace(/\.html?$/i, "");
  const chapterSlug = fileBase === "index" ? null : fileBase;
  return { authorSlug, bookSlug, chapterSlug };
}

/** Decide what kind of link this href is and the final href string. */
function classifyLink(
  href: string,
  ctx: RenderCtx,
): { kind: ContentLinkKind; href: string } | null {
  if (href.startsWith("#")) {
    return { kind: "anchor", href };
  }
  const resolved = resolveHref(href, ctx.chapterUrl);
  if (resolved) {
    const internal = rewriteToInternal(resolved, ctx.bookKeys);
    if (internal) {
      const base = `/${ctx.locale}/books/${internal.authorSlug}/${internal.bookSlug}`;
      const target = internal.chapterSlug ? `${base}/${internal.chapterSlug}` : base;
      return { kind: "internal", href: target };
    }
    if (resolved.protocol === "http:" || resolved.protocol === "https:") {
      return { kind: "external", href: resolved.toString() };
    }
  }
  // Unresolvable / unsupported scheme → drop the anchor (caller keeps text).
  return null;
}

// ---------------------------------------------------------------------------
// 4. node helpers
// ---------------------------------------------------------------------------

function isElement(node: DOMNode): node is Element {
  return node instanceof Element;
}

/** `Element.children` is typed as `ChildNode[]` (includes CDATA); narrow to the
 *  `DOMNode[]` shape html-react-parser actually hands us. */
function childNodes(el: Element): DOMNode[] {
  return el.children as unknown as DOMNode[];
}

/** Recursively collect text content of a DOM node tree. */
function textOf(node: DOMNode): string {
  if (node.type === "text") {
    return (node as unknown as { data: string }).data;
  }
  if (isElement(node)) {
    return node.children.map((c) => textOf(c as DOMNode)).join("");
  }
  return "";
}

function childrenText(el: Element): string {
  return el.children.map((c) => textOf(c as DOMNode)).join("");
}

function isWhitespace(s: string): boolean {
  return s.replace(/ /g, " ").trim().length === 0;
}

// Build the per-pair target set once per render so classify can detect markers.
type PairInfo = {
  /** targets (hrefs without leading #) that participate in a footnote pair */
  footnoteTargets: Set<string>;
};

function collectPairs(clean: string): PairInfo {
  const openTagRe = /<a\b[^>]*>/gi;
  const targetsByKey = new Map<string, Set<string>>();
  for (const match of clean.matchAll(openTagRe)) {
    const hrefMatch = match[0].match(HREF_ATTR_RE);
    if (!hrefMatch) continue;
    const target = hrefMatch[2];
    const key = anchorKey(target);
    if (!key) continue;
    let set = targetsByKey.get(key);
    if (!set) {
      set = new Set();
      targetsByKey.set(key, set);
    }
    set.add(target);
  }
  const footnoteTargets = new Set<string>();
  for (const targets of targetsByKey.values()) {
    if (targets.size === 2) {
      for (const t of targets) footnoteTargets.add(t);
    }
  }
  return { footnoteTargets };
}

// ---------------------------------------------------------------------------
// 5. structure detection
// ---------------------------------------------------------------------------

function isTocTable(el: Element): boolean {
  const text = childrenText(el);
  const hasContentsLabel = text.includes("محتويات") || /contents/i.test(text);
  if (!hasContentsLabel) return false;
  // must contain at least one intra-page anchor
  return hasIntraPageAnchor(el);
}

function hasIntraPageAnchor(el: Element): boolean {
  for (const child of childNodes(el)) {
    if (isElement(child)) {
      if (child.name === "a" && (child.attribs.href ?? "").startsWith("#")) {
        return true;
      }
      if (hasIntraPageAnchor(child)) return true;
    }
  }
  return false;
}

function tableHasRealCells(el: Element): boolean {
  let real = false;
  const visit = (n: DOMNode) => {
    if (!isElement(n)) return;
    if (n.name === "td" || n.name === "th") {
      // real if it has non-whitespace text that isn't only inside an <a>
      const txt = childrenText(n);
      if (!isWhitespace(txt)) {
        const onlyLinkText = childNodes(n).every(
          (c) =>
            (isElement(c) && c.name === "a") ||
            (c.type === "text" && isWhitespace((c as unknown as { data: string }).data)),
        );
        if (!onlyLinkText) real = true;
      }
    }
    n.children.forEach((c) => visit(c as DOMNode));
  };
  el.children.forEach((c) => visit(c as DOMNode));
  return real;
}

function tableHasImage(el: Element): boolean {
  let found = false;
  const visit = (n: DOMNode) => {
    if (!isElement(n)) return;
    if (n.name === "img") found = true;
    n.children.forEach((c) => visit(c as DOMNode));
  };
  el.children.forEach((c) => visit(c as DOMNode));
  return found;
}

/** Build the served URL for a chapter-local image src, or null if not local. */
function imageUrl(src: string, ctx: RenderCtx): string | null {
  const m = src.match(LOCAL_IMG_RE);
  if (!m) return null;
  const file = m[1].split("/").pop() ?? m[1];
  return `/book-images/${ctx.authorSlug}/${ctx.bookSlug}/${encodeURIComponent(file)}`;
}

/** First chapter-local <img> in a subtree, with its served url + alt. */
function firstLocalImage(
  el: Element,
  ctx: RenderCtx,
): { url: string; alt: string } | null {
  let found: { url: string; alt: string } | null = null;
  const visit = (n: DOMNode) => {
    if (found || !isElement(n)) return;
    if (n.name === "img") {
      const url = imageUrl(n.attribs.src ?? "", ctx);
      if (url) found = { url, alt: n.attribs.alt ?? "" };
      return;
    }
    n.children.forEach((c) => visit(c as DOMNode));
  };
  el.children.forEach((c) => visit(c as DOMNode));
  return found;
}

const CAPTION_BOILERPLATE =
  /^(?:\s*(?:St-Takla\.org\s*(?:Image)?\s*:?|صورة\s+في\s+موقع\s+الأنبا\s+تكلا\s*:?))+/i;

/** Caption text from an image-wrapper table: the non-image cells, cleaned and
 *  truncated so a compact floated figure doesn't grow a tall caption column. */
function imageTableCaption(el: Element): string {
  const parts: string[] = [];
  const visit = (n: DOMNode) => {
    if (!isElement(n)) return;
    if (n.name === "td" || n.name === "th") {
      if (!tableCellHasImage(n)) {
        const txt = childrenText(n).replace(/\s+/g, " ").trim();
        if (txt) parts.push(txt);
      }
    }
    n.children.forEach((c) => visit(c as DOMNode));
  };
  el.children.forEach((c) => visit(c as DOMNode));
  let caption = parts.join(" ").replace(/\s+/g, " ").trim();
  caption = caption.replace(CAPTION_BOILERPLATE, "").trim();
  if (caption.length > 140) {
    caption = caption.slice(0, 140).replace(/\s+\S*$/, "") + "…";
  }
  return caption;
}

function tableCellHasImage(td: Element): boolean {
  let found = false;
  const visit = (n: DOMNode) => {
    if (found || !isElement(n)) return;
    if (n.name === "img") found = true;
    else n.children.forEach((c) => visit(c as DOMNode));
  };
  td.children.forEach((c) => visit(c as DOMNode));
  return found;
}

function collectTocEntries(el: Element): TocEntry[] {
  const entries: TocEntry[] = [];
  const visit = (n: DOMNode) => {
    if (!isElement(n)) return;
    if (n.name === "a" && (n.attribs.href ?? "").startsWith("#")) {
      const label = childrenText(n).trim();
      if (label) entries.push({ href: n.attribs.href, label });
      return;
    }
    n.children.forEach((c) => visit(c as DOMNode));
  };
  el.children.forEach((c) => visit(c as DOMNode));
  return entries;
}

const HEADING_RE = /^h([1-6])$/;

/** Decorative source-TOC heading: `<hN><span>N- <a>title</a></span></hN>`. */
function isDecorativeTocHeading(el: Element): boolean {
  if (!HEADING_RE.test(el.name)) return false;
  const text = childrenText(el);
  if (!/^\s*\d+\s*[-–]\s/.test(text)) return false;
  // exactly one element descendant chain ending in a single <a>
  const links: Element[] = [];
  const visit = (n: DOMNode) => {
    if (!isElement(n)) return;
    if (n.name === "a") links.push(n);
    n.children.forEach((c) => visit(c as DOMNode));
  };
  el.children.forEach((c) => visit(c as DOMNode));
  return links.length === 1;
}

// ---------------------------------------------------------------------------
// 6. render
// ---------------------------------------------------------------------------

export function renderChapterHtml(raw: string, ctx: RenderCtx): ReactNode {
  const body = extractBody(raw);
  const reAnchored = reAnchor(body);
  const clean = sanitize(reAnchored);
  const pairs = collectPairs(clean);

  // Track first top-level <h1> so we can strip it (page chrome owns the title).
  let strippedLeadingH1 = false;
  let consecutiveBr = 0;

  const options: HTMLReactParserOptions = {
    replace: (domNode) => {
      if (!isElement(domNode)) {
        return undefined;
      }
      const el = domNode;
      const name = el.name;

      // ---- <br> run collapsing (≥3 consecutive -> 1) ----
      if (name === "br") {
        consecutiveBr += 1;
        if (consecutiveBr >= 3) return <Fragment />;
        return undefined;
      }
      consecutiveBr = 0;

      // ---- headings ----
      const hMatch = name.match(HEADING_RE);
      if (hMatch) {
        const level = Number(hMatch[1]);
        const text = childrenText(el);

        // 3.2 decorative source-TOC heading shells / empty shells -> strip
        if (isDecorativeTocHeading(el) || isWhitespace(text)) {
          return <Fragment />;
        }
        // 3.1 leading chapter-title h1 -> strip the first one
        if (level === 1 && !strippedLeadingH1) {
          strippedLeadingH1 = true;
          return <Fragment />;
        }
        // 3.3 demote: top in-body heading becomes h2, never emit body h1
        const demoted = Math.min(level + 1, 6);
        const tag = `h${demoted}`;
        return createElement(
          tag,
          attributesToProps(el.attribs, tag),
          domToReact(childNodes(el), options),
        );
      }

      // ---- standalone images ----
      if (name === "img") {
        const url = imageUrl(el.attribs.src ?? "", ctx);
        if (!url) return <Fragment />;
        return <ContentImage src={url} alt={el.attribs.alt ?? ""} />;
      }

      // ---- tables ----
      if (name === "table") {
        // image-wrapper table -> floated figure (image + short caption)
        if (tableHasImage(el)) {
          const img = firstLocalImage(el, ctx);
          if (!img) return <Fragment />;
          const caption = imageTableCaption(el);
          return (
            <ContentFigure src={img.url} alt={img.alt} caption={caption || undefined} />
          );
        }
        if (isTocTable(el)) {
          const entries = collectTocEntries(el);
          if (entries.length === 0) return <Fragment />;
          const text = childrenText(el);
          const heading = text.includes("محتويات") ? "محتويات" : "Contents";
          return <ChapterToc entries={entries} heading={heading} />;
        }
        if (!tableHasRealCells(el)) return <Fragment />; // empty leftover
        // 3.6 real data table
        return (
          <ContentTable>
            {domToReact(childNodes(el), options)}
          </ContentTable>
        );
      }

      // ---- paragraphs ----
      if (name === "p") {
        const text = childrenText(el);
        // empty paragraph
        if (isWhitespace(text) && !tableHasImage(el)) {
          // also true if it has no element children worth keeping
          const hasMeaningfulChild = childNodes(el).some(
            (c) => isElement(c) && c.name !== "br",
          );
          if (!hasMeaningfulChild) return <Fragment />;
        }
        // "← see other books" floating block
        if (text.trimStart().startsWith("←")) return <Fragment />;
        return undefined;
      }

      // ---- anchors ----
      if (name === "a") {
        const href = el.attribs.href ?? "";
        const id = el.attribs.id;
        const inner = domToReact(childNodes(el), options);

        // bare anchor with only an id (destination) and no href -> keep as span-anchor
        if (!href) {
          if (id) {
            return (
              <a id={id} className="[scroll-margin-top:5rem]">
                {inner}
              </a>
            );
          }
          return <Fragment>{inner}</Fragment>;
        }

        // 3.8 footnote marker / return-link (participates in a 2-target pair)
        if (href.startsWith("#")) {
          const target = href.slice(1);
          if (pairs.footnoteTargets.has(target)) {
            return (
              <FootnoteRef href={href} id={id}>
                {inner}
              </FootnoteRef>
            );
          }
          // plain intra-page anchor (e.g. TOC slug) -> keep as-is
          return (
            <ContentLink kind="anchor" href={href}>
              {inner}
            </ContentLink>
          );
        }

        // 3.9 general link rewriting
        const classified = classifyLink(href, ctx);
        if (!classified) {
          // unresolvable -> drop anchor, keep inner text
          return <Fragment>{inner}</Fragment>;
        }
        return (
          <ContentLink kind={classified.kind} href={classified.href}>
            {inner}
          </ContentLink>
        );
      }

      // ---- span: unwrap (inert) ---- keep default render (cheap, no style)
      return undefined;
    },
  };

  return parse(clean, options);
}

// ---------------------------------------------------------------------------
// 7. chapterPlainText (excerpt/metadata — no React)
// ---------------------------------------------------------------------------

export function chapterPlainText(raw: string, max = 200): string {
  const body = extractBody(raw);
  const text = body
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= max) return text;
  return text.slice(0, max).replace(/\s+\S*$/, "") + "…";
}
