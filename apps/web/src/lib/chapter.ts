import "server-only";

import { cache } from "react";
import { promises as fs } from "node:fs";
import path from "node:path";

import { bookDirAbsolute, loadBookKeys, loadChapters } from "./catalog";
import type { Locale } from "./i18n";
import type { Chapter } from "./types";

export type ChapterContent = {
  title: string;
  html: string;
  excerpt: string;
  orderSlug: string;
  index: number;
  prev: Chapter | null;
  next: Chapter | null;
};

const STTAKLA_ORIGIN = "https://st-takla.org";

function orderSlugDirname(ch: Chapter): string {
  // manifest "file": "01-introduction.html" → directory "01-introduction"
  return ch.file.replace(/\.html?$/i, "");
}

/**
 * Resolve a relative href into an absolute URL against the chapter's source URL.
 * Returns null if URL construction fails.
 */
function resolveHref(href: string, chapterUrl: string): URL | null {
  try {
    return new URL(href, chapterUrl);
  } catch {
    return null;
  }
}

/**
 * If the resolved URL points to a book file on st-takla.org that we have in
 * our catalog, return its internal path (without locale prefix). Otherwise
 * return null. Handles both `/books/<author>/<book>/...` and
 * `/books/en/<author>/<book>/...` source layouts.
 */
function rewriteToInternal(
  resolved: URL,
  bookKeys: Set<string>,
): { authorSlug: string; bookSlug: string; chapterSlug: string | null } | null {
  if (resolved.hostname !== "st-takla.org" && resolved.hostname !== "www.st-takla.org") {
    return null;
  }
  // Strip leading slash and split.
  const parts = resolved.pathname.replace(/^\/+/, "").split("/");
  if (parts[0] !== "books") return null;
  // Drop optional "en" locale segment in the source URL.
  let i = 1;
  if (parts[i] === "en") i += 1;
  const authorSlug = parts[i];
  const bookSlug = parts[i + 1];
  const file = parts[i + 2];
  if (!authorSlug || !bookSlug || !file) return null;
  if (!bookKeys.has(`${authorSlug}/${bookSlug}`)) return null;

  // File-level segment may itself contain further path bits we don't care about.
  const fileBase = file.replace(/\.html?$/i, "");
  const chapterSlug = fileBase === "index" ? null : fileBase;
  return { authorSlug, bookSlug, chapterSlug };
}

function transformHtml(
  raw: string,
  ctx: {
    chapterUrl: string;
    locale: Locale;
    bookKeys: Set<string>;
  },
): string {
  const { chapterUrl, locale, bookKeys } = ctx;

  // Strip everything outside <body>
  const bodyMatch = raw.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  let html = bodyMatch ? bodyMatch[1] : raw;

  // Remove the leading <h1>...</h1> — we render the title in our page chrome
  html = html.replace(/^\s*<h1[^>]*>[\s\S]*?<\/h1>/i, "");
  // Strip <font>/<center>/<basefont> wrappers, keep content
  html = html.replace(/<\/?(?:font|center|basefont)[^>]*>/gi, "");
  // Strip nested decorative <h1>/<h3> blocks left over from the source TOC
  html = html.replace(/<h1[^>]*>\s*<span>\s*\d+[-–]\s*<a[^>]*>[\s\S]*?<\/a>\s*<\/span>\s*<\/h1>/gi, "");
  html = html.replace(/<h3[^>]*>\s*<\/h3>/gi, "");
  // Strip inline event handlers
  html = html.replace(/\son[a-z]+="[^"]*"/gi, "");
  // Chapter images were not extracted locally. Drop any <table> whose body
  // contains an `images/...` reference (these are decorative image+caption blocks
  // wrapping links back to st-takla.org's Gallery).
  html = html.replace(/<table\b[^>]*>[\s\S]*?<\/table>/gi, (match) =>
    /src=(["'])(?:\.\/)?images\//i.test(match) ? "" : match,
  );
  // Drop any stray <img src="images/..."> outside of tables
  html = html.replace(/<img\b[^>]*src=(["'])(?:\.\/)?images\/[^"']+\1[^>]*\/?>/gi, "");
  // Strip the floating "← see other books" link blocks
  html = html.replace(/<p[^>]*>\s*←[\s\S]*?<\/p>/gi, "");

  // Rewrite anchors:
  //  - http(s) absolute URLs: open in new tab.
  //  - Relative paths: resolve against chapterUrl. If they land on a book in our
  //    catalog, emit an internal /{locale}/books/... route. Otherwise emit an
  //    external st-takla.org link.
  html = html.replace(
    /<a\b([^>]*?)href=(["'])([^"']+)\2([^>]*)>([\s\S]*?)<\/a>/gi,
    (_full, _pre, _q, href: string, _post, inner: string) => {
      const isAbsolute = /^https?:\/\//i.test(href);
      const isAnchor = href.startsWith("#");
      if (isAnchor) {
        const safeAnchor = href.replace(/"/g, "&quot;");
        return `<a href="${safeAnchor}">${inner}</a>`;
      }

      const resolved = resolveHref(href, chapterUrl);
      if (resolved) {
        const internal = rewriteToInternal(resolved, bookKeys);
        if (internal) {
          const base = `/${locale}/books/${internal.authorSlug}/${internal.bookSlug}`;
          const target = internal.chapterSlug ? `${base}/${internal.chapterSlug}` : base;
          return `<a href="${target}">${inner}</a>`;
        }
      }

      if (isAbsolute && resolved) {
        const safe = resolved.toString().replace(/"/g, "&quot;");
        return `<a href="${safe}" target="_blank" rel="noopener noreferrer">${inner}</a>`;
      }
      if (resolved) {
        const safe = resolved.toString().replace(/"/g, "&quot;");
        return `<a href="${safe}" target="_blank" rel="noopener noreferrer">${inner}</a>`;
      }
      // Unresolvable / weird href — drop the anchor but keep its text.
      return inner;
    },
  );

  // Strip empty paragraphs left after cleaning
  html = html.replace(/<p[^>]*>\s*(?:&nbsp;|\s)*<\/p>/gi, "");
  // Strip stylesheet references
  html = html.replace(/<link[^>]*>/gi, "");
  return html.trim();
}

function plainTextExcerpt(html: string, max = 200): string {
  const text = html
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= max) return text;
  return text.slice(0, max).replace(/\s+\S*$/, "") + "…";
}

export const loadChapterContent = cache(async (
  authorSlug: string,
  bookSlug: string,
  chapterSlug: string,
  locale: Locale = "ar",
): Promise<ChapterContent | null> => {
  const [chapters, bookKeys] = await Promise.all([
    loadChapters(authorSlug, bookSlug),
    loadBookKeys(),
  ]);
  const index = chapters.findIndex((c) => c.slug === chapterSlug);
  if (index < 0) return null;
  const ch = chapters[index];
  const orderSlug = orderSlugDirname(ch);
  const filePath = path.join(
    bookDirAbsolute(authorSlug, bookSlug),
    "chapters",
    orderSlug,
    "content.xhtml",
  );
  let raw: string;
  try {
    raw = await fs.readFile(filePath, "utf8");
  } catch {
    return null;
  }
  // Some manifests may carry a missing/odd `url`; fall back to a synthesized
  // st-takla.org path so `new URL(href, base)` still resolves consistently.
  const chapterUrl =
    ch.url && /^https?:\/\//i.test(ch.url)
      ? ch.url
      : `${STTAKLA_ORIGIN}/books/${authorSlug}/${bookSlug}/${ch.file}`;

  const html = transformHtml(raw, { chapterUrl, locale, bookKeys });
  return {
    title: ch.title,
    html,
    excerpt: plainTextExcerpt(html),
    orderSlug,
    index,
    prev: index > 0 ? chapters[index - 1] : null,
    next: index < chapters.length - 1 ? chapters[index + 1] : null,
  };
});
