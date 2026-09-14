"use client";

import { useId, useState } from "react";

import type { MonthPoint } from "@/lib/api";
import { money } from "@/lib/format";

type Series = { key: "dynamic" | "classic"; label: string; color: string; points: MonthPoint[] };

const WIDTH = 760;
const HEIGHT = 280;
const PAD = { top: 16, right: 12, bottom: 34, left: 52 };
const MAX_BAR = 24;
const GAP = 2; // surface gap between the two touching bars of a month

function niceCeiling(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10]) {
    if (step * magnitude >= value) return step * magnitude;
  }
  return 10 * magnitude;
}

/**
 * Revenue per available boat day, month by month: the dynamic rule against the classic
 * week tariff. Two series, so the legend is always present and every value is reachable
 * through the table view underneath.
 */
export default function RevenueChart({
  dynamic,
  classic,
}: {
  dynamic: MonthPoint[];
  classic: MonthPoint[];
}) {
  const titleId = useId();
  const [hover, setHover] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  const months = dynamic.map((m) => m.month);
  const byMonth = (points: MonthPoint[], month: number) =>
    points.find((p) => p.month === month) ?? null;

  const series: Series[] = [
    { key: "dynamic", label: "Dynamische Regel", color: "var(--series-dynamic)", points: dynamic },
    { key: "classic", label: "Klassischer Wochentarif", color: "var(--series-classic)", points: classic },
  ];

  const values = [...dynamic, ...classic].map((m) => m.revpabd_cents / 100);
  const top = niceCeiling(Math.max(1, ...values));
  const plotWidth = WIDTH - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;
  const band = months.length ? plotWidth / months.length : plotWidth;
  const barWidth = Math.min(MAX_BAR, Math.max(6, (band - GAP) / 2 - 6));
  const y = (euro: number) => PAD.top + plotHeight - (euro / top) * plotHeight;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(top * f));

  const best = dynamic.reduce<MonthPoint | null>(
    (peak, m) => (!peak || m.revpabd_cents > peak.revpabd_cents ? m : peak),
    null,
  );

  return (
    <figure className="viz m-0">
      <figcaption className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span id={titleId} className="text-sm font-medium">
          Erlös je verfügbarem Bootstag im Monat
        </span>
        <div className="flex items-center gap-3 text-xs text-muted">
          {series.map((s) => (
            <span key={s.key} className="flex items-center gap-1.5">
              <span
                aria-hidden
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: s.color }}
              />
              {s.label}
            </span>
          ))}
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            className="rounded px-1.5 py-0.5 hover:bg-surface-muted"
          >
            {showTable ? "Diagramm" : "Tabelle"}
          </button>
        </div>
      </figcaption>

      {showTable ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="pb-2">Monat</th>
                <th className="pb-2 text-right">Dynamisch</th>
                <th className="pb-2 text-right">Klassisch</th>
                <th className="pb-2 text-right">Auslastung</th>
                <th className="pb-2 text-right">Ø Preis</th>
              </tr>
            </thead>
            <tbody>
              {months.map((month) => {
                const d = byMonth(dynamic, month);
                const c = byMonth(classic, month);
                return (
                  <tr key={month} className="border-t border-line">
                    <td className="py-1.5">{d?.label}</td>
                    <td className="py-1.5 text-right font-mono">{money(d?.revpabd_cents)}</td>
                    <td className="py-1.5 text-right font-mono">{money(c?.revpabd_cents)}</td>
                    <td className="py-1.5 text-right">{((d?.occupancy ?? 0) * 100).toFixed(0)} %</td>
                    <td className="py-1.5 text-right font-mono">{money(d?.avg_price_cents)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="h-auto w-full"
            role="img"
            aria-labelledby={titleId}
            onMouseLeave={() => setHover(null)}
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line
                  x1={PAD.left}
                  x2={WIDTH - PAD.right}
                  y1={y(tick)}
                  y2={y(tick)}
                  stroke="var(--viz-grid)"
                  strokeWidth={1}
                />
                <text
                  x={PAD.left - 8}
                  y={y(tick) + 4}
                  textAnchor="end"
                  className="fill-[var(--color-muted)] text-[11px]"
                >
                  {tick} €
                </text>
              </g>
            ))}

            {months.map((month, index) => {
              const x0 = PAD.left + index * band;
              const d = byMonth(dynamic, month);
              const c = byMonth(classic, month);
              const groupWidth = barWidth * 2 + GAP;
              const startX = x0 + (band - groupWidth) / 2;
              return (
                <g key={month}>
                  {hover === month ? (
                    <rect
                      x={x0}
                      y={PAD.top}
                      width={band}
                      height={plotHeight}
                      fill="var(--color-surface-muted)"
                      opacity={0.6}
                    />
                  ) : null}
                  {[d, c].map((point, seriesIndex) => {
                    if (!point) return null;
                    const euro = point.revpabd_cents / 100;
                    const height = Math.max(0, PAD.top + plotHeight - y(euro));
                    return (
                      <rect
                        key={seriesIndex}
                        x={startX + seriesIndex * (barWidth + GAP)}
                        y={y(euro)}
                        width={barWidth}
                        height={height}
                        rx={Math.min(4, barWidth / 2)}
                        fill={series[seriesIndex].color}
                      />
                    );
                  })}
                  <text
                    x={x0 + band / 2}
                    y={HEIGHT - 12}
                    textAnchor="middle"
                    className="fill-[var(--color-muted)] text-[11px]"
                  >
                    {d?.label}
                  </text>
                  {best && best.month === month && d ? (
                    <text
                      x={x0 + band / 2}
                      y={y(d.revpabd_cents / 100) - 6}
                      textAnchor="middle"
                      className="fill-[var(--color-foreground)] text-[11px] font-medium"
                    >
                      {money(d.revpabd_cents)}
                    </text>
                  ) : null}
                  <rect
                    x={x0}
                    y={PAD.top}
                    width={band}
                    height={plotHeight}
                    fill="transparent"
                    onMouseEnter={() => setHover(month)}
                  />
                </g>
              );
            })}

            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={PAD.top + plotHeight}
              y2={PAD.top + plotHeight}
              stroke="var(--viz-grid)"
              strokeWidth={1}
            />
          </svg>

          {hover !== null ? (
            <div className="pointer-events-none absolute left-1/2 top-2 -translate-x-1/2 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
              <p className="font-medium">{byMonth(dynamic, hover)?.label}</p>
              {series.map((s) => {
                const point = byMonth(s.points, hover);
                return (
                  <p key={s.key} className="mt-0.5 flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className="inline-block h-2 w-2 rounded-sm"
                      style={{ background: s.color }}
                    />
                    {s.label}: <span className="font-mono">{money(point?.revpabd_cents)}</span>
                  </p>
                );
              })}
              <p className="mt-1 text-muted">
                Auslastung {((byMonth(dynamic, hover)?.occupancy ?? 0) * 100).toFixed(0)} % · Ø{" "}
                {money(byMonth(dynamic, hover)?.avg_price_cents)} je Nacht
              </p>
            </div>
          ) : null}
        </div>
      )}
    </figure>
  );
}
