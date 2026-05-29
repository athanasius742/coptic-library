type Props = {
  size?: number;
  className?: string;
  title?: string;
};

/**
 * Crescent moon in the same hand-drawn idiom as CopticCross — a solid
 * crescent carved out by two offset discs (a filled circle minus an
 * overlapping mask circle), with a small accompanying star.
 */
export function CopticMoon({ size = 32, className, title }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="currentColor"
      role="img"
      aria-label={title ?? "Moon"}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Carve the inner disc out of the outer disc to form the crescent. */}
        <mask id="coptic-moon-crescent">
          <rect x="0" y="0" width="64" height="64" fill="black" />
          <circle cx="30" cy="32" r="20" fill="white" />
          <circle cx="40" cy="26" r="17" fill="black" />
        </mask>
      </defs>

      <rect x="0" y="0" width="64" height="64" fill="currentColor" mask="url(#coptic-moon-crescent)" />

      {/* Small four-pointed Coptic star tucked beside the crescent. */}
      <path d="M48 12 L50 18 L56 20 L50 22 L48 28 L46 22 L40 20 L46 18 Z" />
    </svg>
  );
}
