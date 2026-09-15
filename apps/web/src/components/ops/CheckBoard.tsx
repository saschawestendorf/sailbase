"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { fetchJson } from "@/components/listing/useCatalog";
import ChecklistPanel from "@/components/ops/ChecklistPanel";
import type { Booking, BookingOps, Damage, Partner, Payment } from "@/lib/api";
import { dateLabel, label as labelOf, money, STATUS_LABELS } from "@/lib/format";

const PURPOSE_LABELS: Record<string, string> = {
  deposit: "Anzahlung",
  balance: "Restzahlung",
  security_deposit: "Kaution",
  extras: "Zusatzleistungen",
};

const ORDER_SEQUENCE = ["readiness", "handover", "return"];

function DamageRow({
  damage,
  securityDeposit,
  onChanged,
}: {
  damage: Damage;
  securityDeposit: number;
  onChanged: () => void;
}) {
  const [estimated, setEstimated] = useState(damage.estimated_cents / 100);
  const [withheld, setWithheld] = useState(damage.withheld_cents / 100);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const settled = damage.status !== "open";

  async function assess() {
    setBusy(true);
    setError(null);
    try {
      await fetchJson(`/api/charterer/damages/${damage.id}/assess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          estimated_cents: Math.round(estimated * 100),
          withheld_cents: Math.round(withheld * 100),
        }),
      });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bewertung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="border-t border-line py-3 first:border-0">
      <p className="font-medium">{damage.title}</p>
      {damage.description ? <p className="text-sm text-muted">{damage.description}</p> : null}
      {damage.photos?.length ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {damage.photos.map((url) => (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img key={url} src={url} alt="" className="h-16 w-20 rounded object-cover" />
          ))}
        </div>
      ) : null}
      {settled ? (
        <p className="mt-2 text-sm">
          Geschätzt {money(damage.estimated_cents)} · einbehalten {money(damage.withheld_cents)}
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div>
            <label className="label" htmlFor={`est-${damage.id}`}>
              Geschätzte Kosten
            </label>
            <input
              id={`est-${damage.id}`}
              type="number"
              min={0}
              step={10}
              className="field w-32"
              value={estimated}
              onChange={(e) => setEstimated(Number(e.target.value || 0))}
            />
          </div>
          <div>
            <label className="label" htmlFor={`wh-${damage.id}`}>
              Von der Kaution einbehalten
            </label>
            <input
              id={`wh-${damage.id}`}
              type="number"
              min={0}
              max={securityDeposit / 100}
              step={10}
              className="field w-32"
              value={withheld}
              onChange={(e) => setWithheld(Number(e.target.value || 0))}
            />
          </div>
          <button type="button" className="btn-ghost" onClick={assess} disabled={busy}>
            Bewerten
          </button>
        </div>
      )}
      {error ? (
        <p role="alert" className="mt-2 rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
          {error}
        </p>
      ) : null}
    </li>
  );
}

export default function CheckBoard({
  booking,
  ops,
  partners,
  payments,
}: {
  booking: Booking;
  ops: BookingOps;
  partners: Partner[];
  payments: Payment[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refresh = () => router.refresh();

  const orders = [...ops.orders].sort(
    (a, b) => ORDER_SEQUENCE.indexOf(a.order_type) - ORDER_SEQUENCE.indexOf(b.order_type),
  );
  const openDamages = ops.damages.filter((d) => d.status === "open");
  const canSettle = booking.status === "returned" && openDamages.length === 0 && !ops.payout;

  async function act(path: string, onError: string) {
    setBusy(true);
    setError(null);
    try {
      await fetchJson(path, { method: "POST" });
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : onError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_21rem]">
      <div className="space-y-4">
        {orders.map((order) => (
          <ChecklistPanel key={order.id} order={order} partners={partners} onChanged={refresh} />
        ))}

        <section className="card p-5">
          <h2 className="text-lg">Schäden</h2>
          <p className="mt-1 text-sm text-muted">
            Bei der Rücknahme als Auffälligkeit markierte Punkte landen hier. Vorher-/Nachher-Fotos
            liegen an den jeweiligen Checklistenpunkten.
          </p>
          {ops.damages.length ? (
            <ul className="mt-3">
              {ops.damages.map((damage) => (
                <DamageRow
                  key={damage.id}
                  damage={damage}
                  securityDeposit={booking.security_deposit_cents}
                  onChanged={refresh}
                />
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-muted">Kein Schadenfall offen.</p>
          )}
        </section>

        {ops.contract?.text_md ? (
          <section className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg">Chartervertrag</h2>
              {ops.contract_accepted_charterer_at ? (
                <span className="text-sm text-positive">
                  von dir bestätigt am {dateLabel(ops.contract_accepted_charterer_at)}
                </span>
              ) : (
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={busy}
                  onClick={() =>
                    act(
                      `/api/charterer/bookings/${booking.id}/accept-contract`,
                      "Bestätigung fehlgeschlagen",
                    )
                  }
                >
                  Vertrag bestätigen
                </button>
              )}
            </div>
            <p className="mt-1 text-sm text-muted">
              Kunde:{" "}
              {ops.contract_accepted_customer_at
                ? `bestätigt am ${dateLabel(ops.contract_accepted_customer_at)}`
                : "noch offen"}
            </p>
            <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-muted p-4 text-xs leading-relaxed">
              {ops.contract.text_md}
            </pre>
          </section>
        ) : null}
      </div>

      <aside className="space-y-4">
        <section className="card p-5">
          <h2 className="text-base">Crew und Unterlagen</h2>
          {ops.crew_list?.length ? (
            <ul className="mt-2 space-y-1 text-sm">
              {ops.crew_list.map((member, index) => (
                <li key={`${member.name}-${index}`}>
                  {member.name}
                  {member.role && member.role !== "crew" ? (
                    <span className="ml-1 chip">{member.role === "skipper" ? "Skipper" : "Co-Skipper"}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">Crewliste noch nicht eingereicht.</p>
          )}
          {ops.documents?.length ? (
            <ul className="mt-3 space-y-1 text-sm">
              {ops.documents.map((doc) => (
                <li key={doc.url}>
                  <a href={doc.url} className="text-accent hover:underline" target="_blank" rel="noreferrer">
                    {doc.name || doc.type}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">Keine Dokumente hochgeladen.</p>
          )}
        </section>

        <section className="card p-5">
          <h2 className="text-base">Zahlungen</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {payments.map((payment) => (
              <li key={payment.id} className="flex items-baseline justify-between gap-2">
                <span>{labelOf(PURPOSE_LABELS, payment.purpose)}</span>
                <span className="font-mono">
                  {money(payment.amount_cents)}
                  <span
                    className={`ml-2 text-xs ${payment.status === "succeeded" ? "text-positive" : "text-muted"}`}
                  >
                    {payment.status === "succeeded" ? "bezahlt" : "offen"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="card p-5">
          <h2 className="text-base">Abrechnung</h2>
          {ops.payout ? (
            <dl className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted">Charterpreis</dt>
                <dd className="font-mono">{money(ops.payout.gross_cents)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted">Provision</dt>
                <dd className="font-mono">−{money(ops.payout.commission_cents)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted">Servicekosten</dt>
                <dd className="font-mono">−{money(ops.payout.service_cost_cents)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted">Kautionseinbehalt</dt>
                <dd className="font-mono">+{money(ops.payout.damage_withheld_cents)}</dd>
              </div>
              <div className="mt-2 flex justify-between border-t border-line pt-2 font-semibold">
                <dt>Auszahlung</dt>
                <dd className="font-mono">{money(ops.payout.net_cents)}</dd>
              </div>
            </dl>
          ) : (
            <>
              <p className="mt-2 text-sm text-muted">
                {booking.status === "returned"
                  ? openDamages.length
                    ? `${openDamages.length} Schadenfall noch nicht bewertet.`
                    : "Bereit zur Abrechnung."
                  : "Erst nach dokumentierter Rücknahme möglich."}
              </p>
              <button
                type="button"
                className="btn-primary mt-3 w-full"
                disabled={!canSettle || busy}
                onClick={() =>
                  act(`/api/charterer/bookings/${booking.id}/settle`, "Abrechnung fehlgeschlagen")
                }
              >
                Kaution freigeben und abrechnen
              </button>
            </>
          )}
          <p className="mt-3 text-xs text-muted">
            Status der Buchung: {labelOf(STATUS_LABELS, booking.status)}
          </p>
        </section>

        {error ? (
          <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
            {error}
          </p>
        ) : null}
      </aside>
    </div>
  );
}
