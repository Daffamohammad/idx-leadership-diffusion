/** Pure snapshot-selection logic, deliberately free of React imports. */

export interface IndexEntry {
  snapshot_id: string;
  as_of: string;
  provider?: string;
  provider_mode?: string;
}

/**
 * Pick the snapshot the app should render: the most recent `as_of` in the
 * published index, with a deterministic id tie-break.
 *
 * Provider mode is deliberately NOT a ranking input. A validated
 * public-prototype snapshot dated after the Sectors capture is newer data,
 * and the pipeline's comparability gate (not the provider brand) decides
 * whether two snapshots may be compared. The historical Sectors entry stays
 * in the index as evidence and remains selectable through
 * `VITE_SNAPSHOT_ID`.
 *
 * This lives apart from `SnapshotProvider.tsx` so it can be exercised
 * directly by the test suite without pulling in React.
 */
export function pickLatestEntry(entries: IndexEntry[]): IndexEntry | null {
  if (!entries.length) return null;
  const sorted = [...entries].sort((a, b) =>
    a.as_of.localeCompare(b.as_of) || a.snapshot_id.localeCompare(b.snapshot_id),
  );
  return sorted[sorted.length - 1];
}