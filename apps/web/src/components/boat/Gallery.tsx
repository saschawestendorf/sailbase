"use client";

import { useState } from "react";

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
    return <div className="aspect-[21/9] w-full rounded-2xl bg-surface-muted" />;
  }
  const current = images[Math.min(active, images.length - 1)];

  return (
    <div>
      <div className="relative overflow-hidden rounded-2xl">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={current.url}
          alt={current.caption || name}
          className="aspect-[21/9] w-full object-cover"
        />
        <div className="absolute left-3 top-3 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${ORIGIN_TONE[current.origin] ?? "bg-surface-muted text-muted"}`}
          >
            {ORIGIN_LABELS[current.origin] ?? current.origin}
          </span>
          {current.charter_month ? (
            <span className="rounded-full bg-surface/90 px-2.5 py-1 text-xs text-muted">
              Charter {monthLabel(current.charter_month)}
            </span>
          ) : null}
        </div>
        {current.caption || current.credit ? (
          <p className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-4 pb-3 pt-8 text-xs text-white">
            {current.caption}
            {current.credit ? ` · ${current.credit}` : ""}
          </p>
        ) : null}
      </div>

      {images.length > 1 ? (
        <ul className="mt-2 flex gap-2 overflow-x-auto pb-1">
          {images.map((image, index) => (
            <li key={image.id}>
              <button
                type="button"
                onClick={() => setActive(index)}
                aria-label={ORIGIN_LABELS[image.origin] ?? image.origin}
                aria-current={index === active}
                className={`block overflow-hidden rounded-lg border-2 ${
                  index === active ? "border-accent" : "border-transparent"
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={image.url} alt="" className="h-16 w-24 object-cover" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {images.some((i) => i.origin === "model") ? (
        <p className="mt-2 text-xs text-muted">
          Modellfotos zeigen die Baureihe, nicht dieses Schiff. Aktuelle Aufnahmen sind separat
          gekennzeichnet.
        </p>
      ) : null}
    </div>
  );
}
