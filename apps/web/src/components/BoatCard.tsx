import Link from "next/link";

import type { Base, SearchHit } from "@/lib/api";
import { CHARACTER_LABELS, dateRange, label, money } from "@/lib/format";

function FitBadge({ score }: { score: number }) {
  const tone =
    score >= 80
      ? "bg-positive-soft text-positive"
      : score >= 60
        ? "bg-accent-soft text-accent"
        : "bg-surface-muted text-muted";
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
      {Math.round(score)} % Passung
    </span>
  );
}

type Props = { hit: SearchHit; query: string; basesById: Record<string, Base> };

export default function BoatCard({ hit, query, basesById }: Props) {
  const { boat, offers } = hit;
  const best = offers[0];
  const alternatives = offers.slice(1, 4);
  const href = `/boats/${boat.slug}?${query}`;

  return (
    <article className="card overflow-hidden transition hover:shadow-lg">
      <div className="grid sm:grid-cols-[minmax(0,13rem)_1fr]">
        <Link href={href} className="relative block aspect-[4/3] bg-surface-muted sm:aspect-auto">
          {boat.images?.[0] ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={boat.images[0]}
              alt={boat.name}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : null}
        </Link>

        <div className="flex flex-col gap-3 p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <Link href={href} className="text-lg font-semibold hover:underline">
                {boat.name}
              </Link>
              <p className="text-sm text-muted">
                {boat.manufacturer} {boat.model} · {boat.length_m.toFixed(2)} m ·{" "}
                {boat.base.name}
              </p>
            </div>
            <FitBadge score={hit.fit_score} />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {(boat.character ?? []).map((c) => (
              <span key={c} className="chip">
                {label(CHARACTER_LABELS, c)}
              </span>
            ))}
            <span className="chip">
              {boat.cabins} Kabinen · {boat.berths} Kojen
            </span>
            {boat.headroom_cm ? <span className="chip">Stehhöhe {boat.headroom_cm} cm</span> : null}
            {boat.max_berth_length_cm ? (
              <span className="chip">Koje {boat.max_berth_length_cm} cm</span>
            ) : null}
          </div>

          {hit.fit_reasons.length ? (
            <ul className="space-y-0.5 text-sm text-muted">
              {hit.fit_reasons.slice(0, 3).map((r) => (
                <li key={r}>+ {r}</li>
              ))}
            </ul>
          ) : null}

          {best ? (
            <div className="mt-auto flex flex-wrap items-end justify-between gap-3 border-t border-line pt-3">
              <div>
                <p className="text-xs text-muted">{dateRange(best.start_date, best.end_date)}</p>
                <p className="text-xl font-semibold">
                  {money(best.total_cents)}
                  <span className="ml-1 text-sm font-normal text-muted">
                    · {money(best.per_day_cents)}/Nacht
                  </span>
                </p>
                {best.dropoff_base_id && best.dropoff_base_id !== best.pickup_base_id ? (
                  <p className="text-xs text-accent">
                    One-Way nach {basesById[best.dropoff_base_id]?.name ?? "anderem Hafen"}
                  </p>
                ) : null}
              </div>
              <Link href={href} className="btn-primary">
                Ansehen
              </Link>
            </div>
          ) : (
            <p className="mt-auto border-t border-line pt-3 text-sm text-warn">
              {hit.unavailable_reason || "Kein Angebot in diesem Zeitraum"}
            </p>
          )}

          {alternatives.length ? (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="text-muted">Alternativen:</span>
              {alternatives.map((o) => (
                <Link
                  key={`${o.start_date}-${o.nights}`}
                  href={`/boats/${boat.slug}?start_date=${o.start_date}&end_date=${o.end_date}&persons=${hit.boat.max_persons ? Math.min(hit.boat.max_persons, 4) : 4}`}
                  className="rounded-full border border-line px-2 py-0.5 hover:bg-surface-muted"
                >
                  {o.nights} Nächte ab {dateRange(o.start_date, o.end_date).split(" – ")[0]} ·{" "}
                  {money(o.total_cents)}
                </Link>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
