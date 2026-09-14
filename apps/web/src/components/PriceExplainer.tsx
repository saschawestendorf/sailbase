import type { Breakdown } from "@/lib/api";
import { money } from "@/lib/format";

function factorTone(multiplier: number) {
  if (multiplier > 1.005) return "text-warn";
  if (multiplier < 0.995) return "text-positive";
  return "text-muted";
}

function factorValue(multiplier: number) {
  const pct = (multiplier - 1) * 100;
  if (Math.abs(pct) < 0.5) return "neutral";
  return `${pct > 0 ? "+" : ""}${pct.toFixed(0)} %`;
}

/** Shows why the price is what it is: the whole point of dynamic pricing is being explainable. */
export default function PriceExplainer({ breakdown }: { breakdown: Breakdown }) {
  const factors = [...(breakdown.day_factors ?? []), ...(breakdown.stay_factors ?? [])];
  const fees = breakdown.fee_lines ?? [];
  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-baseline justify-between gap-4 border-b border-line pb-3">
        <span className="text-muted">Grundpreis Hochsaison</span>
        <span className="font-mono">{money(breakdown.reference_per_day_cents)} / Nacht</span>
      </div>

      <ul className="space-y-2">
        {factors.map((f) => (
          <li key={f.key} className="flex items-baseline justify-between gap-4">
            <span>
              {f.label}
              {f.detail ? <span className="block text-xs text-muted">{f.detail}</span> : null}
            </span>
            <span className={`font-mono whitespace-nowrap ${factorTone(f.multiplier)}`}>
              {factorValue(f.multiplier)}
            </span>
          </li>
        ))}
      </ul>

      {breakdown.clamped ? (
        <p className="rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">
          {breakdown.clamped === "floor"
            ? "Preisuntergrenze des Vercharterers erreicht – günstiger geht dieser Zeitraum nicht."
            : "Preisobergrenze des Vercharterers erreicht – teurer wird es trotz hoher Nachfrage nicht."}
        </p>
      ) : null}

      <div className="flex items-baseline justify-between gap-4 border-t border-line pt-3">
        <span className="text-muted">
          Charterpreis · {breakdown.nights} {breakdown.nights === 1 ? "Nacht" : "Nächte"} ×{" "}
          {money(breakdown.per_day_cents)}
        </span>
        <span className="font-mono">{money(breakdown.charter_cents)}</span>
      </div>

      {fees.map((fee) => (
        <div key={fee.key} className="flex items-baseline justify-between gap-4">
          <span>
            {fee.label}
            {fee.detail ? <span className="block text-xs text-muted">{fee.detail}</span> : null}
          </span>
          <span className={`font-mono ${fee.amount_cents < 0 ? "text-positive" : ""}`}>
            {money(fee.amount_cents)}
          </span>
        </div>
      ))}

      <div className="flex items-baseline justify-between gap-4 border-t border-line pt-3 text-base font-semibold">
        <span>Gesamt</span>
        <span className="font-mono">{money(breakdown.total_cents, true)}</span>
      </div>
    </div>
  );
}
