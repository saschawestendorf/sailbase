const EUR = new Intl.NumberFormat("de-DE", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});
const EUR_EXACT = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });

export function money(cents: number | null | undefined, exact = false): string {
  if (cents === null || cents === undefined || Number.isNaN(cents)) return "–";
  return (exact ? EUR_EXACT : EUR).format(cents / 100);
}

export function dateLabel(iso: string | null | undefined, opts?: Intl.DateTimeFormatOptions): string {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("de-DE", opts ?? { day: "2-digit", month: "short", year: "numeric" });
}

export function dateRange(start: string, end: string): string {
  const short: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short" };
  return `${dateLabel(start, short)} – ${dateLabel(end, { ...short, year: "numeric" })}`;
}

export function nightsBetween(start: string, end: string): number {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return Math.max(0, Math.round(ms / 86_400_000));
}

export function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function addDays(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return isoDay(d);
}

/** Percentage with a sign, for the dynamic-vs-static comparison. */
export function signedPercent(value: number, base: number): string {
  if (!base) return "–";
  const pct = (value / base) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1).replace(".", ",")} %`;
}

export const CHARACTER_LABELS: Record<string, string> = {
  good_natured: "gutmütig",
  sporty: "sportlich",
  comfort: "komfortabel",
  bluewater: "seetüchtig",
  classic: "klassisch",
};

export const FEATURE_LABELS: Record<string, string> = {
  bowthruster: "Bugstrahlruder",
  autopilot: "Autopilot",
  plotter: "Kartenplotter",
  radar: "Radar",
  sprayhood: "Sprayhood",
  bimini: "Bimini",
  hardtop: "Hardtop",
  heating: "Heizung",
  generator: "Generator",
  watermaker: "Wassermacher",
  code0: "Code 0",
  carbon_mast: "Carbonmast",
  selftacking_jib: "Selbstwendefock",
  electric_winch: "E-Winsch",
  outdoor_galley: "Außenküche",
  shallow_draft: "Flachkiel",
};

export const LICENSE_LABELS: Record<number, string> = {
  0: "kein Schein",
  1: "SBF Binnen",
  2: "SBF See",
  3: "SKS",
  4: "SSS",
  5: "SHS",
};

export const STATUS_LABELS: Record<string, string> = {
  pending_payment: "Zahlung offen",
  confirmed: "Bestätigt",
  ready: "Bereit zur Übernahme",
  handed_over: "Übergeben",
  returned: "Zurückgegeben",
  settled: "Abgerechnet",
  cancelled: "Storniert",
  expired: "Abgelaufen",
};

export function label(map: Record<string, string>, key: string): string {
  return map[key] ?? key.replace(/_/g, " ");
}
