"use client";

import { useEffect, useRef } from "react";

import { getMockUser } from "@/lib/mock-user";
import { type ReadingProgress, upsertProgress } from "@/lib/reading-progress";

// Everything that defines the record except the position/timestamp the tracker
// derives itself. The chapter RSC already has all of this in scope.
type Props = Omit<ReadingProgress, "updatedAt" | "scrollProgress">;

/**
 * Compute how far the reader has scrolled through the current chapter, as a
 * 0..100 % of the <article>'s scrollable distance against the WINDOW (the page
 * scrolls the document, not a nested container). A chapter shorter than the
 * viewport has nothing to scroll → treated as fully read (100%).
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
 * Invisible island mounted inside the chapter <article>. Records the current
 * chapter on mount (so opening a chapter marks it current even at 0%) and
 * throttles scroll-progress writes, but ONLY when the mock user is signed in
 * (matching real-auth semantics — you must "be" the user to track). Renders
 * null; pure effects, zero markup → no hydration concerns.
 */
export function ReadingProgressTracker(props: Props) {
  // Keep the latest props in a ref so the listeners read current values without
  // re-binding on every render.
  const propsRef = useRef(props);
  propsRef.current = props;

  useEffect(() => {
    // Don't track for anonymous readers.
    if (!getMockUser()) return;

    function save() {
      upsertProgress({
        ...propsRef.current,
        scrollProgress: computeScrollPercent(),
      });
    }

    // Mark this chapter current immediately, at the current scroll position.
    save();

    // Trailing throttle: at most one write per ~250 ms of scrolling.
    let timer: ReturnType<typeof setTimeout> | null = null;
    function onScroll() {
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        save();
      }, 250);
    }
    function onVisibility() {
      if (document.visibilityState === "hidden") save();
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", save);

    return () => {
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", save);
      if (timer) clearTimeout(timer);
      // Flush the final position on unmount (e.g. navigating to next chapter).
      save();
    };
    // Re-run when the chapter identity changes so each chapter is recorded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.authorSlug, props.bookSlug, props.chapterSlug]);

  return null;
}
