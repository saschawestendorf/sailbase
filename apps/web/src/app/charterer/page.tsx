import Link from "next/link";

import { ApiError, type Boat, getMyBoats, getMyBookings, getMyStats } from "@/lib/api";
import { dateLabel, money, signedPercent, STATUS_LABELS, label as labelOf } from "@/lib/format";
import { requireRole } from "@/lib/guard";

export const dynamic = "force-dynamic";
export const metadata = { title: "Meine Flotte – Sailbase" };

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export default async function ChartererPage() {
  const { token, session } = await requireRole("charterer", "/charterer");

  let boats: Boat[] = [];
  let stats = null;
  let bookings = null;
  let error: string | null = null;
  try {
    [boats, stats, bookings] = await Promise.all([
      getMyBoats(token),
      getMyStats(token),
      getMyBookings(token),
    ]);
  } catch (err) {
    error = err instanceof ApiError ? err.message : "Daten konnten nicht geladen werden";
  }

  const openGaps = (stats?.gaps_next_90d ?? []).filter((g) => g.sellable).slice(0, 6);
  const upcoming = (bookings ?? [])
    .filter((b) => b.status !== "cancelled" && b.status !== "expired")
    .slice(0, 8);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {session.full_name || "Meine Flotte"}
          </h1>
          <p className="mt-1 text-muted">Auslastung, Erlöse und was als Nächstes ansteht.</p>
        </div>
        <Link href="/charterer/boats/new" className="btn-primary">
          Boot einstellen
        </Link>
      </div>

      {error ? <p className="card mt-6 p-5 text-sm text-warn">{error}</p> : null}

      {stats ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            label="Auslastung 90 Tage"
            value={`${(stats.occupancy_next_90d * 100).toFixed(0)} %`}
            hint={`${stats.boats} Boote im Bestand`}
          />
          <Stat
            label="Umsatz bestätigt"
            value={money(stats.revenue_cents)}
            hint={`${stats.charter_nights} Chartertage`}
          />
          <Stat
            label="gegenüber statischem Tarif"
            value={signedPercent(stats.dynamic_uplift_cents, stats.static_revenue_cents)}
            hint={`${money(stats.dynamic_uplift_cents)} Unterschied`}
          />
          <Stat
            label="Auszahlung offen"
            value={money(stats.payouts_pending_cents)}
            hint={`${money(stats.commission_cents)} Provision, ${money(stats.service_cost_cents)} Service`}
          />
        </div>
      ) : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section>
          <h2 className="text-lg font-semibold">Boote</h2>
          <div className="mt-3 grid gap-3">
            {boats.map((boat) => (
              <article key={boat.id} className="card flex flex-wrap items-center gap-4 p-4">
                {boat.images?.[0] ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={boat.images[0]}
                    alt=""
                    className="h-16 w-24 rounded-lg object-cover"
                    loading="lazy"
                  />
                ) : null}
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{boat.name}</p>
                  <p className="text-sm text-muted">
                    {boat.manufacturer} {boat.model} · {boat.base.name} · Mindestdauer{" "}
                    {boat.min_days} Nächte
                    {boat.changeover_weekdays?.length ? " · feste Wechseltage" : " · jeder Wechseltag"}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Link href={`/charterer/boats/${boat.id}/pricing`} className="btn-ghost">
                    Preisoptimierung
                  </Link>
                  <Link href={`/charterer/boats/${boat.id}/edit`} className="btn-ghost">
                    Inserat
                  </Link>
                </div>
              </article>
            ))}
            {!boats.length && !error ? (
              <p className="card p-5 text-sm text-muted">
                Noch kein Boot eingestellt. Der Katalog nimmt dir die technischen Daten ab.
              </p>
            ) : null}
          </div>

          <h2 className="mt-8 text-lg font-semibold">Buchungen</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="pb-2">Referenz</th>
                  <th className="pb-2">Zeitraum</th>
                  <th className="pb-2">Boot</th>
                  <th className="pb-2 text-right">Preis</th>
                  <th className="pb-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {upcoming.map((booking) => (
                  <tr key={booking.id} className="border-t border-line">
                    <td className="py-2">
                      <Link
                        href={`/charterer/bookings/${booking.id}`}
                        className="font-mono text-accent hover:underline"
                      >
                        {booking.reference}
                      </Link>
                    </td>
                    <td className="py-2 text-muted">
                      {dateLabel(booking.start_date, { day: "2-digit", month: "2-digit" })} –{" "}
                      {dateLabel(booking.end_date, { day: "2-digit", month: "2-digit" })}
                    </td>
                    <td className="py-2">{booking.boat?.name ?? "–"}</td>
                    <td className="py-2 text-right font-mono">{money(booking.total_cents)}</td>
                    <td className="py-2 text-right">{labelOf(STATUS_LABELS, booking.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!upcoming.length ? (
              <p className="py-4 text-sm text-muted">Noch keine Buchungen.</p>
            ) : null}
          </div>
        </section>

        <aside className="space-y-4">
          <section className="card p-5">
            <h2 className="text-base font-semibold">Verkäufliche Lücken</h2>
            <p className="mt-1 text-xs text-muted">
              Freie Zeiträume der nächsten 90 Tage, die lang genug für eine Buchung sind.
            </p>
            <ul className="mt-3 space-y-2 text-sm">
              {openGaps.map((gap) => (
                <li key={`${gap.boat_id}-${gap.start_date}`} className="border-t border-line pt-2 first:border-0 first:pt-0">
                  <span className="font-medium">{gap.boat_name}</span>
                  <span className="block text-muted">
                    {dateLabel(gap.start_date, { day: "2-digit", month: "2-digit" })} –{" "}
                    {dateLabel(gap.end_date, { day: "2-digit", month: "2-digit" })} · {gap.nights}{" "}
                    Nächte
                  </span>
                </li>
              ))}
              {!openGaps.length ? <li className="text-muted">Keine offenen Lücken.</li> : null}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
