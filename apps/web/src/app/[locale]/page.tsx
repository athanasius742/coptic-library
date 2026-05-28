import Link from "next/link";
import { notFound } from "next/navigation";

import { BookCard } from "@/components/book-card";
import { CopticCross } from "@/components/coptic-cross";
import { CrossDivider } from "@/components/ornament";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { loadAllBooks, loadAuthors } from "@/lib/catalog";
import { isLocale, t, type Locale } from "@/lib/i18n";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const isAr = locale === "ar";

  const [books, authors] = await Promise.all([loadAllBooks(), loadAuthors(locale)]);
  const featured = books.slice(0, 8);
  const topAuthors = authors.slice(0, 6);

  return (
    <>
      <SiteHeader locale={locale} />

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.08]"
            style={{
              backgroundImage:
                "repeating-linear-gradient(45deg, var(--color-gold) 0 1px, transparent 1px 18px), repeating-linear-gradient(-45deg, var(--color-gold) 0 1px, transparent 1px 18px)",
            }}
          />
          <div className="mx-auto max-w-5xl px-6 py-20 text-center sm:py-28">
            <div className="mx-auto mb-6 flex items-center justify-center gap-4">
              <span className="h-px w-16 bg-gradient-to-l from-gold to-transparent" />
              <CopticCross size={36} className="text-gold-100" />
              <span className="h-px w-16 bg-gradient-to-r from-gold to-transparent" />
            </div>
            <h1
              className={`text-4xl font-bold leading-tight text-gold-100 sm:text-6xl ${
                isAr ? "font-arabic" : "font-display tracking-wide"
              }`}
            >
              {t(locale, "site.title")}
            </h1>
            <p className="mt-4 font-display text-xs uppercase tracking-[0.45em] text-gold-600">
              {t(locale, "home.hero.eyebrow")}
            </p>
            <p
              className={`mx-auto mt-8 max-w-2xl text-lg leading-relaxed text-bone/85 ${
                isAr ? "font-arabic" : "font-body"
              }`}
            >
              {t(locale, "home.hero.lead")}
            </p>
            <div className="mt-10 flex items-center justify-center gap-4">
              <Link
                href={`/${locale}/books`}
                className={`halo-glow inline-flex items-center gap-2 bg-gradient-to-b from-gold-100 to-gold px-6 py-3 text-sm font-bold text-ink transition hover:from-gold-50 hover:to-gold-100 ${
                  isAr ? "font-arabic" : "font-display tracking-wide"
                }`}
              >
                {t(locale, "home.cta.browseBooks")}
              </Link>
              <Link
                href={`/${locale}/authors`}
                className={`inline-flex items-center gap-2 border border-gold-600 px-6 py-3 text-sm text-gold-100 transition hover:border-gold hover:bg-gold/10 hover:text-gold-50 ${
                  isAr ? "font-arabic" : "font-display tracking-wide"
                }`}
              >
                {t(locale, "home.cta.browseAuthors")}
              </Link>
            </div>

            <div className="mx-auto mt-14 grid max-w-2xl grid-cols-3 gap-px border border-gold-800/70 bg-gold-800/70 text-center">
              <Stat label={t(locale, "home.stat.books")} value={books.length} locale={locale} />
              <Stat label={t(locale, "home.stat.authors")} value={authors.length} locale={locale} />
              <Stat
                label={t(locale, "home.stat.arabic.label")}
                value={t(locale, "home.stat.arabic.value")}
                locale={locale}
              />
            </div>
          </div>
        </section>

        <CrossDivider />

        <section className="mx-auto max-w-6xl px-6">
          <SectionHeading
            eyebrow={t(locale, "home.section.authors.eyebrow")}
            title={t(locale, "home.section.authors.title")}
            href={`/${locale}/authors`}
            cta={t(locale, "home.section.authors.cta")}
            locale={locale}
          />
          <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {topAuthors.map((author) => (
              <li key={author.slug}>
                <Link
                  href={`/${locale}/authors/${author.slug}`}
                  className="group flex h-full flex-col items-center gap-3 border border-gold-800/70 bg-ink/70 p-5 text-center transition hover:border-gold hover:bg-gold/5"
                >
                  <span className="halo-glow inline-flex h-14 w-14 items-center justify-center rounded-full bg-bg text-gold-200 transition group-hover:text-gold-100">
                    <CopticCross size={28} />
                  </span>
                  <span
                    className={`text-sm leading-tight text-gold-50 ${
                      isAr ? "font-arabic" : "font-body"
                    }`}
                  >
                    {author.name}
                  </span>
                  <span className="font-display text-[10px] uppercase tracking-[0.28em] text-gold-600">
                    {author.bookCount} {t(locale, "author.bookCount.short")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <CrossDivider />

        <section className="mx-auto max-w-6xl px-6 pb-20">
          <SectionHeading
            eyebrow={t(locale, "home.section.books.eyebrow")}
            title={t(locale, "home.section.books.title")}
            href={`/${locale}/books`}
            cta={t(locale, "home.section.books.cta")}
            locale={locale}
          />
          <ul className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {featured.map((book) => (
              <li key={`${book.authorSlug}/${book.bookSlug}`}>
                <BookCard book={book} locale={locale} showAuthor />
              </li>
            ))}
          </ul>
        </section>
      </main>

      <SiteFooter locale={locale} />
    </>
  );
}

function Stat({
  label,
  value,
  locale,
}: {
  label: string;
  value: number | string;
  locale: Locale;
}) {
  const isAr = locale === "ar";
  return (
    <div className="bg-bg px-4 py-5">
      <div className="font-display text-3xl font-semibold text-gold-100">{value}</div>
      <div className={`mt-1 text-xs text-bone/70 ${isAr ? "font-arabic" : "font-body"}`}>
        {label}
      </div>
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  href,
  cta,
  locale,
}: {
  eyebrow: string;
  title: string;
  href: string;
  cta: string;
  locale: Locale;
}) {
  const isAr = locale === "ar";
  const arrow = isAr ? "←" : "→";
  return (
    <div className="mb-8 flex items-end justify-between gap-4">
      <div>
        <p className="font-display text-[10px] uppercase tracking-[0.4em] text-gold-600">
          · {eyebrow} ·
        </p>
        <h2
          className={`mt-2 text-2xl font-bold text-gold-50 sm:text-3xl ${
            isAr ? "font-arabic" : "font-display tracking-wide"
          }`}
        >
          {title}
        </h2>
      </div>
      <Link
        href={href}
        className={`hidden whitespace-nowrap border-b border-gold-800/70 pb-0.5 text-sm text-gold-100 transition hover:border-gold hover:text-gold-50 sm:inline-block ${
          isAr ? "font-arabic" : "font-body"
        }`}
      >
        {cta} {arrow}
      </Link>
    </div>
  );
}
