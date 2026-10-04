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
  // Legacy/listing-scope disclosure (added 2026-08-29).
  is_prefix_sample?: boolean;
  discovered_count?: number;
  used_count?: number;
  discovered_universe_disclosure?: string;
  // The live pipeline now keeps the complete listing while bounding only the
  // expensive daily-history lane for a demo.
  analysis_universe_count?: number;
  analysis_scope?: "BOUNDED_DEMO" | "PAGE_CAPPED" | "FULL_DISCOVERED_UNIVERSE" | string;
  analysis_selection_method?: string;
  full_accessible_universe_listed?: boolean;
  history_request_symbol_cap?: number | null;
  live_http_request_cap?: number | null;
  live_http_requests_made?: number;
  security_master_pagination_completeness?: "COMPLETE" | "PARTIAL" | "UNKNOWN" | null;
  close_pagination_completeness?: "COMPLETE" | "PARTIAL" | "UNKNOWN" | null;
  // Pagination / window-cap flags threaded from provider diagnostics
  // (continuation pass, 2026-09-13). Absent on bundles exported before the
  // pass; UI must treat absent as unknown, never as complete.
  pagination_incomplete?: boolean;
  history_window_capped_90d?: boolean;
  history_window_capped_note?: string | null;
  // Session/alignment disclosure (production pass, 2026-09-13). Absent on
  // older bundles; UI must treat absent as unknown, never as clean.
  suspension_check?: "checked" | "not_supported" | "failed" | string;
  intraday_build?: boolean;
  max_observation_lag_days?: number | null;
  tickers_lagging_gt2d?: number;
}

// Per-ticker acquisition diagnostics persisted by the pipeline as
// `history_diagnostics.json` and forwarded verbatim by the exporter.
// `failed_symbols` entries may be plain tickers or `{ticker, ...}` rows
// depending on the provider; the adapter normalizes both shapes.
export interface HistoryDiagnostics {
  requested_symbols?: number;
  returned_symbols?: number;
  returned_rows?: number;
  failed_symbols?: Array<string | { ticker?: string } | Record<string, unknown>>;
  empty_symbols?: Array<string | Record<string, unknown>>;
  duplicate_symbol_date_rows?: number;
  window_capped_to_90_calendar_days?: boolean;
  requested_start?: string;
  effective_start?: string;
  end?: string;
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
  group_return_ytd?: number | null;
  group_excess_return_ytd?: number | null;
  benchmark_return_ytd?: number | null;
  ytd_start_date?: string | null;
  ytd_eligible_count?: number;
  breadth_positive: number | null;
  breadth_outperforming: number | null;
  breadth_delta: number | null;
  top1_contribution_share: number | null;
  top3_contribution_share: number | null;
  top5_contribution_share: number | null;
  hhi_contribution: number | null;
  leadership_state: LeadershipState;
  diffusion_state: DiffusionState;
  // Diffusion v2 detail (FIRM / FRAGILE qualified states such as
  // BROADENING_FIRM) emitted by signals/diffusion_v2.py. Absent on legacy
  // exports; UI shows it only where emitted, never synthesized.
  diffusion_state_v2?: string | null;
  leadership_rank: number | null;
  change_rank: number | null;
  leadership_persistence?: number;
  diffusion_persistence?: number;
  // Extended breadth denominator + signed concentration diagnostics
  // persisted by newer pipeline builds. All optional for back-compat.
  breadth_total_count?: number | null;
  breadth_eligible_count?: number | null;
  breadth_missing_count?: number | null;
  breadth_positive_count?: number | null;
  breadth_outperforming_count?: number | null;
  breadth_improving_count?: number | null;
  top1_signed_share?: number | null;
  top3_signed_share?: number | null;
}

export interface EvidenceContradictionRow {
  metric: string;
  label: string;
  severity: string;
  evidence?: string | null;
}

export interface EvidenceInvalidationRow {
  condition: string;
  threshold?: string | null;
}

export interface GroupEvidenceRow {
  group_id: string;
  contradictions?: EvidenceContradictionRow[];
  invalidation?: EvidenceInvalidationRow[];
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
  previous_diffusion_state_v2?: string | null;
  current_diffusion_state_v2?: string | null;
  diffusion_transition_v2?: string | null;
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
  return_ytd?: number | null;
  return_ytd_start_date?: string | null;
  return_ytd_end_date?: string | null;
  excess_return_5d: number | null;
  excess_return_20d: number | null;
  excess_return_60d: number | null;
  benchmark_return_ytd?: number | null;
  excess_return_ytd?: number | null;
  relative_strength_level: number | null;
}

export interface SnapshotBreadthHistoryPoint {
  group_id: string;
  as_of: string;
  breadth: number;
  group_excess_return_20d: number | null;
}

/**
 * One dated rotation observation (2026-10-02 refresh). Both axes are the
 * values the rotation contract uses: YTD excess vs the benchmark
 * (relative strength) and 20D/60D excess (momentum). A point is only present
 * when the pipeline actually computed the YTD excess for that date.
 */
export interface SnapshotRotationHistoryPoint {
  group_id: string;
  as_of: string;
  group_excess_return_ytd: number;
  ytd_start_date?: string | null;
  group_excess_return_20d: number | null;
  group_excess_return_60d: number | null;
  relative_momentum: number | null;
}

export interface GroupPriceHistoryPoint {
  date: string;
  value: number;
  benchmark: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
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
// First-party IDX Digital Statistic release
// ────────────────────────────────────────────────────────────────────────

export type IDXInvestorFlowDirection = "NET_BUY" | "NET_SELL" | "FLAT";

export interface IDXInvestorReleaseDay {
  as_of: string;
  foreign_to_domestic_value_idr: number;
  domestic_to_foreign_value_idr: number;
  net_foreign_value_idr: number;
  direction: IDXInvestorFlowDirection;
}

export interface IDXInvestorRelease {
  schema_version: string;
  provider: "IDX" | string;
  provider_mode: string;
  status: DataStatus | string;
  quantitative_use: boolean;
  scope: string;
  release: {
    title: string;
    period: { year: number; month: number; label: string };
    trading_day_count: number;
  };
  as_of: { min: string; max: string };
  daily: IDXInvestorReleaseDay[];
  totals: {
    foreign_to_foreign_value_idr?: number;
    foreign_to_domestic_value_idr: number;
    domestic_to_foreign_value_idr: number;
    domestic_to_domestic_value_idr?: number;
    net_foreign_value_idr: number;
    direction: IDXInvestorFlowDirection;
  };
  quality: {
    source_table_count: number;
    daily_rows: number;
    positive_day_count?: number;
    negative_day_count?: number;
    reconciliation: Record<string, boolean>;
    search_agent_role: string;
    full_month_release: boolean;
  };
  source: {
    publisher: string;
    url: string;
    retrieved_at: string;
    parser: string;
    table_endpoints?: string[];
  };
  limitations: string[];
}

// First-party IDX Daily Statistics PDF cards reduced by the optional
// LlamaParse ingest. This is deliberately a small target-metrics contract;
// the full parser response remains an offline audit sidecar.
export interface IDXDailyStatistics {
  schema_version: string;
  provider: "IDX" | string;
  provider_mode: string;
  status: DataStatus | string;
  quantitative_use: boolean;
  scope: string;
  as_of: string;
  metrics: {
    ihsg: {
      close: number;
      previous: number;
      change: number;
      change_pct: number;
      raw_change?: string;
    };
    net_foreign: {
      today: {
        idr_billion: number;
        usd_million: number;
        usd_approximate: boolean;
        direction: string;
      };
      ytd: {
        idr_billion: number;
        usd_million: number;
        usd_approximate: boolean;
        direction: string;
      };
    };
    fundamental: {
      market_per: number;
      market_pbv: number;
    };
  };
  quality: {
    checks: Record<string, boolean>;
    warnings: string[];
    warning_count: number;
    markdown_sha256: string;
    parsed_page_count?: number;
    parsed_page_numbers?: number[];
  };
  llama: {
    job_id?: string | null;
    file_id?: string | null;
    tier: string;
    version: string;
    estimated_credit_cost?: number | null;
    actual_credit_cost?: number | null;
    actual_credit_cost_known: boolean;
  };
  source: {
    publisher: string;
    url: string | null;
    retrieved_at: string;
    parser: string;
    parser_version?: string;
    tier?: string;
    file_name?: string;
  };
  limitations: string[];
}

export interface OfficialMarketContext {
  schema_version: string;
  provider: "OJK" | string;
  provider_mode: string;
  status: DataStatus | string;
  quantitative_use: boolean;
  scope: string;
  release_date: string;
  period_end: string;
  metrics: {
    ihsg_close: number;
    ihsg_ytd_pct: number;
    equity_net_foreign_idr_trillion: number;
    equity_net_foreign_direction: string;
    equity_flow_ytd_idr_trillion: number;
    equity_rnth_idr_trillion: number;
    local_ownership_pct: number;
    market_cap_idr_trillion: number;
  };
  quality: Record<string, unknown>;
  source: {
    publisher: string;
    url: string;
    published_at?: string;
    retrieved_at?: string;
    parser_agent?: string;
    parser_version?: string;
    parsed_pages?: number[];
  };
  context_compatibility?: {
    role: string;
    snapshot_as_of?: string;
    snapshot_provider_mode?: string;
    used_in_leadership_or_diffusion?: boolean;
    not_per_ticker?: boolean;
    not_per_group?: boolean;
  };
  limitations: string[];
}

export interface ListingRegistryRecord {
  ticker: string;
  company_name: string;
  exchange: string;
  listing_board: string | null;
  listing_status: string | null;
  active: boolean;
  common_equity_status: string | null;
  market_cap: number | null;
  taxonomy: {
    sector: string | null;
    subsector: string | null;
    industry: string | null;
    subindustry: string | null;
  };
  taxonomy_status: string;
  group_id: string | null;
  analysis_requested: boolean;
  analysis_status: string;
  konglo_memberships: Array<Record<string, unknown>>;
  theme_memberships: Array<Record<string, unknown>>;
  source: string | null;
  source_as_of: string | null;
}

export interface ListingRegistry {
  schema_version: string;
  status: string;
  provider_mode: string;
  as_of: string | null;
  scope_label: string;
  full_accessible_universe_listed: boolean;
  discovered_count: number;
  persisted_count: number;
  listed_count: number;
  duplicate_ticker_count: number;
  analysis_requested_count: number;
  observed_feature_count: number;
  taxonomy_complete_count: number;
  taxonomy_coverage_pct: number;
  konglo_mapped_count: number;
  theme_mapped_count: number;
  membership_sources: Record<string, string>;
  integrity: Record<string, unknown>;
  records: ListingRegistryRecord[];
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

export type TaxonomyMembershipType = "PRIMARY" | "SECONDARY" | "EXCLUDED";

export interface TaxonomyMembershipData {
  ticker: string;
  taxonomy_group_id: string;
  taxonomy_group_name: string;
  membership_type: TaxonomyMembershipType;
  confidence: number;
  source: string;
  source_as_of?: string | null;
  // Relationship subtype (control / subsidiary / affiliate / cross-shareholding /
  // founder-director / ecosystem) when a source-backed value is stored. Optional:
  // absent means unresolved, never inferred from a job title or similar name.
  relationship?: string | null;
  relationship_as_of?: string | null;
  relationship_source?: string | null;
}

export interface TaxonomyGroupAggregate {
  taxonomy_group_id: string;
  taxonomy_group_name: string;
  constituent_count: number;
  eligible_constituent_count: number;
  coverage_pct: number;
  equal_weight_return_20d: number | null;
  equal_weight_return_60d: number | null;
  equal_weight_return_ytd?: number | null;
  excess_return_20d: number | null;
  excess_return_60d: number | null;
  excess_return_ytd?: number | null;
  benchmark_return_20d: number | null;
  benchmark_return_60d: number | null;
  benchmark_return_ytd?: number | null;
  ytd_start_date?: string | null;
  ytd_eligible_constituent_count?: number;
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
  memberships?: TaxonomyMembershipData[];
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
  // Bundle-completeness sentinel forwarded from SnapshotReader.load
  // (`COMPLETE` file written last by SnapshotWriter.write). Pre-sentinel
  // bundles report false; legacy exports that predate the forwarding omit
  // the key entirely (unknown — never render as authoritative either way).
  complete?: boolean | null;
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
  history_diagnostics?: HistoryDiagnostics;
  groups: GroupRow[];
  transitions: TransitionRow[];
  features: FeatureRow[];
  constituents: unknown[];
  memberships?: TaxonomyMembershipData[];
  // New exports use an array of persisted absolute breadth observations.
  // Legacy payloads may still carry an empty object.
  breadth_history: SnapshotBreadthHistoryPoint[] | Record<string, unknown>;
  rotation_history?: SnapshotRotationHistoryPoint[] | Record<string, unknown>;
  rotation_daily_history?: {
    sessions: string[];
    points: SnapshotRotationHistoryPoint[];
    panel_files: Record<string, string>;
    snapshot_ids: string[];
    source: "COMPATIBLE_PUBLIC_SNAPSHOTS";
  };
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
    [key: string]: unknown;
  }>;
  change_digest?: Record<string, unknown>;
  // Per-group evidence (contradictions + screen invalidation) from
  // evidence.json. Absent in legacy payloads; UI falls back to placeholders.
  evidence?: GroupEvidenceRow[];
  // Added 2026-08-30:
  taxonomy_views?: Record<string, TaxonomyView>;
  foreign_flow_sample?: ForeignFlowSample;
  idx_investor_release?: IDXInvestorRelease;
  idx_daily_statistics?: IDXDailyStatistics;
  official_market_context?: OfficialMarketContext | null;
  listing_registry?: ListingRegistry;
  research_events?: ResearchEventBundle;
}
