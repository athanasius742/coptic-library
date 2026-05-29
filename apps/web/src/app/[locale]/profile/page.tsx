import { notFound } from "next/navigation";

import { CrossDivider } from "@/components/ornament";
import { ProfileContent } from "@/components/profile-content";
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
  return { title: t(rawLocale as Locale, "profile.title") };
}

export default async function ProfilePage({
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
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-14">
        <div className="text-center">
          <p
            className={`text-gold-600 ${
              isAr ? "font-ruqaa text-base" : "font-display text-xs uppercase tracking-[0.45em]"
            }`}
          >
            {t(locale, "profile.eyebrow")}
          </p>
          <h1
            className={`mt-3 text-4xl font-bold text-gold-100 sm:text-5xl ${
              isAr ? "font-arabic" : "font-display tracking-wide"
            }`}
          >
            {t(locale, "profile.title")}
          </h1>
        </div>
        <CrossDivider />
        <ProfileContent locale={locale} />
      </main>
      <SiteFooter locale={locale} />
    </>
  );
}
