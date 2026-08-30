// Shared snapshot fetcher. Wrap the app once in <SnapshotProvider>; pages
// read via useSnapshotContext().

import { useEffect, useState, type ReactNode } from "react";
import { adaptSnapshot, type AdaptedSnapshot } from "./adapter";
import { SnapshotContext, type SnapshotContextValue } from "./SnapshotContext";
import type { SnapshotPayload } from "./snapshot";

interface IndexEntry {
  snapshot_id: string;
  as_of: string;
  provider?: string;
  provider_mode?: string;
}

async function resolveLatestEntry(): Promise<IndexEntry | null> {
  const envId =
    (import.meta.env.VITE_SNAPSHOT_ID as string | undefined)?.trim() || null;
  if (envId) return { snapshot_id: envId, as_of: "" };
  try {
    const res = await fetch("/snapshots/index.json", { cache: "no-store" });
    if (!res.ok) return null;
    const raw = await res.json();
    if (!Array.isArray(raw)) return null;
    const list = raw.filter(
      (item): item is IndexEntry =>
        !!item &&
        typeof item === "object" &&
        typeof item.snapshot_id === "string" &&
        typeof item.as_of === "string",
    );
    if (!list.length) return null;
    // The live browser index is canonical, but prefer live Sectors entries if
    // an operator intentionally generated a mixed-provider index.
    const live = list.filter(
      (entry) =>
        entry.provider_mode === "SECTORS_LIVE" || entry.provider === "sectors",
    );
    const candidates = live.length ? live : list;
    const sorted = [...candidates].sort((a, b) =>
      a.as_of.localeCompare(b.as_of) || a.snapshot_id.localeCompare(b.snapshot_id),
    );
    return sorted[sorted.length - 1];
  } catch {
    return null;
  }
}

export function SnapshotProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SnapshotContextValue>({
    loading: true,
    error: null,
    data: null,
    snapshotId: null,
    payload: null,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const indexEntry = await resolveLatestEntry();
        const id = indexEntry?.snapshot_id;
        if (!id) {
          if (!cancelled) {
            setState({
              loading: false,
              error:
                "No snapshot JSON found. Run `.venv/bin/python -m scripts.export_snapshot_json --latest` " +
                "to generate app/web/public/snapshots/<id>.json.",
              data: null,
              snapshotId: null,
              payload: null,
            });
          }
          return;
        }
        const res = await fetch(`/snapshots/${id}.json`, { cache: "no-store" });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status} loading /snapshots/${id}.json`);
        }
        const payload = (await res.json()) as SnapshotPayload;
        if (payload.snapshot_id && payload.snapshot_id !== id) {
          throw new Error(
            `Snapshot index mismatch: requested ${id}, payload is ${payload.snapshot_id}`,
          );
        }
        if (indexEntry?.as_of && payload.as_of && indexEntry.as_of !== payload.as_of) {
          throw new Error(
            `Snapshot date mismatch for ${id}: index=${indexEntry.as_of} payload=${payload.as_of}`,
          );
        }
        const payloadMode = payload.manifest?.entries?.[0]?.provider_mode;
        if (indexEntry?.provider_mode && payloadMode && indexEntry.provider_mode !== payloadMode) {
          throw new Error(
            `Snapshot provider mismatch for ${id}: index=${indexEntry.provider_mode} payload=${payloadMode}`,
          );
        }
        if (cancelled) return;
        const adapted: AdaptedSnapshot = adaptSnapshot(payload);
        setState({
          loading: false,
          error: null,
          data: adapted,
          snapshotId: id,
          payload,
        });
      } catch (err) {
        if (cancelled) return;
        setState({
          loading: false,
          error: err instanceof Error ? err.message : String(err),
          data: null,
          snapshotId: null,
          payload: null,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <SnapshotContext.Provider value={state}>
      {children}
    </SnapshotContext.Provider>
  );
}

// Backwards-compatible hook — older call sites import `useSnapshot`.
export { useSnapshotContext as useSnapshot } from "./SnapshotContext";
