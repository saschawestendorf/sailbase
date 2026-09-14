"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function BookingLookup({ defaultReference = "" }: { defaultReference?: string }) {
  const router = useRouter();
  const [reference, setReference] = useState(defaultReference);
  const [email, setEmail] = useState("");

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const ref = reference.trim().toUpperCase();
    if (!ref) return;
    router.push(`/booking/${encodeURIComponent(ref)}?email=${encodeURIComponent(email.trim())}`);
  }

  return (
    <form onSubmit={submit} className="card space-y-3 p-5">
      <div>
        <label className="label" htmlFor="reference">
          Buchungsnummer
        </label>
        <input
          id="reference"
          className="field font-mono"
          placeholder="SB-XXXXXX"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          required
        />
      </div>
      <div>
        <label className="label" htmlFor="lookup-email">
          E-Mail der Buchung
        </label>
        <input
          id="lookup-email"
          className="field"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>
      <button type="submit" className="btn-primary w-full">
        Buchung öffnen
      </button>
    </form>
  );
}
