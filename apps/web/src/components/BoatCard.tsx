import Link from "next/link";

import SailPlaceholder from "@/components/ui/SailPlaceholder";
import type { Base, SearchHit } from "@/lib/api";
import { CHARACTER_LABELS, dateRange, label, money } from "@/lib/format";

function FitBadge({ score }: { score: number }) {
  const tone =
    score >= 80
      ? "bg-positive-soft text-positive"
      : score >= 60
        ? "bg-accent-soft text-accent"
        : "bg-surface-muted text-muted";
  return <span className={`badge ${tone}`}>{Math.round(score)} % Passung</span>;
}

type Props = { hit: SearchHit; query: string; basesById: Record<string, Base> };

export default function BoatCard({ hit, query, basesById }: Props) {
  const { boat, offers } = hit;
  const best = offers[0];
  const alternatives = offers.slice(1, 4);
  const href = `/boats/${boat.slug}?${query}`;
  const oneWay = best?.dropoff_base_id && best.dropoff_base_id !== best.pickup_base_id;

  return (
    <article className="card card-link overflow-hidden">
      <div className="grid sm:grid-cols-[minmax(0,15rem)_1fr]">
        <Link
          href={href}
          className="relative block aspect-[4/3] overflow-hidden sm:aspect-auto sm:min-h-[15rem]"
        >
          {boat.images?.[0] ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={boat.images[0]}
              alt={boat.name}
              className="h-full w-full object-cover transition-transform duration-500 hover:scale-[1.03]"
              loading="lazy"
            />
          ) : (
            <SailPlaceholder name={boat.name} className="h-full w-full" />
          )}
          {/* Die Passung sitzt im Bild, weil sie die erste Frage beantwortet:
              lohnt sich das Weiterlesen? */}
          <span className="absolute left-3 top-3 rounded-full bg-surface/90 px-2.5 py-1 text-[0.72rem] font-bold tracking-wide shadow-sm backdrop-blur">
            {Math.round(hit.fit_score)} % Passung
          </span>
        </Link>

        <div className="flex flex-col gap-3 p-5">
          <div>
            <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
              <Link href={href} className="display text-xl hover:text-accent">
                {boat.name}
              </Link>
              {boat.rating_count ? (
                <span className="text-sm">
                  <span className="text-brass">★</span>{" "}
                  <span className="font-medium">{boat.rating_overall?.toFixed(1)}</span>
                  <span className="ml-1 text-muted">({boat.rating_count})</span>
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-sm text-muted">
              {boat.manufacturer} {boat.model} · {boat.length_m.toFixed(2)} m · {boat.base.name}
            </p>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {(boat.character ?? []).map((c) => (
              <span key={c} className="chip chip-accent">
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
            <ul className="space-y-1 text-sm text-muted">
              {hit.fit_reasons.slice(0, 3).map((r) => (
                <li key={r} className="flex gap-2">
                  <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
                  {r}
                </li>
              ))}
            </ul>
          ) : null}

          {best ? (
            <div className="mt-auto flex flex-wrap items-end justify-between gap-4 border-t border-line pt-4">
              <div>
                <p className="text-xs uppercase tracking-[0.1em] text-faint">
                  {dateRange(best.start_date, best.end_date)}
                </p>
                <p className="price mt-1 text-2xl">
                  {money(best.total_cents)}
                  <span className="ml-1.5 font-sans text-sm font-normal tracking-normal text-muted">
                    · {money(best.per_day_cents)}/Nacht
                  </span>
                </p>
                {oneWay ? (
                  <p className="mt-1 text-xs font-medium text-accent">
                    One-Way nach {basesById[best.dropoff_base_id!]?.name ?? "anderem Hafen"}
                  </p>
                ) : null}
              </div>
              <Link href={href} className="btn-primary">
                Ansehen
              </Link>
            </div>
          ) : (
            <p className="mt-auto flex items-center gap-2 border-t border-line pt-4 text-sm text-warn">
              <FitBadge score={hit.fit_score} />
              {hit.unavailable_reason || "Kein Angebot in diesem Zeitraum"}
            </p>
          )}

          {alternatives.length ? (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="uppercase tracking-[0.1em] text-faint">Alternativen</span>
              {alternatives.map((o) => (
                <Link
                  key={`${o.start_date}-${o.nights}`}
                  href={`/boats/${boat.slug}?start_date=${o.start_date}&end_date=${o.end_date}&persons=${hit.boat.max_persons ? Math.min(hit.boat.max_persons, 4) : 4}`}
                  className="rounded-full border border-line px-2.5 py-1 transition-colors hover:border-accent hover:text-accent"
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
