import "server-only";

import { cache } from "react";
import { promises as fs } from "node:fs";
import path from "node:path";

import { authorDisplayName, cleanAuthorName } from "./author-names";
import { loadAllAuthorInfos, resolveAuthorPortrait } from "./authors-meta";
import type { Locale } from "./i18n";
import type { Author, Book, BookMeta, CatalogEntry, Chapter } from "./types";

const REPO_ROOT = path.resolve(process.cwd(), "..", "..");
const BOOKS_ROOT = path.join(REPO_ROOT, "books");
const CATALOG_PATH = path.join(REPO_ROOT, "tools", "catalog.json");

async function readJson<T>(filePath: string): Promise<T> {
  const raw = await fs.readFile(filePath, "utf8");
  return JSON.parse(raw) as T;
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

export const loadCatalog = cache(async (): Promise<CatalogEntry[]> => {
  const entries = await readJson<CatalogEntry[]>(CATALOG_PATH);
  return entries.filter((e) => e.status === "verified");
});

export const loadAllBooks = cache(async (): Promise<Book[]> => {
  const catalog = await loadCatalog();
  const books: Book[] = [];
  for (const entry of catalog) {
    const metaPath = path.join(REPO_ROOT, entry.dest, "meta.json");
    if (!(await fileExists(metaPath))) continue;
    const meta = await readJson<BookMeta>(metaPath);
    books.push({
      ...meta,
      author: cleanAuthorName(meta.author),
      authorSlug: entry.author_slug,
      bookSlug: entry.book_slug,
      chapterCount: entry.chapter_links_guess,
      coverPath: `/api/cover/${entry.author_slug}/${entry.book_slug}`,
    });
  }
  return books;
});

/**
 * Fast lookup set of "<authorSlug>/<bookSlug>" keys for everything in our catalog.
 * Used to decide whether an external-looking st-takla link points back into our
 * own library and should be rewritten to an internal route.
 */
export const loadBookKeys = cache(async (): Promise<Set<string>> => {
  const books = await loadAllBooks();
  return new Set(books.map((b) => `${b.authorSlug}/${b.bookSlug}`));
});

export const loadAuthors = cache(async (locale: Locale = "ar"): Promise<Author[]> => {
  const books = await loadAllBooks();
  const infos = await loadAllAuthorInfos();
  const byAuthor = new Map<string, number>();
  for (const b of books) {
    byAuthor.set(b.authorSlug, (byAuthor.get(b.authorSlug) ?? 0) + 1);
  }
  return Array.from(byAuthor.entries())
    .map(([slug, count]) => ({
      slug,
      name: authorDisplayName(
        slug,
        books.find((b) => b.authorSlug === slug)?.author ?? slug,
        locale,
      ),
      bookCount: count,
      portraitPath: resolveAuthorPortrait(slug, infos).path,
    }))
    .sort((a, b) => b.bookCount - a.bookCount);
});

export const loadAuthorBooks = cache(async (authorSlug: string): Promise<Book[]> => {
  const all = await loadAllBooks();
  return all
    .filter((b) => b.authorSlug === authorSlug)
    .sort((a, b) => a.title.localeCompare(b.title, "ar"));
});

export const loadBook = cache(async (authorSlug: string, bookSlug: string): Promise<Book | null> => {
  const all = await loadAllBooks();
  return all.find((b) => b.authorSlug === authorSlug && b.bookSlug === bookSlug) ?? null;
});

export const loadChapters = cache(async (authorSlug: string, bookSlug: string): Promise<Chapter[]> => {
  const manifestPath = path.join(BOOKS_ROOT, "st-takla.org", authorSlug, bookSlug, "manifest.json");
  if (!(await fileExists(manifestPath))) return [];
  const all = await readJson<Chapter[]>(manifestPath);
  // The "index" entry (order 0) is the source-site TOC page; no chapter
  // content was extracted for it, so omit it from in-app navigation.
  return all.filter((c) => !(c.order === 0 && c.slug === "index"));
});

export function bookDirAbsolute(authorSlug: string, bookSlug: string): string {
  return path.join(BOOKS_ROOT, "st-takla.org", authorSlug, bookSlug);
}

/**
 * Display fields for a book in the active locale. If English is requested but
 * the meta has no `*_en` entry, returns the Arabic strings as a fallback so
 * the page still has something to render.
 */
export function bookDisplay(
  book: Book,
  locale: Locale,
): {
  title: string;
  author: string;
  description: string | undefined;
  series: string | undefined;
  hasEnglish: boolean;
  authorName: string;
} {
  const hasEnglish = locale === "en" && !!book.title_en && book.title_en.trim().length > 0;
  const useEn = locale === "en" && hasEnglish;
  return {
    title: useEn ? book.title_en! : book.title,
    author:
      useEn && book.author_en && book.author_en.trim().length > 0
        ? book.author_en
        : book.author,
    description:
      useEn && book.description_en && book.description_en.trim().length > 0
        ? book.description_en
        : locale === "ar"
          ? book.description
          : book.description, // English mode without translation falls back to Arabic
    series:
      useEn && book.series_en && book.series_en.trim().length > 0
        ? book.series_en
        : book.series,
    hasEnglish,
    authorName: authorDisplayName(book.authorSlug, book.author, locale),
  };
}
