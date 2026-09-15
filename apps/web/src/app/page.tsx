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
      {/* Hero: dunkle See als Fläche, das Suchpanel bricht über die Kante nach
          unten aus und verbindet damit Bild und Inhalt. */}
      <section className="relative isolate overflow-hidden bg-sea">
        {/* Dünung als Abschluss: gibt der Kante eine Form, ohne den Text zu stören. */}
        <svg
          aria-hidden
          viewBox="0 0 1440 120"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-16 w-full sm:h-24"
        >
          <path d="M0 62 q 180 -34 360 -4 t 360 -6 t 360 8 t 360 -12 V120 H0Z" fill="#04161f" fillOpacity="0.35" />
          <path d="M0 86 q 200 -28 400 -2 t 400 -8 t 640 6 V120 H0Z" fill="#04161f" fillOpacity="0.55" />
        </svg>
        <div className="relative mx-auto w-full max-w-6xl px-4 pb-36 pt-16 sm:pb-40 sm:pt-24">
          <p className="eyebrow text-[#7ae0d7]">Yachtcharter Ostsee</p>
          <h1 className="display mt-5 max-w-3xl text-balance-tight text-[2.5rem] text-[#f6f1e7] sm:text-[3.75rem]">
            Jedes Boot zum besten Preis ausgebucht. Jede Crew auf dem Boot, das passt.
          </h1>
          <p className="mt-6 max-w-2xl text-[1.0625rem] leading-relaxed text-[#b9ccd4] sm:text-lg">
            Sailbase bepreist Segelyachten dynamisch und bricht die starre Wochenlogik auf. Du sagst,
            wann du Zeit hast und was dir wichtig ist – wir zeigen, was wirklich buchbar ist.
          </p>

          <dl className="mt-10 flex flex-wrap gap-x-10 gap-y-4">
            {[
              { k: "50", v: "Modelle im Katalog" },
              { k: "15", v: "Werften" },
              { k: "1–21", v: "Nächte frei wählbar" },
            ].map((item) => (
              <div key={item.v}>
                <dt className="display text-2xl text-[#f6f1e7]">{item.k}</dt>
                <dd className="mt-0.5 text-xs uppercase tracking-[0.12em] text-[#74909c]">
                  {item.v}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="relative z-10 mx-auto -mt-20 w-full max-w-5xl px-4 sm:-mt-24">
        {offline ? (
          <p role="alert" className="card mb-4 p-5 text-sm text-warn">
            Der Buchungsdienst ist gerade nicht erreichbar. Bitte später erneut versuchen.
          </p>
        ) : null}
        <div className="panel-glass p-5 sm:p-6">
          <SearchForm regions={regions} bases={bases} boatClasses={boatClasses} compact />
        </div>
      </section>

      <section className="mx-auto w-full max-w-6xl px-4 py-20">
        <div className="grid gap-8 sm:grid-cols-3 sm:gap-10">
          {PILLARS.map((p, index) => (
            <div key={p.title}>
              <p className="display text-3xl text-brass">{String(index + 1).padStart(2, "0")}</p>
              <hr className="rule mt-4" />
              <h2 className="mt-4 text-lg leading-snug">{p.title}</h2>
              <p className="mt-2.5 text-sm leading-relaxed text-muted">{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      {regions.length ? (
        <section className="mx-auto w-full max-w-6xl px-4 pb-20">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="eyebrow">Reviere</p>
              <h2 className="mt-3 text-2xl sm:text-3xl">Von der Förde bis zum Bodden</h2>
            </div>
            <Link href="/search" className="btn-ghost">
              Alle Boote ansehen
            </Link>
          </div>

          <div className="mt-8 grid gap-5 sm:grid-cols-3">
            {regions.map((r) => (
              <Link
                key={r.id}
                href={`/search?region=${r.slug}`}
                className="card card-link group flex flex-col overflow-hidden"
              >
                <SailPlaceholder name={r.name} className="h-32 w-full" />
                <div className="flex flex-1 flex-col p-5">
                  <h3 className="text-base">{r.name}</h3>
                  <p className="mt-1.5 flex-1 text-sm leading-relaxed text-muted">
                    {r.description}
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent">
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
