import Link from "next/link";
import { notFound } from "next/navigation";

import CheckBoard from "@/components/ops/CheckBoard";
import {
  getChartererBookingOps,
  getChartererPayments,
  getMyBookings,
  getPartners,
} from "@/lib/api";
import { dateLabel, label as labelOf, money, nightsBetween, STATUS_LABELS } from "@/lib/format";
import { requireRole } from "@/lib/guard";

export const dynamic = "force-dynamic";

export default async function CheckPage(props: PageProps<"/charterer/bookings/[id]">) {
  const { id } = await props.params;
  const { token } = await requireRole("charterer", `/charterer/bookings/${id}`);

  const bookings = await getMyBookings(token);
  const booking = bookings.find((b) => b.id === id);
  if (!booking) notFound();

  const [ops, payments, partners] = await Promise.all([
    getChartererBookingOps(token, booking.id),
    getChartererPayments(token, booking.id),
    getPartners(token, booking.boat?.base.id),
  ]);

  const nights = nightsBetween(booking.start_date, booking.end_date);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Link href="/charterer" className="text-sm text-accent hover:underline">
        ← Zurück zur Flotte
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-sm text-muted">{booking.reference}</p>
          <h1 className="text-3xl">
            {booking.boat?.name ?? "Charter"} · {booking.customer_name}
          </h1>
          <p className="mt-1 text-muted">
            {dateLabel(booking.start_date)} – {dateLabel(booking.end_date)} · {nights} Nächte ·{" "}
            {booking.persons} Personen · {money(booking.total_cents)}
          </p>
        </div>
        <span className="rounded-full bg-accent-soft px-3 py-1 text-sm font-semibold text-accent">
          {labelOf(STATUS_LABELS, booking.status)}
        </span>
      </div>

      <div className="mt-6">
        <CheckBoard booking={booking} ops={ops} partners={partners} payments={payments} />
      </div>
    </div>
  );
}
