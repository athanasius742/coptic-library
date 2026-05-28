import Image from "next/image";
import Link from "next/link";

import { authorDisplayName } from "@/lib/author-names";
import { t, type Locale } from "@/lib/i18n";
import type { Book } from "@/lib/types";

import { CornerOrnament } from "./ornament";

type Props = {
  book: Book;
  locale: Locale;
  showAuthor?: boolean;
};

export function BookCard({ book, locale, showAuthor = false }: Props) {
  const hasEnglish = !!book.title_en && book.title_en.trim().length > 0;
  const useEn = locale === "en" && hasEnglish;
  const displayTitle = useEn ? book.title_en! : book.title;
  const displayAuthor = authorDisplayName(book.authorSlug, book.author, locale);
  const isMissingEn = locale === "en" && !hasEnglish;
  // Titles for Arabic-only books should always render with the Arabic font,
  // even in English mode.
  const titleFontClass = useEn ? "font-body" : "font-arabic";
  const authorFontClass = locale === "en" ? "font-body" : "font-arabic";
  const chapterFontClass = "font-display";

  return (
    <Link
      href={`/${locale}/books/${book.authorSlug}/${book.bookSlug}`}
      className={`group relative block overflow-hidden bg-ink p-4 transition gilt-frame hover:-translate-y-0.5 hover:shadow-[0_0_40px_rgba(201,162,39,0.18)] ${
        isMissingEn ? "opacity-90 grayscale-[40%] hover:opacity-100 hover:grayscale-0" : ""
      }`}
    >
      <CornerOrnament className="pointer-events-none absolute right-2 top-2 h-6 w-6 text-gold-600/70" />
      <CornerOrnament className="pointer-events-none absolute bottom-2 left-2 h-6 w-6 -scale-100 text-gold-600/70" />

      <div className="relative mx-auto aspect-[2/3] w-full max-w-[180px] overflow-hidden bg-bg ring-1 ring-gold-800">
        <Image
          src={book.coverPath}
          alt={displayTitle}
          fill
          sizes="(min-width: 1024px) 180px, 40vw"
          className="object-cover transition duration-500 group-hover:scale-[1.03]"
        />
        <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-gold/20" />
        {isMissingEn && (
          <>
            <div className="pointer-events-none absolute inset-0 bg-ink/55" />
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <span
                className="border-2 border-ink bg-gradient-to-b from-gold-100 to-gold px-3 py-1.5 text-center font-display text-[11px] font-bold uppercase tracking-[0.22em] leading-tight text-ink shadow-[0_0_0_2px_var(--color-gold-100),0_6px_18px_rgba(0,0,0,0.55)]"
              >
                {t(locale, "books.notAvailableEn")}
              </span>
            </div>
          </>
        )}
      </div>

      <div className="mt-4 text-center">
        <h3
          className={`line-clamp-3 text-base leading-snug text-gold-50 transition group-hover:text-gold-100 ${titleFontClass}`}
        >
          {displayTitle}
        </h3>
        {showAuthor && (
          <p className={`mt-1 text-xs text-bone/70 ${authorFontClass}`}>
            {displayAuthor}
          </p>
        )}
        {book.chapterCount > 0 && (
          <p
            className={`mt-2 text-[10px] uppercase tracking-[0.28em] text-gold-600 ${chapterFontClass}`}
          >
            {book.chapterCount} {locale === "ar" ? "فصول" : "chapters"}
          </p>
        )}
      </div>
    </Link>
  );
}
