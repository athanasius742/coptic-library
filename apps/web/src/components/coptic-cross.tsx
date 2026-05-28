type Props = {
  size?: number;
  className?: string;
  title?: string;
};

/**
 * Coptic Orthodox cross — a Greek-style cross with equal arms, each
 * terminating in three lobes (trefoil). The twelve lobes represent the
 * Twelve Apostles.
 */
export function CopticCross({ size = 32, className, title }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="currentColor"
      role="img"
      aria-label={title ?? "Coptic Orthodox cross"}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Cross body — thinner so the trefoils dominate the silhouette */}
      <rect x="28" y="12" width="8" height="40" />
      <rect x="12" y="28" width="40" height="8" />

      {/* Top arm trefoil — three overlapping lobes (a clover) */}
      <circle cx="32" cy="7" r="5" />
      <circle cx="26" cy="11" r="4" />
      <circle cx="38" cy="11" r="4" />

      {/* Bottom arm trefoil */}
      <circle cx="32" cy="57" r="5" />
      <circle cx="26" cy="53" r="4" />
      <circle cx="38" cy="53" r="4" />

      {/* Left arm trefoil */}
      <circle cx="7" cy="32" r="5" />
      <circle cx="11" cy="26" r="4" />
      <circle cx="11" cy="38" r="4" />

      {/* Right arm trefoil */}
      <circle cx="57" cy="32" r="5" />
      <circle cx="53" cy="26" r="4" />
      <circle cx="53" cy="38" r="4" />
    </svg>
  );
}
