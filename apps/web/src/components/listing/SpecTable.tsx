"use client";

import type { ResolvedSpec } from "@/lib/api";

const LABELS: Record<string, [string, string]> = {
  length_m: ["Länge über alles", "m"],
  beam_m: ["Breite", "m"],
  draft_m: ["Tiefgang", "m"],
  displacement_kg: ["Verdrängung", "kg"],
  sail_area_m2: ["Segelfläche", "m²"],
  engine_hp: ["Motorleistung", "PS"],
  headroom_cm: ["Stehhöhe Salon", "cm"],
  max_berth_length_cm: ["Längste Koje", "cm"],
  cabins: ["Kabinen", ""],
  berths: ["Kojen", ""],
  heads: ["Nasszellen", ""],
  max_persons: ["Max. Personen", ""],
};

function sourceLabel(source: string | undefined): string {
  if (!source) return "unbekannt";
  if (source === "version") return "Katalog";
  if (source === "owner") return "eigene Angabe";
  return `Variante ${source.replace("variant:", "")}`;
}

function sourceTone(source: string | undefined): string {
  if (source === "owner") return "text-warn";
  if (source?.startsWith("variant:")) return "text-accent";
  return "text-muted";
}

/**
 * The resolved configuration with the origin of every number. An owner needs to see what the
 * catalog asserts and what they changed themselves, otherwise a deviation is invisible.
 */
export default function SpecTable({
  spec,
  onOverride,
  overrides,
}: {
  spec: ResolvedSpec;
  onOverride?: (field: string, value: number | null) => void;
  overrides?: Record<string, number | null>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="pb-2">Merkmal</th>
            <th className="pb-2 text-right">Wert</th>
            <th className="pb-2 text-right">Quelle</th>
            {onOverride ? <th className="pb-2 text-right">Abweichend</th> : null}
          </tr>
        </thead>
        <tbody>
          {Object.entries(LABELS).map(([field, [label, unit]]) => {
            const value = spec.values[field];
            const source = spec.sources[field];
            return (
              <tr key={field} className="border-t border-line">
                <td className="py-1.5">{label}</td>
                <td className="py-1.5 text-right font-mono">
                  {value === null || value === undefined ? (
                    <span className="text-warn">unbekannt</span>
                  ) : (
                    `${value}${unit ? ` ${unit}` : ""}`
                  )}
                </td>
                <td className={`py-1.5 text-right text-xs ${sourceTone(source)}`}>
                  {sourceLabel(source)}
                </td>
                {onOverride ? (
                  <td className="py-1.5 text-right">
                    <input
                      type="number"
                      step="any"
                      aria-label={`${label} abweichend`}
                      className="field w-24 py-1 text-right"
                      value={overrides?.[field] ?? ""}
                      onChange={(e) =>
                        onOverride(field, e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
      {spec.unknown.length ? (
        <p className="mt-3 rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">
          Unbekannt und als unbekannt ausgewiesen:{" "}
          {spec.unknown.map((f) => LABELS[f]?.[0] ?? f).join(", ")}. Trage sie rechts ein, wenn du
          sie kennst.
        </p>
      ) : null}
    </div>
  );
}
