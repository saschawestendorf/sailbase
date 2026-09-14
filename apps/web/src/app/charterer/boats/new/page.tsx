import ListingWizard from "@/components/listing/ListingWizard";
import { getBases } from "@/lib/api";
import { requireRole } from "@/lib/guard";

export const dynamic = "force-dynamic";
export const metadata = { title: "Boot einstellen – Sailbase" };

export default async function NewBoatPage() {
  await requireRole("charterer", "/charterer/boats/new");
  const bases = await getBases();

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Boot einstellen</h1>
      <p className="mt-2 max-w-2xl text-muted">
        Modell aus dem Katalog wählen, Varianten bestätigen, Regeln und Preisrahmen setzen. Den
        Rest übernimmt die Preisoptimierung.
      </p>
      <div className="mt-6">
        <ListingWizard bases={bases} />
      </div>
    </div>
  );
}
