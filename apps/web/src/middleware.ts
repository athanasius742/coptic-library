import { NextResponse, type NextRequest } from "next/server";

import { isLocale } from "@/lib/i18n";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const seg = pathname.split("/").filter(Boolean)[0];
  const locale = isLocale(seg) ? seg : "ar";

  // Propagate the active locale to the rendering pipeline via a request header
  // so the root layout can render the right `lang`/`dir` on <html>.
  const headers = new Headers(request.headers);
  headers.set("x-locale", locale);
  headers.set("x-pathname", pathname);

  return NextResponse.next({ request: { headers } });
}

export const config = {
  // Skip Next internals, API routes, sitemap/robots, and static assets.
  matcher: ["/((?!_next/|api/|favicon\\.ico|sitemap\\.xml|robots\\.txt).*)"],
};
