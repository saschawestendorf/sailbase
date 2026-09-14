import BookingLookup from "@/components/BookingLookup";

export const metadata = { title: "Meine Buchung – Sailbase" };

export default function BookingIndexPage() {
  return (
    <div className="mx-auto w-full max-w-md px-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">Meine Buchung</h1>
      <p className="mt-2 text-sm text-muted">
        Buchungsnummer und E-Mail eingeben, um Vertrag, Zahlungen, Crewliste und Übergabetermin zu
        sehen.
      </p>
      <div className="mt-6">
        <BookingLookup />
      </div>
    </div>
  );
}
