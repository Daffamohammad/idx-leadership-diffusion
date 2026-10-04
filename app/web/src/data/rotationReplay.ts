import { sampleRotationHistory, type RotationInterval } from "./rotation";
import type { TaxonomyKind } from "./snapshot";

export interface ReplayPoint {
  as_of: string;
  group_excess_return_ytd: number;
  group_excess_return_20d: number;
  group_excess_return_60d: number;
  relative_momentum: number;
  source_ids: string[];
}
export interface ReplayGroup {
  group_id: string; name: string; current_segment_id: string | null;
  daily_available: boolean; weekly_available: boolean; reason: string | null;
  gaps: { as_of: string; reason: string }[];
  segments: { segment_id: string; sessions: string[]; points: ReplayPoint[]; source_ids: string[] }[];
}
export interface RotationReplay {
  schema_version: "rotation-history-v1"; snapshot_id: string; as_of: string; start: string;
  sessions: string[]; taxonomies: Record<TaxonomyKind, Record<string, ReplayGroup>>;
  sources: Record<string, { observed_on: string; published_on: string | null; available_on: string | null; publication_basis?: string }>;
}

/** A single group cannot enable or disable another group's verified trail. */
export function replaySelection(asset: RotationReplay, kind: TaxonomyKind, groupId: string,
  interval: RotationInterval, endpoint: { relativeStrength: number | null; excess20d: number | null; excess60d: number | null }) {
  const group = asset.taxonomies?.[kind]?.[groupId];
  const unavailable = (reason: string) => ({ points: [] as ReplayPoint[], reason });
  if (!group) return unavailable("No dated history for this group");
  const segment = group.segments?.find(s => s.segment_id === group.current_segment_id);
  if (!segment) return unavailable(group.reason ?? "No comparable segment reaches the current date");
  if (!segment.sessions?.length || !segment.points?.length) return unavailable("History is incomplete");
  const expected = asset.sessions.filter(s => s >= segment.sessions[0] && s <= asset.as_of);
  if (JSON.stringify(expected) !== JSON.stringify(segment.sessions)) return unavailable("History has missing trading sessions");
  const last = segment.points[segment.points.length - 1];
  if (last.as_of !== asset.as_of || [
    [last.group_excess_return_ytd, endpoint.relativeStrength],
    [last.group_excess_return_20d, endpoint.excess20d],
    [last.group_excess_return_60d, endpoint.excess60d],
  ].some(([a, b]) => a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b) || Math.abs(a - b) > 0.00011)) {
    return unavailable("History does not match the current point");
  }
  if (segment.points.some(p => !Number.isFinite(p.group_excess_return_20d) || !Number.isFinite(p.group_excess_return_60d)
    || Math.abs(p.relative_momentum - (p.group_excess_return_20d - p.group_excess_return_60d)) > 1e-8)) {
    return unavailable("History coordinates are invalid");
  }
  if (segment.points.some(point => !point.source_ids?.length || point.source_ids.some(id => {
    const source = asset.sources[id];
    return !source || (!source.published_on && source.publication_basis !== "capture_upper_bound") || !source.available_on || (source.published_on != null && source.published_on > source.available_on)
      || source.observed_on > point.as_of || source.available_on > point.as_of;
  }))) return unavailable("Publication evidence unavailable");
  const points = sampleRotationHistory(segment.points, segment.sessions, interval);
  return points.length ? { points, reason: null } : unavailable(`Fewer than three comparable ${interval === "daily" ? "daily observations" : "weekly endpoints"}`);
}
