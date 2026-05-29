"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getProgress } from "@/lib/reading-progress";
import { t, type Locale } from "@/lib/i18n";

/**
 * Table-of-contents call-to-action that resumes the reader where they left off.
 *
 * The book page is a server component, but reading progress lives in
 * localStorage (see reading-progress.ts) — so this thin client island reads it
 * after mount. Mirrors the theme-toggle / reading-font-controls idiom: the
 * server and first client render show the neutral "start from chapter one" link
 * (so SSR/CSR markup agree → no hydration mismatch); once mounted, if a saved
 * record exists for THIS book, the label/href swap to "Continue reading" and
 * point at the stored chapter. Both states share the exact button styling so
 * the layout never shifts — only the text and target differ.
 *
 * Progress is only ever written while signed in, so the mere existence of a
 * record is sufficient to offer a resume — no separate sign-in gate needed.
 */
export function ContinueReadingCta({
  locale,
  authorSlug,
  bookSlug,
  firstChapterSlug,
  uiFontClass,
}: {
  locale: Locale;
  authorSlug: string;
  bookSlug: string;
  // The slug the default "start reading" CTA links to (the first chapter).
  firstChapterSlug: string;
  // The UI font class the surrounding page applies to chrome (font-arabic /
  // font-body) so this button renders identically to the original inline CTA.
  uiFontClass: string;
}) {
  const [resumeSlug, setResumeSlug] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const progress = getProgress(authorSlug, bookSlug);
    setResumeSlug(progress?.chapterSlug ?? null);
    setMounted(true);
  }, [authorSlug, bookSlug]);

  // Pre-mount (and on the server) hold the neutral start-from-chapter-one state
  // so SSR and the first client render agree; swap to resume after we've read
  // localStorage and confirmed a saved position exists.
  const resuming = mounted && resumeSlug !== null;
  const targetSlug = resuming ? resumeSlug! : firstChapterSlug;
  const label = resuming
    ? t(locale, "reading.progress.resume")
    : t(locale, "book.toc.startReading");

  return (
    <Link
      href={`/${locale}/books/${authorSlug}/${bookSlug}/${targetSlug}`}
      className={`mt-6 inline-flex items-center gap-2 border border-gold-600 px-5 py-2.5 text-sm text-gold-100 transition hover:border-gold hover:bg-gold/10 ${uiFontClass}`}
    >
      {label}
    </Link>
  );
}
