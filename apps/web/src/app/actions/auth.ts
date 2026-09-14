"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { SESSION_COOKIE } from "@/lib/session";

export type AuthState = { error?: string };

const COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
  maxAge: 60 * 60 * 24,
};

function destination(role: string, requested: string | null): string {
  // Only same-origin paths, so a crafted ?next= cannot bounce someone off the site.
  if (requested && requested.startsWith("/") && !requested.startsWith("//")) return requested;
  if (role === "charterer") return "/charterer";
  if (role === "partner") return "/partner";
  return "/search";
}

async function storeToken(token: string): Promise<string> {
  const store = await cookies();
  store.set(SESSION_COOKIE, token, COOKIE_OPTIONS);
  const me = await apiFetch<{ role: string }>("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return me.role;
}

export async function login(_prev: AuthState, formData: FormData): Promise<AuthState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const next = formData.get("next") ? String(formData.get("next")) : null;
  if (!email || !password) return { error: "E-Mail und Passwort sind nötig." };

  let role: string;
  try {
    const { access_token } = await apiFetch<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    role = await storeToken(access_token);
  } catch (error) {
    return { error: error instanceof ApiError ? error.message : "Anmeldung fehlgeschlagen." };
  }
  redirect(destination(role, next));
}

export async function register(_prev: AuthState, formData: FormData): Promise<AuthState> {
  const payload = {
    email: String(formData.get("email") ?? "").trim(),
    password: String(formData.get("password") ?? ""),
    full_name: String(formData.get("full_name") ?? "").trim(),
    role: String(formData.get("role") ?? "customer"),
    charterer_name: formData.get("charterer_name")
      ? String(formData.get("charterer_name")).trim()
      : null,
  };
  if (payload.password.length < 8) {
    return { error: "Das Passwort braucht mindestens acht Zeichen." };
  }

  let role: string;
  try {
    const { access_token } = await apiFetch<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    role = await storeToken(access_token);
  } catch (error) {
    return { error: error instanceof ApiError ? error.message : "Registrierung fehlgeschlagen." };
  }
  redirect(destination(role, null));
}

export async function logout(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
  redirect("/");
}
