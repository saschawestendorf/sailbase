"use client";

import Link from "next/link";

import type { BoatRow } from "@/lib/api";
import { dateLabel, money } from "@/lib/format";

import { minimum, niveauVon, ZELLE } from "./scale";

type Props = {
  rows: BoatRow[];
  /** Dauer, für die diese Zeilen gerechnet wurden (kommt vom Server). */
  focusNights: number;
  /** Im Raster gerade gewählte Dauer – weicht sie ab, passt die Ansicht nicht. */
  selectedNights: number;
  /** Adresse, die die Bootsansicht auf die gewählte Dauer umstellt. */
  reloadHref: string;
  selectedStart: string;
  onPickStart: (start: string) => void;
};

/**
 * Boote über die Tage: eine Zeile je Schiff, eine Spalte je Abfahrtstag.
 *
 * Der Kalender darüber zeigt nur den günstigsten Preis des Tages — hier steht,
 * welches Boot ihn macht und was die anderen kosten. Alle Zellen haben dieselbe
 * Dauer, deshalb ist ein Vergleich über die ganze Fläche hier zulässig.
 */
export default function BoatMatrix({
  rows,
  focusNights,
  selectedNights,
  reloadHref,
  selectedStart,
  onPickStart,
}: Props) {
  const tage = Array.from(new Set(rows.flatMap((r) => r.prices.map((p) => p.start_date)))).sort();
  const bezug = minimum(rows.flatMap((r) => r.prices.map((p) => p.total_cents)));

  if (!rows.length || !tage.length) {
    return <p className="mt-4 text-sm text-muted">Für diese Dauer bietet kein Boot einen Törn an.</p>;
  }

  return (
    <div className="mt-3">
      {selectedNights !== focusNights ? (
        <p className="mb-3 rounded-xl bg-surface-muted px-4 py-2.5 text-xs leading-relaxed text-muted">
          Diese Ansicht ist für <strong className="font-semibold">{focusNights} Nächte</strong>{" "}
          gerechnet, im Raster stehen gerade {selectedNights}.{" "}
          <Link href={reloadHref} className="font-medium text-accent hover:text-accent-strong">
            Für {selectedNights} Nächte neu rechnen →
          </Link>
        </p>
      ) : null}

      <div className="-mx-1 overflow-x-auto px-1 pb-2">
        <table className="border-separate border-spacing-1 text-center">
          <caption className="sr-only">
            Gesamtpreis je Boot und Abfahrtstag für {focusNights} Nächte
          </caption>
          <thead>
            <tr>
              <th
                scope="col"
                className="sticky left-0 z-10 border-r border-line bg-surface pr-2 text-left align-bottom"
                style={{ minWidth: "11rem" }}
              >
                <span className="label mb-0">Boot · {focusNights} Nächte</span>
              </th>
              {tage.map((t) => (
                <th
                  key={t}
                  scope="col"
                  className="w-[4.5rem] pb-1 text-[0.7rem] font-medium uppercase tracking-wider text-faint"
                >
                  {dateLabel(t, { day: "2-digit", month: "2-digit" })}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((zeile) => {
              const nachTag = new Map(zeile.prices.map((p) => [p.start_date, p]));
              return (
                <tr key={zeile.boat_id}>
                  <th scope="row" className="sticky left-0 z-10 border-r border-line bg-surface pr-2 text-left">
                    <Link
                      href={`/boats/${zeile.slug}`}
                      className="block text-sm font-medium hover:text-accent"
                    >
                      {zeile.name}
                    </Link>
                    <span className="block text-[0.7rem] text-faint">
                      {zeile.length_m.toFixed(2).replace(".", ",")} m · {zeile.base_name}
                    </span>
                  </th>
                  {tage.map((t) => {
                    const preis = nachTag.get(t);
                    if (!preis) {
                      return (
                        <td key={t}>
                          <div className="rounded-lg border border-dashed border-line bg-surface-muted px-1 py-2 text-xs text-faint opacity-70">
                            –
                          </div>
                        </td>
                      );
                    }
                    const aktiv = t === selectedStart;
                    const stufe = niveauVon(preis.total_cents, bezug);
                    return (
                      <td key={t}>
                        <button
                          type="button"
                          onClick={() => onPickStart(t)}
                          aria-pressed={aktiv}
                          title={`${zeile.name} · ${money(preis.per_day_cents)}/Nacht`}
                          className={`tnum w-full rounded-lg border px-1 py-2 text-xs font-semibold transition hover:-translate-y-0.5 hover:shadow-sm ${
                            aktiv ? "border-accent bg-accent-soft shadow-sm" : ZELLE[stufe]
                          }`}
                        >
                          {money(preis.total_cents)}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-faint">
        Nach günstigstem Preis sortiert. Alle Zellen gelten für {focusNights} Nächte, deshalb sind
        sie über die ganze Fläche vergleichbar. Ein Strich heißt: an diesem Tag nicht frei.
      </p>
    </div>
  );
}
