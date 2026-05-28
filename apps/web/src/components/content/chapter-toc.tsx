"use client";

import { useState } from "react";

export type TocEntry = { href: string; label: string };

/**
 * Collapsible table-of-contents card rendered for source "محتويات"/"Contents"
 * tables. Client island so the open/closed state is interactive; the in-page
 * `#anchor` links are made functional by the re-anchoring pass in
 * `render-content.tsx`.
 */
export function ChapterToc({
  entries,
  heading,
}: {
  entries: TocEntry[];
  heading: string;
}) {
  const [open, setOpen] = useState(true);

  if (entries.length === 0) return null;

  return (
    <nav
      aria-label={heading}
      className="my-8 rounded-md border border-gold-800/60 bg-ink/40 px-5 py-4"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 text-start font-display text-sm font-bold uppercase tracking-[0.18em] text-gold-100 transition hover:text-gold-50"
      >
        <span>{heading}</span>
        <span
          aria-hidden
          className={`text-gold-400 transition-transform ${open ? "rotate-90" : ""}`}
        >
          ›
        </span>
      </button>
      {open ? (
        <ul className="mt-3 space-y-1.5 border-t border-gold-800/40 pt-3">
          {entries.map((entry, i) => (
            <li key={`${entry.href}-${i}`}>
              <a
                href={entry.href}
                className="text-gold-100 underline decoration-gold/40 underline-offset-[3px] transition hover:text-gold-50 hover:decoration-gold"
              >
                {entry.label}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </nav>
  );
}
