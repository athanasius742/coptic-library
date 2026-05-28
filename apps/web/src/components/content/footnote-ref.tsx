import type { ReactNode } from "react";

/**
 * Footnote marker / return-link. Both the body marker (`[1]`) and the note's
 * back-link are rendered through this component. The destination `id` is
 * injected by the re-anchoring pre-pass in `render-content.tsx` and survives
 * sanitization; we read it back here so the matching link can scroll to it.
 *
 * `scroll-margin-top` keeps the jump target clear of any sticky page chrome.
 * Server component (no interactivity until/unless a hover popover is added).
 */
export function FootnoteRef({
  href,
  id,
  children,
}: {
  href: string;
  id?: string;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      id={id}
      className="footnote-ref text-gold-200 no-underline [scroll-margin-top:5rem] hover:text-gold-50"
    >
      {children}
    </a>
  );
}
