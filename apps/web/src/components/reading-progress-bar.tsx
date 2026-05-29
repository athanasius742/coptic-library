"use client";

import { useEffect, useState } from "react";

// Hide the bar until the reader has scrolled past this many px, so it doesn't
// clutter the top of the page when there's effectively nothing to track yet.
const REVEAL_AT = 64;

/**
 * Compute how far the reader has scrolled through the current chapter, as a
 * 0..100 % of the <article>'s scrollable distance against the WINDOW (the page
 * scrolls the document, not a nested container). Mirrors the formula in
 * reading-progress-tracker.tsx exactly — the two islands share the math but stay
 * decoupled. A chapter shorter than the viewport has nothing to scroll →
 * treated as fully read (100%).
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
 * Visual-only island mounted inside the chapter <article>: a thin fixed bar
 * pinned to the very top of the viewport (above the header) that fills from the
 * start edge as the reader scrolls the chapter prose. It fades in once the
 * reader is ~64px down and hides again near the top. Purely decorative and
 * sign-in–independent — it writes nothing (the tracker handles persistence).
 *
 * Mirrors the mounted-gate idiom of theme-toggle.tsx: SSR and the first client
 * render agree on 0% / hidden, then we read the real scroll position after
 * mount. Listeners are passive and coalesced into one rAF per frame for smooth,
 * cheap updates. The fill uses `inlineSize` (a logical property) so it grows
 * from the start edge under both LTR and RTL.
 */
export function ReadingProgressBar() {
  const [percent, setPercent] = useState(0);
  const [visible, setVisible] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);

    let frame: number | null = null;
    function update() {
      frame = null;
      setPercent(computeScrollPercent());
      setVisible(window.scrollY > REVEAL_AT);
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

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-x-0 top-0 z-40 h-1 bg-gold-800/30 transition-opacity duration-200 ease-out motion-reduce:transition-none"
      // The whole bar (track + fill) fades in once the reader is past REVEAL_AT,
      // so nothing shows at the very top. Hidden pre-mount so SSR/CSR agree.
      style={{ opacity: mounted && visible ? 1 : 0 }}
    >
      <div
        // `ms-auto` anchors the fill to the END edge so it grows toward the
        // START as the reader scrolls (reversed direction); the gradient leads
        // with the brighter tone at the growing edge. Logical props keep this
        // correct under both LTR and RTL.
        className="ms-auto h-full bg-gradient-to-l from-gold-600 to-gold-100 transition-[inline-size] duration-150 ease-out motion-reduce:transition-none"
        style={{ inlineSize: mounted ? `${percent}%` : "0%" }}
      />
    </div>
  );
}
