type Props = {
  size?: number;
  className?: string;
  title?: string;
};

/**
 * Coptic-style reader/orant — a haloed bust echoing the icon-figure idiom of
 * Coptic manuscript portraits. Built from currentColor strokes + a small solid
 * trefoil-less halo to sit alongside the CopticCross / CopticGlobe family.
 */
export function CopticUser({ size = 32, className, title }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      role="img"
      aria-label={title ?? "Profile"}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Halo */}
      <circle cx="32" cy="22" r="20" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
      {/* Head */}
      <circle cx="32" cy="22" r="11" stroke="currentColor" strokeWidth="2.5" />
      {/* Shoulders / bust */}
      <path
        d="M12 56c0-11 9-19 20-19s20 8 20 19"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* Small cross above the halo, echoing the icon idiom */}
      <rect x="30.5" y="1" width="3" height="8" fill="currentColor" />
      <rect x="28" y="3.5" width="8" height="3" fill="currentColor" />
    </svg>
  );
}
