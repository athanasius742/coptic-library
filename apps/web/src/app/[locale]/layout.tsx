import type { Metadata } from "next";
import Script from "next/script";
import { notFound } from "next/navigation";

import { dirFor, isLocale, langFor, t, type Locale } from "@/lib/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) return {};
  const locale: Locale = rawLocale;
  return {
    title: {
      default: t(locale, "site.title"),
      template: t(locale, "site.title.template"),
    },
    description: t(locale, "site.description"),
  };
}

export function generateStaticParams() {
  return [{ locale: "ar" }, { locale: "en" }];
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const lang = langFor(locale);
  const dir = dirFor(locale);

  // Defensive: also set lang/dir on <html> via an inline script so the document
  // attributes match the active locale even if the request-time header sniff in
  // the root layout misses (e.g. during client-side navigation between locales).
  const inline = `try{var e=document.documentElement;e.lang=${JSON.stringify(lang)};e.dir=${JSON.stringify(dir)};}catch(_){}`;

  return (
    <>
      <Script id={`set-html-${lang}`} strategy="beforeInteractive">
        {inline}
      </Script>
      {children}
    </>
  );
}
