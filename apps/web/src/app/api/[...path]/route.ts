/**
 * Transparent proxy to the Sailbase API.
 *
 * Client components call same-origin `/api/...`, so the backend URL stays a server-side
 * runtime setting and never has to be baked into the browser bundle at build time.
 */
import { cookies } from "next/headers";
import { NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { SESSION_COOKIE } from "@/lib/session";

export const dynamic = "force-dynamic";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

async function forward(req: NextRequest, path: string[]) {
  const target = `${API_BASE_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });
  // The token stays in an HttpOnly cookie and only becomes a bearer header here, so a
  // client component can call the API without ever holding the token itself.
  if (!headers.has("authorization")) {
    const token = (await cookies()).get(SESSION_COOKIE)?.value;
    if (token) headers.set("authorization", `Bearer ${token}`);
  }
  headers.delete("cookie");

  const method = req.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(target, { method, headers, body, redirect: "manual", cache: "no-store" });
  } catch {
    return Response.json({ detail: "Backend nicht erreichbar" }, { status: 503 });
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) out.set(key, value);
  });
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
