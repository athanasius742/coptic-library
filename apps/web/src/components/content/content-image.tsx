type ContentImageProps = {
  src: string;
  alt: string;
};

/**
 * A chapter image, served from the per-book images route. Rendered as a plain
 * <img> (not next/image) because the source path is a dynamic disk-served URL.
 * Compact + floated styling lives in globals.css (`.content-image`), which
 * floats it to the inline-end side so running text wraps around it.
 */
export function ContentImage({ src, alt }: ContentImageProps) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className="content-image"
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
    />
  );
}
