import Link from "next/link";

import SailPlaceholder from "@/components/ui/SailPlaceholder";
import { ApiError, type Boat, getMyBoats, getMyBookings, getMyStats } from "@/lib/api";
import { dateLabel, money, signedPercent, STATUS_LABELS, label as labelOf } from "@/lib/format";
import { requireRole } from "@/lib/guard";

export const dynamic = "force-dynamic";
export const metadata = { title: "Meine Flotte – Sailbase" };

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card p-5">
      <p className="stat-label">{label}</p>
      <p className="stat-value mt-2">{value}</p>
      {hint ? <p className="mt-1.5 text-xs text-muted">{hint}</p> : null}
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
  // Nach vorne sortiert statt nach hinten: was als Nächstes ansteht, ist das,
  // wofür jemand dieses Dashboard öffnet. Die Liste vom Server läuft rückwärts
  // durchs Jahr und zeigte sonst zuerst die fernste Buchung.
  const todayIso = new Date().toISOString().slice(0, 10);
  const relevant = (bookings ?? []).filter(
    (b) => b.status !== "cancelled" && b.status !== "expired",
  );
  const upcoming = [
    ...relevant.filter((b) => b.end_date >= todayIso).sort((a, b) => a.start_date.localeCompare(b.start_date)),
    ...relevant.filter((b) => b.end_date < todayIso).sort((a, b) => b.start_date.localeCompare(a.start_date)),
  ].slice(0, 10);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Meine Flotte</p>
          <h1 className="mt-2.5 text-3xl">{session.full_name || "Meine Flotte"}</h1>
          <p className="mt-1.5 text-muted">Auslastung, Erlöse und was als Nächstes ansteht.</p>
        </div>
        <Link href="/charterer/boats/new" className="btn-primary">
          Boot einstellen
        </Link>
      </div>

      {error ? <p className="card mt-6 p-5 text-sm text-warn">{error}</p> : null}

      {stats ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
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
          {/* Der Vergleich rechnet dieselben Buchungen zum festen Saisontarif nach.
              Er sagt nichts darüber, ob ein starrer Tarif sie überhaupt bekommen
              hätte – genau das rechnet die Preisoptimierung je Boot. Das gehört
              in den Hinweis, sonst liest sich ein Minus wie ein Verlust. */}
          <Stat
            label="Preis ggü. festem Saisontarif"
            value={signedPercent(stats.dynamic_uplift_cents, stats.static_revenue_cents)}
            hint={`${money(stats.dynamic_uplift_cents)} bei gleichen Buchungen · was ein starrer Tarif gar nicht verkauft hätte, zeigt die Preisoptimierung`}
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
          <h2 className="text-xl">Boote</h2>
          <div className="mt-4 grid gap-4">
            {boats.map((boat) => (
              <article key={boat.id} className="card flex flex-wrap items-center gap-4 p-4">
                {boat.images?.[0] ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={boat.images[0]}
                    alt=""
                    className="h-16 w-24 rounded-xl object-cover"
                    loading="lazy"
                  />
                ) : (
                  <SailPlaceholder name={boat.name} className="h-16 w-24 rounded-xl" />
                )}
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

          <h2 className="mt-10 text-xl">Buchungen</h2>
          <div className="card mt-4 overflow-x-auto p-1.5">
            <table className="w-full text-sm">
              <thead className="text-left text-[0.7rem] uppercase tracking-[0.1em] text-faint">
                <tr>
                  <th className="px-3 py-3">Referenz</th>
                  <th className="px-3 py-3">Zeitraum</th>
                  <th className="px-3 py-3">Boot</th>
                  <th className="px-3 py-3 text-right">Preis</th>
                  <th className="px-3 py-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {upcoming.map((booking) => (
                  <tr key={booking.id} className="border-t border-line transition-colors hover:bg-surface-muted/60">
                    <td className="px-3 py-2.5">
                      <Link
                        href={`/charterer/bookings/${booking.id}`}
                        className="font-mono text-accent hover:underline"
                      >
                        {booking.reference}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 text-muted">
                      {dateLabel(booking.start_date, { day: "2-digit", month: "2-digit" })} –{" "}
                      {dateLabel(booking.end_date, { day: "2-digit", month: "2-digit" })}
                    </td>
                    <td className="px-3 py-2.5">{booking.boat?.name ?? "–"}</td>
                    <td className="px-3 py-2.5 text-right font-medium">
                      {money(booking.total_cents)}
                    </td>
                    <td className="px-3 py-2.5 text-right text-muted">
                      {labelOf(STATUS_LABELS, booking.status)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!upcoming.length ? (
              <p className="px-3 py-5 text-sm text-muted">Noch keine Buchungen.</p>
            ) : null}
          </div>
        </section>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <section className="card p-6">
            <h2 className="text-lg">Verkäufliche Lücken</h2>
            <p className="mt-1.5 text-xs leading-relaxed text-muted">
              Freie Zeiträume der nächsten 90 Tage, die lang genug für eine Buchung sind.
            </p>
            <ul className="mt-4 space-y-2.5 text-sm">
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
