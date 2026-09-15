import { buildSceneSvg } from "@/lib/illustration";

/**
 * Liefert die gezeichnete Seeszene als Bilddatei aus.
 *
 * Damit können Demo- und Platzhalterbilder über eine gewöhnliche Bild-URL
 * eingebunden werden, ohne dass das Portal Fremdquellen anfragt. Der Startwert
 * steckt im Pfad; er bestimmt nur Zahlen in der Zeichnung.
 */
export async function GET(_request: Request, ctx: RouteContext<"/illustration/[seed]">) {
  const { seed } = await ctx.params;
  const svg = buildSceneSvg(seed.replace(/\.svg$/, ""));
  return new Response(svg, {
    headers: {
      "Content-Type": "image/svg+xml; charset=utf-8",
      // Die Zeichnung hängt nur am Pfad und ändert sich nie.
      "Cache-Control": "public, max-age=31536000, immutable",
    },
  });
}
