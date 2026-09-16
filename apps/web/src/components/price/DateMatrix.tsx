"use client";

import { useEffect, useRef } from "react";

import type { PriceCell } from "@/lib/api";
import { dateLabel, money } from "@/lib/format";

import { niveauVon, ZELLE } from "./scale";

type Props = {
  cells: PriceCell[];
  /** Abfahrtstag, um den herum das Raster aufgespannt wird. */
  anchor: string;
  selectedNights: number;
  onPick: (cell: PriceCell) => void;
  /** Wie viele Tage vor und nach dem Ankertag gezeigt werden. */
  spread?: number;
};

/**
 * Abfahrt gegen Rückgabe — das Raster, das zeigt, ob ein bestimmter Abfahrts-
 * **oder** Abgabetag teuer ist.
 *
 * Bewusst auf ein Fenster um den gewählten Tag begrenzt: über die ganze Saison
 * wäre die Matrix fast leer, weil jede Zeile nur so viele Rückgabetage hat, wie
 * es angebotene Dauern gibt. Eng gefasst ist sie dicht und lesbar.
 */
export default function DateMatrix({
  cells,
  anchor,
  selectedNights,
  onPick,
  spread = 3,
}: Props) {
  const abfahrten = Array.from(new Set(cells.map((c) => c.start_date)))
    .sort()
    .filter((d) => Math.abs(abstandInTagen(d, anchor)) <= spread);

  const imFenster = cells.filter((c) => abfahrten.includes(c.start_date));
  const rueckgaben = Array.from(new Set(imFenster.map((c) => c.end_date))).sort();

  const nachSchluessel = new Map(imFenster.map((c) => [`${c.start_date}|${c.end_date}`, c]));

  // Die Matrix ist diagonal besetzt: ein späterer Abfahrtstag hat seine Preise
  // weiter rechts. Ohne diesen Sprung sähe ein schmales Gerät nur leere Zellen.
  const behaelter = useRef<HTMLDivElement>(null);
  const ersteSpalte = imFenster
    .filter((c) => c.start_date === anchor)
    .map((c) => rueckgaben.indexOf(c.end_date))
    .filter((i) => i >= 0)
    .sort((a, b) => a - b)[0];
  useEffect(() => {
    const el = behaelter.current;
    if (!el || ersteSpalte === undefined) return;
    const spaltenBreite = el.scrollWidth / (rueckgaben.length + 1);
    el.scrollLeft = Math.max(0, (ersteSpalte - 0.5) * spaltenBreite);
  }, [ersteSpalte, rueckgaben.length, anchor]);
  // Ein Raster mit gemischten Dauern braucht je Dauer einen eigenen Bezugswert,
  // sonst wäre die kürzeste Spalte automatisch die grünste.
  const bezugJeDauer = new Map<number, number>();
  for (const c of imFenster) {
    const bisher = bezugJeDauer.get(c.nights);
    if (bisher === undefined || c.total_cents < bisher) bezugJeDauer.set(c.nights, c.total_cents);
  }

  if (!abfahrten.length || !rueckgaben.length) {
    return (
      <p className="mt-4 text-sm text-muted">
        Um den {dateLabel(anchor, { day: "2-digit", month: "short" })} herum gibt es keine
        Kombination aus Abfahrt und Rückgabe.
      </p>
    );
  }

  return (
    <div className="mt-3">
      <div ref={behaelter} className="-mx-1 overflow-x-auto px-1 pb-2">
        <table className="w-full min-w-[34rem] border-separate border-spacing-1 text-center">
          <caption className="sr-only">
            Gesamtpreis je Kombination aus Abfahrts- und Rückgabetag
          </caption>
          <thead>
            <tr>
              <th scope="col" className="sticky left-0 z-10 w-24 border-r border-line bg-surface pb-1 pr-2 text-left align-bottom">
                <span className="label mb-0 block leading-tight">
                  Abfahrt ↓<br />
                  Rückgabe →
                </span>
              </th>
              {rueckgaben.map((r) => (
                <th
                  key={r}
                  scope="col"
                  className="w-20 pb-1 align-bottom text-[0.7rem] font-medium uppercase tracking-wider text-faint"
                >
                  {dateLabel(r, { day: "2-digit", month: "2-digit" })}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {abfahrten.map((a) => (
              <tr key={a}>
                <th
                  scope="row"
                  className="sticky left-0 z-10 whitespace-nowrap border-r border-line bg-surface pr-2 text-left text-[0.7rem] font-medium uppercase tracking-wider text-faint"
                >
                  {dateLabel(a, { day: "2-digit", month: "2-digit" })}
                </th>
                {rueckgaben.map((r) => {
                  const zelle = nachSchluessel.get(`${a}|${r}`);
                  if (!zelle) {
                    return (
                      <td key={r}>
                        <div className="rounded-lg border border-dashed border-line bg-surface-muted px-1 py-2 text-xs text-faint opacity-70">
                          –
                        </div>
                      </td>
                    );
                  }
                  const aktiv = zelle.start_date === anchor && zelle.nights === selectedNights;
                  const stufe = niveauVon(zelle.total_cents, bezugJeDauer.get(zelle.nights));
                  return (
                    <td key={r}>
                      <button
                        type="button"
                        onClick={() => onPick(zelle)}
                        aria-pressed={aktiv}
                        title={`${zelle.nights} Nächte · ${money(zelle.per_day_cents)}/Nacht · ${zelle.boat_name}`}
                        className={`tnum w-full rounded-lg border px-1 py-2 text-xs font-semibold transition hover:-translate-y-0.5 hover:shadow-sm ${
                          aktiv ? "border-accent bg-accent-soft shadow-sm" : ZELLE[stufe]
                        }`}
                      >
                        {money(zelle.total_cents)}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-faint">
        Jede Zeile ist ein Abfahrtstag, jede Spalte ein Rückgabetag. Die Farbe vergleicht innerhalb
        derselben Dauer, damit eine kurze Spalte nicht allein deshalb grün wirkt.
      </p>
    </div>
  );
}

function abstandInTagen(a: string, b: string): number {
  return Math.round((new Date(a).getTime() - new Date(b).getTime()) / 86_400_000);
}
