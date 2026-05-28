import Link from "next/link";
import { notFound } from "next/navigation";

import { AuthorAvatar } from "@/components/author-avatar";
import { BookCard } from "@/components/book-card";
import { CrossDivider } from "@/components/ornament";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { loadAuthorInfo } from "@/lib/authors-meta";
import { loadAuthorBooks, loadAuthors } from "@/lib/catalog";
import { isLocale, t, type Locale } from "@/lib/i18n";

type Params = { locale: string; slug: string };

export async function generateMetadata({ params }: { params: Promise<Params> }) {
  const { locale: rawLocale, slug } = await params;
  if (!isLocale(rawLocale)) return {};
  const locale: Locale = rawLocale;
  const authors = await loadAuthors(locale);
  const author = authors.find((a) => a.slug === slug);
  return { title: author ? author.name : t(locale, "common.notFound.author") };
}

export default async function AuthorPage({ params }: { params: Promise<Params> }) {
  const { locale: rawLocale, slug } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const isAr = locale === "ar";

  const [authors, books, info] = await Promise.all([
    loadAuthors(locale),
    loadAuthorBooks(slug),
    loadAuthorInfo(slug),
  ]);
  const author = authors.find((a) => a.slug === slug);
  if (!author) notFound();

  const bio = isAr ? info?.bio_ar : info?.bio_en;

  return (
    <>
      <SiteHeader locale={locale} />
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-14">
        <nav className={`mb-8 text-sm text-bone/60 ${isAr ? "font-arabic" : "font-body"}`}>
          <Link href={`/${locale}/authors`} className="hover:text-gold-100">
            {t(locale, "nav.authors")}
          </Link>{" "}
          <span className="mx-2 text-gold-800">/</span>{" "}
          <span className="text-gold-100">{author.name}</span>
        </nav>

        <header className="text-center">
          <div className="mb-6 flex justify-center">
            <AuthorAvatar
              slug={author.slug}
              name={author.name}
              size={160}
              portraitPath={author.portraitPath}
            />
          </div>
          <p className="font-display text-[10px] uppercase tracking-[0.45em] text-gold-600">
            {t(locale, "author.eyebrow")}
          </p>
          <h1
            className={`mt-3 text-4xl font-bold text-gold-100 sm:text-5xl ${
              isAr ? "font-arabic" : "font-display tracking-wide"
            }`}
          >
            {author.name}
          </h1>
          <p className={`mt-3 text-sm text-bone/70 ${isAr ? "font-arabic" : "font-body"}`}>
            {author.bookCount} {t(locale, "author.subtitle.suffix")}
          </p>
          {bio && (
            <p
              className={`mx-auto mt-5 max-w-2xl text-sm leading-relaxed text-bone/80 ${
                isAr ? "font-arabic" : "font-body"
              }`}
            >
              {bio}
            </p>
          )}
        </header>

        <CrossDivider />

        <ul className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
          {books.map((book) => (
            <li key={`${book.authorSlug}/${book.bookSlug}`}>
              <BookCard book={book} locale={locale} />
            </li>
          ))}
        </ul>
      </main>
      <SiteFooter locale={locale} />
    </>
  );
}
