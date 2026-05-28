import type { ReactNode } from "react";

/**
 * Real data table (not a TOC, not an image-wrapper). Wrapped in a horizontal
 * scroll container for narrow viewports. The bordered cell look is owned by the
 * `.content-table` rule in globals.css (moved out of `.prose-coptic table` per
 * the renderer spec) so the table styling is component-scoped.
 *
 * `colspan`/`rowspan` are preserved by passing the parsed children through
 * untouched; the parser already converts them to `colSpan`/`rowSpan` props.
 */
export function ContentTable({ children }: { children: ReactNode }) {
  return (
    <div className="my-6 -mx-1 overflow-x-auto">
      <table className="content-table mx-auto border-collapse text-[0.95em]">
        {children}
      </table>
    </div>
  );
}
