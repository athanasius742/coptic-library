import Image from "next/image";

import { CopticCross } from "./coptic-cross";

type Props = {
  slug: string;
  name: string;
  size: number;
  portraitPath: string | null;
  ringClass?: string;
};

/**
 * Circular author avatar. Renders the portrait when one exists, otherwise the
 * Coptic cross inside a halo'd, gold-ringed circle — matching the fallback
 * treatment used across the author lists and headers.
 */
export function AuthorAvatar({
  name,
  size,
  portraitPath,
  ringClass = "ring-1 ring-gold-600",
}: Props) {
  const box = { width: size, height: size };

  if (portraitPath) {
    return (
      <span
        className={`halo-glow relative inline-flex shrink-0 overflow-hidden rounded-full bg-bg ${ringClass}`}
        style={box}
      >
        <Image
          src={portraitPath}
          alt={name}
          fill
          sizes={`${size}px`}
          className="object-cover"
        />
      </span>
    );
  }

  return (
    <span
      className={`halo-glow inline-flex shrink-0 items-center justify-center rounded-full bg-bg text-gold-200 transition group-hover:text-gold-100 ${ringClass}`}
      style={box}
    >
      <CopticCross size={Math.round(size * 0.5)} />
    </span>
  );
}
