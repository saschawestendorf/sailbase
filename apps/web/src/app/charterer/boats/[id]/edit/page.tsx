import { notFound } from "next/navigation";

import ListingWizard from "@/components/listing/ListingWizard";
import { apiFetch, authed, type BoatDetail, getBases } from "@/lib/api";
import { requireRole } from "@/lib/guard";

export const dynamic = "force-dynamic";

export default async function EditBoatPage(props: PageProps<"/charterer/boats/[id]/edit">) {
  const { id } = await props.params;
  const { token } = await requireRole("charterer", `/charterer/boats/${id}/edit`);
  const [bases, boats] = await Promise.all([
    getBases(),
    apiFetch<BoatDetail[]>("/charterer/boats", authed(token)),
  ]);
  const boat = boats.find((b) => b.id === id);
  if (!boat) notFound();

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <h1 className="text-3xl">{boat.name} bearbeiten</h1>
      <p className="mt-2 text-muted">
        {boat.manufacturer} {boat.model} · {boat.base.name}
      </p>
      <div className="mt-6">
        <ListingWizard bases={bases} existing={boat} />
      </div>
    </div>
  );
}
