type Props = {
  size?: number;
  className?: string;
  title?: string;
};

/**
 * Coptic / Byzantine-style globe — a globus cruciger: a meridian-and-equator
 * globe surmounted by a small trefoil cross (echoing CopticCross's three-lobed
 * arms). Built from currentColor strokes (globe) + solid fills (cross) to match
 * the CopticCross / CopticSun icon family.
 */
export function CopticGlobe({ size = 32, className, title }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="currentColor"
      role="img"
      aria-label={title ?? "Language"}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Globe outline */}
      <circle cx="32" cy="40" r="17" fill="none" stroke="currentColor" strokeWidth="2.5" />
      {/* Equator (latitude) */}
      <ellipse cx="32" cy="40" rx="17" ry="6" fill="none" stroke="currentColor" strokeWidth="2" />
      {/* Meridian (longitude) */}
      <ellipse cx="32" cy="40" rx="6.5" ry="17" fill="none" stroke="currentColor" strokeWidth="2" />

      {/* Globus cruciger — small cross resting on top of the globe */}
      <rect x="30" y="6" width="4" height="18" />
      <rect x="24.5" y="11" width="15" height="4" />
      {/* Trefoil top lobes, echoing CopticCross */}
      <circle cx="32" cy="5" r="3" />
      <circle cx="27.5" cy="8" r="2.3" />
      <circle cx="36.5" cy="8" r="2.3" />
    </svg>
  );
}
