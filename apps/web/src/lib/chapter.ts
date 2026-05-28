import "server-only";

import { cache } from "react";
import { promises as fs } from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";

import { bookDirAbsolute, loadBookKeys, loadChapters } from "./catalog";
import type { Locale } from "./i18n";
import { chapterPlainText, renderChapterHtml } from "./render-content";
import type { Chapter } from "./types";

export type ChapterContent = {
  title: string;
  node: ReactNode;
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

  const node = renderChapterHtml(raw, { chapterUrl, locale, bookKeys });
  return {
    title: ch.title,
    node,
    excerpt: chapterPlainText(raw),
    orderSlug,
    index,
    prev: index > 0 ? chapters[index - 1] : null,
    next: index < chapters.length - 1 ? chapters[index + 1] : null,
  };
});
