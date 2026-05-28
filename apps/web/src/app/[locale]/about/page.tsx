import { notFound } from "next/navigation";

import { CrossDivider } from "@/components/ornament";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { isLocale, t, type Locale } from "@/lib/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) return {};
  return { title: t(rawLocale as Locale, "about.title") };
}

export default async function AboutPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const isAr = locale === "ar";

  return (
    <>
      <SiteHeader locale={locale} />
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-14 text-center">
        <h1
          className={`text-4xl font-bold text-gold-100 sm:text-5xl ${
            isAr ? "font-arabic" : "font-display tracking-wide"
          }`}
        >
          {t(locale, "about.title")}
        </h1>
        <CrossDivider />
        <p
          className={`text-base text-bone/80 ${
            isAr ? "font-arabic" : "font-body"
          }`}
        >
          {t(locale, "about.placeholder")}
        </p>
      </main>
      <SiteFooter locale={locale} />
    </>
  );
}
