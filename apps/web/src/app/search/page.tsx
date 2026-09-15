import Link from "next/link";

import BoatCard from "@/components/BoatCard";
import PriceGrid from "@/components/PriceGrid";
import SearchForm from "@/components/SearchForm";
import {
  ApiError,
  type Base,
  type BoatClass,
  getBases,
  getBoatClasses,
  getPriceGrid,
  type PriceGridResult,
  getRegions,
  searchBoats,
  type Region,
  type SearchResult,
} from "@/lib/api";
import { addDays, isoDay, nightsBetween } from "@/lib/format";

export const dynamic = "force-dynamic";

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function all(value: string | string[] | undefined): string[] {
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

export default async function SearchPage(props: PageProps<"/search">) {
  const sp = await props.searchParams;
  const today = isoDay(new Date());
  const startDate = first(sp.start_date) ?? addDays(today, 30);
  const endDate = first(sp.end_date) ?? addDays(startDate, 7);
  const sort = first(sp.sort) ?? "fit";

  let regions: Region[] = [];
  let bases: Base[] = [];
  let boatClasses: BoatClass[] = [];
  let catalogError: string | null = null;
  try {
    [regions, bases, boatClasses] = await Promise.all([getRegions(), getBases(), getBoatClasses()]);
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    catalogError = "Die Suchfilter konnten nicht geladen werden. Bitte versuche es erneut.";
  }
  const basesById: Record<string, Base> = Object.fromEntries(bases.map((b) => [b.id, b]));

  const query = {
    start_date: startDate,
    end_date: endDate,
    persons: first(sp.persons) ?? "4",
    min_nights: first(sp.min_nights),
    max_nights: first(sp.max_nights),
    region: first(sp.region),
    pickup_base_id: first(sp.pickup_base_id),
    dropoff_base_id: first(sp.dropoff_base_id),
    boat_class: first(sp.boat_class),
    character: all(sp.character),
    tallest_cm: first(sp.tallest_cm),
    license_level: first(sp.license_level),
    experience_nm: first(sp.experience_nm),
    with_skipper: first(sp.with_skipper),
    sort,
  };

  // Das Preisraster stellt eine andere Frage als die Liste: nicht „welches Boot
  // passt auf diese Woche", sondern „welche Woche ist die günstigste". Bei festen
  // Daten wird dafür ein Fenster um den Wunschtermin gelegt und die Dauer um zwei
  // Nächte nach beiden Seiten geöffnet — sonst gäbe es nichts zu vergleichen.
  const wunschNaechte = Math.max(1, nightsBetween(startDate, endDate));
  const flexibel = Boolean(query.min_nights);
  const gridStart = flexibel
    ? startDate
    : [today, addDays(startDate, -14)].sort().at(-1)!;
  const gridQuery = {
    window_start: gridStart,
    // Das Fenster muss die längste gezeigte Dauer aufnehmen können, sonst hätte
    // ein langer Törn kein einziges Vergleichsdatum.
    window_end: flexibel ? endDate : addDays(gridStart, Math.max(60, wunschNaechte + 9)),
    min_nights: flexibel ? query.min_nights! : String(Math.max(1, wunschNaechte - 2)),
    max_nights: flexibel ? (query.max_nights ?? query.min_nights!) : String(wunschNaechte + 2),
    persons: query.persons,
    region: query.region,
    pickup_base_id: query.pickup_base_id,
    dropoff_base_id: query.dropoff_base_id,
    boat_class: query.boat_class,
    character: query.character,
    tallest_cm: query.tallest_cm,
    license_level: query.license_level,
    experience_nm: query.experience_nm,
    with_skipper: query.with_skipper,
  };

  let result: SearchResult | null = null;
  let error: string | null = null;
  let grid: PriceGridResult | null = null;
  try {
    // Parallel: das Raster darf die Ergebnisliste nicht ausbremsen.
    [result, grid] = await Promise.all([
      searchBoats(query),
      // Ein Raster ist eine Zugabe. Fällt es aus, bleibt die Suche benutzbar.
      getPriceGrid(gridQuery).catch(() => null),
    ]);
  } catch (err) {
    error = err instanceof ApiError ? err.message : "Suche fehlgeschlagen";
  }

  // Beim Übernehmen einer Rasterzelle bleiben alle Filter außer den Daten stehen.
  // Mehrfachwerte bleiben mehrfach – `character` darf nicht zu einem Wert schrumpfen.
  const DATUMSFELDER = new Set(["start_date", "end_date", "min_nights", "max_nights"]);
  const gridBaseQuery: [string, string][] = Object.entries(query).flatMap(([k, v]) => {
    if (DATUMSFELDER.has(k)) return [];
    if (Array.isArray(v)) return v.filter(Boolean).map((x) => [k, String(x)] as [string, string]);
    return v ? [[k, String(v)] as [string, string]] : [];
  });

  const boatQuery = new URLSearchParams();
  boatQuery.set("start_date", startDate);
  boatQuery.set("end_date", endDate);
  boatQuery.set("persons", String(query.persons));
  if (query.pickup_base_id) boatQuery.set("pickup_base_id", query.pickup_base_id);
  if (query.dropoff_base_id) boatQuery.set("dropoff_base_id", query.dropoff_base_id);

  const sortLinks = [
    { key: "fit", label: "Beste Passung" },
    { key: "price_asc", label: "Preis aufsteigend" },
    { key: "price_desc", label: "Preis absteigend" },
    { key: "length_desc", label: "Größe" },
  ];

  function sortHref(key: string) {
    const next = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => {
      if (Array.isArray(v)) v.forEach((x) => next.append(k, x));
      else if (v) next.set(k, String(v));
    });
    next.set("sort", key);
    return `/search?${next.toString()}`;
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <div className="card card-raised p-5 sm:p-6">
        <SearchForm regions={regions} bases={bases} boatClasses={boatClasses} />
      </div>
      {catalogError ? (
        <p role="alert" className="card mt-4 p-5 text-sm text-warn">
          {catalogError}
        </p>
      ) : null}

      {grid && grid.cells.length ? (
        <div className="mt-6">
          <PriceGrid
            /* Neu aufsetzen, sobald der Server eine andere Auswahl liefert: sonst
               bliebe die im Raster gemerkte Auswahl stehen, während die Seite
               darunter schon den neuen Zeitraum zeigt. */
            key={`${grid.window_start}|${startDate}|${wunschNaechte}`}
            cells={grid.cells}
            durations={grid.durations}
            windowStart={grid.window_start}
            windowEnd={grid.window_end}
            truncated={grid.truncated}
            selectedStart={startDate}
            selectedNights={wunschNaechte}
            basePath="/search"
            baseQuery={gridBaseQuery}
            title="Welcher Zeitraum ist der günstigste?"
            hint={`Über ${grid.boats_considered} Boote gerechnet. Jede Kachel zeigt den Gesamtpreis des günstigsten passenden Boots für diesen Start.`}
          />
        </div>
      ) : null}

      <div className="mt-10 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Ergebnisse</p>
          <h1 className="mt-2.5 text-2xl sm:text-3xl">
            {result ? `${result.count} Boote gefunden` : "Suche"}
            {query.min_nights ? (
              <span className="ml-2.5 font-sans text-sm font-normal tracking-normal text-muted">
                flexibel, {query.min_nights}–{query.max_nights} Nächte
              </span>
            ) : null}
          </h1>
          <p className="mt-1.5 max-w-xl text-sm text-muted">
            {query.min_nights
              ? "Jedes Boot zeigt die Termine, die sich in deinem Fenster wirtschaftlich anbieten lassen."
              : "Feste Daten. Für mehr Auswahl das Zeitfenster öffnen und eine Dauer von bis angeben."}
          </p>
        </div>
        {/* Segmentierte Steuerung statt loser Links: die aktive Sortierung ist
            damit auch ohne Farbe als Zustand erkennbar. */}
        <div className="flex flex-wrap gap-0.5 rounded-full border border-line bg-surface-muted p-1 text-sm">
          {sortLinks.map((s) => (
            <Link
              key={s.key}
              href={sortHref(s.key)}
              aria-current={sort === s.key ? "true" : undefined}
              className={`rounded-full px-3 py-1.5 transition-colors ${
                sort === s.key
                  ? "bg-surface font-medium text-foreground shadow-sm"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {s.label}
            </Link>
          ))}
        </div>
      </div>

      {error ? (
        <p className="card mt-6 p-5 text-sm text-warn">{error}</p>
      ) : result && result.hits.length === 0 ? (
        <div className="card mt-6 p-7 text-sm text-muted">
          <p className="display text-lg text-foreground">Kein Boot passt zu diesen Angaben.</p>
          <ul className="mt-3 list-inside list-disc space-y-1.5">
            <li>Zeitfenster öffnen und eine Dauer von bis angeben, statt feste Daten zu setzen.</li>
            <li>Anderen Abholhafen oder ein Nachbarrevier zulassen.</li>
            <li>
              Fehlt die Qualifikation für die gewünschte Yacht, hilft die Option „Mit Skipper“.
            </li>
          </ul>
        </div>
      ) : (
        <div className="mt-6 grid gap-5">
          {result?.hits.map((hit) => (
            <BoatCard key={hit.boat.id} hit={hit} query={boatQuery.toString()} basesById={basesById} />
          ))}
        </div>
      )}
    </div>
  );
}
