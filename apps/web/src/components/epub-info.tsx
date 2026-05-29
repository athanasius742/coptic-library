"use client";

import * as HoverCard from "@radix-ui/react-hover-card";
import Link from "next/link";

import { dirFor, t, type Locale } from "@/lib/i18n";

/**
 * A small "info" icon button shown next to the Download EPUB button.
 * - Click navigates to the full /[locale]/epub-format help page.
 * - Hover/focus reveals a short, reassuring explanation (accessible via
 *   Radix HoverCard); on touch the tap simply follows the link.
 */
export function EpubInfo({ locale }: { locale: Locale }) {
  const isAr = locale === "ar";
  const dir = dirFor(locale);
  const uiFontClass = isAr ? "font-arabic" : "font-body";

  return (
    <HoverCard.Root openDelay={120} closeDelay={120}>
      <HoverCard.Trigger asChild>
        <Link
          href={`/${locale}/epub-format`}
          aria-label={t(locale, "epub.info.aria")}
          className="halo-glow inline-flex aspect-square h-full items-center justify-center border border-gold-800 px-3 text-gold-100 transition hover:border-gold hover:bg-gold/10"
        >
          <InfoIcon />
        </Link>
      </HoverCard.Trigger>
      <HoverCard.Portal>
        <HoverCard.Content
          dir={dir}
          side="top"
          align="center"
          sideOffset={10}
          collisionPadding={12}
          className={`z-50 w-72 max-w-[calc(100vw-2rem)] border border-gold-800 bg-panel p-4 text-bone shadow-xl ${uiFontClass}`}
        >
          <p className="text-sm leading-relaxed text-bone/90">
            {t(locale, "epub.info.body")}
          </p>
          <Link
            href={`/${locale}/epub-format`}
            className="mt-3 inline-block text-sm font-bold text-gold-100 transition hover:text-gold-50"
          >
            {t(locale, "epub.info.readMore")}
          </Link>
          <HoverCard.Arrow className="fill-gold-800" />
        </HoverCard.Content>
      </HoverCard.Portal>
    </HoverCard.Root>
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
