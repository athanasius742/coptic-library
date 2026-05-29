type Props = {
  size?: number;
  className?: string;
  title?: string;
};

/**
 * Coptic / Byzantine-style sun — a haloed central disc ringed by stylized
 * rays, echoing the gilded nimbus that surrounds saints in Coptic icons.
 * Built from solid currentColor shapes to match CopticCross.
 */
export function CopticSun({ size = 32, className, title }: Props) {
  // Twelve rays evenly around the disc; alternating long/short for the
  // hand-drawn, icon-like cadence rather than a mechanical starburst.
  const rays = Array.from({ length: 12 }, (_, i) => {
    const angle = (i * 30 * Math.PI) / 180;
    const long = i % 2 === 0;
    const inner = 19;
    const outer = long ? 30 : 26;
    const x1 = 32 + inner * Math.cos(angle);
    const y1 = 32 + inner * Math.sin(angle);
    const x2 = 32 + outer * Math.cos(angle);
    const y2 = 32 + outer * Math.sin(angle);
    return (
      <line
        key={i}
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke="currentColor"
        strokeWidth={long ? 3 : 2.5}
        strokeLinecap="round"
      />
    );
  });

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="currentColor"
      role="img"
      aria-label={title ?? "Sun"}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Nimbus ring — the icon's halo outline */}
      <circle cx="32" cy="32" r="15" fill="none" stroke="currentColor" strokeWidth="2.5" />
      {/* Solid central disc */}
      <circle cx="32" cy="32" r="9" />
      {rays}
    </svg>
  );
}
