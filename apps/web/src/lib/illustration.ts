/**
 * Gezeichnete Ersatzbilder.
 *
 * Für Boote ohne Foto braucht das Portal etwas Besseres als eine graue Fläche,
 * aber nichts, was sich als Aufnahme dieses Schiffs ausgeben könnte. Also eine
 * erkennbare Illustration: Horizont, Segel, Dünung. Aus einem Startwert – Name
 * oder Slug – ergibt sich eine stabile Variante, damit zwei Boote nebeneinander
 * verschieden aussehen und dasselbe Boot immer gleich.
 *
 * Eine Quelle für beides: die React-Komponente und die SVG-Route, die dieselbe
 * Szene als Datei ausliefert.
 */

export type SceneTone = "sea" | "dusk" | "dawn";

const TONES: Record<SceneTone, { sky: string; deep: string; mid: string; glow: string }> = {
  sea: { sky: "#0f3a4e", mid: "#0b2a3a", deep: "#061f2d", glow: "#45cfc4" },
  dusk: { sky: "#123c4c", mid: "#0d2b39", deep: "#07202b", glow: "#d9b169" },
  dawn: { sky: "#0e4150", mid: "#0a2c3c", deep: "#051d29", glow: "#7ae0d7" },
};

const TONE_ORDER: SceneTone[] = ["sea", "dusk", "dawn"];

export function seedFrom(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) % 100000;
  }
  return hash;
}

/**
 * Baut die Szene als SVG-Zeichenkette. Alles Eingesetzte ist eine Zahl oder
 * stammt aus TONES – der Startwert selbst landet nie im Markup.
 */
export function buildSceneSvg(
  seedValue: string,
  { width = 1200, height = 800 }: { width?: number; height?: number } = {},
): string {
  const seed = seedFrom(seedValue);
  const id = seed % 9973;
  const tone = TONES[TONE_ORDER[seed % TONE_ORDER.length]];
  const horizon = 58 + (seed % 9);
  const shift = -8 + (seed % 17);
  const scale = (0.86 + ((seed >> 3) % 7) / 20).toFixed(2);
  const secondSail = seed % 3 !== 0;
  const sunX = 30 + (seed % 100);

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 100" width="${width}" height="${height}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustration einer Segelyacht auf See">
  <defs>
    <linearGradient id="g${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${tone.sky}"/>
      <stop offset="45%" stop-color="${tone.mid}"/>
      <stop offset="100%" stop-color="${tone.deep}"/>
    </linearGradient>
    <radialGradient id="s${id}" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="${tone.glow}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="${tone.glow}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="c${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fdfbf6" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#dfe8ea" stop-opacity="0.7"/>
    </linearGradient>
  </defs>

  <rect width="160" height="100" fill="url(#g${id})"/>
  <circle cx="${sunX}" cy="${horizon - 14}" r="34" fill="url(#s${id})"/>
  <line x1="0" y1="${horizon}" x2="160" y2="${horizon}" stroke="#cfe0e6" stroke-opacity="0.35" stroke-width="0.5"/>

  <g transform="translate(${80 + shift} ${horizon}) scale(${scale})">
    <path d="M0 -42 L0 -2 L-19 -2 Z" fill="url(#c${id})"/>
    ${secondSail ? `<path d="M1.5 -34 L13 -2 L1.5 -2 Z" fill="#fdfbf6" fill-opacity="0.55"/>` : ""}
    <path d="M-22 -2 L15 -2 L9 3.4 L-16 3.4 Z" fill="#04161f" fill-opacity="0.9"/>
    <path d="M-14 4.6 L8 4.6 L4 8 L-10 8 Z" fill="#fdfbf6" fill-opacity="0.08"/>
  </g>

  <path d="M0 ${horizon + 12} q 26 -4 52 0 t 52 0 t 56 0" stroke="#cfe0e6" stroke-opacity="0.16" stroke-width="0.7" fill="none"/>
  <path d="M0 ${horizon + 24} q 30 -5 60 0 t 60 0 t 40 0" stroke="#cfe0e6" stroke-opacity="0.12" stroke-width="0.7" fill="none"/>
  <path d="M0 ${horizon + 38} q 34 -6 68 0 t 68 0" stroke="#cfe0e6" stroke-opacity="0.09" stroke-width="0.7" fill="none"/>
</svg>`;
}
