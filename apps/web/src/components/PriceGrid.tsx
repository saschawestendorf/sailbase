"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { PriceCell } from "@/lib/api";
import { addDays, dateLabel, money } from "@/lib/format";

/** Wie stark ein Preis vom günstigsten derselben Dauer abweichen darf, um noch
 *  als günstig bzw. normal zu gelten. Die Schwellen sind bewusst grob: sie
 *  sollen eine Richtung zeigen, keine Genauigkeit vortäuschen. */
const GUENSTIG_BIS = 1.06;
const NORMAL_BIS = 1.22;

type Niveau = "guenstig" | "normal" | "teuer";

const NIVEAU_ZELLE: Record<Niveau, string> = {
  guenstig: "border-positive/45 bg-positive-soft text-foreground",
  normal: "border-line bg-surface text-foreground",
  teuer: "border-warn/35 bg-warn-soft/50 text-foreground",
};

const NIVEAU_PUNKT: Record<Niveau, string> = {
  guenstig: "bg-positive",
  normal: "bg-line-strong",
  teuer: "bg-warn",
};

const NIVEAU_TEXT: Record<Niveau, string> = {
  guenstig: "günstig",
  normal: "üblich",
  teuer: "teuer",
};

export type PriceGridProps = {
  cells: PriceCell[];
  durations: number[];
  windowStart: string;
  windowEnd: string;
  truncated?: boolean;
  /** Vorauswahl aus der URL, damit das Raster dort aufsetzt, wo der Nutzer steht. */
  selectedStart?: string;
  selectedNights?: number;
  /** Ziel des Übernehmen-Knopfs, z. B. "/search" oder "/boats/ostwind-iv". */
  basePath: string;
  /** Übrige Parameter, die beim Übernehmen erhalten bleiben (Personen, Häfen …).
   *  Als Einträge, nicht als Objekt: ein Filter wie `character` kann mehrfach
   *  vorkommen, und ein Objekt würde alle bis auf den letzten Wert verschlucken. */
  baseQuery?: [string, string][];
  /** Auf der Suchseite nennt jede Zelle ein Boot, auf der Bootsseite nicht. */
  showBoat?: boolean;
  /** Überschrift und Erklärtext lassen sich je Seite anpassen. */
  title?: string;
  hint?: string;
};

function key(start: string, nights: number) {
  return `${start}|${nights}`;
}

function delta(cents: number): string {
  if (cents === 0) return "±0";
  return `${cents > 0 ? "+" : "−"}${money(Math.abs(cents))}`;
}

export default function PriceGrid({
  cells,
  durations,
  windowStart,
  windowEnd,
  truncated = false,
  selectedStart,
  selectedNights,
  basePath,
  baseQuery = [],
  showBoat = true,
  title = "Preise im Zeitfenster",
  hint,
}: PriceGridProps) {
  const byKey = useMemo(() => {
    const map = new Map<string, PriceCell>();
    for (const c of cells) map.set(key(c.start_date, c.nights), c);
    return map;
  }, [cells]);

  const startDates = useMemo(
    () => Array.from(new Set(cells.map((c) => c.start_date))).sort(),
    [cells],
  );

  // Günstigster Törn über alles: pro Nacht gerechnet, sonst gewänne immer die
  // kürzeste Dauer und der Hinweis wäre wertlos.
  const bester = useMemo(
    () =>
      cells.reduce<PriceCell | null>(
        (best, c) =>
          best === null ||
          c.per_day_cents < best.per_day_cents ||
          (c.per_day_cents === best.per_day_cents && c.total_cents < best.total_cents)
            ? c
            : best,
        null,
      ),
    [cells],
  );

  const [dauer, setDauer] = useState<number>(() => {
    if (selectedNights && durations.includes(selectedNights)) return selectedNights;
    return bester?.nights ?? durations[0] ?? 7;
  });
  const [start, setStart] = useState<string>(() => {
    if (selectedStart && byKey.has(key(selectedStart, selectedNights ?? dauer))) return selectedStart;
    return bester?.start_date ?? startDates[0] ?? windowStart;
  });

  // Referenz für die Farbgebung: der günstigste Preis derselben Dauer. Ein
  // Vergleich über Dauern hinweg wäre keiner – sieben Nächte kosten immer mehr
  // als fünf, das sagt über „günstig“ nichts aus.
  const guenstigsterDerDauer = useMemo(() => {
    const map = new Map<number, number>();
    for (const c of cells) {
      const vorher = map.get(c.nights);
      if (vorher === undefined || c.total_cents < vorher) map.set(c.nights, c.total_cents);
    }
    return map;
  }, [cells]);

  function niveau(c: PriceCell): Niveau {
    const basis = guenstigsterDerDauer.get(c.nights);
    if (!basis) return "normal";
    const faktor = c.total_cents / basis;
    if (faktor <= GUENSTIG_BIS) return "guenstig";
    if (faktor <= NORMAL_BIS) return "normal";
    return "teuer";
  }

  const gewaehlt = byKey.get(key(start, dauer)) ?? null;
  const letzterStart = startDates.at(-1) ?? null;

  function href(cell: PriceCell): string {
    const q = new URLSearchParams(baseQuery);
    q.set("start_date", cell.start_date);
    q.set("end_date", cell.end_date);
    return `${basePath}?${q.toString()}`;
  }

  if (!cells.length) {
    return (
      <section className="card p-6 sm:p-7">
        <h2 className="text-xl">{title}</h2>
        <p className="mt-3 text-sm text-muted">
          Für {dateLabel(windowStart, { day: "2-digit", month: "short" })} bis{" "}
          {dateLabel(windowEnd, { day: "2-digit", month: "short" })} lässt sich kein Preis rechnen.
          Ein größeres Zeitfenster oder eine andere Dauer bringt meist Treffer.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-5 sm:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-xl">{title}</h2>
        <p className="text-sm text-muted">
          {dateLabel(windowStart, { day: "2-digit", month: "short" })} –{" "}
          {dateLabel(windowEnd, { day: "2-digit", month: "short", year: "numeric" })}
        </p>
      </div>
      {hint ? <p className="mt-1.5 text-sm leading-relaxed text-muted">{hint}</p> : null}

      {/* Der Fund zuerst: was ist im ganzen Fenster das Günstigste? */}
      {bester ? (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-positive/40 bg-positive-soft px-4 py-3.5">
          <div>
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-muted">
              Günstigster Törn im Fenster
            </p>
            <p className="mt-1 text-[0.95rem]">
              <span className="tnum font-semibold">{money(bester.total_cents)}</span>
              <span className="text-muted">
                {" "}
                · {dateLabel(bester.start_date, { day: "2-digit", month: "short" })} –{" "}
                {dateLabel(bester.end_date, { day: "2-digit", month: "short" })} · {bester.nights}{" "}
                Nächte · {money(bester.per_day_cents)}/Nacht
                {showBoat ? ` · ${bester.boat_name}` : ""}
              </span>
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setDauer(bester.nights);
              setStart(bester.start_date);
            }}
            className="shrink-0 rounded-full border border-positive/45 bg-surface px-3.5 py-1.5 text-sm font-medium transition-colors hover:bg-positive-soft"
          >
            Im Raster zeigen
          </button>
        </div>
      ) : null}

      {/* Dauer: hier steht die Antwort auf „spare ich, wenn ich einen Tag später ende?“ */}
      <div className="mt-6">
        <p className="label">Dauer · Unterschied für Start {dateLabel(start, { day: "2-digit", month: "short" })}</p>
        <div className="mt-2.5 -mx-1 flex gap-2 overflow-x-auto px-1 pb-1.5">
          {durations.map((n) => {
            const zelle = byKey.get(key(start, n));
            const aktiv = n === dauer;
            const diff =
              zelle && gewaehlt ? zelle.total_cents - gewaehlt.total_cents : null;
            return (
              <button
                key={n}
                type="button"
                disabled={!zelle}
                onClick={() => setDauer(n)}
                aria-pressed={aktiv}
                className={`min-w-[5.5rem] shrink-0 rounded-xl border px-3 py-2 text-center transition ${
                  aktiv
                    ? "border-accent bg-accent-soft shadow-sm"
                    : zelle
                      ? "border-line bg-surface hover:border-line-strong hover:shadow-sm"
                      : "cursor-not-allowed border-dashed border-line bg-surface-muted opacity-60"
                }`}
              >
                <span className="block text-[0.7rem] uppercase tracking-wider text-faint">
                  {n} Nächte
                </span>
                <span className="tnum mt-0.5 block text-sm font-semibold">
                  {zelle ? money(zelle.total_cents) : "–"}
                </span>
                <span
                  className={`tnum mt-0.5 block text-[0.7rem] ${
                    diff === null
                      ? "text-faint"
                      : diff < 0
                        ? "text-positive"
                        : diff > 0
                          ? "text-muted"
                          : "text-faint"
                  }`}
                >
                  {diff === null ? "nicht frei" : delta(diff)}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Startdatum: der eigentliche Preiskalender. */}
      <div className="mt-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <p className="label">Übernahme · Gesamtpreis für {dauer} Nächte</p>
          <div className="flex items-center gap-3 text-[0.7rem] text-muted">
            {(["guenstig", "normal", "teuer"] as Niveau[]).map((n) => (
              <span key={n} className="inline-flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${NIVEAU_PUNKT[n]}`} aria-hidden />
                {NIVEAU_TEXT[n]}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-7">
          {startDates.map((tag) => {
            const zelle = byKey.get(key(tag, dauer));
            const aktiv = tag === start;
            const label = (
              <>
                <span className="block text-[0.7rem] uppercase tracking-wider text-faint">
                  {dateLabel(tag, { day: "2-digit", month: "2-digit" })}
                </span>
                <span className="tnum mt-0.5 block text-sm font-semibold">
                  {zelle ? money(zelle.total_cents) : "–"}
                </span>
              </>
            );
            if (!zelle) {
              return (
                <div
                  key={tag}
                  title={`${dauer} Nächte ab diesem Tag nicht verfügbar`}
                  className="rounded-xl border border-dashed border-line bg-surface-muted px-2 py-2.5 text-center opacity-70"
                >
                  {label}
                </div>
              );
            }
            const stufe = niveau(zelle);
            return (
              <button
                key={tag}
                type="button"
                onClick={() => setStart(tag)}
                aria-pressed={aktiv}
                title={
                  showBoat
                    ? `${zelle.boat_name}${zelle.boat_count > 1 ? ` und ${zelle.boat_count - 1} weitere` : ""} · ${money(zelle.per_day_cents)}/Nacht`
                    : `${money(zelle.per_day_cents)}/Nacht`
                }
                className={`rounded-xl border px-2 py-2.5 text-center transition hover:-translate-y-0.5 hover:shadow-sm ${
                  aktiv ? "border-accent bg-accent-soft shadow-sm" : NIVEAU_ZELLE[stufe]
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Die Auswahl im Klartext, dann der Weg dorthin. */}
      {gewaehlt ? (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
          <div className="text-sm">
            <p>
              <span className="tnum font-semibold">{money(gewaehlt.total_cents)}</span>
              <span className="text-muted">
                {" "}
                für {gewaehlt.nights} Nächte ·{" "}
                {dateLabel(gewaehlt.start_date, { day: "2-digit", month: "short" })} –{" "}
                {dateLabel(gewaehlt.end_date, { day: "2-digit", month: "short" })} ·{" "}
                {money(gewaehlt.per_day_cents)}/Nacht
              </span>
            </p>
            {showBoat ? (
              <p className="mt-0.5 text-muted">
                Günstigstes Boot: {gewaehlt.boat_name}
                {gewaehlt.boat_count > 1
                  ? ` · ${gewaehlt.boat_count - 1} weitere${gewaehlt.boat_count === 2 ? "s" : ""} verfügbar`
                  : " · einziges freies Boot"}
              </p>
            ) : null}
          </div>
          <Link href={href(gewaehlt)} className="btn-primary shrink-0">
            Diesen Zeitraum übernehmen
          </Link>
        </div>
      ) : null}

      {letzterStart && letzterStart < windowEnd ? (
        <p className="mt-4 text-xs leading-relaxed text-muted">
          Ab dem {dateLabel(addDays(letzterStart, 1), { day: "2-digit", month: "short" })} ist im
          Fenster bis {dateLabel(windowEnd, { day: "2-digit", month: "short" })} kein Törn mehr
          buchbar — belegt, außerhalb der Saison oder unterhalb der Mindestdauer.
        </p>
      ) : null}

      {truncated ? (
        <p className="mt-4 rounded-xl bg-warn-soft px-4 py-2.5 text-xs leading-relaxed text-warn">
          Das Fenster ist so groß, dass nicht jede Kombination gerechnet wurde. Die gezeigten Preise
          stimmen, aber es kann außerhalb noch Günstigeres geben. Ein engeres Fenster rechnet
          vollständig.
        </p>
      ) : null}

      <p className="mt-3 text-xs leading-relaxed text-faint">
        Farbe vergleicht innerhalb derselben Dauer: grün heißt günstig für {dauer} Nächte, nicht
        günstig gegenüber einem kürzeren Törn. Preise sind Gesamtpreise inklusive Nebenkosten und
        werden beim Buchen erneut bestätigt.
      </p>
    </section>
  );
}
