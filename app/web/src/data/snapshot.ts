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

export type ForeignFlowDirection = "NET_BUY" | "NET_SELL" | "FLAT" | "UNCONFIRMED";
export type ForeignFlowScope = "MARKET_TOTAL" | "TOP_LIST_SAMPLE" | "GROUP_SAMPLE";
export type ResearchEventCategory =
  | "earnings"
  | "dividend"
  | "rights_issue"
  | "stock_split"
  | "suspension"
  | "index_inclusion"
  | "corporate_action"
  | "major_filing"
  | "other_sourced_event";

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

export interface GroupPriceHistoryPoint {
  date: string;
  value: number;
  benchmark: number | null;
}

// ────────────────────────────────────────────────────────────────────────
// Foreign flow sample envelope (added 2026-08-30)
// ────────────────────────────────────────────────────────────────────────

export interface ForeignFlowObservation {
  as_of: string;
  scope: ForeignFlowScope | string;
  ticker: string | null;
  group_id: string | null;
  taxonomy_version: string;
  mapping_status: string;
  market_scope: string;
  net_value_idr: number | null;
  buy_value_idr: number | null;
  sell_value_idr: number | null;
  direction: ForeignFlowDirection;
  reconciliation_status: string;
  reconciliation_delta_idr: number | null;
  source_url: string;
  source_published_at: string;
  source_kind: string;
  source_name: string;
  source_locator: string;
  quantitative_use: boolean;
}

export interface ForeignFlowDailyMarket {
  as_of: string;
  scope: string;
  net_value_idr: number;
  direction: ForeignFlowDirection;
  coverage_scope: string;
}

export interface ForeignFlowDailySample {
  as_of: string;
  scope: string;
  sample_net_value_idr: number;
  direction: ForeignFlowDirection;
  observed_company_count: number;
  mapped_company_count: number;
  positive_company_count: number;
  negative_company_count: number;
  coverage_scope: string;
}

export interface ForeignFlowGroupSummary {
  as_of: string;
  group_id: string;
  taxonomy_version: string;
  net_value_idr: number;
  direction: ForeignFlowDirection;
  observed_company_count: number;
  positive_company_count: number;
  negative_company_count: number;
  mapping_status: string;
  scope: string;
}

export interface ForeignFlowRolling {
  as_of: string;
  rolling_3d_sample_net_value_idr: number;
  window_size: number;
  direction: ForeignFlowDirection;
}

export interface ForeignFlowBreadth {
  sample_positive_day_count: number;
  sample_negative_day_count: number;
  market_positive_day_count: number;
  market_negative_day_count: number;
  last_sample_direction: ForeignFlowDirection;
  last_market_direction: ForeignFlowDirection;
  market_sample_aligned: boolean;
}

export interface ForeignFlowSignalEligibility {
  market_day_count: number;
  company_observation_count: number;
  mapped_company_observation_pct: number;
  market_days_meets_threshold: boolean;
  company_rows_meets_threshold: boolean;
  mapped_pct_meets_threshold: boolean;
  sample_diagnostics_met?: boolean;
  full_universe_coverage_met?: boolean;
  coverage_gate_met: boolean;
  missing_dates: string[];
  stale_dates: string[];
  regime_diversity: boolean;
  signal_eligible: boolean;
}

export interface ForeignFlowCoverage {
  market_observation_count: number;
  market_day_count: number;
  company_observation_count: number;
  unique_company_ticker_count: number;
  mapped_company_observation_count: number;
  mapped_ticker_count: number;
  unmapped_tickers: string[];
  mapped_company_observation_pct: number;
  coverage_label: string;
  synthetic_test_rows: number;
}

export interface ForeignFlowProvenance {
  source_url: string;
  source_name: string;
  source_kind: string;
  source_published_at: string;
  source_locators: string[];
  observed_rows: number;
  quantitative_use: boolean;
  numeric_role: string;
}

export interface ForeignFlowSample {
  schema_version: string;
  provider_mode: string;
  status: DataStatus | string;
  as_of: { min: string; max: string };
  quantitative_use: boolean;
  scope: string;
  calculation: Record<string, unknown>;
  coverage: ForeignFlowCoverage;
  quality: {
    rows_validated: number;
    reconciliation_status_counts: Record<string, number>;
    reported_net_preserved: boolean;
    missing_company_buy_sell_not_inferred: boolean;
    missing_dates: string[];
    stale_dates: string[];
  };
  market_observations: ForeignFlowObservation[];
  company_observations: ForeignFlowObservation[];
  daily_market_totals: ForeignFlowDailyMarket[];
  daily_company_samples: ForeignFlowDailySample[];
  group_summaries: ForeignFlowGroupSummary[];
  rolling_sample_flow: ForeignFlowRolling[];
  breadth_observed: ForeignFlowBreadth;
  signal_eligibility: ForeignFlowSignalEligibility;
  provenance: ForeignFlowProvenance[];
  synthetic_test_only: ForeignFlowObservation[];
  source_discovery: Record<string, unknown>;
  limitations: string[];
  context_compatibility?: {
    role: string;
    snapshot_as_of?: string | null;
    snapshot_provider_mode?: string;
    source_provider_mode?: string;
    cross_provider_context?: boolean;
    used_in_leadership_or_diffusion?: boolean;
    reason?: string;
  };
}

// ────────────────────────────────────────────────────────────────────────
// Taxonomy views (sector / Konglo / Themes)
// ────────────────────────────────────────────────────────────────────────

export type TaxonomyKind = "SECTOR" | "KONGLO" | "THEMES";
export type TaxonomySourceKind =
  | "PROTOTYPE_CONFIG"
  | "ANALYST_DEFINED"
  | "PRIMARY_INDEX"
  | "THIRD_PARTY";

export interface TaxonomyGroupAggregate {
  taxonomy_group_id: string;
  taxonomy_group_name: string;
  constituent_count: number;
  eligible_constituent_count: number;
  coverage_pct: number;
  equal_weight_return_20d: number | null;
  equal_weight_return_60d: number | null;
  excess_return_20d: number | null;
  excess_return_60d: number | null;
  benchmark_return_20d: number | null;
  benchmark_return_60d: number | null;
  breadth_outperforming: number | null;
  prev_breadth_outperforming: number | null;
  breadth_delta: number | null;
  leadership_state: string;
  diffusion_state: string;
  concentration_top3: number | null;
  map_x: number | null;
  map_y: number | null;
  off_scale: boolean;
  data_quality: string;
  prototype: boolean;
  membership_kind_breakdown?: Record<string, number>;
  sample_foreign_flow_idr?: number | null;
  sample_foreign_flow_direction?: ForeignFlowDirection | null;
}

export interface TaxonomyView {
  schema_version: string;
  taxonomy_id: string;
  taxonomy_name: string;
  taxonomy_version: string;
  taxonomy_kind: TaxonomyKind;
  source_kind: TaxonomySourceKind;
  source_as_of?: string | null;
  membership_policy: string;
  provider_mode: string;
  snapshot_provider_mode?: string;
  taxonomy_definition_provider_mode?: string;
  source_snapshot_id?: string;
  source_snapshot_price_basis?: string;
  previous_snapshot_id?: string | null;
  point_in_time_eligible?: boolean;
  benchmark_id?: string;
  as_of?: string | null;
  coverage?: Record<string, unknown>;
  calculation?: Record<string, unknown>;
  calculation_coverage?: Record<string, unknown>;
  comparability?: Record<string, unknown>;
  groups: TaxonomyGroupAggregate[];
}

// ────────────────────────────────────────────────────────────────────────
// Research events
// ────────────────────────────────────────────────────────────────────────

export interface ResearchEventRow {
  event_id: string;
  event_date: string;
  published_at: string;
  ticker: string;
  sector_id: string | null;
  konglo_id: string | null;
  theme_ids: string[];
  category: ResearchEventCategory | string;
  title: string;
  summary: string;
  source_url: string;
  source_name: string;
  provider: string;
  quantitative_use: boolean;
  status: string;
}

export interface ResearchEventBundle {
  schema_version: string;
  provider_mode: string;
  event_count?: number;
  as_of?: string | null;
  events: ResearchEventRow[];
  sources: Array<{
    source_url: string;
    source_name: string;
    provider: string;
    published_at?: string;
  }>;
  context_compatibility?: {
    role: string;
    snapshot_provider_mode?: string;
    used_in_leadership_or_diffusion?: boolean;
    publication_cutoff_enforced?: boolean;
  };
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
  // Descriptive equal-weight group index, rebased to 100. This is chart-only
  // data and is never consumed by the analytical signal pipeline.
  group_price_history?: Record<string, GroupPriceHistoryPoint[]>;
  // Real per-ticker persisted prices, rebased to 100 with an aligned IHSG
  // benchmark. Never synthesized from return features.
  ticker_price_history?: Record<string, GroupPriceHistoryPoint[]>;
  endpoints: unknown[];
  security_master?: Array<{
    ticker: string;
    company_name?: string;
    group_id?: string;
    sector?: string;
  }>;
  change_digest?: Record<string, unknown>;
  // Added 2026-08-30:
  taxonomy_views?: Record<string, TaxonomyView>;
  foreign_flow_sample?: ForeignFlowSample;
  research_events?: ResearchEventBundle;
}
