"use client";

import { useEffect, useState } from "react";

import type { CatalogModel, CatalogModelDetail, ResolvedSpec } from "@/lib/api";

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.detail ?? `Fehler ${res.status}`);
  return body as T;
}

/** Debounced catalog search; an empty query lists everything. */
export function useModelSearch(query: string) {
  const [models, setModels] = useState<CatalogModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const params = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : "";
        const data = await fetchJson<CatalogModel[]>(`/api/catalog/models${params}`);
        if (!cancelled) setModels(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Katalog nicht erreichbar");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  return { models, loading, error };
}

/**
 * The result is stored together with the input it belongs to and the match is derived on
 * render. That way switching models shows nothing stale without an effect that clears state.
 */
type Loaded<T> = { key: string; value: T | null; error: string | null };

export function useModelDetail(modelId: string | null) {
  const [loaded, setLoaded] = useState<Loaded<CatalogModelDetail> | null>(null);

  useEffect(() => {
    if (!modelId) return;
    let cancelled = false;
    fetchJson<CatalogModelDetail>(`/api/catalog/models/${modelId}`)
      .then((data) => {
        if (!cancelled) setLoaded({ key: modelId, value: data, error: null });
      })
      .catch((err: Error) => {
        if (!cancelled) setLoaded({ key: modelId, value: null, error: err.message });
      });
    return () => {
      cancelled = true;
    };
  }, [modelId]);

  const current = loaded && loaded.key === modelId ? loaded : null;
  return { detail: current?.value ?? null, error: current?.error ?? null };
}

export type ResolveInput = {
  versionId: string | null;
  variantIds: string[];
  yearBuilt: number | null;
  overrides: Record<string, number | null>;
};

/** Live preview of the chosen configuration, including where each value came from. */
export function useResolvedSpec({ versionId, variantIds, yearBuilt, overrides }: ResolveInput) {
  const [loaded, setLoaded] = useState<Loaded<ResolvedSpec> | null>(null);
  const key = JSON.stringify({ versionId, variantIds, yearBuilt, overrides });

  useEffect(() => {
    if (!versionId) return;
    let cancelled = false;
    const input = JSON.parse(key) as ResolveInput;
    fetchJson<ResolvedSpec>("/api/catalog/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        version_id: input.versionId,
        variant_ids: input.variantIds,
        year_built: input.yearBuilt,
        overrides: input.overrides,
      }),
    })
      .then((data) => {
        if (!cancelled) setLoaded({ key, value: data, error: null });
      })
      .catch((err: Error) => {
        if (!cancelled) setLoaded({ key, value: null, error: err.message });
      });
    return () => {
      cancelled = true;
    };
  }, [key, versionId]);

  const current = loaded && loaded.key === key ? loaded : null;
  return { spec: current?.value ?? null, error: current?.error ?? null };
}
