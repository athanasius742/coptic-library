"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isLocale, t, type Locale } from "@/lib/i18n";

export function LanguageSwitch({ locale }: { locale: Locale }) {
  const pathname = usePathname() ?? `/${locale}`;
  const arHref = swapLocaleSegment(pathname, "ar");
  const enHref = swapLocaleSegment(pathname, "en");

  return (
    <div className="flex items-center gap-1 border border-gold-800/70 bg-ink/60 p-0.5 text-xs">
      <Link
        href={arHref}
        aria-current={locale === "ar" ? "true" : undefined}
        prefetch={false}
        className={`rounded-[2px] px-2.5 py-1 font-arabic transition ${
          locale === "ar"
            ? "bg-gold/15 text-gold-50"
            : "text-gold-200 hover:text-gold-50"
        }`}
      >
        {t(locale, "lang.arabic")}
      </Link>
      <Link
        href={enHref}
        aria-current={locale === "en" ? "true" : undefined}
        prefetch={false}
        className={`rounded-[2px] px-2.5 py-1 font-display uppercase tracking-[0.18em] transition ${
          locale === "en"
            ? "bg-gold/15 text-gold-50"
            : "text-gold-200 hover:text-gold-50"
        }`}
      >
        {t(locale, "lang.english")}
      </Link>
    </div>
  );
}

function swapLocaleSegment(pathname: string, next: Locale): string {
  const parts = pathname.split("/");
  // pathname starts with "/", so parts[0] is "".
  if (parts.length >= 2 && isLocale(parts[1])) {
    parts[1] = next;
    return parts.join("/") || `/${next}`;
  }
  return `/${next}`;
}
