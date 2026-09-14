import type { RatingSummary, Review } from "@/lib/api";
import { dateLabel } from "@/lib/format";

const DETAIL_LABELS: Record<string, string> = {
  care: "Pflege",
  cleanliness: "Sauberkeit",
  accuracy: "Beschreibungstreue",
  equipment: "Funktion der Ausstattung",
  organisation: "Organisation",
  handover: "Übergabe",
};

function Stars({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted">–</span>;
  const rounded = Math.round(value);
  return (
    <span aria-label={`${value} von 5`} className="text-accent">
      {"★".repeat(rounded)}
      <span className="text-muted">{"★".repeat(5 - rounded)}</span>
    </span>
  );
}

function Bar({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-44 shrink-0 text-muted">{label}</span>
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-muted">
        <span
          className="block h-full rounded-full bg-accent"
          style={{ width: `${((value ?? 0) / 5) * 100}%` }}
        />
      </span>
      <span className="w-8 text-right font-mono text-xs">{value?.toFixed(1) ?? "–"}</span>
    </div>
  );
}

function monthLabel(month: string): string {
  if (!/^\d{4}-\d{2}$/.test(month)) return "";
  return dateLabel(`${month}-01`, { month: "long", year: "numeric" });
}

export default function Reviews({
  summary,
  reviews,
}: {
  summary: RatingSummary | null;
  reviews: Review[];
}) {
  if (!summary || summary.count === 0) {
    return (
      <section className="card p-5">
        <h2 className="text-lg font-semibold">Bewertungen</h2>
        <p className="mt-2 text-sm text-muted">
          Noch keine Bewertung. Bewerten darf nur, wer diese Yacht nachweislich gechartert hat.
          Wenige Bewertungen heißen also nicht, dass etwas nicht stimmt.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">Bewertungen</h2>
        <p className="text-sm text-muted">{summary.count} verifizierte Charter</p>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        {[
          ["Bootsmodell", summary.model],
          ["Zustand dieses Schiffs", summary.condition],
          ["Service des Vercharterers", summary.service],
        ].map(([label, value]) => (
          <div key={label as string} className="rounded-lg bg-surface-muted p-3">
            <p className="text-xs uppercase tracking-wide text-muted">{label as string}</p>
            <p className="mt-1 text-xl font-semibold">
              {(value as number | null)?.toFixed(1) ?? "–"}
              <span className="ml-2 text-sm font-normal">
                <Stars value={value as number | null} />
              </span>
            </p>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-2">
        {Object.entries(DETAIL_LABELS).map(([key, label]) => (
          <Bar key={key} label={label} value={summary.details[key] ?? null} />
        ))}
      </div>

      <ul className="mt-5 space-y-4">
        {reviews.map((review) => (
          <li key={review.id} className="border-t border-line pt-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium">{review.title || "Bewertung"}</p>
              <p className="text-xs text-muted">
                {review.author_name} · Charter {monthLabel(review.charter_month)}
              </p>
            </div>
            <p className="mt-1 text-sm">
              <Stars value={review.overall} />
            </p>
            {review.body ? <p className="mt-2 text-sm text-muted">{review.body}</p> : null}
            {review.photos?.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {review.photos.map((url) => (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img key={url} src={url} alt="" className="h-20 w-28 rounded-lg object-cover" />
                ))}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
