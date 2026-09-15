"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import PhotoUploader from "@/components/PhotoUploader";
import SpecTable from "@/components/listing/SpecTable";
import {
  fetchJson,
  useModelDetail,
  useModelSearch,
  useResolvedSpec,
} from "@/components/listing/useCatalog";
import type { Base, BoatDetail, CatalogModel, ModelVersion } from "@/lib/api";
import { CHARACTER_LABELS, FEATURE_LABELS, label as labelOf, money } from "@/lib/format";

const VARIANT_KIND_LABELS: Record<string, string> = {
  layout: "Innenausbau",
  keel: "Kiel",
  rig: "Rigg und Besegelung",
  engine: "Motorisierung",
};

const EXTRA_FEATURES = [
  "bowthruster",
  "autopilot",
  "plotter",
  "radar",
  "sprayhood",
  "bimini",
  "hardtop",
  "heating",
  "generator",
  "watermaker",
  "code0",
  "electric_winch",
  "outdoor_galley",
];

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

const STEPS = ["Modell", "Konfiguration", "Dieses Boot", "Regeln", "Preisrahmen"];

type Props = { bases: Base[]; existing?: BoatDetail };

export default function ListingWizard({ bases, existing }: Props) {
  const router = useRouter();
  const [step, setStep] = useState(existing ? 2 : 0);

  // Step 1: model
  const [query, setQuery] = useState("");
  const { models, loading, error: searchError } = useModelSearch(query);
  const [modelId, setModelId] = useState<string | null>(null);
  const { detail } = useModelDetail(modelId);

  // Step 2: configuration
  const [versionId, setVersionId] = useState<string | null>(existing?.model_version_id ?? null);
  const [yearBuilt, setYearBuilt] = useState<number | null>(existing?.year_built ?? null);
  const [variantIds, setVariantIds] = useState<string[]>(existing?.variant_ids ?? []);
  const [overrides, setOverrides] = useState<Record<string, number | null>>(
    existing?.spec_overrides ?? {},
  );
  const { spec, error: specError } = useResolvedSpec({
    versionId,
    variantIds,
    yearBuilt,
    overrides,
  });

  const version: ModelVersion | null = useMemo(() => {
    for (const v of detail?.versions ?? []) if (v.id === versionId) return v;
    return null;
  }, [detail, versionId]);

  // Step 3: this particular boat
  const [name, setName] = useState(existing?.name ?? "");
  const [baseId, setBaseId] = useState(existing?.base.id ?? bases[0]?.id ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [character, setCharacter] = useState<string[]>(existing?.character ?? []);
  const [extraFeatures, setExtraFeatures] = useState<string[]>(
    existing ? EXTRA_FEATURES.filter((f) => (existing.features ?? []).includes(f)) : [],
  );
  const [images, setImages] = useState<string[]>(existing?.images ?? []);
  const [yearRefit, setYearRefit] = useState<number | null>(existing?.year_refit ?? null);
  const [requiredLicense, setRequiredLicense] = useState(existing?.required_license ?? 2);
  const [requiredExperience, setRequiredExperience] = useState(
    existing?.required_experience_nm ?? 0,
  );

  // Step 4: charter rules
  const [minDays, setMinDays] = useState(existing?.min_days ?? 3);
  const [maxDays, setMaxDays] = useState(existing?.max_days ?? 21);
  const [minLead, setMinLead] = useState(existing?.min_lead_days ?? 2);
  const [turnaround, setTurnaround] = useState(existing?.turnaround_days ?? 0);
  const [changeover, setChangeover] = useState<number[]>(existing?.changeover_weekdays ?? []);
  const [oneWay, setOneWay] = useState(existing?.one_way_enabled ?? false);
  const [oneWayFee, setOneWayFee] = useState((existing?.one_way_fee_cents ?? 0) / 100);
  const [deposit, setDeposit] = useState((existing?.deposit_cents ?? 200000) / 100);
  const [cleaning, setCleaning] = useState((existing?.cleaning_fee_cents ?? 15000) / 100);
  const [restrictions, setRestrictions] = useState(existing?.region_restrictions ?? "");

  // Step 5: price frame
  const [reference, setReference] = useState((existing?.pricing?.reference_price_cents ?? 0) / 100);
  const [floor, setFloor] = useState((existing?.pricing?.floor_price_cents ?? 0) / 100);
  const [ceiling, setCeiling] = useState((existing?.pricing?.ceiling_price_cents ?? 0) / 100);
  const [strategy, setStrategy] = useState(existing?.pricing?.strategy ?? "balanced");

  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function chooseModel(model: CatalogModel) {
    setModelId(model.id);
    setVersionId(null);
    setVariantIds([]);
    setStep(1);
  }

  function chooseVersion(v: ModelVersion) {
    setVersionId(v.id);
    setYearBuilt(yearBuilt ?? v.year_to ?? v.year_from ?? null);
    setVariantIds(v.variants.filter((x) => x.is_default).map((x) => x.id));
    if (!name) setName("");
  }

  function pickVariant(kind: string, id: string) {
    if (!version) return;
    const others = variantIds.filter((vid) => {
      const found = version.variants.find((v) => v.id === vid);
      return found ? found.kind !== kind : false;
    });
    setVariantIds(id ? [...others, id] : others);
  }

  function toggle(list: string[], value: string, set: (v: string[]) => void) {
    set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  const canContinue = [
    Boolean(modelId),
    Boolean(versionId && spec && !specError),
    Boolean(name.trim() && baseId),
    maxDays >= minDays,
    reference > 0 && floor > 0 && ceiling >= floor && reference >= floor && reference <= ceiling,
  ];

  async function submit() {
    setBusy(true);
    setSubmitError(null);
    try {
      const payload = {
        version_id: versionId,
        variant_ids: variantIds,
        year_built: yearBuilt,
        spec_overrides: Object.fromEntries(
          Object.entries(overrides).filter(([, v]) => v !== null && v !== undefined),
        ),
        name: name.trim(),
        base_id: baseId,
        year_refit: yearRefit,
        description,
        extra_features: extraFeatures,
        character,
        images,
        required_license: requiredLicense,
        required_experience_nm: requiredExperience,
        min_days: minDays,
        max_days: maxDays,
        min_lead_days: minLead,
        turnaround_days: turnaround,
        changeover_weekdays: changeover,
        one_way_enabled: oneWay,
        one_way_fee_cents: Math.round(oneWayFee * 100),
        deposit_cents: Math.round(deposit * 100),
        cleaning_fee_cents: Math.round(cleaning * 100),
        region_restrictions: restrictions,
        is_active: true,
      };
      const boat = existing
        ? await fetchJson<BoatDetail>(`/api/charterer/boats/${existing.id}/from-catalog`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          })
        : await fetchJson<BoatDetail>("/api/charterer/boats/from-catalog", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });

      await fetchJson(`/api/charterer/boats/${boat.id}/pricing`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "corridor",
          reference_price_cents: Math.round(reference * 100),
          floor_price_cents: Math.round(floor * 100),
          ceiling_price_cents: Math.round(ceiling * 100),
          strategy,
        }),
      });
      router.push(`/charterer/boats/${boat.id}/pricing?listed=1`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <ol className="flex flex-wrap gap-2 text-sm">
        {STEPS.map((title, index) => (
          <li key={title}>
            <button
              type="button"
              onClick={() => index <= step && setStep(index)}
              disabled={index > step}
              className={`rounded-full px-3 py-1 ${
                index === step
                  ? "bg-brand font-medium text-white dark:text-[#071722]"
                  : index < step
                    ? "bg-accent-soft text-accent"
                    : "bg-surface-muted text-muted"
              }`}
            >
              {index + 1}. {title}
            </button>
          </li>
        ))}
      </ol>

      {step === 0 ? (
        <section className="card p-5">
          <h2 className="text-lg">Welches Modell ist es?</h2>
          <p className="mt-1 text-sm text-muted">
            Wähle das Modell aus dem Katalog. Maße, Tankgrößen und Werksvarianten kommen von dort,
            du musst sie nicht abtippen.
          </p>
          <input
            className="field mt-3"
            placeholder="Hersteller oder Modell suchen, z. B. Bavaria oder 418"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          {searchError ? (
            <p className="mt-3 rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">{searchError}</p>
          ) : null}
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {models.map((model) => (
              <li key={model.id}>
                <button
                  type="button"
                  onClick={() => chooseModel(model)}
                  className="w-full rounded-lg border border-line px-3 py-2 text-left hover:bg-surface-muted"
                >
                  <span className="block font-medium">
                    {model.manufacturer.name} {model.name}
                  </span>
                  {model.designer ? (
                    <span className="block text-xs text-muted">Riss: {model.designer}</span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
          {!loading && models.length === 0 ? (
            <p className="mt-3 text-sm text-muted">
              Kein Treffer. Wenn dein Modell fehlt, melde es der Katalogpflege; bis dahin wähle das
              nächstliegende und trage Abweichungen im nächsten Schritt ein.
            </p>
          ) : null}
        </section>
      ) : null}

      {step === 1 && detail ? (
        <section className="card space-y-4 p-5">
          <div>
            <h2 className="text-lg">
              {detail.manufacturer.name} {detail.name}
            </h2>
            <p className="mt-1 text-sm text-muted">
              Baureihe und Baujahr bestimmen die Werksdaten. Unplausible Kombinationen weist der
              Katalog zurück.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <span className="label">Baureihe</span>
              <div className="space-y-2">
                {detail.versions.map((v) => (
                  <button
                    type="button"
                    key={v.id}
                    onClick={() => chooseVersion(v)}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${
                      versionId === v.id
                        ? "border-transparent bg-accent-soft text-accent"
                        : "border-line hover:bg-surface-muted"
                    }`}
                  >
                    <span className="block font-medium">{v.name}</span>
                    <span className="block text-xs">
                      {v.year_from
                        ? `Bauzeit ${v.year_from}–${v.year_to ?? "heute"}`
                        : "Bauzeit nicht belegt"}{" "}
                      · {v.length_m.toFixed(2)} m
                    </span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="label" htmlFor="year">
                Baujahr dieses Boots
              </label>
              <input
                id="year"
                type="number"
                className="field"
                min={1900}
                max={2100}
                value={yearBuilt ?? ""}
                onChange={(e) => setYearBuilt(e.target.value ? Number(e.target.value) : null)}
              />
              {version ? (
                <p className="mt-1 text-xs text-muted">
                  Quelle der Werksdaten: {version.source || "nicht angegeben"}
                  {version.verified_on ? ` · geprüft am ${version.verified_on}` : ""} · Stand{" "}
                  {version.revision}
                </p>
              ) : null}
            </div>
          </div>

          {version ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {["layout", "keel", "rig", "engine"].map((kind) => {
                const options = version.variants.filter((v) => v.kind === kind);
                if (!options.length) return null;
                const selected = options.find((o) => variantIds.includes(o.id));
                return (
                  <div key={kind}>
                    <label className="label" htmlFor={`variant-${kind}`}>
                      {VARIANT_KIND_LABELS[kind]}
                    </label>
                    <select
                      id={`variant-${kind}`}
                      className="field"
                      value={selected?.id ?? ""}
                      onChange={(e) => pickVariant(kind, e.target.value)}
                    >
                      <option value="">keine Angabe</option>
                      {options.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.name}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          ) : null}

          {specError ? (
            <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
              {specError}
            </p>
          ) : null}

          {spec ? (
            <div>
              <h3 className="text-sm">Das ergibt diese Konfiguration</h3>
              <div className="mt-2">
                <SpecTable
                  spec={spec}
                  overrides={overrides}
                  onOverride={(field, value) =>
                    setOverrides((prev) => ({ ...prev, [field]: value }))
                  }
                />
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {step === 2 ? (
        <section className="card space-y-4 p-5">
          <h2 className="text-lg">Was nur für dieses Boot gilt</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="boat-name">
                Bootsname
              </label>
              <input
                id="boat-name"
                className="field"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="base">
                Heimathafen
              </label>
              <select
                id="base"
                className="field"
                value={baseId}
                onChange={(e) => setBaseId(e.target.value)}
              >
                {bases.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}, {b.city}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="refit">
                Letztes Refit (optional)
              </label>
              <input
                id="refit"
                type="number"
                className="field"
                min={1900}
                max={2100}
                value={yearRefit ?? ""}
                onChange={(e) => setYearRefit(e.target.value ? Number(e.target.value) : null)}
              />
            </div>
            <div>
              <label className="label" htmlFor="license">
                Nötiger Führerschein
              </label>
              <select
                id="license"
                className="field"
                value={requiredLicense}
                onChange={(e) => setRequiredLicense(Number(e.target.value))}
              >
                {[
                  [0, "keiner"],
                  [1, "SBF Binnen"],
                  [2, "SBF See"],
                  [3, "SKS"],
                  [4, "SSS"],
                  [5, "SHS"],
                ].map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="experience">
                Nötige Erfahrung in Seemeilen
              </label>
              <input
                id="experience"
                type="number"
                min={0}
                className="field"
                value={requiredExperience}
                onChange={(e) => setRequiredExperience(Number(e.target.value || 0))}
              />
            </div>
          </div>

          <div>
            <label className="label" htmlFor="description">
              Beschreibung
            </label>
            <textarea
              id="description"
              rows={4}
              className="field"
              placeholder="Wie segelt sie, für wen ist sie gedacht, was ist besonders?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div>
            <span className="label">Charakter</span>
            <div className="flex flex-wrap gap-2">
              {Object.keys(CHARACTER_LABELS).map((value) => (
                <button
                  type="button"
                  key={value}
                  onClick={() => toggle(character, value, setCharacter)}
                  className={`rounded-full border px-3 py-1 text-sm ${
                    character.includes(value)
                      ? "border-transparent bg-accent-soft font-medium text-accent"
                      : "border-line text-muted hover:bg-surface-muted"
                  }`}
                >
                  {labelOf(CHARACTER_LABELS, value)}
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-muted">
              Leer lassen übernimmt den typischen Charakter des Modells.
            </p>
          </div>

          <div>
            <span className="label">Zusätzliche Ausstattung über den Werksstand hinaus</span>
            <div className="flex flex-wrap gap-2">
              {EXTRA_FEATURES.filter((f) => !(spec?.features ?? []).includes(f)).map((value) => (
                <button
                  type="button"
                  key={value}
                  onClick={() => toggle(extraFeatures, value, setExtraFeatures)}
                  className={`rounded-full border px-3 py-1 text-sm ${
                    extraFeatures.includes(value)
                      ? "border-transparent bg-accent-soft font-medium text-accent"
                      : "border-line text-muted hover:bg-surface-muted"
                  }`}
                >
                  {labelOf(FEATURE_LABELS, value)}
                </button>
              ))}
            </div>
            {spec?.features.length ? (
              <p className="mt-2 text-xs text-muted">
                Bereits ab Werk: {spec.features.map((f) => labelOf(FEATURE_LABELS, f)).join(", ")}
              </p>
            ) : null}
          </div>

          <div>
            <span className="label">Fotos dieses Boots</span>
            <PhotoUploader urls={images} onChange={setImages} />
            <p className="mt-1 text-xs text-muted">
              Modellfotos des Herstellers kommen automatisch dazu und bleiben als solche
              gekennzeichnet. Sie ersetzen keine aktuellen Aufnahmen.
            </p>
          </div>
        </section>
      ) : null}

      {step === 3 ? (
        <section className="card space-y-4 p-5">
          <h2 className="text-lg">Wann und wie darf gechartert werden?</h2>
          <p className="text-sm text-muted">
            Diese Regeln begrenzen, was der Algorithmus anbieten darf. Je enger sie sind, desto
            weniger Lücken kann er füllen.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="min-days">
                Mindestdauer in Nächten
              </label>
              <input
                id="min-days"
                type="number"
                min={1}
                max={30}
                className="field"
                value={minDays}
                onChange={(e) => setMinDays(Number(e.target.value || 1))}
              />
            </div>
            <div>
              <label className="label" htmlFor="max-days">
                Höchstdauer
              </label>
              <input
                id="max-days"
                type="number"
                min={1}
                max={90}
                className="field"
                value={maxDays}
                onChange={(e) => setMaxDays(Number(e.target.value || 1))}
              />
            </div>
            <div>
              <label className="label" htmlFor="lead">
                Mindestvorlauf in Tagen
              </label>
              <input
                id="lead"
                type="number"
                min={0}
                max={60}
                className="field"
                value={minLead}
                onChange={(e) => setMinLead(Number(e.target.value || 0))}
              />
            </div>
            <div>
              <label className="label" htmlFor="turnaround">
                Turnaround in Tagen
              </label>
              <input
                id="turnaround"
                type="number"
                min={0}
                max={7}
                className="field"
                value={turnaround}
                onChange={(e) => setTurnaround(Number(e.target.value || 0))}
              />
            </div>
            <div>
              <label className="label" htmlFor="deposit">
                Kaution in Euro
              </label>
              <input
                id="deposit"
                type="number"
                min={0}
                step={50}
                className="field"
                value={deposit}
                onChange={(e) => setDeposit(Number(e.target.value || 0))}
              />
            </div>
            <div>
              <label className="label" htmlFor="cleaning">
                Endreinigung in Euro
              </label>
              <input
                id="cleaning"
                type="number"
                min={0}
                step={10}
                className="field"
                value={cleaning}
                onChange={(e) => setCleaning(Number(e.target.value || 0))}
              />
            </div>
          </div>

          <div>
            <span className="label">Erlaubte Wechseltage</span>
            <div className="flex flex-wrap gap-2">
              {WEEKDAYS.map((day, index) => (
                <button
                  type="button"
                  key={day}
                  onClick={() =>
                    setChangeover(
                      changeover.includes(index)
                        ? changeover.filter((d) => d !== index)
                        : [...changeover, index],
                    )
                  }
                  className={`rounded-full border px-3 py-1 text-sm ${
                    changeover.includes(index)
                      ? "border-transparent bg-accent-soft font-medium text-accent"
                      : "border-line text-muted hover:bg-surface-muted"
                  }`}
                >
                  {day}
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-muted">
              Keiner ausgewählt heißt: jeder Tag ist möglich. Genau das hebt die Samstagslogik auf.
            </p>
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={oneWay}
                onChange={(e) => setOneWay(e.target.checked)}
                className="h-4 w-4 accent-[var(--accent)]"
              />
              One-Way erlauben: Crew gibt das Boot in einem anderen Hafen ab
            </label>
            {oneWay ? (
              <div className="max-w-xs">
                <label className="label" htmlFor="one-way-fee">
                  One-Way-Gebühr in Euro
                </label>
                <input
                  id="one-way-fee"
                  type="number"
                  min={0}
                  step={10}
                  className="field"
                  value={oneWayFee}
                  onChange={(e) => setOneWayFee(Number(e.target.value || 0))}
                />
                <p className="mt-1 text-xs text-muted">
                  Überführung und Rückführungsrisiko rechnet die Plattform zusätzlich aus.
                </p>
              </div>
            ) : null}
          </div>

          <div>
            <label className="label" htmlFor="restrictions">
              Revierbeschränkungen
            </label>
            <input
              id="restrictions"
              className="field"
              placeholder="z. B. nur deutsche und dänische Ostsee"
              value={restrictions}
              onChange={(e) => setRestrictions(e.target.value)}
            />
          </div>
        </section>
      ) : null}

      {step === 4 ? (
        <section className="card space-y-4 p-5">
          <h2 className="text-lg">Dein Preisrahmen</h2>
          <p className="text-sm text-muted">
            Du gibst die Grenzen vor, der Algorithmus arbeitet strikt darin. Unter die
            Untergrenze geht er nie, auch nicht bei leerem Kalender.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="floor">
                Untergrenze je Nacht
              </label>
              <input
                id="floor"
                type="number"
                min={0}
                step={10}
                className="field"
                value={floor}
                onChange={(e) => setFloor(Number(e.target.value || 0))}
              />
            </div>
            <div>
              <label className="label" htmlFor="reference">
                Referenzpreis Hochsaison
              </label>
              <input
                id="reference"
                type="number"
                min={0}
                step={10}
                className="field"
                value={reference}
                onChange={(e) => setReference(Number(e.target.value || 0))}
              />
            </div>
            <div>
              <label className="label" htmlFor="ceiling">
                Obergrenze je Nacht
              </label>
              <input
                id="ceiling"
                type="number"
                min={0}
                step={10}
                className="field"
                value={ceiling}
                onChange={(e) => setCeiling(Number(e.target.value || 0))}
              />
            </div>
          </div>
          {!canContinue[4] ? (
            <p className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
              Der Referenzpreis muss zwischen Unter- und Obergrenze liegen.
            </p>
          ) : (
            <p className="text-sm text-muted">
              Eine Woche in der Hochsaison läge damit bei rund {money(reference * 700)}.
            </p>
          )}
          <div>
            <span className="label">Wie offensiv soll verkauft werden?</span>
            <div className="grid gap-2 sm:grid-cols-3">
              {[
                ["conservative", "Zurückhaltend", "Schützt den Kalender, lehnt zerstückelnde Buchungen eher ab."],
                ["balanced", "Ausgewogen", "Standard: Lücken füllen, aber attraktive Wochen nicht zerschneiden."],
                ["aggressive", "Offensiv", "Verkauft jeden Tag, der die Untergrenze trägt."],
              ].map(([value, title, text]) => (
                <button
                  type="button"
                  key={value}
                  onClick={() => setStrategy(value)}
                  className={`rounded-lg border p-3 text-left text-sm ${
                    strategy === value
                      ? "border-transparent bg-accent-soft text-accent"
                      : "border-line hover:bg-surface-muted"
                  }`}
                >
                  <span className="block font-medium">{title}</span>
                  <span className="mt-1 block text-xs">{text}</span>
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted">
              Nach dem Speichern siehst du, was die Einstellung über das Jahr bedeutet, und kannst
              sie dort weiter justieren.
            </p>
          </div>
          {submitError ? (
            <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
              {submitError}
            </p>
          ) : null}
        </section>
      ) : null}

      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          className="btn-ghost"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
        >
          Zurück
        </button>
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            className="btn-primary"
            onClick={() => setStep((s) => s + 1)}
            disabled={!canContinue[step]}
          >
            Weiter
          </button>
        ) : (
          <button type="button" className="btn-primary" onClick={submit} disabled={busy || !canContinue[4]}>
            {busy ? "Wird gespeichert …" : existing ? "Änderungen speichern" : "Boot einstellen"}
          </button>
        )}
      </div>
    </div>
  );
}
