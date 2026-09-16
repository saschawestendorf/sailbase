/**
 * Die Farbskala des Preisrasters — an einer Stelle, damit Kalender, Datumsraster
 * und Bootsansicht dieselbe Sprache sprechen.
 *
 * Verglichen wird immer gegen einen **Bezugswert derselben Art**: den günstigsten
 * Preis derselben Dauer. Ein Vergleich über Dauern hinweg wäre keiner — sieben
 * Nächte kosten immer mehr als fünf, grün hieße dann nur „kurz".
 *
 * Die Schwellen sind bewusst grob. Sie sollen eine Richtung zeigen, keine
 * Genauigkeit vortäuschen, die ein Preisvergleich nicht hergibt.
 */

export type Niveau = "guenstig" | "normal" | "teuer";

const GUENSTIG_BIS = 1.06;
const NORMAL_BIS = 1.22;

export function niveauVon(total: number, bezug: number | undefined): Niveau {
  if (!bezug) return "normal";
  const faktor = total / bezug;
  if (faktor <= GUENSTIG_BIS) return "guenstig";
  if (faktor <= NORMAL_BIS) return "normal";
  return "teuer";
}

export const ZELLE: Record<Niveau, string> = {
  guenstig: "border-positive/45 bg-positive-soft text-foreground",
  normal: "border-line bg-surface text-foreground",
  teuer: "border-warn/35 bg-warn-soft/50 text-foreground",
};

export const PUNKT: Record<Niveau, string> = {
  guenstig: "bg-positive",
  normal: "bg-line-strong",
  teuer: "bg-warn",
};

export const NIVEAU_TEXT: Record<Niveau, string> = {
  guenstig: "günstig",
  normal: "üblich",
  teuer: "teuer",
};

/** Die Legende, die unter jeder der drei Ansichten steht. */
export const NIVEAUS: Niveau[] = ["guenstig", "normal", "teuer"];

export function minimum(werte: number[]): number | undefined {
  return werte.length ? Math.min(...werte) : undefined;
}
