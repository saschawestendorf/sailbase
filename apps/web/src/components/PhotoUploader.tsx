"use client";

import { useRef, useState } from "react";

type Props = {
  urls: string[];
  onChange: (urls: string[]) => void;
  /** Guests upload against their booking; signed-in users against the generic endpoint. */
  endpoint?: string;
  max?: number;
  label?: string;
};

export default function PhotoUploader({
  urls,
  onChange,
  endpoint = "/api/uploads",
  max = 12,
  label = "Fotos hinzufügen",
}: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setError(null);
    const added: string[] = [];
    try {
      for (const file of Array.from(files).slice(0, max - urls.length)) {
        const body = new FormData();
        body.append("file", file);
        const res = await fetch(endpoint, { method: "POST", body });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data?.detail ?? `Upload fehlgeschlagen (${res.status})`);
        added.push(data.url);
      }
      onChange([...urls, ...added]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen");
      if (added.length) onChange([...urls, ...added]);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div>
      {urls.length ? (
        <ul className="mb-2 grid grid-cols-3 gap-2 sm:grid-cols-4">
          {urls.map((url) => (
            <li key={url} className="group relative overflow-hidden rounded-lg border border-line">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={url} alt="" className="aspect-[4/3] w-full object-cover" />
              <button
                type="button"
                onClick={() => onChange(urls.filter((u) => u !== url))}
                className="absolute right-1 top-1 rounded bg-black/60 px-1.5 py-0.5 text-xs text-white"
                aria-label="Foto entfernen"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <button
        type="button"
        className="btn-ghost"
        onClick={() => input.current?.click()}
        disabled={busy || urls.length >= max}
      >
        {busy ? "Lädt …" : urls.length >= max ? `Maximal ${max} Fotos` : label}
      </button>
      {error ? (
        <p role="alert" className="mt-2 rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
          {error}
        </p>
      ) : null}
    </div>
  );
}
