// Shared snapshot state for the React app. One fetch, many consumers.
import { createContext, useContext } from "react";
import type { AdaptedSnapshot } from "./adapter";
import type { SnapshotPayload } from "./snapshot";
import type { SelectedRelease } from "./release";

export interface SnapshotContextValue {
  loading: boolean;
  error: string | null;
  data: AdaptedSnapshot | null;
  snapshotId: string | null;
  payload: SnapshotPayload | null;
  release: SelectedRelease | null;
}

export const SnapshotContext = createContext<SnapshotContextValue>({
  loading: true,
  error: null,
  data: null,
  snapshotId: null,
  payload: null,
  release: null,
});

export function useSnapshotContext(): SnapshotContextValue {
  return useContext(SnapshotContext);
}
