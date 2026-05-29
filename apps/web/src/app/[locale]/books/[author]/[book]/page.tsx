import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ContinueReadingCta } from "@/components/continue-reading-cta";
import { CopticCross } from "@/components/coptic-cross";
import { EpubInfo } from "@/components/epub-info";
import { CornerOrnament, CrossDivider } from "@/components/ornament";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { bookDisplay, loadAuthors, loadBook, loadChapters } from "@/lib/catalog";
import { isLocale, t, type Locale } from "@/lib/i18n";

type Params = { locale: string; author: string; book: string };

export async function generateMetadata({ params }: { params: Promise<Params> }) {
  const { locale: rawLocale, author, book } = await params;
  if (!isLocale(rawLocale)) return {};
  const locale: Locale = rawLocale;
  const meta = await loadBook(author, book);
  if (!meta) return { title: t(locale, "common.notFound.book") };
  const display = bookDisplay(meta, locale);
  return { title: display.title };
}

export default async function BookPage({ params }: { params: Promise<Params> }) {
  const { locale: rawLocale, author, book } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const isAr = locale === "ar";

  const [meta, chapters, authors] = await Promise.all([
    loadBook(author, book),
    loadChapters(author, book),
    loadAuthors(locale),
  ]);
  if (!meta) notFound();
  const authorEntry = authors.find((a) => a.slug === meta.authorSlug);
  const display = bookDisplay(meta, locale);

  // In English mode, if the book has no English translation we still render
  // the page but flag it with a banner and use the Arabic title in the
  // Amiri font.
  const titleIsArabic = locale === "ar" || !display.hasEnglish;
  const titleFontClass = titleIsArabic ? "font-arabic" : "font-display tracking-wide";
  const uiFontClass = isAr ? "font-arabic" : "font-body";

  // The book's own content language drives direction and font for content
  // strings (title, description, chapter titles) independently of UI locale.
  const bookIsLatin = meta.language === "en";
  const bookDir: "ltr" | "rtl" = bookIsLatin ? "ltr" : "rtl";
  const bookFontClass = bookIsLatin ? "font-body" : "font-arabic";

  return (
    <>
      <SiteHeader locale={locale} />
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-14">
        <nav className={`mb-8 text-sm text-bone/60 ${uiFontClass}`}>
          <Link href={`/${locale}/books`} className="hover:text-gold-100">
            {t(locale, "nav.books")}
          </Link>{" "}
          <span className="mx-2 text-gold-800">/</span>{" "}
          <Link href={`/${locale}/authors/${meta.authorSlug}`} className="hover:text-gold-100">
            {authorEntry?.name ?? display.authorName}
          </Link>{" "}
          <span className="mx-2 text-gold-800">/</span>{" "}
          <span className="text-gold-100">{display.title}</span>
        </nav>

        {locale === "en" && !display.hasEnglish && (
          <div className="mb-8 border border-gold-800/70 bg-ink/70 px-5 py-4">
            <p className="font-display text-xs uppercase tracking-[0.32em] text-gold-100">
              {t(locale, "book.arabicOnlyBanner.title")}
            </p>
            <p className="mt-2 font-body text-sm text-bone/80">
              {t(locale, "book.arabicOnlyBanner.body")}
            </p>
          </div>
        )}

        <article className="relative grid gap-10 md:grid-cols-[260px_1fr]">
          {/* Cover panel */}
          <aside className="relative">
            <div className="gilt-frame relative mx-auto aspect-[2/3] w-full max-w-[260px] overflow-hidden bg-ink p-2">
              <CornerOrnament className="pointer-events-none absolute right-2 top-2 z-10 h-7 w-7 text-gold-600/80" />
              <CornerOrnament className="pointer-events-none absolute bottom-2 left-2 z-10 h-7 w-7 -scale-100 text-gold-600/80" />
              <div className="relative h-full w-full overflow-hidden">
                <Image
                  src={meta.coverPath}
                  alt={display.title}
                  fill
                  sizes="260px"
                  className="object-cover"
                />
                <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-gold/30" />
              </div>
            </div>

            {meta.epub && (
              <div className="mt-6 flex items-stretch gap-3">
                <a
                  href={`/api/epub/${meta.authorSlug}/${meta.bookSlug}`}
                  className={`halo-glow inline-flex flex-1 items-center justify-center gap-3 bg-gradient-to-b from-gold-100 to-gold px-5 py-3 text-sm font-bold text-ink transition hover:from-gold-50 hover:to-gold-100 ${uiFontClass}`}
                >
                  <DownloadIcon /> {t(locale, "book.downloadEpub")}
                </a>
                <EpubInfo locale={locale} />
              </div>
            )}
            <a
              href={meta.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className={`mt-3 inline-flex w-full items-center justify-center gap-2 border border-gold-800 px-5 py-2.5 text-sm text-gold-100 transition hover:border-gold hover:bg-gold/10 ${uiFontClass}`}
            >
              {t(locale, "book.sourceLink")}
            </a>
          </aside>

          {/* Meta panel */}
          <section>
            <p
              className={`text-gold-600 ${
                isAr
                  ? "font-ruqaa text-base"
                  : "font-display text-[10px] uppercase tracking-[0.45em]"
              }`}
            >
              {t(locale, "book.fromSource.prefix")} {meta.source} {t(locale, "book.fromSource.suffix")}
            </p>
            <h1
              className={`mt-3 text-3xl font-bold leading-tight text-gold-100 sm:text-4xl ${titleFontClass}`}
              dir={titleIsArabic ? bookDir : undefined}
            >
              {display.title}
            </h1>
            <p
              className={`mt-4 text-base text-bone/85 ${bookFontClass}`}
              dir={bookDir}
            >
              {display.author}
            </p>

            {display.description && (
              <p
                className={`mt-6 text-base leading-relaxed text-bone/90 ${bookFontClass}`}
                dir={bookDir}
              >
                {display.description}
              </p>
            )}

            <dl className={`mt-8 grid grid-cols-2 gap-3 border-y border-gold-800/60 py-5 text-sm ${uiFontClass}`}>
              <Field
                label={t(locale, "book.field.chapters")}
                value={String(chapters.length || meta.chapterCount || "—")}
                locale={locale}
              />
              <Field
                label={t(locale, "book.field.language")}
                value={
                  meta.language === "ar"
                    ? t(locale, "book.field.language.ar")
                    : meta.language === "en"
                      ? t(locale, "book.field.language.en")
                      : meta.language || "—"
                }
                locale={locale}
              />
              {display.series && (
                <Field label={t(locale, "book.field.series")} value={display.series} locale={locale} />
              )}
              <Field label={t(locale, "book.field.source")} value={meta.source} locale={locale} />
            </dl>
          </section>
        </article>

        {chapters.length > 0 && (
          <>
            <CrossDivider />
            <section>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p
                    className={`text-gold-600 ${
                      isAr
                        ? "font-ruqaa text-base"
                        : "font-display text-[10px] uppercase tracking-[0.4em]"
                    }`}
                  >
                    {t(locale, "book.toc.eyebrow")}
                  </p>
                  <h2
                    className={`mt-2 text-2xl font-bold text-gold-50 ${
                      isAr ? "font-arabic" : "font-display tracking-wide"
                    }`}
                  >
                    {t(locale, "book.toc.title")}
                  </h2>
                </div>
                <CopticCross size={28} className="text-gold-200" />
              </div>

              {chapters.length > 0 && (
                <ContinueReadingCta
                  locale={locale}
                  authorSlug={meta.authorSlug}
                  bookSlug={meta.bookSlug}
                  firstChapterSlug={chapters[0].slug}
                  uiFontClass={uiFontClass}
                />
              )}
              <ol className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {chapters.map((ch) => (
                  <li
                    key={`${ch.order}-${ch.slug}`}
                    className="group flex items-baseline gap-3 border-b border-gold-800/40 py-3"
                  >
                    <span className="font-display text-xs text-gold-600">
                      {String(ch.order).padStart(2, "0")}
                    </span>
                    <Link
                      href={`/${locale}/books/${meta.authorSlug}/${meta.bookSlug}/${ch.slug}`}
                      className={`${bookFontClass} text-sm leading-snug text-bone transition group-hover:text-gold-100`}
                      dir={bookDir}
                    >
                      {ch.title}
                    </Link>
                  </li>
                ))}
              </ol>
            </section>
          </>
        )}
      </main>
      <SiteFooter locale={locale} />
    </>
  );
}

function Field({
  label,
  value,
  locale,
}: {
  label: string;
  value: string;
  locale: Locale;
}) {
  const isAr = locale === "ar";
  return (
    <div>
      <dt
        className={`text-gold-600 ${
          isAr
            ? "font-arabic text-xs"
            : "font-display text-[10px] uppercase tracking-[0.32em]"
        }`}
      >
        {label}
      </dt>
      <dd className="mt-1 text-bone">{value}</dd>
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 4v12m0 0 4-4m-4 4-4-4M5 20h14"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
