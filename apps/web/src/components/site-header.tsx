import Link from "next/link";

import { t, type Locale } from "@/lib/i18n";

import { CopticCross } from "./coptic-cross";
import { LanguageSwitch } from "./language-switch";

export function SiteHeader({ locale }: { locale: Locale }) {
  const isAr = locale === "ar";
  return (
    <header className="relative z-10 border-b border-gold-800/60 bg-ink/60 backdrop-blur-sm">
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-gold to-transparent opacity-70" />
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-5">
        <Link href={`/${locale}`} className="group flex items-center gap-3">
          <span className="halo-glow rounded-full bg-ink p-2 text-gold-200 transition group-hover:text-gold-50">
            <CopticCross size={22} />
          </span>
          <span className="flex flex-col leading-tight">
            <span
              className={`${isAr ? "font-arabic" : "font-display"} text-xl font-bold text-gold-100`}
            >
              {t(locale, "site.brand.line1")}
            </span>
            <span className="font-display text-[10px] uppercase tracking-[0.32em] text-gold-600">
              {t(locale, "site.brand.line2")}
            </span>
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <nav className="flex items-center gap-1 text-sm">
            <NavLink href={`/${locale}`} locale={locale}>
              {t(locale, "nav.home")}
            </NavLink>
            <NavLink href={`/${locale}/authors`} locale={locale}>
              {t(locale, "nav.authors")}
            </NavLink>
            <NavLink href={`/${locale}/books`} locale={locale}>
              {t(locale, "nav.books")}
            </NavLink>
          </nav>
          <LanguageSwitch locale={locale} />
        </div>
      </div>
    </header>
  );
}

function NavLink({
  href,
  locale,
  children,
}: {
  href: string;
  locale: Locale;
  children: React.ReactNode;
}) {
  const fontClass = locale === "ar" ? "font-arabic" : "font-display tracking-wide";
  return (
    <Link
      href={href}
      className={`rounded-sm px-3 py-1.5 text-gold-100 transition hover:bg-gold/10 hover:text-gold-50 ${fontClass}`}
    >
      {children}
    </Link>
  );
}
