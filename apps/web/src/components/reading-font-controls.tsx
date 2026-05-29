"use client";

import { useEffect, useState } from "react";

import { t, type Locale } from "@/lib/i18n";

// Bounds mirror the no-flash bootstrap in app/layout.tsx — keep them in sync.
const MIN = 0.85;
const MAX = 1.6;
const STEP = 0.075;
const DEFAULT = 1;
const EPS = 0.001;

function clamp(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT;
  // round to 3 decimals so repeated +/- STEP doesn't accumulate float drift
  const rounded = Math.round(value * 1000) / 1000;
  return Math.min(MAX, Math.max(MIN, rounded));
}

/**
 * Compute how far the reader has scrolled through the current chapter, as a
 * 0..100 % of the <article>'s scrollable distance against the WINDOW (the page
 * scrolls the document, not a nested container). Copied verbatim from the
 * reading-progress islands so the three share the math while staying decoupled
 * (no cross-island imports). A chapter shorter than the viewport has nothing to
 * scroll → treated as fully read (100%).
 */
function computeScrollPercent(): number {
  const el = document.querySelector("article");
  if (!el) return 0;
  const rect = el.getBoundingClientRect();
  const total = rect.height - window.innerHeight; // scrollable distance
  if (total <= 0) return 100;
  const scrolled = -rect.top; // px scrolled past the article's top
  const pct = Math.round((scrolled / total) * 100);
  return Math.min(100, Math.max(0, pct));
}

/**
 * Render a percentage the same way the font pill does: the Arabic UI gets a
 * leading `٪` + Arabic-Indic digits, while the English UI keeps Western digits
 * + a trailing `%`. Shared by both indicators so they stay typographically
 * consistent.
 */
function formatPercent(value: number, isAr: boolean): string {
  const num = String(value);
  return isAr
    ? `٪${num.replace(/[0-9]/g, (d) => "٠١٢٣٤٥٦٧٨٩"[Number(d)])}`
    : `${num}%`;
}

/**
 * Reading-only pill (A− / percentage-reset / A+) that scales ONLY the chapter
 * prose by setting the `--reading-font-scale` CSS var on <html>, which
 * `.prose-coptic` consumes. Mirrors theme-toggle.tsx: the no-flash bootstrap in
 * layout.tsx applies the stored value pre-paint, and we read it back from the
 * DOM/localStorage after mount to sync the indicator. The glyph + percentage
 * follow the UI locale (Latin "A"/`%` vs Arabic "أ"/`٪` with Arabic-Indic
 * digits); placement orients by the UI `dir`, independent of the book's dir.
 */
export function ReadingFontControls({
  locale,
  chapterIndex,
  totalChapters,
}: {
  locale: Locale;
  // Current chapter position in the book (0-based) + total, used to derive the
  // whole-book percentage shown beside the per-page one. Optional so the control
  // still works without them (book row simply hidden).
  chapterIndex?: number;
  totalChapters?: number;
}) {
  // Starts at DEFAULT so SSR and the first client render agree (100%); the
  // actual persisted value is read from the DOM/localStorage after mount, so the
  // indicator updates post-hydration without a markup mismatch. The prose itself
  // is already correctly scaled pre-paint by the inline bootstrap in layout.tsx.
  const [scale, setScale] = useState(DEFAULT);
  const isAr = locale === "ar";

  useEffect(() => {
    const fromDom = getComputedStyle(document.documentElement).getPropertyValue(
      "--reading-font-scale",
    );
    let value = parseFloat(fromDom);
    if (!Number.isFinite(value)) {
      try {
        value = parseFloat(localStorage.getItem("reading-font-scale") ?? "");
      } catch {
        value = DEFAULT;
      }
    }
    setScale(clamp(value));
  }, []);

  function apply(next: number) {
    const value = clamp(next);
    if (value === DEFAULT) {
      document.documentElement.style.removeProperty("--reading-font-scale");
    } else {
      document.documentElement.style.setProperty(
        "--reading-font-scale",
        String(value),
      );
    }
    try {
      localStorage.setItem("reading-font-scale", String(value));
    } catch {
      // localStorage may be unavailable (private mode); scale still applies.
    }
    setScale(value);
  }

  const atMin = scale <= MIN + EPS;
  const atMax = scale >= MAX - EPS;
  // Arabic UI gets Arabic-Indic digits + a leading `٪` to match the rest of the
  // chrome; English keeps Western digits + trailing `%`.
  const percent = formatPercent(Math.round(scale * 100), isAr);

  // Size glyph: Latin "A" for the English UI, Arabic alef "أ" for the Arabic UI.
  const sizeGlyph = isAr ? "أ" : "A";
  const glyphFont = isAr ? "font-arabic" : "";
  const labelFont = isAr ? "font-arabic" : "font-display uppercase tracking-[0.18em]";

  const pill = (
    <div
      className="pointer-events-auto flex items-stretch gap-1 rounded-full border border-gold-800/70 bg-ink/80 px-1.5 py-1 text-gold-200 shadow-lg backdrop-blur-sm"
      role="group"
      aria-label={t(locale, "reading.font.label")}
    >
        <button
          type="button"
          onClick={() => apply(scale - STEP)}
          disabled={atMin}
          aria-label={t(locale, "reading.font.decrease")}
          title={t(locale, "reading.font.decrease")}
          className="flex cursor-pointer items-baseline rounded-full px-2.5 py-1 leading-none transition hover:text-gold-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-gold-600 disabled:cursor-default disabled:opacity-40 disabled:hover:text-gold-200"
        >
          <span className={`text-xs font-bold ${glyphFont}`}>{sizeGlyph}</span>
          <span className="ms-0.5 text-sm">−</span>
        </button>

        <span className="my-1 w-px self-stretch bg-gold-800/50" aria-hidden="true" />

        <button
          type="button"
          onClick={() => apply(DEFAULT)}
          aria-label={t(locale, "reading.font.reset")}
          title={t(locale, "reading.font.reset")}
          className={`flex min-w-[3.25rem] cursor-pointer items-center justify-center rounded-full px-1.5 py-1 text-xs leading-none transition hover:text-gold-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-gold-600 ${labelFont}`}
        >
          <span aria-live="polite">{percent}</span>
        </button>

        <span className="my-1 w-px self-stretch bg-gold-800/50" aria-hidden="true" />

        <button
          type="button"
          onClick={() => apply(scale + STEP)}
          disabled={atMax}
          aria-label={t(locale, "reading.font.increase")}
          title={t(locale, "reading.font.increase")}
          className="flex cursor-pointer items-baseline rounded-full px-2.5 py-1 leading-none transition hover:text-gold-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-gold-600 disabled:cursor-default disabled:opacity-40 disabled:hover:text-gold-200"
        >
          <span className={`text-base font-bold ${glyphFont}`}>{sizeGlyph}</span>
          <span className="ms-0.5 text-sm">+</span>
        </button>
    </div>
  );

  // A small sibling pill, styled with the SAME tokens as the font pill so the
  // two read as one cluster (and theme light/dark for free), showing how far the
  // reader has progressed through the current page and the whole book. Grouped
  // with the font pill in each wrapper below so it sits immediately adjacent.
  const readPill = (
    <ReadProgressPill
      locale={locale}
      isAr={isAr}
      chapterIndex={chapterIndex}
      totalChapters={totalChapters}
    />
  );

  // Group the read indicator + font pill so they sit side by side (the read
  // indicator leads on the START edge via flex source order, which flips for RTL
  // under the UI `dir`). `items-center` keeps them aligned across both wrappers.
  const cluster = (
    <div className="pointer-events-none flex items-center gap-2">
      {readPill}
      {pill}
    </div>
  );

  return (
    <>
      {/* Very wide screens: a fixed bottom bar mirroring the page's max-w-7xl
          content width; the cluster is placed just PAST the content's trailing
          edge (`start-full` → flips for RTL via the UI `dir`) so it floats in the
          outer page margin, clear of the (wide) prose. Only shown where the
          margin is actually wide enough to hold it. pointer-events pass through
          except on the pills. */}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-30 hidden min-[1700px]:block">
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
          <div className="absolute bottom-0 start-full ms-4">{cluster}</div>
        </div>
      </div>

      {/* Narrower screens: not enough outer margin for a side cluster — float it
          in the trailing-bottom corner, inset from the screen edge. */}
      <div className="pointer-events-none fixed bottom-4 end-4 z-30 min-[1700px]:hidden">
        {cluster}
      </div>
    </>
  );
}

/**
 * Reading-progress indicator: a compact, display-only pill beside the font-size
 * pill showing two labeled percentages — how far through the current PAGE
 * (chapter scroll, via the shared `computeScrollPercent()` formula) and how far
 * through the whole BOOK (the completed chapters plus the current chapter's
 * scroll, divided by the total). It writes nothing — the reading-progress-
 * tracker island owns persistence; this is purely visual and sign-in–
 * independent (everyone sees it). Matches the font pill's token styling so it
 * themes (light/dark) for free, and follows the UI locale for digit shaping and
 * orientation. The book row is omitted when the book position isn't known.
 *
 * Mirrors the mounted-gate idiom: SSR and the first client render agree on 0%,
 * then we read the real scroll position after mount — no hydration mismatch.
 * Listeners are passive and coalesced into one rAF per frame; the pending frame
 * is cancelled and listeners removed on cleanup.
 */
function ReadProgressPill({
  locale,
  isAr,
  chapterIndex,
  totalChapters,
}: {
  locale: Locale;
  isAr: boolean;
  chapterIndex?: number;
  totalChapters?: number;
}) {
  const [percent, setPercent] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);

    let frame: number | null = null;
    function update() {
      frame = null;
      setPercent(computeScrollPercent());
    }
    function onScrollOrResize() {
      // Coalesce bursts of scroll/resize events into a single per-frame compute.
      if (frame !== null) return;
      frame = requestAnimationFrame(update);
    }

    // Sync to the current position immediately (e.g. restored scroll on reload).
    update();

    window.addEventListener("scroll", onScrollOrResize, { passive: true });
    window.addEventListener("resize", onScrollOrResize, { passive: true });

    return () => {
      window.removeEventListener("scroll", onScrollOrResize);
      window.removeEventListener("resize", onScrollOrResize);
      if (frame !== null) cancelAnimationFrame(frame);
    };
  }, []);

  // Hold a stable 0% pre-mount so SSR/CSR agree; render real progress after.
  const pagePct = mounted ? percent : 0;

  // Whole-book %: combine the completed chapters with the scroll position in the
  // current one. Guard a missing/zero total so we never divide by zero.
  const hasBook =
    typeof chapterIndex === "number" &&
    typeof totalChapters === "number" &&
    totalChapters > 0;
  const bookPct = hasBook
    ? Math.min(
        100,
        Math.max(
          0,
          Math.round(((chapterIndex! + pagePct / 100) / totalChapters!) * 100),
        ),
      )
    : 0;

  return (
    <div className="pointer-events-auto flex items-stretch gap-2 rounded-full border border-gold-800/70 bg-ink/90 px-3 py-1.5 text-gold-200 shadow-lg backdrop-blur-sm">
      <ProgressRow
        label={t(locale, "reading.progress.page")}
        value={pagePct}
        isAr={isAr}
        live
      />
      {hasBook && (
        <>
          <span className="my-0.5 w-px self-stretch bg-gold-800/50" aria-hidden="true" />
          <ProgressRow
            label={t(locale, "reading.progress.book")}
            value={bookPct}
            isAr={isAr}
          />
        </>
      )}
    </div>
  );
}

/**
 * One compact "<label> <percentage>" segment inside the read-progress pill, the
 * two sitting side by side. The label is muted and the value prominent; the
 * value carries the polite live region (only when it actually changes with
 * scroll) so it's announced without spamming.
 */
function ProgressRow({
  label,
  value,
  isAr,
  live = false,
}: {
  label: string;
  value: number;
  isAr: boolean;
  live?: boolean;
}) {
  const labelFont = isAr ? "font-arabic" : "font-display uppercase tracking-[0.14em]";
  const valueFont = isAr ? "font-arabic" : "font-display";
  const formatted = formatPercent(value, isAr);
  return (
    <div
      className="flex items-center gap-1.5 leading-none"
      aria-label={`${label}: ${formatted}`}
    >
      <span className={`text-xs text-gold-200 ${labelFont}`}>{label}</span>
      <span
        className={`text-xs font-semibold tabular-nums text-gold-50 ${valueFont}`}
        aria-live={live ? "polite" : undefined}
      >
        {formatted}
      </span>
    </div>
  );
}
