import { buildSceneSvg } from "@/lib/illustration";

/**
 * Bildersatz für Boote ohne eigene Fotos.
 *
 * Eine leere graue Fläche lässt ein Inserat unfertig wirken, ein zufälliges
 * Fremdfoto lässt es unseriös wirken. Deshalb dieselbe gezeichnete Szene, die
 * auch die Illustrations-Route ausliefert – eine Quelle, zwei Wege.
 */
export default function SailPlaceholder({
  name,
  className = "",
}: {
  name: string;
  className?: string;
}) {
  // Das Markup stammt aus dem eigenen Generator; der Name landet dort nie im
  // Ergebnis, sondern wird nur zu Zahlen verrechnet.
  const svg = buildSceneSvg(name);
  return (
    <div
      className={`overflow-hidden [&>svg]:h-full [&>svg]:w-full ${className}`}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
