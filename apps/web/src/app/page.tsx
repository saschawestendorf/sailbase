import Link from "next/link";

import SearchForm from "@/components/SearchForm";
import SailPlaceholder from "@/components/ui/SailPlaceholder";
import {
  ApiError,
  type Base,
  type BoatClass,
  getBases,
  getBoatClasses,
  getRegions,
  type Region,
} from "@/lib/api";

export const dynamic = "force-dynamic";

const PILLARS = [
  {
    title: "Preise wie im Hotel, nicht wie im Prospekt",
    body: "Saison, Wochentag, Nachfrage vergleichbarer Boote, Vorlaufzeit und Törnlänge fließen in jeden Preis ein. Jede Position ist nachvollziehbar aufgeschlüsselt.",
  },
  {
    title: "Zeiträume statt Samstag-bis-Samstag",
    body: "Vier Tage über ein langes Wochenende, zehn Tage im September oder eine kurzfristige Lückenbuchung: Der Algorithmus schlägt vor, was wirtschaftlich sinnvoll ist.",
  },
  {
    title: "Das Boot, das zur Crew passt",
    body: "Stehhöhe, Kojenlänge, Charakter und nötige Qualifikation werden mitgedacht. Nicht nur die Bootsklasse, sondern der tatsächliche Fit.",
  },
];

const FIGURES = [
  { k: "50", v: "Modelle im Katalog" },
  { k: "15", v: "Werften" },
  { k: "1–21", v: "Nächte frei wählbar" },
];

export default async function HomePage() {
  let regions: Region[] = [];
  let bases: Base[] = [];
  let boatClasses: BoatClass[] = [];
  let offline = false;
  try {
    [regions, bases, boatClasses] = await Promise.all([getRegions(), getBases(), getBoatClasses()]);
  } catch (error) {
    offline = error instanceof ApiError;
    if (!offline) throw error;
  }

  return (
    <div>
      {/* Weißer Hero: die Wirkung kommt aus Weißraum und Schriftgröße, nicht aus
          einer Farbfläche. Rechts die gezeichnete See als ruhiger Anker. */}
      <section className="bg-horizon">
        <div className="mx-auto w-full max-w-6xl px-4 pb-24 pt-16 sm:pt-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1.15fr_1fr]">
            <div>
              <p className="eyebrow">Yachtcharter Ostsee</p>
              <h1 className="display mt-6 max-w-2xl text-balance-tight text-[2.5rem] sm:text-[3.5rem]">
                Jedes Boot zum besten Preis ausgebucht. Jede Crew auf dem Boot, das passt.
              </h1>
              <p className="lede mt-6 max-w-xl">
                Sailbase bepreist Segelyachten dynamisch und bricht die starre Wochenlogik auf. Du
                sagst, wann du Zeit hast und was dir wichtig ist – wir zeigen, was wirklich buchbar
                ist.
              </p>

              <dl className="mt-10 flex flex-wrap gap-x-12 gap-y-5">
                {FIGURES.map((item) => (
                  <div key={item.v}>
                    <dt className="display text-[1.75rem] text-brand">{item.k}</dt>
                    <dd className="mt-1 text-xs uppercase tracking-[0.14em] text-faint">
                      {item.v}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            <SailPlaceholder
              name="Sailbase Ostsee"
              className="hidden aspect-[5/4] w-full rounded-[1.5rem] border border-line lg:block"
            />
          </div>
        </div>
      </section>

      <section className="mx-auto -mt-12 w-full max-w-5xl px-4">
        {offline ? (
          <p role="alert" className="card card-raised mb-4 p-5 text-sm text-warn">
            Der Buchungsdienst ist gerade nicht erreichbar. Bitte später erneut versuchen.
          </p>
        ) : null}
        <div className="panel-raised p-5 sm:p-7">
          <SearchForm regions={regions} bases={bases} boatClasses={boatClasses} compact />
        </div>
      </section>

      <section className="mx-auto w-full max-w-6xl px-4 py-24">
        <div className="grid gap-10 sm:grid-cols-3 sm:gap-12">
          {PILLARS.map((p, index) => (
            <div key={p.title}>
              <p className="display text-[1.75rem] text-brass">
                {String(index + 1).padStart(2, "0")}
              </p>
              <hr className="rule-soft mt-4" />
              <h2 className="mt-5 text-lg leading-snug">{p.title}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted">{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      {regions.length ? (
        <section className="mx-auto w-full max-w-6xl px-4 pb-24">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="eyebrow">Reviere</p>
              <h2 className="mt-4 text-2xl sm:text-3xl">Von der Förde bis zum Bodden</h2>
            </div>
            <Link href="/search" className="btn-ghost">
              Alle Boote ansehen
            </Link>
          </div>

          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            {regions.map((r) => (
              <Link
                key={r.id}
                href={`/search?region=${r.slug}`}
                className="card card-link group flex flex-col overflow-hidden"
              >
                <SailPlaceholder name={r.name} className="h-36 w-full border-b border-line" />
                <div className="flex flex-1 flex-col p-6">
                  <h3 className="text-lg">{r.name}</h3>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">{r.description}</p>
                  <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-accent">
                    Boote im Revier
                    <span className="transition-transform duration-200 group-hover:translate-x-1">
                      →
                    </span>
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
