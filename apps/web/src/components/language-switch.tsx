"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isLocale, t, type Locale } from "@/lib/i18n";

import { CopticGlobe } from "./coptic-globe";

export function LanguageSwitch({ locale }: { locale: Locale }) {
  const pathname = usePathname() ?? `/${locale}`;
  const isAr = locale === "ar";
  const target: Locale = isAr ? "en" : "ar";
  const targetHref = swapLocaleSegment(pathname, target);
  const label =
    target === "en" ? "Switch to English" : "التبديل إلى العربية";

  return (
    <Link
      href={targetHref}
      prefetch={false}
      aria-label={label}
      title={label}
      className="flex items-center gap-2 rounded-[2px] border border-gold-800/70 bg-ink/60 px-3 py-1.5 text-gold-200 transition hover:border-gold hover:text-gold-50"
    >
      <CopticGlobe size={18} />
      <span
        className={
          isAr
            ? "font-arabic text-sm"
            : "font-display text-xs uppercase tracking-[0.18em]"
        }
      >
        {t(locale, "lang.switch")}
      </span>
    </Link>
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
