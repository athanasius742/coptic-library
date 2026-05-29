"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { t, type Locale } from "@/lib/i18n";
import {
  getAllProgress,
  READING_PROGRESS_KEY,
  type ReadingProgress,
} from "@/lib/reading-progress";

import { CurrentlyReadingCard } from "./currently-reading-card";
import { CrossDivider } from "./ornament";
import { useMockUser } from "./use-mock-user";

/**
 * "Currently Reading" shelf — reads the localStorage progress records after
 * mount and renders a grid of resume cards, gated on the mock user being
 * signed in. Used on both the home page and the profile page via `variant`,
 * which controls the empty-state behavior:
 *   - "home": self-hides entirely when signed out OR empty (owns its leading
 *     CrossDivider so the logged-out home is byte-identical to before).
 *   - "profile": renders an empty-state message when signed in but with no
 *     progress (the signed-out case is handled by the profile shell upstream).
 */
export function CurrentlyReadingShelf({
  locale,
  variant,
  reloadKey,
}: {
  locale: Locale;
  variant: "home" | "profile";
  // Bump to force a re-read after an in-tab mutation (e.g. "clear history"),
  // which doesn't fire the cross-tab `storage` event.
  reloadKey?: number;
}) {
  const { user, mounted } = useMockUser();
  const [records, setRecords] = useState<ReadingProgress[]>([]);

  useEffect(() => {
    setRecords(getAllProgress());
    function onStorage(e: StorageEvent) {
      if (e.key === READING_PROGRESS_KEY) setRecords(getAllProgress());
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [user, reloadKey]);

  // Until mounted (and signed in), render the neutral empty state the server
  // produced — no hydration mismatch.
  if (!mounted || !user) return null;

  const isAr = locale === "ar";

  if (records.length === 0) {
    if (variant === "home") return null;
    return (
      <p
        className={`border border-gold-800/70 bg-ink/60 px-5 py-8 text-center text-bone/70 ${
          isAr ? "font-arabic" : "font-body"
        }`}
      >
        {t(locale, "profile.empty")}
      </p>
    );
  }

  const arrow = isAr ? "←" : "→";

  return (
    <>
      {variant === "home" && <CrossDivider />}
      <section className={variant === "home" ? "mx-auto max-w-6xl px-6" : ""}>
        <div className="mb-8 flex items-end justify-between gap-4">
          <div>
            <p
              className={`text-gold-600 ${
                isAr
                  ? "font-ruqaa text-base"
                  : "font-display text-[10px] uppercase tracking-[0.4em]"
              }`}
            >
              {t(locale, "home.section.currentlyReading.eyebrow")}
            </p>
            <h2
              className={`mt-2 text-2xl font-bold text-gold-50 sm:text-3xl ${
                isAr ? "font-arabic" : "font-display tracking-wide"
              }`}
            >
              {t(locale, "home.section.currentlyReading.title")}
            </h2>
          </div>
          {variant === "home" && (
            <Link
              href={`/${locale}/profile`}
              className={`hidden whitespace-nowrap border-b border-gold-800/70 pb-0.5 text-sm text-gold-100 transition hover:border-gold hover:text-gold-50 sm:inline-block ${
                isAr ? "font-arabic" : "font-body"
              }`}
            >
              {t(locale, "home.section.currentlyReading.cta")} {arrow}
            </Link>
          )}
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {records.map((rec) => (
            <li key={`${rec.authorSlug}/${rec.bookSlug}`}>
              <CurrentlyReadingCard rec={rec} locale={locale} />
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
