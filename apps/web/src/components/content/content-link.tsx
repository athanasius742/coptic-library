import Link from "next/link";
import type { ReactNode } from "react";

/**
 * General anchor inside chapter content. Branch logic (which href is internal vs
 * external vs intra-page) is resolved in `render-content.tsx`; this component
 * only chooses the right element:
 *
 *  - `kind: "internal"` → Next `<Link>` (client-side nav within the library)
 *  - `kind: "external"` → `<a target="_blank" rel="noopener noreferrer">`
 *  - `kind: "anchor"`   → plain `<a>` for in-page `#` jumps
 *
 * Styling is inherited from `.prose-coptic a`.
 */
export type ContentLinkKind = "internal" | "external" | "anchor";

export function ContentLink({
  kind,
  href,
  children,
}: {
  kind: ContentLinkKind;
  href: string;
  children: ReactNode;
}) {
  if (kind === "internal") {
    return <Link href={href}>{children}</Link>;
  }
  if (kind === "external") {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  }
  return <a href={href}>{children}</a>;
}
