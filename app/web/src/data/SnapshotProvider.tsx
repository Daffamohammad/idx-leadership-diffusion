// Shared snapshot fetcher. Wrap the app once in <SnapshotProvider>; pages
// read via useSnapshotContext().

import { useEffect, useState, type ReactNode } from "react";
import { adaptSnapshot, type AdaptedSnapshot } from "./adapter";
import { SnapshotContext, type SnapshotContextValue } from "./SnapshotContext";
import type { SnapshotPayload } from "./snapshot";
import { loadActiveRelease, loadReleaseAsset, loadReleaseAdditionalFile } from "./release";

export function SnapshotProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SnapshotContextValue>({
    loading: true,
    error: null,
    data: null,
    snapshotId: null,
    payload: null,
    release: null,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const release = await loadActiveRelease();
        const id = release.manifest.snapshot_identity.snapshot_id;
        const payload = await loadReleaseAsset<SnapshotPayload>(release, release.manifest.families.snapshot);
        if (payload.snapshot_id !== id || payload.as_of !== release.manifest.target_session) {
          throw new Error(`Snapshot identity differs from selected release ${release.id}`);
        }
        const payloadMode = payload.manifest?.entries?.[0]?.provider_mode;
        const snapshotEntry = payload.manifest?.entries?.[0];
        if (snapshotEntry && (
          snapshotEntry.provider !== release.manifest.snapshot_identity.provider ||
          payloadMode !== release.manifest.snapshot_identity.provider_mode ||
          snapshotEntry.price_basis !== release.manifest.snapshot_identity.price_basis
        )) {
          throw new Error(`Snapshot provider or price basis differs from selected release ${release.id}`);
        }
        if (cancelled) return;
        const [idxInvestorRelease, idxDailyStatistics] = await Promise.all([
          loadReleaseAdditionalFile(release, "idx_investor_release"),
          loadReleaseAdditionalFile(release, "idx_daily_statistics"),
        ]);
        const adapted: AdaptedSnapshot = adaptSnapshot(
          payload,
          idxInvestorRelease,
          idxDailyStatistics,
        );
        setState({
          loading: false,
          error: null,
          data: adapted,
          snapshotId: id,
          payload,
          release,
        });
      } catch (err) {
        if (cancelled) return;
        setState({
          loading: false,
          error: err instanceof Error ? err.message : String(err),
          data: null,
          snapshotId: null,
          payload: null,
          release: null,
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
