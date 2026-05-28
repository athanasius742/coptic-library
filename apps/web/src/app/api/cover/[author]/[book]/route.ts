import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";

import { bookDirAbsolute } from "@/lib/catalog";

type Params = { author: string; book: string };

export async function GET(_req: Request, ctx: { params: Promise<Params> }) {
  const { author, book } = await ctx.params;
  if (!/^[a-z0-9-]+$/i.test(author) || !/^[a-z0-9-]+$/i.test(book)) {
    return new NextResponse("Bad request", { status: 400 });
  }
  const coverPath = path.join(bookDirAbsolute(author, book), "cover.jpg");
  try {
    const data = await fs.readFile(coverPath);
    return new NextResponse(new Uint8Array(data), {
      status: 200,
      headers: {
        "Content-Type": "image/jpeg",
        "Cache-Control": "public, max-age=3600, immutable",
      },
    });
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }
}
