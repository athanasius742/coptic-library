"use client";

import { useState } from "react";

import { t, type Locale } from "@/lib/i18n";
import { clearAllProgress } from "@/lib/reading-progress";

import { CurrentlyReadingShelf } from "./currently-reading-shelf";
import { useMockUser } from "./use-mock-user";

/**
 * Client body of the profile page. Branches on the mock-user seam: signed in →
 * greeting + Currently Reading shelf + sign-out / clear-history; signed out → a
 * mock sign-in CTA. Before mount (and on the server) it renders the signed-out
 * CTA, the neutral state the server can know → no hydration mismatch.
 */
export function ProfileContent({ locale }: { locale: Locale }) {
  const { user, mounted, signIn, signOut } = useMockUser();
  const [reloadKey, setReloadKey] = useState(0);
  const isAr = locale === "ar";
  const headingFont = isAr ? "font-arabic" : "font-display tracking-wide";
  const bodyFont = isAr ? "font-arabic" : "font-body";

  function handleClear() {
    clearAllProgress();
    setReloadKey((k) => k + 1);
  }

  // Signed out (also the pre-mount / SSR state).
  if (!mounted || !user) {
    return (
      <div className="mx-auto max-w-md text-center">
        <p className={`text-base leading-relaxed text-bone/80 ${bodyFont}`}>
          {t(locale, "profile.signInPrompt")}
        </p>
        <button
          type="button"
          onClick={() => signIn(t(locale, "profile.defaultName"))}
          className={`mt-8 inline-flex items-center gap-2 bg-gradient-to-b from-gold-100 to-gold px-6 py-3 text-sm font-bold text-ink transition hover:from-gold-50 hover:to-gold-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-600 ${
            isAr ? "font-arabic" : "font-display tracking-wide"
          }`}
        >
          {t(locale, "profile.signIn")}
        </button>
        <p className={`mt-6 text-xs text-bone/50 ${bodyFont}`}>
          {t(locale, "profile.mockNote")}
        </p>
      </div>
    );
  }

  // Signed in.
  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p
            className={`text-gold-600 ${
              isAr ? "font-ruqaa text-base" : "font-display text-[10px] uppercase tracking-[0.4em]"
            }`}
          >
            {t(locale, "profile.greeting")}
          </p>
          <h2 className={`mt-2 text-2xl font-bold text-gold-50 sm:text-3xl ${headingFont}`}>
            {user.name}
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleClear}
            className={`border border-gold-800/70 px-4 py-2 text-sm text-gold-100 transition hover:border-gold hover:bg-gold/5 hover:text-gold-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-600 ${bodyFont}`}
          >
            {t(locale, "profile.clearHistory")}
          </button>
          <button
            type="button"
            onClick={signOut}
            className={`border border-gold-800/70 px-4 py-2 text-sm text-gold-100 transition hover:border-gold hover:bg-gold/5 hover:text-gold-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-600 ${bodyFont}`}
          >
            {t(locale, "profile.signOut")}
          </button>
        </div>
      </div>

      <div className="mt-10">
        <CurrentlyReadingShelf locale={locale} variant="profile" reloadKey={reloadKey} />
      </div>
    </div>
  );
}
