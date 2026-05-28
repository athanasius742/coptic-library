import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";

import { authorPortraitAbsolute } from "@/lib/authors-meta";

type Params = { author: string };

export async function GET(_req: Request, ctx: { params: Promise<Params> }) {
  const { author } = await ctx.params;
  if (!/^[a-z0-9-]+$/i.test(author)) {
    return new NextResponse("Bad request", { status: 400 });
  }
  const portraitPath = authorPortraitAbsolute(author);
  try {
    const data = await fs.readFile(portraitPath);
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
