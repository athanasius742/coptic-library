import { notFound } from "next/navigation";

import { BooksExplorer } from "@/components/books-explorer";
import { CrossDivider } from "@/components/ornament";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { loadAllBooks } from "@/lib/catalog";
import { isLocale, t, type Locale } from "@/lib/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) return {};
  return { title: t(rawLocale as Locale, "books.title") };
}

export default async function BooksPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const isAr = locale === "ar";

  const books = await loadAllBooks();
  return (
    <>
      <SiteHeader locale={locale} />
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-14">
        <header className="text-center">
          <p className="font-display text-[10px] uppercase tracking-[0.45em] text-gold-600">
            · {t(locale, "books.eyebrow")} ·
          </p>
          <h1
            className={`mt-3 text-4xl font-bold text-gold-100 sm:text-5xl ${
              isAr ? "font-arabic" : "font-display tracking-wide"
            }`}
          >
            {t(locale, "books.title")}
          </h1>
        </header>
        <CrossDivider />
        <BooksExplorer books={books} locale={locale} />
      </main>
      <SiteFooter locale={locale} />
    </>
  );
}
