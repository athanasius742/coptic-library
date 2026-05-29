import Image from "next/image";
import Link from "next/link";

import { authorDisplayName } from "@/lib/author-names";
import { t, type Locale } from "@/lib/i18n";
import { overallPercent, type ReadingProgress } from "@/lib/reading-progress";

const toArabicDigits = (n: number | string) =>
  String(n).replace(/[0-9]/g, (d) => "٠١٢٣٤٥٦٧٨٩"[Number(d)]);

/**
 * Presentational "continue reading" card — cover + book/chapter + a progress
 * bar, linking to the CURRENT chapter (resume), not the book index. Reads
 * nothing from storage; it's handed one denormalized ReadingProgress record by
 * the shelf. Reuses BookCard's gilt-frame / token styling so it themes for free
 * and orients by the UI `locale` (book-language only drives the title/chapter
 * font, exactly like BookCard).
 */
export function CurrentlyReadingCard({
  rec,
  locale,
}: {
  rec: ReadingProgress;
  locale: Locale;
}) {
  const isAr = locale === "ar";
  const hasEnglish = !!rec.bookTitleEn && rec.bookTitleEn.trim().length > 0;
  const useEn = locale === "en" && hasEnglish;
  const displayTitle = useEn ? rec.bookTitleEn! : rec.bookTitle;
  const displayAuthor = authorDisplayName(rec.authorSlug, rec.author, locale);

  // Title/chapter font follows the book's own language (Arabic-only books keep
  // the Arabic font even under an English UI), like BookCard.
  const bookIsLatin = rec.language === "en";
  const titleFontClass = bookIsLatin && useEn ? "font-body" : "font-arabic";
  const authorFontClass = locale === "en" ? "font-body" : "font-arabic";

  const percent = overallPercent(rec);
  const percentLabel = isAr ? `٪${toArabicDigits(percent)}` : `${percent}%`;
  const chapterNo = isAr ? toArabicDigits(rec.chapterIndex + 1) : rec.chapterIndex + 1;
  const totalNo = isAr ? toArabicDigits(rec.totalChapters) : rec.totalChapters;

  const href = `/${locale}/books/${rec.authorSlug}/${rec.bookSlug}/${rec.chapterSlug}`;

  return (
    <Link
      href={href}
      className="group relative flex gap-4 overflow-hidden bg-ink p-4 transition gilt-frame hover:-translate-y-0.5 hover:shadow-[0_0_40px_rgba(201,162,39,0.18)]"
    >
      <div className="relative aspect-[2/3] w-20 shrink-0 overflow-hidden bg-bg ring-1 ring-gold-800">
        <Image
          src={rec.coverPath}
          alt={displayTitle}
          fill
          sizes="80px"
          className="object-cover transition duration-500 group-hover:scale-[1.03]"
        />
        <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-gold/20" />
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <h3
          className={`line-clamp-2 text-base leading-snug text-gold-50 transition group-hover:text-gold-100 ${titleFontClass}`}
        >
          {displayTitle}
        </h3>
        <p className={`mt-1 truncate text-xs text-bone/70 ${authorFontClass}`}>
          {displayAuthor}
        </p>

        <p
          className={`mt-2 text-gold-600 ${
            isAr
              ? "font-arabic text-xs"
              : "font-display text-[10px] uppercase tracking-[0.22em]"
          }`}
        >
          {t(locale, "reading.progress.chapter")} {chapterNo}{" "}
          {t(locale, "reading.progress.of")} {totalNo}
        </p>

        {/* Progress bar */}
        <div className="mt-auto pt-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-gold-800/40">
            <div
              className="h-full rounded-full bg-gradient-to-r from-gold-600 to-gold-100"
              style={{ inlineSize: `${percent}%` }}
            />
          </div>
          <div className="mt-1.5 flex items-center justify-between">
            <span
              className={`text-gold-600 ${
                isAr ? "font-arabic text-[11px]" : "font-display text-[10px] tracking-wide"
              }`}
            >
              {percentLabel}
            </span>
            <span
              className={`text-gold-200 transition group-hover:text-gold-50 ${
                isAr ? "font-arabic text-[11px]" : "font-body text-[11px]"
              }`}
            >
              {t(locale, "reading.progress.resume")}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}
