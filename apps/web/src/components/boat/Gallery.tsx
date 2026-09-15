"use client";

import { useState } from "react";

import SailPlaceholder from "@/components/ui/SailPlaceholder";
import type { BoatImage } from "@/lib/api";
import { dateLabel } from "@/lib/format";

const ORIGIN_LABELS: Record<string, string> = {
  owner: "Foto des Vercharterers",
  guest: "Foto eines Chartergastes",
  model: "Modellfoto des Herstellers",
};

const ORIGIN_TONE: Record<string, string> = {
  owner: "bg-surface-muted text-muted",
  guest: "bg-accent-soft text-accent",
  model: "bg-warn-soft text-warn",
};

/**
 * Gezeichnete Ersatzbilder dürfen nie als Aufnahme durchgehen. Die Marke richtet
 * sich deshalb nach der Bildquelle, nicht nur nach dem hinterlegten Ursprung:
 * was aus der eigenen Illustrationsroute kommt, heißt Illustration.
 */
function isIllustration(url: string): boolean {
  return url.startsWith("/illustration/");
}

function monthLabel(month: string): string {
  if (!/^\d{4}-\d{2}$/.test(month)) return "";
  return dateLabel(`${month}-01`, { month: "long", year: "numeric" });
}

/**
 * Pictures carry their origin on the picture, not in a footnote: a stock shot of the model
 * must never read as a photo of this particular boat.
 */
export default function Gallery({ images, name }: { images: BoatImage[]; name: string }) {
  const [active, setActive] = useState(0);
  if (!images.length) {
    return (
      <SailPlaceholder name={name} className="aspect-[21/9] w-full rounded-[1.75rem] shadow-card" />
    );
  }
  const current = images[Math.min(active, images.length - 1)];

  return (
    <div>
      <div className="relative overflow-hidden rounded-[1.75rem] shadow-card">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={current.url}
          alt={current.caption || name}
          className="aspect-[21/9] w-full object-cover"
        />
        <div className="absolute left-4 top-4 flex flex-wrap items-center gap-2">
          <span
            className={`badge shadow-sm ${
              isIllustration(current.url)
                ? "bg-surface/90 text-muted backdrop-blur"
                : (ORIGIN_TONE[current.origin] ?? "bg-surface-muted text-muted")
            }`}
          >
            {isIllustration(current.url)
              ? "Illustration, kein Foto"
              : (ORIGIN_LABELS[current.origin] ?? current.origin)}
          </span>
          {current.charter_month ? (
            <span className="badge bg-surface/90 text-muted shadow-sm backdrop-blur">
              Charter {monthLabel(current.charter_month)}
            </span>
          ) : null}
        </div>
        {current.caption || current.credit ? (
          /* Ein dunkler Verlauf trägt weiße Schrift nur über einem Foto. Über der
             hellen Zeichnung wäre er weder schön noch lesbar, deshalb dort eine
             helle Leiste mit Tintenschrift. */
          <p
            className={
              isIllustration(current.url)
                ? "absolute inset-x-0 bottom-0 border-t border-line bg-surface/90 px-5 py-2.5 text-xs text-muted backdrop-blur"
                : "absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 via-black/25 to-transparent px-5 pb-4 pt-12 text-xs text-white/90"
            }
          >
            {current.caption}
            {current.credit ? ` · ${current.credit}` : ""}
          </p>
        ) : null}
      </div>

      {images.length > 1 ? (
        <ul className="mt-3 flex gap-2.5 overflow-x-auto pb-1">
          {images.map((image, index) => (
            <li key={image.id}>
              <button
                type="button"
                onClick={() => setActive(index)}
                aria-label={ORIGIN_LABELS[image.origin] ?? image.origin}
                aria-current={index === active}
                className={`block overflow-hidden rounded-xl ring-2 transition ${
                  index === active
                    ? "ring-accent"
                    : "ring-transparent hover:ring-line-strong"
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={image.url}
                  alt=""
                  className={`h-16 w-24 object-cover transition ${index === active ? "" : "opacity-80 hover:opacity-100"}`}
                />
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {images.some((i) => i.origin === "model" && !isIllustration(i.url)) ? (
        <p className="mt-3 text-xs text-muted">
          Modellfotos zeigen die Baureihe, nicht dieses Schiff. Aktuelle Aufnahmen sind separat
          gekennzeichnet.
        </p>
      ) : null}
    </div>
  );
}
