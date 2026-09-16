"use client";

import { useId } from "react";

/** Gemeinsame Grundlage beider Regler: Spur, gefüllter Abschnitt, Beschriftung. */
function Spur({ von, bis, aus }: { von: number; bis: number; aus?: boolean }) {
  return (
    <>
      <div className="range-track inset-x-0 bg-surface-sunk" />
      <div
        className={`range-track transition-colors ${aus ? "bg-line-strong" : "bg-accent"}`}
        style={{ left: `${von * 100}%`, right: `${(1 - bis) * 100}%` }}
      />
    </>
  );
}

export type SliderProps = {
  label: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  onChange: (value: number) => void;
  /** Beschriftungen unter der Spur, gleichmäßig verteilt (links, Mitte, rechts …). */
  marks?: string[];
  /** Klartext der aktuellen Position, rechts neben der Beschriftung. */
  valueLabel?: string;
  disabled?: boolean;
  /** Ein Schalter rechts oben, z. B. „egal“ – ohne ihn gäbe es kein Aus. */
  toggle?: { label: string; active: boolean; onClick: () => void };
};

/** Ein Regler mit einem Griff – für eine Achse wie den Segelcharakter. */
export function Slider({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  marks,
  valueLabel,
  disabled = false,
  toggle,
}: SliderProps) {
  const id = useId();
  const anteil = (value - min) / (max - min || 1);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label className="label mb-0" htmlFor={id}>
          {label}
        </label>
        {toggle ? (
          <button
            type="button"
            onClick={toggle.onClick}
            aria-pressed={toggle.active}
            className={`rounded-full px-2.5 py-0.5 text-xs transition-colors ${
              toggle.active
                ? "bg-surface-muted font-medium text-foreground"
                : "text-muted hover:text-foreground"
            }`}
          >
            {toggle.label}
          </button>
        ) : null}
      </div>

      <div className="relative mt-3 h-6">
        <Spur von={0} bis={disabled ? 0 : anteil} aus={disabled} />
        <input
          id={id}
          type="range"
          className="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          aria-valuetext={valueLabel}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </div>

      {marks?.length ? (
        <div className="mt-1 flex justify-between text-[0.7rem] leading-tight text-faint">
          {marks.map((m, i) => (
            <span
              key={m}
              className={i === 0 ? "text-left" : i === marks.length - 1 ? "text-right" : "text-center"}
            >
              {m}
            </span>
          ))}
        </div>
      ) : null}

      {valueLabel ? (
        <p className={`mt-1.5 text-sm ${disabled ? "text-faint" : "text-foreground"}`}>{valueLabel}</p>
      ) : null}
    </div>
  );
}

export type RangeSliderProps = {
  label: string;
  min: number;
  max: number;
  step?: number;
  from: number;
  to: number;
  onChange: (from: number, to: number) => void;
  /** Formatiert einen Wert für die Anzeige, z. B. „9,5 m“ oder „1.200 €“. */
  format: (value: number) => string;
  /** Text, wenn der Bereich offen ist – dann filtert er nichts. */
  openLabel?: string;
};

/**
 * Zwei Griffe für einen Bereich. Stehen beide am Anschlag, filtert der Regler
 * nichts – das ist der Ausgangszustand und wird auch so benannt, damit niemand
 * einen Filter vermutet, wo keiner ist.
 */
export function RangeSlider({
  label,
  min,
  max,
  step = 1,
  from,
  to,
  onChange,
  format,
  openLabel = "beliebig",
}: RangeSliderProps) {
  const spanne = max - min || 1;
  const vonAnteil = (from - min) / spanne;
  const bisAnteil = (to - min) / spanne;
  const offen = from <= min && to >= max;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="label mb-0">{label}</span>
        <span className={`text-sm ${offen ? "text-faint" : "text-foreground"}`}>
          {offen ? openLabel : `${format(from)} – ${format(to)}`}
        </span>
      </div>

      <div className="relative mt-3 h-6">
        <Spur von={vonAnteil} bis={bisAnteil} aus={offen} />
        {/* Der untere Griff darf den oberen nicht blockieren, deshalb wird
            beim Ziehen jeweils der näher liegende Wert bewegt. */}
        <input
          type="range"
          className="range"
          aria-label={`${label}, von`}
          min={min}
          max={max}
          step={step}
          value={from}
          onChange={(e) => onChange(Math.min(Number(e.target.value), to), to)}
        />
        <input
          type="range"
          className="range"
          aria-label={`${label}, bis`}
          min={min}
          max={max}
          step={step}
          value={to}
          onChange={(e) => onChange(from, Math.max(Number(e.target.value), from))}
        />
      </div>

      <div className="mt-1 flex justify-between text-[0.7rem] text-faint">
        <span>{format(min)}</span>
        <span>{format(max)}+</span>
      </div>
    </div>
  );
}
