"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { fetchJson } from "@/components/listing/useCatalog";
import PhotoUploader from "@/components/PhotoUploader";
import type { Booking, BookingOps, ReviewEligibility } from "@/lib/api";
import { dateLabel } from "@/lib/format";

const RATING_GROUPS: { key: string; label: string; hint?: string }[][] = [
  [
    { key: "rating_model", label: "Das Bootsmodell", hint: "Wie gut passt dieser Bootstyp?" },
    { key: "rating_condition", label: "Zustand dieses Schiffs" },
    { key: "rating_service", label: "Service des Vercharterers" },
  ],
  [
    { key: "rating_care", label: "Pflege" },
    { key: "rating_cleanliness", label: "Sauberkeit" },
    { key: "rating_accuracy", label: "Beschreibungstreue" },
    { key: "rating_equipment", label: "Funktion der Ausstattung" },
    { key: "rating_organisation", label: "Organisation" },
    { key: "rating_handover", label: "Übergabe" },
  ],
];

function StarPicker({
  value,
  onChange,
  label,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  label: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm">{label}</span>
      <span className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            type="button"
            key={star}
            onClick={() => onChange(value === star ? null : star)}
            aria-label={`${label}: ${star} von 5`}
            aria-pressed={value !== null && star <= value}
            className={`px-0.5 text-xl leading-none ${
              value !== null && star <= value ? "text-accent" : "text-muted"
            }`}
          >
            ★
          </button>
        ))}
      </span>
    </div>
  );
}

type Props = {
  booking: Booking;
  ops: BookingOps;
  eligibility: ReviewEligibility | null;
  email: string;
};

export default function CustomerCheck({ booking, ops, eligibility, email }: Props) {
  const router = useRouter();
  const [crew, setCrew] = useState(
    ops.crew_list?.length
      ? ops.crew_list.map((m) => ({ name: m.name, role: m.role ?? "crew" }))
      : [{ name: booking.customer_name, role: "skipper" }],
  );
  const [documents, setDocuments] = useState(ops.documents ?? []);
  const [ratings, setRatings] = useState<Record<string, number | null>>(() => {
    const existing = eligibility?.existing;
    const start: Record<string, number | null> = {};
    for (const group of RATING_GROUPS) {
      for (const item of group) {
        start[item.key] = existing
          ? ((existing as unknown as Record<string, number | null>)[item.key] ?? null)
          : null;
      }
    }
    return start;
  });
  const [title, setTitle] = useState(eligibility?.existing?.title ?? "");
  const [body, setBody] = useState(eligibility?.existing?.body ?? "");
  const [photos, setPhotos] = useState<string[]>(eligibility?.existing?.photos ?? []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const guestQuery = `?email=${encodeURIComponent(email)}`;
  const uploadEndpoint = `/api/bookings/${booking.reference}/uploads${guestQuery}`;

  async function call(path: string, init: RequestInit, message: string) {
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      await fetchJson(path, init);
      setSaved(message);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Das hat nicht geklappt");
    } finally {
      setBusy(false);
    }
  }

  const saveCrew = () =>
    call(
      `/api/bookings/${booking.reference}/crew${guestQuery}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ crew: crew.filter((m) => m.name.trim().length > 1) }),
      },
      "Crewliste gespeichert",
    );

  const confirm = (step: "handover" | "return") =>
    call(
      `/api/bookings/${booking.reference}/confirm/${step}${guestQuery}`,
      { method: "POST" },
      step === "handover" ? "Übernahme bestätigt" : "Rückgabe bestätigt",
    );

  const submitReview = () =>
    call(
      `/api/bookings/${booking.reference}/review${guestQuery}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...ratings, title, body, photos }),
      },
      "Danke, deine Bewertung ist veröffentlicht",
    );

  async function addDocument(urls: string[]) {
    const fresh = urls.filter((url) => !documents.some((d) => d.url === url));
    setDocuments(urls.map((url) => documents.find((d) => d.url === url) ?? { type: "license", name: "Dokument", url }));
    for (const url of fresh) {
      await call(
        `/api/bookings/${booking.reference}/documents${guestQuery}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type: "license", name: "Dokument", url }),
        },
        "Dokument hinterlegt",
      );
    }
  }

  const handover = ops.orders.find((o) => o.order_type === "handover");
  const returned = ops.orders.find((o) => o.order_type === "return");
  const mainRatingSet = ["rating_model", "rating_condition", "rating_service"].some(
    (key) => ratings[key] !== null,
  );

  return (
    <div className="space-y-5">
      {saved ? (
        <p className="rounded-xl bg-positive-soft px-4 py-3 text-sm text-positive">{saved}</p>
      ) : null}
      {error ? (
        <p role="alert" className="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
          {error}
        </p>
      ) : null}

      <section className="card p-5">
        <h2 className="text-lg font-semibold">Crew und Papiere</h2>
        <p className="mt-1 text-sm text-muted">
          Vor der Übernahme brauchen wir, wer an Bord ist und wer das Schiff führt.
        </p>
        <ul className="mt-3 space-y-2">
          {crew.map((member, index) => (
            <li key={index} className="flex gap-2">
              <input
                className="field"
                placeholder="Name"
                value={member.name}
                onChange={(e) =>
                  setCrew(crew.map((m, i) => (i === index ? { ...m, name: e.target.value } : m)))
                }
              />
              <select
                className="field w-40"
                aria-label="Rolle"
                value={member.role}
                onChange={(e) =>
                  setCrew(crew.map((m, i) => (i === index ? { ...m, role: e.target.value } : m)))
                }
              >
                <option value="skipper">Skipper</option>
                <option value="co_skipper">Co-Skipper</option>
                <option value="crew">Crew</option>
              </select>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setCrew(crew.filter((_, i) => i !== index))}
                aria-label="Person entfernen"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setCrew([...crew, { name: "", role: "crew" }])}
            disabled={crew.length >= booking.persons}
          >
            Person hinzufügen
          </button>
          <button type="button" className="btn-primary" onClick={saveCrew} disabled={busy}>
            Crewliste speichern
          </button>
        </div>
        <p className="mt-2 text-xs text-muted">
          Maximal {booking.persons} Personen laut Buchung.
        </p>

        <div className="mt-4 border-t border-line pt-4">
          <span className="label">Führerscheine und Nachweise</span>
          <PhotoUploader
            urls={documents.map((d) => d.url)}
            onChange={addDocument}
            endpoint={uploadEndpoint}
            max={8}
            label="Dokument hochladen"
          />
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-lg font-semibold">Übernahme und Rückgabe</h2>
        <p className="mt-1 text-sm text-muted">
          Der Vercharterer arbeitet die Checkliste ab und dokumentiert den Zustand mit Fotos. Du
          bestätigst anschließend digital.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {[
            ["handover", "Übernahme", handover, ops.handover_confirmed_customer_at] as const,
            ["return", "Rückgabe", returned, ops.return_confirmed_customer_at] as const,
          ].map(([step, label, order, confirmedAt]) => (
            <div key={step} className="rounded-lg border border-line p-3">
              <p className="font-medium">{label}</p>
              <p className="mt-1 text-sm text-muted">
                {order
                  ? order.status === "done"
                    ? "Protokoll abgeschlossen"
                    : "Protokoll noch offen"
                  : "noch nicht geplant"}
              </p>
              {confirmedAt ? (
                <p className="mt-2 text-sm text-positive">
                  Von dir bestätigt am {dateLabel(confirmedAt)}
                </p>
              ) : (
                <button
                  type="button"
                  className="btn-ghost mt-2"
                  disabled={busy || !order || order.status !== "done"}
                  onClick={() => confirm(step)}
                >
                  {label} bestätigen
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-lg font-semibold">Deine Bewertung</h2>
        {!eligibility?.may_review ? (
          <p className="mt-2 rounded-lg bg-surface-muted px-3 py-2 text-sm text-muted">
            {eligibility?.reason ||
              "Bewerten kannst du, sobald die Rückgabe dokumentiert ist. So steht hinter jeder Bewertung eine echte Charter."}
          </p>
        ) : (
          <>
            <p className="mt-1 text-sm text-muted">
              Modell, Zustand dieses Schiffs und Service werden getrennt bewertet. So sieht die
              nächste Crew, woran ein Punktabzug lag.
            </p>
            <div className="mt-4 space-y-4">
              <div className="space-y-2">
                {RATING_GROUPS[0].map((item) => (
                  <StarPicker
                    key={item.key}
                    label={item.label}
                    value={ratings[item.key] ?? null}
                    onChange={(v) => setRatings({ ...ratings, [item.key]: v })}
                  />
                ))}
              </div>
              <details className="rounded-lg border border-line p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  Genauer bewerten (optional)
                </summary>
                <div className="mt-3 space-y-2">
                  {RATING_GROUPS[1].map((item) => (
                    <StarPicker
                      key={item.key}
                      label={item.label}
                      value={ratings[item.key] ?? null}
                      onChange={(v) => setRatings({ ...ratings, [item.key]: v })}
                    />
                  ))}
                </div>
              </details>
              <div>
                <label className="label" htmlFor="review-title">
                  Überschrift
                </label>
                <input
                  id="review-title"
                  className="field"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={255}
                />
              </div>
              <div>
                <label className="label" htmlFor="review-body">
                  Wie war der Törn?
                </label>
                <textarea
                  id="review-body"
                  rows={4}
                  className="field"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                />
              </div>
              <div>
                <span className="label">Deine Fotos</span>
                <PhotoUploader
                  urls={photos}
                  onChange={setPhotos}
                  endpoint={uploadEndpoint}
                  max={12}
                />
                <p className="mt-1 text-xs text-muted">
                  Deine Bilder erscheinen in der Galerie mit dem Chartermonat, getrennt von
                  Anbieter- und Modellfotos.
                </p>
              </div>
              <button
                type="button"
                className="btn-primary"
                onClick={submitReview}
                disabled={busy || !mainRatingSet}
              >
                {eligibility.existing ? "Bewertung aktualisieren" : "Bewertung veröffentlichen"}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
