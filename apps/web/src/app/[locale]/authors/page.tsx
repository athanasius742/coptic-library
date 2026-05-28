import Link from "next/link";
import { notFound } from "next/navigation";

import { AuthorAvatar } from "@/components/author-avatar";
import { CrossDivider } from "@/components/ornament";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { loadAuthors } from "@/lib/catalog";
import { isLocale, t, type Locale } from "@/lib/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) return {};
  return { title: t(rawLocale as Locale, "authors.title") };
}

export default async function AuthorsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const isAr = locale === "ar";

  const authors = await loadAuthors(locale);
  const subtitle = `${authors.length} ${t(locale, "authors.subtitle.suffix")}`;

  return (
    <>
      <SiteHeader locale={locale} />
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-14">
        <PageTitle
          eyebrow={t(locale, "authors.eyebrow")}
          title={t(locale, "authors.title")}
          subtitle={subtitle}
          locale={locale}
        />
        <CrossDivider />
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {authors.map((a) => (
            <li key={a.slug}>
              <Link
                href={`/${locale}/authors/${a.slug}`}
                className="group flex items-center justify-between gap-4 border border-gold-800/70 bg-ink/60 px-5 py-4 transition hover:border-gold hover:bg-gold/5"
              >
                <span className="flex items-center gap-4">
                  <AuthorAvatar
                    slug={a.slug}
                    name={a.name}
                    size={40}
                    portraitPath={a.portraitPath}
                  />
                  <span className={`text-base text-gold-50 ${isAr ? "font-arabic" : "font-body"}`}>
                    {a.name}
                  </span>
                </span>
                <span className="font-display text-[10px] uppercase tracking-[0.32em] text-gold-600">
                  {a.bookCount}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </main>
      <SiteFooter locale={locale} />
    </>
  );
}

function PageTitle({
  eyebrow,
  title,
  subtitle,
  locale,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  locale: Locale;
}) {
  const isAr = locale === "ar";
  return (
    <div className="text-center">
      <p className="font-display text-[10px] uppercase tracking-[0.45em] text-gold-600">
        · {eyebrow} ·
      </p>
      <h1
        className={`mt-3 text-4xl font-bold text-gold-100 sm:text-5xl ${
          isAr ? "font-arabic" : "font-display tracking-wide"
        }`}
      >
        {title}
      </h1>
      {subtitle && (
        <p className={`mt-3 text-sm text-bone/70 ${isAr ? "font-arabic" : "font-body"}`}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
