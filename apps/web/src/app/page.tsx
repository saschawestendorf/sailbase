import Link from "next/link";

import SearchForm from "@/components/SearchForm";
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
      <section className="border-b border-line bg-gradient-to-b from-surface to-background">
        <div className="mx-auto w-full max-w-6xl px-4 py-12 sm:py-16">
          <p className="text-sm font-semibold uppercase tracking-widest text-accent">
            Yachtcharter Ostsee
          </p>
          <h1 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight tracking-tight sm:text-5xl">
            Jedes Boot zum besten Preis ausgebucht. Jede Crew auf dem Boot, das passt.
          </h1>
          <p className="mt-4 max-w-2xl text-base text-muted sm:text-lg">
            Sailbase bepreist Segelyachten dynamisch und bricht die starre Wochenlogik auf. Du sagst,
            wann du Zeit hast und was dir wichtig ist – wir zeigen, was wirklich buchbar ist.
          </p>

          <div className="mt-8">
            {offline ? (
              <p className="card p-5 text-sm text-warn">
                Der Buchungsdienst ist gerade nicht erreichbar. Bitte später erneut versuchen.
              </p>
            ) : null}
            <SearchForm regions={regions} bases={bases} boatClasses={boatClasses} compact />
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-6xl px-4 py-12">
        <div className="grid gap-5 sm:grid-cols-3">
          {PILLARS.map((p) => (
            <div key={p.title} className="card p-5">
              <h2 className="text-base font-semibold">{p.title}</h2>
              <p className="mt-2 text-sm text-muted">{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      {regions.length ? (
        <section className="mx-auto w-full max-w-6xl px-4 pb-16">
          <h2 className="text-xl font-semibold">Reviere</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            {regions.map((r) => (
              <Link
                key={r.id}
                href={`/search?region=${r.slug}`}
                className="card p-5 transition hover:shadow-lg"
              >
                <h3 className="font-semibold">{r.name}</h3>
                <p className="mt-1 text-sm text-muted">{r.description}</p>
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
