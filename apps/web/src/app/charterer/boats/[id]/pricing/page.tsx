import Link from "next/link";
import { notFound } from "next/navigation";

import PricingStudio from "@/components/pricing/PricingStudio";
import { apiFetch, authed, type BoatDetail } from "@/lib/api";
import { requireRole } from "@/lib/guard";

export const dynamic = "force-dynamic";

export default async function PricingPage(props: PageProps<"/charterer/boats/[id]/pricing">) {
  const { id } = await props.params;
  const listed = (await props.searchParams).listed;
  const { token } = await requireRole("charterer", `/charterer/boats/${id}/pricing`);
  const boats = await apiFetch<BoatDetail[]>("/charterer/boats", authed(token));
  const boat = boats.find((b) => b.id === id);
  if (!boat) notFound();

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      {listed ? (
        <p className="mb-4 rounded-xl bg-positive-soft px-4 py-3 text-sm text-positive">
          {boat.name} ist eingestellt. Jetzt festlegen, wie der Algorithmus damit arbeiten soll.
        </p>
      ) : null}

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Preisoptimierung · {boat.name}</h1>
          <p className="mt-1 text-muted">
            {boat.manufacturer} {boat.model} · {boat.base.name} · Mindestdauer {boat.min_days}{" "}
            Nächte
          </p>
        </div>
        <div className="flex gap-2">
          <Link href={`/charterer/boats/${boat.id}/edit`} className="btn-ghost">
            Inserat bearbeiten
          </Link>
          <Link href={`/boats/${boat.slug}`} className="btn-ghost">
            Öffentliche Seite
          </Link>
        </div>
      </div>

      <div className="mt-6">
        <PricingStudio boat={boat} />
      </div>
    </div>
  );
}
