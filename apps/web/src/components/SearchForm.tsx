"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { RangeSlider, Slider } from "@/components/ui/Slider";
import type { Base, Region } from "@/lib/api";
import { addDays, isoDay, money } from "@/lib/format";

type Props = {
  regions: Region[];
  bases: Base[];
  compact?: boolean;
};

/** Die Achse des Segelcharakters, wie sie das Backend versteht: -1 bis +1. */
const ACHSE_SCHRITT = 0.25;
const ACHSE_MARKEN = ["seetüchtig\nklassisch", "Fahrten­kreuzer", "Sport­yacht"];

function achseKlartext(wert: number): string {
  if (wert <= -0.6) return "Seetüchtig und klassisch — Substanz vor Tempo";
  if (wert <= -0.2) return "Gutmütiger Fahrtenkreuzer — verzeiht viel";
  if (wert < 0.3) return "Familienfahrtenkreuzer — Platz und einfaches Handling";
  if (wert < 0.7) return "Sportlich getrimmt — Segeleigenschaften im Vordergrund";
  return "Sportyacht — Leistung vor Komfort";
}

// Bereichsgrenzen der Regler. Sie begrenzen nur die Bedienung, nicht den Katalog:
// steht ein Griff am Anschlag, wird der Filter gar nicht erst mitgeschickt.
const LAENGE_MIN = 7;
const LAENGE_MAX = 18;
const PREIS_MIN = 0;
const PREIS_MAX = 10_000;
const PREIS_SCHRITT = 250;

const LICENSES = [
  { value: "", label: "keine Angabe" },
  { value: "1", label: "SBF Binnen" },
  { value: "2", label: "SBF See" },
  { value: "3", label: "SKS" },
  { value: "4", label: "SSS" },
  { value: "5", label: "SHS" },
];

export default function SearchForm({ regions, bases, compact = false }: Props) {
  const router = useRouter();
  const params = useSearchParams();

  const defaultStart = params.get("start_date") ?? addDays(isoDay(new Date()), 30);
  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(params.get("end_date") ?? addDays(defaultStart, 7));
  const [flexible, setFlexible] = useState(Boolean(params.get("min_nights")));
  const [minNights, setMinNights] = useState(params.get("min_nights") ?? "3");
  const [maxNights, setMaxNights] = useState(params.get("max_nights") ?? "7");
  const [persons, setPersons] = useState(params.get("persons") ?? "4");
  const [region, setRegion] = useState(params.get("region") ?? "");
  const [pickup, setPickup] = useState(params.get("pickup_base_id") ?? "");
  const [dropoff, setDropoff] = useState(params.get("dropoff_base_id") ?? "");
  // Wie bei Mietwagen: der zweite Hafen erscheint erst, wenn er gebraucht wird.
  const [einweg, setEinweg] = useState(Boolean(params.get("dropoff_base_id")));

  const achseAusUrl = params.get("character_axis");
  const [achse, setAchse] = useState(achseAusUrl ? Number(achseAusUrl) : 0);
  const [achseEgal, setAchseEgal] = useState(achseAusUrl === null);

  const [laengeVon, setLaengeVon] = useState(Number(params.get("min_length") ?? LAENGE_MIN));
  const [laengeBis, setLaengeBis] = useState(Number(params.get("max_length") ?? LAENGE_MAX));

  const preisAusUrl = (name: string, fallback: number) => {
    const cent = params.get(name);
    return cent ? Number(cent) / 100 : fallback;
  };
  const [preisVon, setPreisVon] = useState(preisAusUrl("min_price", PREIS_MIN));
  const [preisBis, setPreisBis] = useState(preisAusUrl("max_price", PREIS_MAX));

  const [tallest, setTallest] = useState(params.get("tallest_cm") ?? "");
  const [license, setLicense] = useState(params.get("license_level") ?? "");
  const [experience, setExperience] = useState(params.get("experience_nm") ?? "");
  const [withSkipper, setWithSkipper] = useState(params.get("with_skipper") === "true");
  const [showMore, setShowMore] = useState(!compact);

  const visibleBases = region ? bases.filter((b) => b.region.slug === region) : bases;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams();
    next.set("start_date", start);
    next.set("end_date", end);
    next.set("persons", persons);
    if (flexible) {
      next.set("min_nights", minNights);
      next.set("max_nights", maxNights);
    }
    if (region) next.set("region", region);
    if (pickup) next.set("pickup_base_id", pickup);
    if (einweg && dropoff) next.set("dropoff_base_id", dropoff);
    if (!achseEgal) next.set("character_axis", String(achse));
    // Ein Griff am Anschlag heißt: dieser Filter ist offen und gehört nicht in die URL.
    if (laengeVon > LAENGE_MIN) next.set("min_length", String(laengeVon));
    if (laengeBis < LAENGE_MAX) next.set("max_length", String(laengeBis));
    if (preisVon > PREIS_MIN) next.set("min_price", String(Math.round(preisVon * 100)));
    if (preisBis < PREIS_MAX) next.set("max_price", String(Math.round(preisBis * 100)));
    if (tallest) next.set("tallest_cm", tallest);
    if (license) next.set("license_level", license);
    if (experience) next.set("experience_nm", experience);
    if (withSkipper) next.set("with_skipper", "true");
    router.push(`/search?${next.toString()}`);
  }

  return (
    <form onSubmit={submit}>
      {/* Ort zuerst: wo soll es losgehen? */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className={einweg ? "" : "lg:col-span-2"}>
          <label className="label" htmlFor="pickup">
            Abfahrtshafen
          </label>
          <select
            id="pickup"
            className="field"
            value={pickup}
            onChange={(e) => setPickup(e.target.value)}
          >
            <option value="">jeder Hafen im Revier</option>
            {visibleBases.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}, {b.city}
              </option>
            ))}
          </select>
        </div>

        {einweg ? (
          <div>
            <label className="label" htmlFor="dropoff">
              Rückgabehafen
            </label>
            <select
              id="dropoff"
              className="field"
              value={dropoff}
              onChange={(e) => setDropoff(e.target.value)}
            >
              <option value="">bitte wählen</option>
              {visibleBases.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}, {b.city}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div>
          <label className="label" htmlFor="start">
            {flexible ? "Zeitfenster ab" : "Übernahme"}
          </label>
          <input
            id="start"
            type="date"
            required
            className="field"
            value={start}
            onChange={(e) => {
              setStart(e.target.value);
              if (e.target.value >= end) setEnd(addDays(e.target.value, 7));
            }}
          />
        </div>
        <div>
          <label className="label" htmlFor="end">
            {flexible ? "Zeitfenster bis" : "Rückgabe"}
          </label>
          <input
            id="end"
            type="date"
            required
            className="field"
            min={addDays(start, 1)}
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-3 text-sm">
        <label className="flex cursor-pointer items-center gap-2.5">
          <input
            type="checkbox"
            checked={einweg}
            onChange={(e) => {
              setEinweg(e.target.checked);
              if (!e.target.checked) setDropoff("");
            }}
            className="h-4 w-4 rounded accent-[var(--accent)]"
          />
          Rückgabe in einem anderen Hafen
        </label>
        <label className="flex cursor-pointer items-center gap-2.5">
          <input
            type="checkbox"
            checked={flexible}
            onChange={(e) => setFlexible(e.target.checked)}
            className="h-4 w-4 rounded accent-[var(--accent)]"
          />
          Flexible Dauer im Zeitfenster
        </label>
        {flexible ? (
          <span className="flex items-center gap-2 text-muted">
            <input
              type="number"
              min={1}
              max={60}
              aria-label="kürzeste Dauer in Nächten"
              className="field w-16 py-1"
              value={minNights}
              onChange={(e) => setMinNights(e.target.value)}
            />
            bis
            <input
              type="number"
              min={1}
              max={60}
              aria-label="längste Dauer in Nächten"
              className="field w-16 py-1"
              value={maxNights}
              onChange={(e) => setMaxNights(e.target.value)}
            />
            Nächte
          </span>
        ) : null}
      </div>

      {showMore ? (
        <div className="mt-5 border-t border-line pt-6">
          <div className="grid gap-x-8 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
            <Slider
              label="Segelcharakter"
              min={-1}
              max={1}
              step={ACHSE_SCHRITT}
              value={achse}
              onChange={(v) => {
                setAchse(v);
                setAchseEgal(false);
              }}
              disabled={achseEgal}
              marks={ACHSE_MARKEN}
              valueLabel={achseEgal ? "Alle Charaktere" : achseKlartext(achse)}
              toggle={{
                label: "egal",
                active: achseEgal,
                onClick: () => setAchseEgal((v) => !v),
              }}
            />

            <RangeSlider
              label="Bootslänge"
              min={LAENGE_MIN}
              max={LAENGE_MAX}
              step={0.5}
              from={laengeVon}
              to={laengeBis}
              onChange={(a, b) => {
                setLaengeVon(a);
                setLaengeBis(b);
              }}
              format={(v) => `${v.toFixed(1).replace(".", ",")} m`}
              openLabel="jede Größe"
            />

            <RangeSlider
              label="Gesamtpreis"
              min={PREIS_MIN}
              max={PREIS_MAX}
              step={PREIS_SCHRITT}
              from={preisVon}
              to={preisBis}
              onChange={(a, b) => {
                setPreisVon(a);
                setPreisBis(b);
              }}
              format={(v) => money(v * 100)}
              openLabel="jeder Preis"
            />
          </div>

          <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="label" htmlFor="region">
                Seegebiet
              </label>
              <select
                id="region"
                className="field"
                value={region}
                onChange={(e) => {
                  setRegion(e.target.value);
                  setPickup("");
                  setDropoff("");
                }}
              >
                <option value="">alle Reviere</option>
                {regions.map((r) => (
                  <option key={r.id} value={r.slug}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="persons">
                Personen
              </label>
              <input
                id="persons"
                type="number"
                min={1}
                max={20}
                className="field"
                value={persons}
                onChange={(e) => setPersons(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="tallest">
                Größte Person (cm)
              </label>
              <input
                id="tallest"
                type="number"
                min={100}
                max={230}
                placeholder="z. B. 192"
                className="field"
                value={tallest}
                onChange={(e) => setTallest(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="license">
                Führerschein
              </label>
              <select
                id="license"
                className="field"
                value={license}
                onChange={(e) => setLicense(e.target.value)}
              >
                {LICENSES.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="experience">
                Erfahrung (sm)
              </label>
              <input
                id="experience"
                type="number"
                min={0}
                placeholder="z. B. 600"
                className="field"
                value={experience}
                onChange={(e) => setExperience(e.target.value)}
              />
            </div>
            <label className="flex cursor-pointer items-center gap-2.5 self-end pb-2 text-sm">
              <input
                type="checkbox"
                checked={withSkipper}
                onChange={(e) => setWithSkipper(e.target.checked)}
                className="h-4 w-4 rounded accent-[var(--accent)]"
              />
              Mit Skipper (Qualifikation egal)
            </label>
          </div>
        </div>
      ) : null}

      <div className="mt-5 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setShowMore((v) => !v)}
          aria-expanded={showMore}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-strong"
        >
          {showMore ? "Weniger Filter" : "Mehr Filter"}
          <span aria-hidden className={showMore ? "rotate-180 transition-transform" : "transition-transform"}>
            ⌄
          </span>
        </button>
        <button type="submit" className="btn-primary">
          Passende Boote zeigen
        </button>
      </div>
    </form>
  );
}
