import { promises as fs } from "node:fs";
import path from "node:path";

import { bookDirAbsolute } from "@/lib/catalog";

// Serve chapter images that live next to the book data
// (books/st-takla.org/<author>/<book>/images/<file>) — that tree is outside
// apps/web/public, so it can't be served statically.

const FILE_RE = /^[A-Za-z0-9._-]+\.(jpe?g|png|gif|webp)$/i;

const MIME: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".gif": "image/gif",
  ".webp": "image/webp",
};

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ author: string; book: string; file: string }> },
) {
  const { author, book, file } = await params;

  // Reject anything that isn't a plain image filename (blocks path traversal).
  if (!FILE_RE.test(file)) {
    return new Response("Not found", { status: 404 });
  }

  const filePath = path.join(bookDirAbsolute(author, book), "images", file);

  let data: Buffer;
  try {
    data = await fs.readFile(filePath);
  } catch {
    return new Response("Not found", { status: 404 });
  }

  const ext = path.extname(file).toLowerCase();
  return new Response(new Uint8Array(data), {
    headers: {
      "Content-Type": MIME[ext] ?? "application/octet-stream",
      "Cache-Control": "public, max-age=31536000, immutable",
    },
  });
}
