"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchJson } from "@/components/listing/useCatalog";
import RevenueChart from "@/components/pricing/RevenueChart";
import type { BoatDetail, Simulation } from "@/lib/api";
import { money, signedPercent } from "@/lib/format";

const DEMAND_LEVELS = [
  { value: "low", label: "Wenig", hint: "viele freie Wochen" },
  { value: "medium", label: "Normal", hint: "rund 40 % der Saison gebucht" },
  { value: "high", label: "Gut", hint: "rund die halbe Saison gebucht" },
  { value: "very_high", label: "Sehr gut", hint: "fast ausgebucht" },
];

const STRATEGIES = [
  {
    value: "conservative",
    title: "Zurückhaltend",
    text: "Schützt zusammenhängende Wochen. Kurzbuchungen, die attraktive Zeiträume zerschneiden, werden abgelehnt.",
  },
  {
    value: "balanced",
    title: "Ausgewogen",
    text: "Füllt Lücken, wenn der Erlös den Schaden durch Resttage übersteigt.",
  },
  {
    value: "aggressive",
    title: "Offensiv",
    text: "Verkauft jeden Tag, der die Untergrenze trägt, auch wenn Resttage übrig bleiben.",
  },
];

function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "positive" | "warn";
}) {
  const toneClass =
    tone === "positive" ? "text-positive" : tone === "warn" ? "text-warn" : "text-foreground";
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${toneClass}`}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export default function PricingStudio({ boat }: { boat: BoatDetail }) {
  const policy = boat.pricing;
  const [floor, setFloor] = useState((policy?.floor_price_cents ?? 10000) / 100);
  const [reference, setReference] = useState((policy?.reference_price_cents ?? 20000) / 100);
  const [ceiling, setCeiling] = useState((policy?.ceiling_price_cents ?? 40000) / 100);
  const [strategy, setStrategy] = useState(policy?.strategy ?? "balanced");
  const [maxDeadGap, setMaxDeadGap] = useState<number | null>(policy?.max_dead_gap_days ?? null);
  const [demandLevel, setDemandLevel] = useState("medium");

  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [simError, setSimError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const latest = useRef(0);

  const valid =
    floor > 0 && ceiling >= floor && reference >= floor && reference <= ceiling && reference > 0;

  const proposal = useMemo(
    () => ({
      reference_price_cents: Math.round(reference * 100),
      floor_price_cents: Math.round(floor * 100),
      ceiling_price_cents: Math.round(ceiling * 100),
      strategy,
      max_dead_gap_days: maxDeadGap,
    }),
    [reference, floor, ceiling, strategy, maxDeadGap],
  );

  const simulate = useCallback(async () => {
    if (!valid) return;
    const run = ++latest.current;
    setSimulating(true);
    try {
      const data = await fetchJson<Simulation>(`/api/charterer/boats/${boat.id}/pricing/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...proposal, demand_level: demandLevel }),
      });
      if (run === latest.current) {
        setSimulation(data);
        setSimError(null);
      }
    } catch (err) {
      if (run === latest.current) {
        setSimError(err instanceof Error ? err.message : "Vorschau nicht möglich");
      }
    } finally {
      if (run === latest.current) setSimulating(false);
    }
  }, [boat.id, proposal, valid, demandLevel]);

  useEffect(() => {
    const timer = setTimeout(simulate, 400);
    return () => clearTimeout(timer);
  }, [simulate]);

  async function save() {
    setSaveState("saving");
    setSaveError(null);
    try {
      await fetchJson(`/api/charterer/boats/${boat.id}/pricing`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "corridor", currency: "EUR", ...proposal }),
      });
      setSaveState("saved");
    } catch (err) {
      setSaveState("error");
      setSaveError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    }
  }

  const dyn = simulation?.dynamic;
  const cls = simulation?.static;

  return (
    <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
      <div className="space-y-4">
        <section className="card space-y-4 p-5">
          <div>
            <h2 className="text-lg font-semibold">Dein Preisrahmen</h2>
            <p className="mt-1 text-sm text-muted">
              Der Algorithmus arbeitet strikt zwischen diesen Werten. Unter die Untergrenze geht er
              nie, auch nicht bei leerem Kalender.
            </p>
          </div>

          {/* The corridor as a bar makes the room the algorithm has immediately legible. */}
          <div>
            <div className="flex items-baseline justify-between text-xs text-muted">
              <span>{money(floor * 100)}</span>
              <span>Spielraum {ceiling > floor ? `${Math.round((ceiling / floor - 1) * 100)} %` : "keiner"}</span>
              <span>{money(ceiling * 100)}</span>
            </div>
            <div className="relative mt-1.5 h-2 rounded-full bg-surface-muted">
              <div className="absolute inset-y-0 left-0 right-0 rounded-full bg-accent-soft" />
              {ceiling > floor ? (
                <div
                  className="absolute -top-1 h-4 w-1 rounded bg-accent"
                  style={{
                    left: `${Math.min(100, Math.max(0, ((reference - floor) / (ceiling - floor)) * 100))}%`,
                  }}
                  aria-hidden
                />
              ) : null}
            </div>
            <p className="mt-1 text-center text-xs text-muted">
              Referenz Hochsaison {money(reference * 100)}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            {[
              ["Untergrenze je Nacht", floor, setFloor, "floor"],
              ["Referenzpreis Hochsaison", reference, setReference, "reference"],
              ["Obergrenze je Nacht", ceiling, setCeiling, "ceiling"],
            ].map(([label, value, setter, id]) => (
              <div key={id as string}>
                <label className="label" htmlFor={id as string}>
                  {label as string}
                </label>
                <input
                  id={id as string}
                  type="number"
                  min={0}
                  step={10}
                  className="field"
                  value={value as number}
                  onChange={(e) => (setter as (v: number) => void)(Number(e.target.value || 0))}
                />
              </div>
            ))}
          </div>
          {!valid ? (
            <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
              Der Referenzpreis muss zwischen Unter- und Obergrenze liegen.
            </p>
          ) : null}
        </section>

        <section className="card space-y-3 p-5">
          <h2 className="text-lg font-semibold">Wie offensiv verkaufen?</h2>
          <div className="space-y-2">
            {STRATEGIES.map((option) => (
              <button
                type="button"
                key={option.value}
                onClick={() => setStrategy(option.value)}
                className={`w-full rounded-lg border p-3 text-left text-sm ${
                  strategy === option.value
                    ? "border-transparent bg-accent-soft text-accent"
                    : "border-line hover:bg-surface-muted"
                }`}
              >
                <span className="block font-medium">{option.title}</span>
                <span className="mt-0.5 block text-xs">{option.text}</span>
              </button>
            ))}
          </div>
          <div>
            <span className="label">Wie gefragt ist dein Boot heute?</span>
            <div className="grid grid-cols-2 gap-2">
              {DEMAND_LEVELS.map((level) => (
                <button
                  type="button"
                  key={level.value}
                  onClick={() => setDemandLevel(level.value)}
                  className={`rounded-lg border px-3 py-2 text-left text-sm ${
                    demandLevel === level.value
                      ? "border-transparent bg-accent-soft text-accent"
                      : "border-line hover:bg-surface-muted"
                  }`}
                >
                  <span className="block font-medium">{level.label}</span>
                  <span className="block text-xs">{level.hint}</span>
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-muted">
              Das ist eine Annahme für die Vorschau, keine Einstellung am Algorithmus. Sie
              bestimmt, wie viele Anfragen die Rechnung unterstellt.
            </p>
          </div>

          <div>
            <label className="label" htmlFor="dead-gap">
              Resttage, die noch verkäuflich sind
            </label>
            <input
              id="dead-gap"
              type="number"
              min={0}
              max={14}
              placeholder={`Standard: Mindestdauer (${boat.min_days})`}
              className="field"
              value={maxDeadGap ?? ""}
              onChange={(e) => setMaxDeadGap(e.target.value === "" ? null : Number(e.target.value))}
            />
            <p className="mt-1 text-xs text-muted">
              Kürzere Lücken gelten als verloren und werden einer Buchung als Kosten angerechnet.
            </p>
          </div>
        </section>

        <div className="flex items-center gap-3">
          <button type="button" className="btn-primary" onClick={save} disabled={!valid || saveState === "saving"}>
            {saveState === "saving" ? "Speichert …" : "Einstellung übernehmen"}
          </button>
          {saveState === "saved" ? <span className="text-sm text-positive">Gespeichert</span> : null}
        </div>
        {saveError ? (
          <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
            {saveError}
          </p>
        ) : null}
      </div>

      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            label="Erlös je Bootstag"
            value={money(dyn?.revpabd_cents)}
            hint="über die verfügbaren Tage des Jahres"
          />
          <Stat
            label="klassischer Wochentarif"
            value={money(cls?.revpabd_cents)}
            hint={
              simulation
                ? `${signedPercent(simulation.uplift_cents, cls?.revenue_cents ?? 0)} Unterschied im Jahr`
                : undefined
            }
            tone={simulation && simulation.uplift_cents >= 0 ? "positive" : undefined}
          />
          <Stat
            label="Auslastung"
            value={dyn ? `${(dyn.occupancy * 100).toFixed(0)} %` : "–"}
            hint={dyn ? `${Math.round(dyn.booked_days)} von ${dyn.available_days} Tagen` : undefined}
          />
          <Stat
            label="Ø Preis je Nacht"
            value={money(dyn?.avg_price_cents)}
            hint={cls ? `klassisch ${money(cls.avg_price_cents)}` : undefined}
          />
        </div>

        <section className="card p-5">
          {simError ? (
            <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
              {simError}
            </p>
          ) : simulation ? (
            <>
              <RevenueChart dynamic={simulation.dynamic.months} classic={simulation.static.months} />
              <p className="mt-4 border-t border-line pt-3 text-xs text-muted">
                {String(simulation.assumptions.baseline ?? "")} {String(simulation.assumptions.note ?? "")}
              </p>
            </>
          ) : (
            <p className="py-12 text-center text-sm text-muted">
              {simulating ? "Rechnet das Jahr durch …" : "Setze einen gültigen Preisrahmen."}
            </p>
          )}
        </section>

        <section className="card p-5 text-sm">
          <h2 className="text-base font-semibold">Was die Zahl bedeutet</h2>
          <p className="mt-2 text-muted">
            Der Erlös je verfügbarem Bootstag rechnet den Jahresumsatz auf die Tage um, an denen
            das Boot überhaupt verfügbar war. Winterlager und Sperrzeiten zählen nicht mit. Damit
            ist ein leerer Juli teuer, ein ausgebuchter Oktober zu billig verkauft aber auch.
          </p>
          <p className="mt-2 text-muted">
            Der Vergleichswert ist der Markt von heute: ein fester Saisonpreis für sieben Nächte,
            Samstag bis Samstag. Wie groß der Unterschied ausfällt, hängt an der angenommenen
            Nachfrage. Bei einem Boot mit freien Wochen holt Flexibilität Buchungen, die eine
            starre Woche nie erreicht. Ist das Boot ohnehin voll, zählt fast nur noch der Preis,
            und beide Modelle liegen nah beieinander.
          </p>
          <p className="mt-2 text-muted">
            Die Strategie wirkt erst, wenn der Kalender umkämpft ist. In einem leeren Kalender
            zerschneidet eine Kurzbuchung nichts, also verlangt auch die zurückhaltende
            Einstellung keinen Aufschlag.
          </p>
        </section>
      </div>
    </div>
  );
}
