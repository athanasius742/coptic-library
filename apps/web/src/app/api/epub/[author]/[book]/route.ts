import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";

import { bookDirAbsolute, loadBook } from "@/lib/catalog";

type Params = { author: string; book: string };

export async function GET(_req: Request, ctx: { params: Promise<Params> }) {
  const { author, book } = await ctx.params;
  if (!/^[a-z0-9-]+$/i.test(author) || !/^[a-z0-9-]+$/i.test(book)) {
    return new NextResponse("Bad request", { status: 400 });
  }
  const meta = await loadBook(author, book);
  if (!meta?.epub) return new NextResponse("Not found", { status: 404 });
  const epubPath = path.join(bookDirAbsolute(author, book), meta.epub);
  try {
    const data = await fs.readFile(epubPath);
    return new NextResponse(new Uint8Array(data), {
      status: 200,
      headers: {
        "Content-Type": "application/epub+zip",
        "Content-Disposition": `attachment; filename="${meta.epub}"`,
      },
    });
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }
}
