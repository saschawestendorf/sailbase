"use client";

import { useState } from "react";

import type { BookingCreated, Quote } from "@/lib/api";
import { money } from "@/lib/format";

type Props = {
  boatId: string;
  startDate: string;
  endDate: string;
  persons: number;
  pickupBaseId?: string;
  dropoffBaseId?: string;
  quote: Quote | null;
  quoteError?: string;
};

/**
 * Two steps against the API: `/quotes` locks the dynamically computed price for a few minutes,
 * `/bookings` turns that quote into a hold plus a payment checkout.
 */
export default function BookingForm({
  boatId,
  startDate,
  endDate,
  persons,
  pickupBaseId,
  dropoffBaseId,
  quote,
  quoteError,
}: Props) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [terms, setTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function book(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // Re-quote right before booking so the customer always pays the price they just saw.
      const quoteRes = await fetch("/api/quotes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          boat_id: boatId,
          start_date: startDate,
          end_date: endDate,
          persons,
          pickup_base_id: pickupBaseId || null,
          dropoff_base_id: dropoffBaseId || null,
        }),
      });
      const fresh = await quoteRes.json();
      if (!quoteRes.ok) throw new Error(fresh?.detail ?? "Angebot konnte nicht erstellt werden");

      const bookingRes = await fetch("/api/bookings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quote_id: fresh.id,
          customer_name: name,
          customer_email: email,
          accept_terms: terms,
        }),
      });
      const created: BookingCreated & { detail?: string } = await bookingRes.json();
      if (!bookingRes.ok) throw new Error(created?.detail ?? "Buchung fehlgeschlagen");

      // The payment provider takes over; it redirects back to the booking page when done.
      window.location.href = created.checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unerwarteter Fehler");
      setBusy(false);
    }
  }

  if (!quote) {
    return (
      <p className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
        {quoteError ?? "Für diesen Zeitraum gibt es kein Angebot."}
      </p>
    );
  }

  const deposit = Math.max(1, Math.round(quote.total_cents * 0.3));

  return (
    <form onSubmit={book} className="space-y-3">
      <div>
        <label className="label" htmlFor="customer-name">
          Name der Crew-Verantwortlichen Person
        </label>
        <input
          id="customer-name"
          className="field"
          required
          minLength={2}
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
        />
      </div>
      <div>
        <label className="label" htmlFor="customer-email">
          E-Mail
        </label>
        <input
          id="customer-email"
          className="field"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <p className="mt-1 text-xs text-muted">
          Mit dieser Adresse rufst du deine Buchung später auf.
        </p>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={terms}
          onChange={(e) => setTerms(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-[var(--accent)]"
          required
        />
        <span>
          Ich akzeptiere die Chartervertragsbedingungen. Der Vertrag wird nach der Anzahlung
          erstellt und kann digital bestätigt werden.
        </span>
      </label>

      {error ? <p className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">{error}</p> : null}

      <button type="submit" className="btn-primary w-full" disabled={busy}>
        {busy ? "Wird gebucht …" : `Verbindlich buchen · ${money(deposit)} Anzahlung`}
      </button>
      <p className="text-center text-xs text-muted">
        Restzahlung bis 30 Tage vor Übernahme. Kaution separat vor Törnbeginn.
      </p>
    </form>
  );
}
