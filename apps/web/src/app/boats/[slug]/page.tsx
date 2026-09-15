import Link from "next/link";
import { notFound } from "next/navigation";

import BookingForm from "@/components/BookingForm";
import Gallery from "@/components/boat/Gallery";
import Reviews from "@/components/boat/Reviews";
import PriceExplainer from "@/components/PriceExplainer";
import {
  ApiError,
  apiFetch,
  type CalendarResult,
  getBases,
  getBoat,
  getBoatReviews,
  getCalendar,
  type Quote,
  type Review,
} from "@/lib/api";
import {
  addDays,
  CHARACTER_LABELS,
  dateLabel,
  FEATURE_LABELS,
  isoDay,
  label,
  LICENSE_LABELS,
  money,
  nightsBetween,
} from "@/lib/format";

export const dynamic = "force-dynamic";

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function Spec({ term, value }: { term: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line py-2 last:border-0">
      <dt className="text-muted">{term}</dt>
      <dd className="tnum text-right font-medium">{value}</dd>
    </div>
  );
}

export default async function BoatPage(props: PageProps<"/boats/[slug]">) {
  const { slug } = await props.params;
  const sp = await props.searchParams;

  let boat;
  try {
    boat = await getBoat(slug);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const today = isoDay(new Date());
  const startDate = first(sp.start_date) ?? addDays(today, 30);
  const endDate = first(sp.end_date) ?? addDays(startDate, Math.max(boat.min_days, 7));
  const persons = Number(first(sp.persons) ?? Math.min(boat.max_persons || 4, 4));
  const pickupBaseId = first(sp.pickup_base_id);
  const dropoffBaseId = first(sp.dropoff_base_id);
  const nights = nightsBetween(startDate, endDate);

  const [bases, reviewData] = await Promise.all([
    getBases(),
    getBoatReviews(slug).catch(() => ({ summary: boat.ratings, reviews: [] as Review[] })),
  ]);
  const pickupName = pickupBaseId
    ? (bases.find((b) => b.id === pickupBaseId)?.name ?? "anderer Hafen")
    : boat.base.name;
  const dropoffName = dropoffBaseId
    ? (bases.find((b) => b.id === dropoffBaseId)?.name ?? "anderer Hafen")
    : pickupName;

  let quote: Quote | null = null;
  let quoteError: string | undefined;
  try {
    quote = await apiFetch<Quote>("/quotes", {
      method: "POST",
      body: JSON.stringify({
        boat_id: boat.id,
        start_date: startDate,
        end_date: endDate,
        persons,
        pickup_base_id: pickupBaseId ?? null,
        dropoff_base_id: dropoffBaseId ?? null,
      }),
    });
  } catch (error) {
    quoteError = error instanceof ApiError ? error.message : "Preis konnte nicht berechnet werden";
  }

  let calendar: CalendarResult | null = null;
  try {
    calendar = await getCalendar(slug, {
      start: today,
      days: 45,
      nights: Math.max(nights || boat.min_days, boat.min_days),
      pickup_base_id: pickupBaseId,
      dropoff_base_id: dropoffBaseId,
    });
  } catch {
    calendar = null;
  }

  const availableDays = calendar?.days.filter((d) => d.available && d.per_day_cents) ?? [];
  const cheapest = availableDays.reduce<number | null>(
    (min, d) => (min === null || (d.per_day_cents ?? 0) < min ? (d.per_day_cents ?? min) : min),
    null,
  );

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Link
        href="/search"
        className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-accent"
      >
        <span aria-hidden>←</span> Zurück zur Suche
      </Link>

      <header className="mt-5 flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="eyebrow">
            {boat.base.name}, {boat.base.city}
          </p>
          <h1 className="display mt-3 text-3xl sm:text-[2.75rem]">{boat.name}</h1>
          <p className="mt-2 text-muted">
            {boat.manufacturer} {boat.model}
            {boat.year_built ? ` · Baujahr ${boat.year_built}` : ""} · {boat.charterer.name}
          </p>
          {boat.ratings?.count ? (
            <p className="mt-2 text-sm">
              <span className="text-brass">★</span>{" "}
              <span className="font-medium">{boat.ratings.overall?.toFixed(1)}</span>
              <span className="ml-1 text-muted">
                aus {boat.ratings.count} verifizierten Charter
                {boat.ratings.count === 1 ? "" : "n"}
              </span>
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {(boat.character ?? []).map((c) => (
            <span key={c} className="chip chip-accent">
              {label(CHARACTER_LABELS, c)}
            </span>
          ))}
        </div>
      </header>

      <div className="mt-7">
        <Gallery images={boat.gallery ?? []} name={boat.name} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-6">
          <section className="card p-6 sm:p-7">
            <h2 className="text-xl">Über dieses Schiff</h2>
            <p className="mt-3 text-[0.95rem] leading-relaxed text-muted">{boat.description}</p>
            <hr className="rule my-6" />
            <dl className="grid gap-x-10 text-sm sm:grid-cols-2">
              <Spec term="Länge" value={`${boat.length_m.toFixed(2)} m`} />
              <Spec term="Breite" value={boat.beam_m ? `${boat.beam_m.toFixed(2)} m` : null} />
              <Spec term="Tiefgang" value={boat.draft_m ? `${boat.draft_m.toFixed(2)} m` : null} />
              <Spec term="Segelfläche" value={boat.sail_area_m2 ? `${boat.sail_area_m2} m²` : null} />
              <Spec term="Motor" value={boat.engine_hp ? `${boat.engine_hp} PS` : null} />
              <Spec term="Kabinen" value={boat.cabins} />
              <Spec term="Kojen" value={boat.berths} />
              <Spec term="Max. Personen" value={boat.max_persons} />
              <Spec term="Nasszellen" value={boat.heads} />
              <Spec term="Stehhöhe Salon" value={boat.headroom_cm ? `${boat.headroom_cm} cm` : null} />
              <Spec
                term="Längste Koje"
                value={boat.max_berth_length_cm ? `${boat.max_berth_length_cm} cm` : null}
              />
              <Spec term="Nötiger Schein" value={label(LICENSE_LABELS, String(boat.required_license))} />
              <Spec
                term="Nötige Erfahrung"
                value={boat.required_experience_nm ? `${boat.required_experience_nm} sm` : "keine"}
              />
              <Spec term="Kaution" value={money(boat.deposit_cents)} />
            </dl>

            {boat.features?.length ? (
              <div className="mt-6 flex flex-wrap gap-1.5">
                {boat.features.map((f) => (
                  <span key={f} className="chip">
                    {label(FEATURE_LABELS, f)}
                  </span>
                ))}
              </div>
            ) : null}

            {boat.region_restrictions ? (
              <p className="mt-5 rounded-xl border border-line bg-surface-muted px-4 py-3 text-sm text-muted">
                Revierbeschränkung: {boat.region_restrictions}
              </p>
            ) : null}

            {boat.model_info?.version_name ? (
              /* Die Quellenlage gehört auf die Seite, aber nicht in den Vordergrund:
                 wer sie sucht, klappt sie auf; wer das Boot ansieht, wird nicht von
                 einer Textwand ausgebremst. */
              <details className="group mt-6 rounded-xl border border-line bg-surface-muted/60 px-4 py-3 text-xs leading-relaxed text-muted">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 font-medium text-foreground marker:content-none">
                  Woher diese Werksdaten stammen
                  <span
                    aria-hidden
                    className="text-muted transition-transform group-open:rotate-180"
                  >
                    ⌄
                  </span>
                </summary>
                <div className="mt-3 space-y-1.5">
                <p>
                  Werksdaten aus dem Katalog: {boat.model_info.manufacturer}{" "}
                  {boat.model_info.model_name}, {boat.model_info.version_name}, Bauzeit{" "}
                  {boat.model_info.build_years}
                  {boat.model_info.designer ? ` · Riss ${boat.model_info.designer}` : ""}
                </p>
                <p>
                  Quelle: {boat.model_info.source || "nicht angegeben"} · Stand{" "}
                  {boat.model_info.revision}
                  {boat.model_info.water_tank_l
                    ? ` · Wasser ${boat.model_info.water_tank_l} l`
                    : ""}
                  {boat.model_info.fuel_tank_l ? ` · Diesel ${boat.model_info.fuel_tank_l} l` : ""}
                </p>
                {boat.model_info.caveat ? (
                  <p className="text-warn">Offen laut Quellenlage: {boat.model_info.caveat}</p>
                ) : null}
                {Object.keys(boat.spec_overrides ?? {}).length ? (
                  <p className="text-warn">
                    Vom Katalog abweichend und vom Vercharterer angegeben:{" "}
                    {Object.keys(boat.spec_overrides).join(", ")}
                  </p>
                ) : null}
                {boat.unknown_specs?.length ? (
                  <p>Nicht belegt: {boat.unknown_specs.join(", ")}</p>
                ) : null}
                </div>
              </details>
            ) : null}
          </section>

          <Reviews summary={reviewData.summary} reviews={reviewData.reviews} />

          <section className="card p-6 sm:p-7">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-xl">Preise der nächsten Wochen</h2>
              <p className="text-sm text-muted">
                Törnlänge {calendar?.nights ?? boat.min_days} Nächte
                {cheapest ? ` · ab ${money(cheapest)}/Nacht` : ""}
              </p>
            </div>
            {calendar ? (
              <div className="mt-5 grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-7">
                {calendar.days.map((day) => {
                  const active = day.date === startDate;
                  const href = `/boats/${boat.slug}?start_date=${day.date}&end_date=${addDays(day.date, calendar!.nights)}&persons=${persons}`;
                  const content = (
                    <>
                      <span className="block text-[0.7rem] uppercase tracking-wider text-faint">
                        {dateLabel(day.date, { day: "2-digit", month: "2-digit" })}
                      </span>
                      <span className="tnum mt-0.5 block text-sm font-semibold">
                        {day.available && day.per_day_cents ? money(day.per_day_cents) : "–"}
                      </span>
                    </>
                  );
                  if (!day.available) {
                    return (
                      <div
                        key={day.date}
                        title={day.reason}
                        className="rounded-xl border border-dashed border-line bg-surface-muted px-2 py-2.5 text-center opacity-70"
                      >
                        {content}
                      </div>
                    );
                  }
                  return (
                    <Link
                      key={day.date}
                      href={href}
                      className={`rounded-xl border px-2 py-2.5 text-center transition ${
                        active
                          ? "border-accent bg-accent-soft text-accent shadow-sm"
                          : "border-line hover:-translate-y-0.5 hover:border-line-strong hover:shadow-sm"
                      }`}
                    >
                      {content}
                    </Link>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">Kalender derzeit nicht verfügbar.</p>
            )}
          </section>
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <section className="card p-6">
            <h2 className="text-lg">Dein Törn</h2>
            <dl className="mt-4 text-sm">
              <Spec term="Übernahme" value={`${dateLabel(startDate)} · ${pickupName}`} />
              <Spec term="Rückgabe" value={`${dateLabel(endDate)} · ${dropoffName}`} />
              <Spec term="Dauer" value={`${nights} Nächte`} />
              <Spec term="Personen" value={persons} />
            </dl>

            <div className="mt-5 border-t border-line pt-5">
              {quote ? (
                <PriceExplainer breakdown={quote.breakdown} />
              ) : (
                <p className="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
                  {quoteError ?? "Kein Angebot für diesen Zeitraum."}
                </p>
              )}
            </div>
          </section>

          <section className="card p-6">
            <h2 className="text-lg">Jetzt buchen</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted">
              Preis gilt für diesen Zeitraum und wird beim Buchen erneut bestätigt.
            </p>
            <div className="mt-5">
              <BookingForm
                boatId={boat.id}
                startDate={startDate}
                endDate={endDate}
                persons={persons}
                pickupBaseId={pickupBaseId}
                dropoffBaseId={dropoffBaseId}
                quote={quote}
                quoteError={quoteError}
              />
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
