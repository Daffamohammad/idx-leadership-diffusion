// Wire types describing the JSON emitted by scripts/export_snapshot_json.py.
// All numeric fields use 0 (or null) when the snapshot lacks the source value;
// downstream pages label these clearly as "snapshot did not emit".

export type LeadershipState =
  | "LEADING"
  | "IMPROVING"
  | "WEAKENING"
  | "LAGGING"
  | "UNCONFIRMED";

export type DiffusionState =
  | "BROADENING"
  | "STABLE"
  | "NARROWING"
  | "UNCONFIRMED";

export type DataStatus =
  | "READY"
  | "READY_WITH_GAPS"
  | "PARTIAL"
  | "STALE"
  | "FAILED"
  | "DATA_GAP"
  | "UNAVAILABLE";

/** Normalize persisted backend status values before they reach presentation components. */
export function normalizeDataStatus(status: string | null | undefined): DataStatus | null {
  if (!status) return null;
  const normalized = status.trim().toUpperCase().replace(/[\s-]+/g, "_");
  if (
    normalized === "READY" ||
    normalized === "READY_WITH_GAPS" ||
    normalized === "PARTIAL" ||
    normalized === "STALE" ||
    normalized === "FAILED" ||
    normalized === "DATA_GAP" ||
    normalized === "UNAVAILABLE"
  ) {
    return normalized;
  }
  // Unknown status values remain visibly unavailable rather than being
  // silently promoted to READY or READY_WITH_GAPS.
  return "UNAVAILABLE";
}

export interface ManifestEntry {
  snapshot_id: string;
  snapshot_date: string;
  as_of: string;
  provider: string;
  provider_mode?: string;
  price_basis?: string;
  coverage_status: string;
  coverage_pct: number;
  method_version?: string;
  universe_version?: string;
  taxonomy_version?: string;
  feature_version?: string;
  leadership_version?: string;
  diffusion_version?: string;
  concentration_version?: string;
}

export interface Quality {
  status: DataStatus | string;
  issues: string[];
  coverage_pct: number;
  requested_securities: number;
  loaded_securities: number;
  usable_securities: number;
  failed_securities: number;
  benchmark_latest_date?: string;
  latest_common_date?: string;
  stale: boolean;
}

export interface Coverage {
  security_master_total?: number;
  history_requested_securities?: number;
  securities_with_any_price_history?: number;
  securities_with_usable_price_history?: number;
  eligible_securities?: number;
  excluded_securities?: number;
  exclusion_reasons?: Record<string, number>;
  taxonomy_complete_securities?: number;
  taxonomy_coverage_pct?: number;
  latest_available_security_trade_date?: string;
  latest_available_benchmark_date?: string;
  stale_security_count?: number;
  price_history_coverage_pct?: number;
  // Full denominator contract (added 2026-08-29).
  raw_candidate_constituents?: number;
  policy_eligible_constituents?: number;
  policy_excluded_constituents?: number;
  acquisition_failed_constituents?: number;
  acquisition_empty_constituents?: number;
  acquired_constituents?: number;
  observed_eligible_features?: number;
  coverage_pct?: number;
  coverage_gate_60pct_met?: boolean;
  // Prefix sample disclosure (added 2026-08-29).
  is_prefix_sample?: boolean;
  discovered_count?: number;
  used_count?: number;
  discovered_universe_disclosure?: string;
  security_master_pagination_completeness?: "COMPLETE" | "PARTIAL" | "UNKNOWN" | null;
  close_pagination_completeness?: "COMPLETE" | "PARTIAL" | "UNKNOWN" | null;
  pagination_incomplete?: boolean;
}

export interface Comparability {
  as_of: string;
  comparison_kind: "persisted_snapshot" | "intra_window" | "none";
  status: "COMPATIBLE" | "INCOMPARABLE";
  selected_previous: string | null;
  previous_intra_window_source: string | null;
  previous_groups: string[];
  reasons: string[];
  warnings: string[];
  policy_universe_hash: string;
}

export interface GroupRow {
  snapshot_date: string;
  taxonomy_level: string;
  group_id: string;
  group_name: string | null;
  constituent_count: number;
  raw_candidate_count?: number;
  policy_eligible_count?: number;
  acquisition_failed_count?: number;
  eligible_count: number;
  missing_count: number;
  group_return_equal_weight: number | null;
  group_excess_return: number | null;
  group_excess_return_5d: number | null;
  group_excess_return_20d: number | null;
  group_excess_return_60d: number | null;
  breadth_positive: number | null;
  breadth_outperforming: number | null;
  breadth_delta: number | null;
  top1_contribution_share: number | null;
  top3_contribution_share: number | null;
  top5_contribution_share: number | null;
  hhi_contribution: number | null;
  leadership_state: LeadershipState;
  diffusion_state: DiffusionState;
  leadership_rank: number | null;
  change_rank: number | null;
  leadership_persistence?: number;
  diffusion_persistence?: number;
}

export interface TransitionRow {
  current_date: string;
  previous_date: string;
  taxonomy_level: string;
  group_id: string;
  previous_leadership_state: LeadershipState | null;
  current_leadership_state: LeadershipState;
  previous_diffusion_state: DiffusionState | null;
  current_diffusion_state: DiffusionState;
  leadership_transition: string | null;
  diffusion_transition: string | null;
  breadth_delta: number | null;
  relative_strength_delta: number | null;
  rank_delta: number | null;
  materiality_label: string;
  materiality_reason: string;
}

export interface FeatureRow {
  ticker: string;
  as_of: string;
  latest_close: number | null;
  return_5d: number | null;
  return_20d: number | null;
  return_60d: number | null;
  excess_return_5d: number | null;
  excess_return_20d: number | null;
  excess_return_60d: number | null;
  relative_strength_level: number | null;
}

export interface SnapshotBreadthHistoryPoint {
  group_id: string;
  as_of: string;
  breadth: number;
  group_excess_return_20d: number | null;
}

export interface SnapshotPayload {
  schema_version: string;
  snapshot_id: string;
  as_of: string;
  previous_snapshot_id: string | null;
  comparability?: Comparability;
  manifest: { entries: ManifestEntry[] };
  quality: Quality;
  coverage?: Coverage;
  data_warnings?: { warnings?: string[] };
  provider_provenance?: Record<string, unknown>;
  tavily_context?: Record<string, unknown>;
  you_context?: Record<string, unknown>;
  api_credit_audit?: Record<string, unknown>;
  security_master_diagnostics?: Record<string, unknown>;
  history_diagnostics?: Record<string, unknown>;
  groups: GroupRow[];
  transitions: TransitionRow[];
  features: FeatureRow[];
  constituents: unknown[];
  // New exports use an array of persisted absolute breadth observations.
  // Legacy payloads may still carry an empty object.
  breadth_history: SnapshotBreadthHistoryPoint[] | Record<string, unknown>;
  endpoints: unknown[];
  security_master?: Array<{
    ticker: string;
    company_name?: string;
    group_id?: string;
    sector?: string;
  }>;
  change_digest?: Record<string, unknown>;
}
