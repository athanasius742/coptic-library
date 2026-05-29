import { ContentImage } from "./content-image";

type ContentFigureProps = {
  src: string;
  alt: string;
  caption?: string;
};

/**
 * An image with a caption (from the source's image-wrapper tables). The whole
 * figure floats to the inline-end side via `.content-figure` in globals.css so
 * the caption stays with its image and text wraps around the block.
 */
export function ContentFigure({ src, alt, caption }: ContentFigureProps) {
  return (
    <figure className="content-figure">
      <ContentImage src={src} alt={alt} />
      {caption ? (
        <figcaption className="content-figcaption">{caption}</figcaption>
      ) : null}
    </figure>
  );
}
