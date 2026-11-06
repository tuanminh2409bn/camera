import { NextResponse, type NextRequest } from "next/server";
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const dev = process.env.NODE_ENV === "development";
  const policy = `default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}; style-src 'self' 'nonce-${nonce}'; img-src 'self' data:; font-src 'self'; media-src 'self' blob:; connect-src 'self'${dev ? " ws://127.0.0.1:3000" : ""}; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`;
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("Cache-Control", "no-store");
  return response;
}
export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
