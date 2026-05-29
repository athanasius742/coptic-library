import Link from "next/link";

import { t, type Locale } from "@/lib/i18n";

import { CopticCross } from "./coptic-cross";

const GITHUB_URL = "https://github.com/athanasius742/coptic-library";

export function SiteFooter({ locale }: { locale: Locale }) {
  const isAr = locale === "ar";
  return (
    <footer className="relative mt-20 border-t border-gold-800/60 bg-ink/60">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-gold to-transparent opacity-70" />
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-5 px-6 py-8 text-center">
        <CopticCross size={24} className="text-gold-200" />

        <nav className="flex items-center gap-2">
          <Link
            href={`/${locale}/about`}
            aria-label={t(locale, "footer.about")}
            title={t(locale, "footer.about")}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-gold-800/70 text-gold-200 transition hover:border-gold hover:bg-gold/10 hover:text-gold-50"
          >
            <InfoIcon />
          </Link>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={t(locale, "footer.github")}
            title={t(locale, "footer.github")}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-gold-800/70 text-gold-200 transition hover:border-gold hover:bg-gold/10 hover:text-gold-50"
          >
            <GithubIcon />
          </a>
        </nav>

        <p
          className={`text-gold-600 ${
            isAr
              ? "font-ruqaa text-base"
              : "font-display text-[10px] uppercase tracking-[0.32em]"
          }`}
        >
          {t(locale, "footer.glory")}
        </p>
      </div>
    </footer>
  );
}

function InfoIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M12 11v6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <circle cx="12" cy="8" r="1" fill="currentColor" />
    </svg>
  );
}

function GithubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2c-3.2.7-3.87-1.36-3.87-1.36-.52-1.33-1.27-1.68-1.27-1.68-1.04-.71.08-.69.08-.69 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.25 3.33.95.1-.74.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.47.11-3.06 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.79 0c2.21-1.49 3.18-1.18 3.18-1.18.62 1.59.23 2.77.11 3.06.74.81 1.18 1.84 1.18 3.1 0 4.42-2.69 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.68.8.56A11.51 11.51 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
    </svg>
  );
}
