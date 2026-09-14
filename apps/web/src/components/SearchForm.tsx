"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import type { Base, BoatClass, Region } from "@/lib/api";
import { addDays, isoDay } from "@/lib/format";

type Props = {
  regions: Region[];
  bases: Base[];
  boatClasses: BoatClass[];
  compact?: boolean;
};

const CHARACTERS = [
  { value: "good_natured", label: "Gutmütig" },
  { value: "sporty", label: "Sportlich" },
  { value: "comfort", label: "Komfortabel" },
  { value: "bluewater", label: "Seetüchtig" },
  { value: "classic", label: "Klassisch" },
];

const LICENSES = [
  { value: "", label: "keine Angabe" },
  { value: "1", label: "SBF Binnen" },
  { value: "2", label: "SBF See" },
  { value: "3", label: "SKS" },
  { value: "4", label: "SSS" },
  { value: "5", label: "SHS" },
];

export default function SearchForm({ regions, bases, boatClasses, compact = false }: Props) {
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
  const [boatClass, setBoatClass] = useState(params.get("boat_class") ?? "");
  const [character, setCharacter] = useState<string[]>(params.getAll("character"));
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
    if (dropoff) next.set("dropoff_base_id", dropoff);
    if (boatClass) next.set("boat_class", boatClass);
    character.forEach((c) => next.append("character", c));
    if (tallest) next.set("tallest_cm", tallest);
    if (license) next.set("license_level", license);
    if (experience) next.set("experience_nm", experience);
    if (withSkipper) next.set("with_skipper", "true");
    router.push(`/search?${next.toString()}`);
  }

  function toggleCharacter(value: string) {
    setCharacter((prev) => (prev.includes(value) ? prev.filter((c) => c !== value) : [...prev, value]));
  }

  return (
    <form onSubmit={submit} className="card p-4 sm:p-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={flexible}
            onChange={(e) => setFlexible(e.target.checked)}
            className="h-4 w-4 accent-[var(--accent)]"
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
        <div className="mt-4 grid gap-3 border-t border-line pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="label" htmlFor="pickup">
              Abholhafen
            </label>
            <select id="pickup" className="field" value={pickup} onChange={(e) => setPickup(e.target.value)}>
              <option value="">Heimathafen des Boots</option>
              {visibleBases.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="dropoff">
              Abgabehafen (One-Way)
            </label>
            <select id="dropoff" className="field" value={dropoff} onChange={(e) => setDropoff(e.target.value)}>
              <option value="">wie Abholhafen</option>
              {visibleBases.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="boatClass">
              Bootsklasse
            </label>
            <select
              id="boatClass"
              className="field"
              value={boatClass}
              onChange={(e) => setBoatClass(e.target.value)}
            >
              <option value="">alle Größen</option>
              {boatClasses.map((c) => (
                <option key={c.id} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </select>
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
            <select id="license" className="field" value={license} onChange={(e) => setLicense(e.target.value)}>
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
          <div className="sm:col-span-2">
            <span className="label">Charakter</span>
            <div className="flex flex-wrap gap-2">
              {CHARACTERS.map((c) => {
                const active = character.includes(c.value);
                return (
                  <button
                    type="button"
                    key={c.value}
                    onClick={() => toggleCharacter(c.value)}
                    aria-pressed={active}
                    className={`rounded-full border px-3 py-1 text-sm ${
                      active
                        ? "border-transparent bg-accent-soft font-medium text-accent"
                        : "border-line text-muted hover:bg-surface-muted"
                    }`}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>
          <label className="flex items-center gap-2 self-end text-sm">
            <input
              type="checkbox"
              checked={withSkipper}
              onChange={(e) => setWithSkipper(e.target.checked)}
              className="h-4 w-4 accent-[var(--accent)]"
            />
            Mit Skipper (Qualifikation egal)
          </label>
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setShowMore((v) => !v)}
          className="text-sm font-medium text-accent hover:underline"
        >
          {showMore ? "Weniger Filter" : "Mehr Filter"}
        </button>
        <button type="submit" className="btn-primary">
          Passende Boote zeigen
        </button>
      </div>
    </form>
  );
}
