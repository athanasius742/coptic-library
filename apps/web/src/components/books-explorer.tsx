"use client";

import { useMemo, useState } from "react";

import { BookCard } from "@/components/book-card";
import { AUTHOR_NAMES_AR, AUTHOR_NAMES_EN } from "@/lib/author-names";
import { t, type Locale } from "@/lib/i18n";
import type { Book } from "@/lib/types";

type Props = { books: Book[]; locale: Locale };

export function BooksExplorer({ books, locale }: Props) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return books;
    return books.filter((b) => {
      const titleAr = b.title.toLowerCase();
      const titleEn = (b.title_en ?? "").toLowerCase();
      const authorRaw = b.author.toLowerCase();
      const authorAr = (AUTHOR_NAMES_AR[b.authorSlug] ?? "").toLowerCase();
      const authorEn = (AUTHOR_NAMES_EN[b.authorSlug] ?? "").toLowerCase();
      const desc = (b.description ?? "").toLowerCase();
      const descEn = (b.description_en ?? "").toLowerCase();
      return (
        titleAr.includes(needle) ||
        titleEn.includes(needle) ||
        authorRaw.includes(needle) ||
        authorAr.includes(needle) ||
        authorEn.includes(needle) ||
        desc.includes(needle) ||
        descEn.includes(needle)
      );
    });
  }, [q, books]);

  const isAr = locale === "ar";
  const placeholder = t(locale, "books.search.placeholder");

  return (
    <div>
      <div className="relative mx-auto mb-10 max-w-xl">
        <div className={`pointer-events-none absolute inset-y-0 ${isAr ? "right-4" : "left-4"} flex items-center text-gold-600`}>
          <SearchIcon />
        </div>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={placeholder}
          className={`w-full border border-gold-800/80 bg-ink/70 px-4 py-3 ${isAr ? "pr-12" : "pl-12"} ${isAr ? "font-arabic" : "font-body"} text-base text-bone placeholder:text-bone/40 outline-none transition focus:border-gold focus:bg-ink focus:ring-2 focus:ring-gold/30`}
          dir={isAr ? "rtl" : "ltr"}
        />
        <div className="pointer-events-none absolute -bottom-px left-0 right-0 h-px bg-gradient-to-r from-transparent via-gold to-transparent opacity-60" />
      </div>

      <p className={`mb-6 text-center text-xs text-bone/60 ${isAr ? "font-arabic" : "font-body"}`}>
        {filtered.length === books.length
          ? `${books.length} ${t(locale, "books.count.singular.suffix")}`
          : `${filtered.length} ${t(locale, "books.count.of")} ${books.length}`}
      </p>

      <ul className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
        {filtered.map((book) => (
          <li key={`${book.authorSlug}/${book.bookSlug}`}>
            <BookCard book={book} locale={locale} showAuthor />
          </li>
        ))}
      </ul>

      {filtered.length === 0 && (
        <p className={`mt-16 text-center text-sm text-bone/60 ${isAr ? "font-arabic" : "font-body"}`}>
          {t(locale, "books.empty")}
        </p>
      )}
    </div>
  );
}

function SearchIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.6" />
      <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
