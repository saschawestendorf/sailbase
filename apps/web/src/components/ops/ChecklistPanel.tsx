"use client";

import { useState } from "react";

import { fetchJson } from "@/components/listing/useCatalog";
import PhotoUploader from "@/components/PhotoUploader";
import type { ChecklistItem, Partner, ServiceOrder } from "@/lib/api";
import { dateLabel, money } from "@/lib/format";

const ORDER_LABELS: Record<string, string> = {
  readiness: "Bootsbereitschaft",
  handover: "Übergabe an die Crew",
  return: "Rücknahme",
  cleaning: "Reinigung",
  technical: "Technik",
  laundry: "Wäsche",
};

const ORDER_INTROS: Record<string, string> = {
  readiness: "Vor der Charter: Technik, Sicherheit, Tank, Gas, Wasser, Reinigung und Inventar.",
  handover: "Beim Check-in: Zustand fotografieren, Einweisung geben, Papiere prüfen.",
  return: "Beim Check-out: derselbe Umfang rückwärts. Auffälligkeiten als Problem markieren, daraus entsteht ein Schadenfall.",
};

const STATUS_LABELS: Record<string, string> = {
  open: "offen",
  assigned: "geplant",
  in_progress: "in Arbeit",
  done: "erledigt",
  cancelled: "storniert",
};

export default function ChecklistPanel({
  order,
  partners,
  onChanged,
}: {
  order: ServiceOrder;
  partners: Partner[];
  onChanged: () => void;
}) {
  const [items, setItems] = useState<ChecklistItem[]>(order.checklist ?? []);
  const [notes, setNotes] = useState(order.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(order.status !== "done");

  const done = order.status === "done";
  const complete = items.filter((i) => i.done).length;
  const required = items.filter((i) => i.required);
  const blocking = required.filter((i) => !i.done || (i.photo_required && !i.photos?.length));

  function update(key: string, patch: Partial<ChecklistItem>) {
    setItems((prev) => prev.map((i) => (i.key === key ? { ...i, ...patch } : i)));
  }

  async function persist(thenComplete = false) {
    setBusy(true);
    setError(null);
    try {
      await fetchJson(`/api/charterer/orders/${order.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: items.map((i) => ({
            key: i.key,
            done: i.done,
            issue: i.issue,
            note: i.note,
            photos: i.photos,
          })),
          notes,
        }),
      });
      if (thenComplete) {
        await fetchJson(`/api/charterer/orders/${order.id}/complete`, { method: "POST" });
      }
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function assign(partnerId: string) {
    setBusy(true);
    setError(null);
    try {
      await fetchJson(`/api/charterer/orders/${order.id}/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ partner_id: partnerId || null }),
      });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Zuweisung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
        <div>
          <h3 className="font-semibold">{ORDER_LABELS[order.order_type] ?? order.order_type}</h3>
          <p className="text-sm text-muted">
            {order.scheduled_for
              ? dateLabel(order.scheduled_for, {
                  day: "2-digit",
                  month: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "Termin offen"}{" "}
            · {STATUS_LABELS[order.status] ?? order.status} · {complete} von {items.length} Punkten
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!done ? (
            <select
              className="field w-auto py-1.5 text-sm"
              value={order.partner_id ?? ""}
              onChange={(e) => assign(e.target.value)}
              disabled={busy}
              aria-label="Zuständigkeit"
            >
              <option value="">Ich mache das selbst</option>
              {partners.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.prices[order.order_type] ? ` · ${money(p.prices[order.order_type])}` : ""}
                </option>
              ))}
            </select>
          ) : order.partner ? (
            <span className="chip">{order.partner.name}</span>
          ) : null}
          <button type="button" className="btn-ghost" onClick={() => setOpen((v) => !v)}>
            {open ? "Zuklappen" : "Öffnen"}
          </button>
        </div>
      </header>

      {open ? (
        <div className="space-y-3 p-4">
          {ORDER_INTROS[order.order_type] ? (
            <p className="text-sm text-muted">{ORDER_INTROS[order.order_type]}</p>
          ) : null}

          <ul className="space-y-3">
            {items.map((item) => (
              <li key={item.key} className="border-t border-line pt-3 first:border-0 first:pt-0">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={item.done}
                    disabled={done}
                    onChange={(e) => update(item.key, { done: e.target.checked })}
                    className="mt-1 h-4 w-4 accent-[var(--accent)]"
                    id={`${order.id}-${item.key}`}
                  />
                  <div className="min-w-0 flex-1">
                    <label htmlFor={`${order.id}-${item.key}`} className="text-sm">
                      {item.label}
                      {!item.required ? <span className="ml-1 text-xs text-muted">(optional)</span> : null}
                      {item.photo_required ? (
                        <span className="ml-1 text-xs text-accent">Foto nötig</span>
                      ) : null}
                    </label>

                    {!done ? (
                      <div className="mt-2 space-y-2">
                        <label className="flex items-center gap-2 text-xs text-muted">
                          <input
                            type="checkbox"
                            checked={item.issue}
                            onChange={(e) => update(item.key, { issue: e.target.checked })}
                            className="h-3.5 w-3.5 accent-[var(--warn)]"
                          />
                          Auffälligkeit
                          {order.order_type === "return" ? " (eröffnet einen Schadenfall)" : ""}
                        </label>
                        <input
                          className="field py-1 text-sm"
                          placeholder="Notiz"
                          value={item.note ?? ""}
                          onChange={(e) => update(item.key, { note: e.target.value })}
                        />
                        <PhotoUploader
                          urls={item.photos ?? []}
                          onChange={(urls) => update(item.key, { photos: urls })}
                          max={6}
                          label="Foto aufnehmen"
                        />
                      </div>
                    ) : (
                      <div className="mt-1 text-xs text-muted">
                        {item.issue ? <span className="text-warn">Auffälligkeit. </span> : null}
                        {item.note}
                        {item.photos?.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {item.photos.map((url) => (
                              /* eslint-disable-next-line @next/next/no-img-element */
                              <img
                                key={url}
                                src={url}
                                alt=""
                                className="h-16 w-20 rounded object-cover"
                              />
                            ))}
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {!done ? (
            <>
              <div>
                <label className="label" htmlFor={`${order.id}-notes`}>
                  Bemerkungen
                </label>
                <textarea
                  id={`${order.id}-notes`}
                  rows={2}
                  className="field"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>
              {error ? (
                <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
                  {error}
                </p>
              ) : null}
              {blocking.length ? (
                <p className="rounded-lg bg-surface-muted px-3 py-2 text-xs text-muted">
                  Zum Abschließen fehlen noch: {blocking.map((i) => i.label).join(", ")}
                </p>
              ) : null}
              <div className="flex gap-2">
                <button type="button" className="btn-ghost" onClick={() => persist()} disabled={busy}>
                  Zwischenstand sichern
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => persist(true)}
                  disabled={busy || blocking.length > 0}
                >
                  Abschließen
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm text-positive">
              Abgeschlossen
              {order.completed_at
                ? ` am ${dateLabel(order.completed_at, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`
                : ""}
              .
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}
