import Link from "next/link";
import { notFound } from "next/navigation";

import { CopticCross } from "@/components/coptic-cross";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { ScrollArea } from "@/components/ui/scroll-area";
import { bookDisplay, loadAuthors, loadBook, loadChapters } from "@/lib/catalog";
import { loadChapterContent } from "@/lib/chapter";
import { isLocale, t, type Locale } from "@/lib/i18n";

type Params = { locale: string; author: string; book: string; chapter: string };

const toArabicDigits = (n: number) =>
  String(n).replace(/[0-9]/g, (d) => "٠١٢٣٤٥٦٧٨٩"[Number(d)]);

export async function generateMetadata({ params }: { params: Promise<Params> }) {
  const { locale: rawLocale, author, book, chapter } = await params;
  if (!isLocale(rawLocale)) return {};
  const locale: Locale = rawLocale;
  const [meta, content] = await Promise.all([
    loadBook(author, book),
    loadChapterContent(author, book, chapter, locale),
  ]);
  if (!meta || !content) return { title: t(locale, "common.notFound.chapter") };
  const display = bookDisplay(meta, locale);
  return {
    title: `${content.title} · ${display.title}`,
    description: content.excerpt,
    openGraph: {
      title: `${content.title} · ${display.title}`,
      description: content.excerpt,
      type: "article",
      locale: locale === "ar" ? "ar_EG" : "en_US",
    },
  };
}

export default async function ChapterPage({ params }: { params: Promise<Params> }) {
  const { locale: rawLocale, author, book, chapter } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const isAr = locale === "ar";

  const [meta, chapters, content, authors] = await Promise.all([
    loadBook(author, book),
    loadChapters(author, book),
    loadChapterContent(author, book, chapter, locale),
    loadAuthors(locale),
  ]);
  if (!meta || !content) notFound();
  const authorEntry = authors.find((a) => a.slug === meta.authorSlug);
  const display = bookDisplay(meta, locale);
  const uiFontClass = isAr ? "font-arabic" : "font-body";

  // The book content's own language drives direction + font for the chapter
  // title, sidebar TOC, prev/next titles, and the prose body — independent
  // of the UI locale.
  const bookIsLatin = meta.language === "en";
  const bookDir: "ltr" | "rtl" = bookIsLatin ? "ltr" : "rtl";
  const bookFontClass = bookIsLatin ? "font-body" : "font-arabic";

  return (
    <>
      <SiteHeader locale={locale} />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10 sm:px-6 lg:py-14">
        <nav className={`mb-6 text-sm text-bone/60 ${uiFontClass}`}>
          <Link href={`/${locale}/books`} className="hover:text-gold-100">
            {t(locale, "nav.books")}
          </Link>{" "}
          <span className="mx-2 text-gold-800">/</span>{" "}
          <Link
            href={`/${locale}/authors/${meta.authorSlug}`}
            className="hover:text-gold-100"
          >
            {authorEntry?.name ?? display.authorName}
          </Link>{" "}
          <span className="mx-2 text-gold-800">/</span>{" "}
          <Link
            href={`/${locale}/books/${meta.authorSlug}/${meta.bookSlug}`}
            className="hover:text-gold-100"
          >
            {display.title}
          </Link>{" "}
          <span className="mx-2 text-gold-800">/</span>{" "}
          <span className="text-gold-100" dir={bookDir}>
            {content.title}
          </span>
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

        <div className="grid gap-10 lg:grid-cols-[260px_1fr]">
          {/* TOC sidebar */}
          <aside className="lg:sticky lg:top-6">
            <div className="border border-gold-800/70 bg-ink/60 p-5">
              <div className="flex items-center gap-2">
                <CopticCross size={20} className="text-gold-200" />
                <h2
                  className={`text-sm font-bold text-gold-100 ${
                    isAr ? "font-arabic" : "font-display tracking-wide"
                  }`}
                >
                  {t(locale, "chapter.toc")}
                </h2>
              </div>
              <ScrollArea
                dir={bookDir}
                className="mt-4 lg:max-h-[calc(100vh-9rem)]"
              >
                <ol className="space-y-1 pe-2.5">
                  {chapters.map((c) => {
                    const active = c.slug === chapter;
                    return (
                      <li key={c.slug}>
                        <Link
                          href={`/${locale}/books/${meta.authorSlug}/${meta.bookSlug}/${c.slug}`}
                          className={`flex items-baseline gap-2 border-r-2 px-3 py-2 ${bookFontClass} text-sm leading-snug transition ${
                            active
                              ? "border-gold bg-gold/10 text-gold-50"
                              : "border-transparent text-bone/80 hover:border-gold-800 hover:bg-gold/5 hover:text-gold-100"
                          }`}
                          dir={bookDir}
                        >
                          <span className="font-display text-[10px] text-gold-600">
                            {String(c.order).padStart(2, "0")}
                          </span>
                          <span>{c.title}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ol>
              </ScrollArea>
            </div>
          </aside>

          {/* Content */}
          <article>
            <header className="mb-8 border-b border-gold-800/60 pb-6">
              {isAr ? (
                <p className="font-ruqaa text-base text-gold-600">
                  {t(locale, "chapter.eyebrow.prefix")} {toArabicDigits(content.index + 1)}{" "}
                  {t(locale, "chapter.eyebrow.of")} {toArabicDigits(chapters.length)}
                </p>
              ) : (
                <p className="font-display text-[10px] uppercase tracking-[0.4em] text-gold-600">
                  {t(locale, "chapter.eyebrow.prefix")} {content.index + 1} {t(locale, "chapter.eyebrow.of")}{" "}
                  {chapters.length} {t(locale, "chapter.eyebrow.suffix")}
                </p>
              )}
              <h1
                className={`mt-3 ${bookFontClass} text-3xl font-bold leading-tight text-gold-100 sm:text-4xl`}
                dir={bookDir}
              >
                {content.title}
              </h1>
              <p className={`mt-2 text-sm text-bone/70 ${uiFontClass}`}>
                {t(locale, "chapter.from")}{" "}
                <Link
                  href={`/${locale}/books/${meta.authorSlug}/${meta.bookSlug}`}
                  className="text-gold-200 underline-offset-4 hover:underline"
                >
                  {display.title}
                </Link>
              </p>
            </header>

            <div className="prose-coptic" dir={bookDir}>
              {content.node}
            </div>

            {/* Prev / Next */}
            <nav className="mt-12 grid gap-3 border-t border-gold-800/60 pt-6 sm:grid-cols-2">
              {content.prev ? (
                <Link
                  href={`/${locale}/books/${meta.authorSlug}/${meta.bookSlug}/${content.prev.slug}`}
                  className="group border border-gold-800/70 bg-ink/60 p-4 transition hover:border-gold hover:bg-gold/5"
                >
                  <p
                    className={`text-gold-600 ${
                      isAr
                        ? "font-arabic text-xs"
                        : "font-display text-[10px] uppercase tracking-[0.32em]"
                    }`}
                  >
                    {t(locale, "chapter.prev")}
                  </p>
                  <p className={`mt-1 ${bookFontClass} text-sm text-gold-100`} dir={bookDir}>
                    {content.prev.title}
                  </p>
                </Link>
              ) : (
                <span />
              )}
              {content.next ? (
                <Link
                  href={`/${locale}/books/${meta.authorSlug}/${meta.bookSlug}/${content.next.slug}`}
                  className="group border border-gold-800/70 bg-ink/60 p-4 text-left transition hover:border-gold hover:bg-gold/5 sm:text-right"
                >
                  <p
                    className={`text-gold-600 ${
                      isAr
                        ? "font-arabic text-xs"
                        : "font-display text-[10px] uppercase tracking-[0.32em]"
                    }`}
                  >
                    {t(locale, "chapter.next")}
                  </p>
                  <p className={`mt-1 ${bookFontClass} text-sm text-gold-100`} dir={bookDir}>
                    {content.next.title}
                  </p>
                </Link>
              ) : (
                <span />
              )}
            </nav>
          </article>
        </div>
      </main>
      <SiteFooter locale={locale} />
    </>
  );
}
