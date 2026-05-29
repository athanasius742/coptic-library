"use client";

import Link from "next/link";

import { t, type Locale } from "@/lib/i18n";

import { CopticUser } from "./coptic-user";
import { useMockUser } from "./use-mock-user";

/**
 * Header control linking to the profile page. Styled like LanguageSwitch (icon
 * + locale-aware label). When the mock user is signed in we surface a small
 * gold dot affordance — gated by `mounted` so SSR and the first client render
 * match (the server can't know the localStorage state).
 */
export function ProfileButton({ locale }: { locale: Locale }) {
  const { user, mounted } = useMockUser();
  const isAr = locale === "ar";
  const label = t(locale, "nav.profile");
  const signedIn = mounted && !!user;

  return (
    <Link
      href={`/${locale}/profile`}
      aria-label={label}
      title={label}
      className="relative flex items-center gap-2 rounded-[2px] border border-gold-800/70 bg-ink/60 px-3 py-1.5 text-gold-200 transition hover:border-gold hover:text-gold-50"
    >
      <CopticUser size={18} title={label} />
      {signedIn && (
        <span
          aria-hidden
          className="absolute -end-1 -top-1 h-2.5 w-2.5 rounded-full bg-gold ring-2 ring-ink"
        />
      )}
      <span
        className={
          isAr
            ? "font-arabic text-sm"
            : "font-display text-xs uppercase tracking-[0.18em]"
        }
      >
        {label}
      </span>
    </Link>
  );
}
