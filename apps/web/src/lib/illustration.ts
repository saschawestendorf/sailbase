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

export type SceneTone = "morgen" | "mittag" | "abend";

// Helle Szenen: Himmel fast weiß, Wasser ein Hauch Grün, Segel weiß mit einer
// Kante. Der Rumpf ist der einzige dunkle Wert – so bleibt das Bild ruhig genug,
// um neben Text zu stehen, und trägt trotzdem eine Silhouette.
const TONES: Record<SceneTone, { top: string; mid: string; water: string; glow: string }> = {
  morgen: { top: "#ffffff", mid: "#f4f7f7", water: "#dfeceb", glow: "#0a6f6a" },
  mittag: { top: "#fdfefe", mid: "#f1f6f7", water: "#d9e9ea", glow: "#1f6fb2" },
  abend: { top: "#fffdf9", mid: "#f8f3ea", water: "#e6e7dd", glow: "#94703a" },
};

const TONE_ORDER: SceneTone[] = ["morgen", "mittag", "abend"];

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
  const horizon = 52 + (seed % 9);
  const shift = -8 + (seed % 17);
  const scale = (0.86 + ((seed >> 3) % 7) / 20).toFixed(2);
  const secondSail = seed % 3 !== 0;
  const sunX = 30 + (seed % 100);

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 100" width="${width}" height="${height}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustration einer Segelyacht auf See">
  <defs>
    <linearGradient id="sky${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${tone.top}"/>
      <stop offset="100%" stop-color="${tone.mid}"/>
    </linearGradient>
    <linearGradient id="sea${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${tone.water}"/>
      <stop offset="100%" stop-color="${tone.mid}"/>
    </linearGradient>
    <radialGradient id="sun${id}" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="${tone.glow}" stop-opacity="0.14"/>
      <stop offset="100%" stop-color="${tone.glow}" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="160" height="${horizon}" fill="url(#sky${id})"/>
  <rect y="${horizon}" width="160" height="${100 - horizon}" fill="url(#sea${id})"/>
  <circle cx="${sunX}" cy="${horizon - 16}" r="30" fill="url(#sun${id})"/>
  <line x1="0" y1="${horizon}" x2="160" y2="${horizon}" stroke="#12222a" stroke-opacity="0.12" stroke-width="0.4"/>

  <g transform="translate(${80 + shift} ${horizon}) scale(${scale})">
    <path d="M0 -42 L0 -2 L-19 -2 Z" fill="#ffffff" stroke="#12222a" stroke-opacity="0.35" stroke-width="0.5" stroke-linejoin="round"/>
    ${secondSail ? `<path d="M1.5 -34 L13 -2 L1.5 -2 Z" fill="#ffffff" stroke="#12222a" stroke-opacity="0.22" stroke-width="0.5" stroke-linejoin="round"/>` : ""}
    <line x1="0" y1="-43" x2="0" y2="-2" stroke="#12222a" stroke-opacity="0.45" stroke-width="0.6"/>
    <path d="M-22 -2 L15 -2 L9 3.4 L-16 3.4 Z" fill="#12222a" fill-opacity="0.88"/>
    <path d="M-14 4.8 L8 4.8 L4 7.6 L-10 7.6 Z" fill="#12222a" fill-opacity="0.1"/>
  </g>

  <path d="M0 ${horizon + 12} q 26 -4 52 0 t 52 0 t 56 0" stroke="#12222a" stroke-opacity="0.08" stroke-width="0.6" fill="none"/>
  <path d="M0 ${horizon + 24} q 30 -5 60 0 t 60 0 t 40 0" stroke="#12222a" stroke-opacity="0.06" stroke-width="0.6" fill="none"/>
  <path d="M0 ${horizon + 38} q 34 -6 68 0 t 68 0" stroke="#12222a" stroke-opacity="0.05" stroke-width="0.6" fill="none"/>
</svg>`;
}
