/**
 * Session handling.
 *
 * The access token lives in an HttpOnly cookie, so no script in the page can read it. The
 * API proxy attaches it as a bearer header on the way out, which keeps the token off the
 * client entirely while still letting client components call the API.
 */
import { cookies } from "next/headers";

import { apiFetch, ApiError } from "@/lib/api";

export const SESSION_COOKIE = "sailbase_session";

export type Session = {
  id: string;
  email: string;
  full_name: string;
  role: "customer" | "charterer" | "partner" | "admin";
  license_level: number;
  experience_nm: number;
  height_cm: number | null;
  charterer_id: string | null;
  partner_id: string | null;
};

export async function readToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

/** The signed-in user, or null. Never throws: a stale cookie just means signed out. */
export async function getSession(): Promise<Session | null> {
  const token = await readToken();
  if (!token) return null;
  try {
    return await apiFetch<Session>("/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (error) {
    if (error instanceof ApiError) return null;
    throw error;
  }
}

export const ROLE_LABELS: Record<Session["role"], string> = {
  customer: "Charterkunde",
  charterer: "Vercharterer",
  partner: "Servicepartner",
  admin: "Administration",
};
