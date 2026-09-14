"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import { type AuthState, login, register } from "@/app/actions/auth";

function Submit({ label, pending }: { label: string; pending: boolean }) {
  return (
    <button type="submit" className="btn-primary w-full" disabled={pending}>
      {pending ? "Einen Moment …" : label}
    </button>
  );
}

function ErrorNote({ state }: { state: AuthState }) {
  if (!state.error) return null;
  return (
    <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
      {state.error}
    </p>
  );
}

export function LoginForm({ next }: { next?: string }) {
  const [state, action, pending] = useActionState<AuthState, FormData>(login, {});
  return (
    <form action={action} className="card space-y-3 p-5">
      {next ? <input type="hidden" name="next" value={next} /> : null}
      <div>
        <label className="label" htmlFor="email">
          E-Mail
        </label>
        <input id="email" name="email" type="email" required autoComplete="email" className="field" />
      </div>
      <div>
        <label className="label" htmlFor="password">
          Passwort
        </label>
        <input
          id="password"
          name="password"
          type="password"
          required
          autoComplete="current-password"
          className="field"
        />
      </div>
      <ErrorNote state={state} />
      <Submit label="Anmelden" pending={pending} />
      <p className="text-center text-sm text-muted">
        Noch kein Konto?{" "}
        <Link href="/register" className="text-accent hover:underline">
          Registrieren
        </Link>
      </p>
    </form>
  );
}

export function RegisterForm() {
  const [state, action, pending] = useActionState<AuthState, FormData>(register, {});
  const [role, setRole] = useState("customer");
  return (
    <form action={action} className="card space-y-3 p-5">
      <fieldset>
        <legend className="label">Ich möchte</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {[
            { value: "customer", label: "Ein Boot chartern" },
            { value: "charterer", label: "Mein Boot vermieten" },
          ].map((option) => (
            <label
              key={option.value}
              className={`cursor-pointer rounded-lg border px-3 py-2 text-sm ${
                role === option.value
                  ? "border-transparent bg-accent-soft font-medium text-accent"
                  : "border-line hover:bg-surface-muted"
              }`}
            >
              <input
                type="radio"
                name="role"
                value={option.value}
                checked={role === option.value}
                onChange={(e) => setRole(e.target.value)}
                className="sr-only"
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div>
        <label className="label" htmlFor="full_name">
          Name
        </label>
        <input id="full_name" name="full_name" required className="field" autoComplete="name" />
      </div>
      {role === "charterer" ? (
        <div>
          <label className="label" htmlFor="charterer_name">
            Firma oder Bootsname
          </label>
          <input id="charterer_name" name="charterer_name" className="field" />
        </div>
      ) : null}
      <div>
        <label className="label" htmlFor="reg-email">
          E-Mail
        </label>
        <input id="reg-email" name="email" type="email" required className="field" autoComplete="email" />
      </div>
      <div>
        <label className="label" htmlFor="reg-password">
          Passwort
        </label>
        <input
          id="reg-password"
          name="password"
          type="password"
          required
          minLength={8}
          className="field"
          autoComplete="new-password"
        />
        <p className="mt-1 text-xs text-muted">Mindestens acht Zeichen.</p>
      </div>
      <ErrorNote state={state} />
      <Submit label="Konto anlegen" pending={pending} />
      <p className="text-center text-sm text-muted">
        Schon registriert?{" "}
        <Link href="/login" className="text-accent hover:underline">
          Anmelden
        </Link>
      </p>
    </form>
  );
}
