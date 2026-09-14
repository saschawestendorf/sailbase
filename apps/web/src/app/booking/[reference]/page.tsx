import Link from "next/link";

import BookingLookup from "@/components/BookingLookup";
import PriceExplainer from "@/components/PriceExplainer";
import {
  ApiError,
  type Booking,
  type BookingOps,
  getBooking,
  getBookingOps,
} from "@/lib/api";
import { dateLabel, label, money, nightsBetween, STATUS_LABELS } from "@/lib/format";

export const dynamic = "force-dynamic";

const PURPOSE_LABELS: Record<string, string> = {
  deposit: "Anzahlung",
  balance: "Restzahlung",
  security_deposit: "Kaution",
  extras: "Zusatzleistungen",
};

const ORDER_LABELS: Record<string, string> = {
  readiness: "Bootsbereitschaft",
  handover: "Übergabe",
  return: "Rücknahme",
  cleaning: "Reinigung",
  technical: "Technik",
  laundry: "Wäsche",
};

const ORDER_STATUS: Record<string, string> = {
  open: "offen",
  assigned: "geplant",
  in_progress: "läuft",
  done: "erledigt",
  cancelled: "storniert",
};

function statusTone(status: string) {
  if (["confirmed", "ready", "handed_over", "settled"].includes(status))
    return "bg-positive-soft text-positive";
  if (["cancelled", "expired"].includes(status)) return "bg-warn-soft text-warn";
  return "bg-accent-soft text-accent";
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function BookingPage(props: PageProps<"/booking/[reference]">) {
  const { reference } = await props.params;
  const sp = await props.searchParams;
  const email = first(sp.email) ?? "";

  if (!email) {
    return (
      <div className="mx-auto w-full max-w-md px-4 py-12">
        <h1 className="text-2xl font-semibold tracking-tight">Buchung {reference}</h1>
        <p className="mt-2 text-sm text-muted">
          Zur Sicherheit brauchen wir die E-Mail-Adresse, mit der gebucht wurde.
        </p>
        <div className="mt-6">
          <BookingLookup defaultReference={reference} />
        </div>
      </div>
    );
  }

  let booking: Booking;
  let ops: BookingOps | null = null;
  try {
    booking = await getBooking(reference, email);
    ops = await getBookingOps(reference, email).catch(() => null);
  } catch (error) {
    const message =
      error instanceof ApiError ? error.message : "Buchung konnte nicht geladen werden";
    return (
      <div className="mx-auto w-full max-w-md px-4 py-12">
        <h1 className="text-2xl font-semibold tracking-tight">Buchung {reference}</h1>
        <p className="mt-3 rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">{message}</p>
        <div className="mt-6">
          <BookingLookup defaultReference={reference} />
        </div>
      </div>
    );
  }

  const nights = nightsBetween(booking.start_date, booking.end_date);
  const openPayments = booking.payments.filter((p) => p.status !== "succeeded");
  const paid = booking.payments
    .filter((p) => p.status === "succeeded")
    .reduce((sum, p) => sum + p.amount_cents, 0);

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-sm text-muted">{booking.reference}</p>
          <h1 className="text-2xl font-semibold tracking-tight">
            {booking.boat?.name ?? "Charterbuchung"}
          </h1>
          <p className="mt-1 text-muted">
            {dateLabel(booking.start_date)} – {dateLabel(booking.end_date)} · {nights} Nächte ·{" "}
            {booking.persons} Personen
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-semibold ${statusTone(booking.status)}`}>
          {label(STATUS_LABELS, booking.status)}
        </span>
      </div>

      {booking.status === "pending_payment" ? (
        <p className="mt-4 rounded-xl bg-accent-soft px-4 py-3 text-sm text-accent">
          Die Anzahlung ist noch offen. Das Boot ist bis{" "}
          {dateLabel(booking.hold_expires_at, {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}{" "}
          reserviert.
        </p>
      ) : null}

      <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-5">
          <section className="card p-5">
            <h2 className="text-lg font-semibold">Zahlungen</h2>
            <table className="mt-3 w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="pb-2">Position</th>
                  <th className="pb-2">Fällig</th>
                  <th className="pb-2 text-right">Betrag</th>
                  <th className="pb-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {booking.payments.map((p) => (
                  <tr key={p.id} className="border-t border-line">
                    <td className="py-2">{label(PURPOSE_LABELS, p.purpose)}</td>
                    <td className="py-2 text-muted">{p.due_at ? dateLabel(p.due_at) : "–"}</td>
                    <td className="py-2 text-right font-mono">{money(p.amount_cents, true)}</td>
                    <td className="py-2 text-right">
                      {p.status === "succeeded" ? (
                        <span className="text-positive">bezahlt</span>
                      ) : (
                        <span className="text-muted">offen</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-sm text-muted">
              Bezahlt: <span className="font-mono">{money(paid, true)}</span> von{" "}
              <span className="font-mono">{money(booking.total_cents, true)}</span> Charterpreis
              {booking.security_deposit_cents
                ? ` zzgl. ${money(booking.security_deposit_cents)} Kaution`
                : ""}
              .
            </p>
            {openPayments.length ? (
              <p className="mt-2 text-xs text-muted">
                Offene Beträge können im Kundenportal bezahlt werden, sobald die Buchung bestätigt
                ist.
              </p>
            ) : null}
          </section>

          {ops?.orders?.length ? (
            <section className="card p-5">
              <h2 className="text-lg font-semibold">Ablauf</h2>
              <ul className="mt-3 space-y-3">
                {ops.orders.map((order) => {
                  const total = order.checklist?.length ?? 0;
                  const done = order.checklist?.filter((i) => i.done).length ?? 0;
                  return (
                    <li key={order.id} className="border-t border-line pt-3 first:border-0 first:pt-0">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="font-medium">{label(ORDER_LABELS, order.order_type)}</span>
                        <span className="text-sm text-muted">
                          {order.scheduled_for
                            ? dateLabel(order.scheduled_for, {
                                day: "2-digit",
                                month: "2-digit",
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : "Termin offen"}{" "}
                          · {label(ORDER_STATUS, order.status)}
                        </span>
                      </div>
                      {total ? (
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-muted">
                          <div
                            className="h-full rounded-full bg-accent"
                            style={{ width: `${Math.round((done / total) * 100)}%` }}
                          />
                        </div>
                      ) : null}
                      {order.base_name ? (
                        <p className="mt-1 text-xs text-muted">{order.base_name}</p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}

          {ops?.contract?.text_md ? (
            <section className="card p-5">
              <h2 className="text-lg font-semibold">Chartervertrag</h2>
              <p className="mt-1 text-sm text-muted">
                Version {ops.contract.version} ·{" "}
                {ops.contract_accepted_customer_at
                  ? `von dir bestätigt am ${dateLabel(ops.contract_accepted_customer_at)}`
                  : "noch nicht bestätigt"}
              </p>
              <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-muted p-4 text-xs leading-relaxed">
                {ops.contract.text_md}
              </pre>
            </section>
          ) : null}
        </div>

        <aside className="space-y-5">
          {booking.boat ? (
            <section className="card p-5">
              <h2 className="text-base font-semibold">Schiff und Hafen</h2>
              <p className="mt-2 text-sm text-muted">
                {booking.boat.manufacturer} {booking.boat.model} · {booking.boat.length_m.toFixed(2)} m
              </p>
              <p className="mt-1 text-sm text-muted">
                {booking.boat.base.name}, {booking.boat.base.city}
              </p>
              <p className="mt-1 text-sm text-muted">Vercharterer: {booking.boat.charterer.name}</p>
              <Link
                href={`/boats/${booking.boat.slug}`}
                className="mt-3 inline-block text-sm text-accent hover:underline"
              >
                Schiffsdetails ansehen
              </Link>
            </section>
          ) : null}

          {booking.price_breakdown?.total_cents ? (
            <section className="card p-5">
              <h2 className="text-base font-semibold">Preisdetails</h2>
              <div className="mt-3">
                <PriceExplainer breakdown={booking.price_breakdown} />
              </div>
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
