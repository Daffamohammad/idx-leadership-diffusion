import { useEffect, useState } from "react";
import { useSnapshot } from "./SnapshotProvider";
import { loadReleaseAdditionalFile, loadReleaseAsset, type ReleaseFamily } from "./release";

export interface MarketStock {
  ticker: string; company_name: string; instrument_type: string; analysis_requested: boolean;
  close: number | null; previous_close: number | null; return_1d: number | null; return_1w: number | null;
  market_cap: number | null; traded: boolean; signal_eligible: boolean; history_status: string;
  volume_shares: number | null; value_idr: number | null; frequency_trades: number | null;
  foreign_buy_shares: number | null; foreign_sell_shares: number | null; foreign_net_shares: number | null;
  taxonomy: { sector?: string; subindustry?: string }; classification_as_of: string | null; listing_board: string | null;
}
export interface OwnershipEdge {
  group_id: string; group_name: string; holder: string; ticker: string; percentage: number;
  as_of: string; source: string; relationship: string;
  control_source: { source: string; as_of: string; ultimate_holders?: string[] } | null;
}
export interface MarketWorkspace {
  schema_version: "market-workspace-v1"; snapshot_id: string; as_of: string;
  records: MarketStock[]; benchmark: { date: string; close: number }[];
  breadth: { advancers: number; flat: number; decliners: number; traded_count: number; not_traded_or_unavailable: number; scope: string };
  index_movers: { status: string; reason?: string; residual?: number; calculated_change?: number; official_change?: number; method?: string; source?: string;
    rows: { ticker: string; company_name: string; points: number; return_1d: number | null }[] };
  weekly_start: string; weekly_end: string; ownership_edges: OwnershipEdge[];
  coverage: { requested: number; observed_histories: number; signal_eligible: number; gaps: { failed: string[]; quarantined: string[] } };
  limitations: string[]; sources: Record<string, unknown>;
}

export interface HistoricalComparison {
  schema_version: "historical-comparison-v1" | "historical-comparison-v2"; as_of: string; comparison_dates: string[];
  analysis_dates?: string[];
  title: string; replay_basis: string; membership_as_of: string;
  cohort: { count: number; sha256: string; group_cohorts: Record<string, { count: number; sha256: string }> };
  weekly: { as_of: string; groups: Array<{
    group_id: string; name: string; cohort_count: number; cohort_hash: string;
    excess_return_20d: number; excess_return_60d: number; excess_return_ytd: number;
    relative_momentum: number; breadth_pct: number; breadth_change_pp: number | null;
    leadership: string; diffusion: string; concentration_top3_pct: number | null;
    concentration_change_pp?: number | null; coverage_pct: number;
    leadership_transition?: string | null; diffusion_transition?: string | null; material_shift?: string | null;
  }> }[];
  persistence: Record<string, { current_leadership_weeks: number; observations: number }>;
  sector_baskets: {
    start: string; end: string; basis: string; benchmark: string; benchmark_basis: string;
    series: Array<{ as_of: string; return_pct: number }>;
    groups: Array<{ group_id: string; name: string; contributor_count: number; cohort_hash: string; values: Array<{ as_of: string; return_pct: number }> }>;
  };
  taxonomies?: Record<string, {
    taxonomy_id: string; taxonomy_name: string; taxonomy_version: string; taxonomy_kind: string;
    membership_as_of: string | null; membership_source_basis: string; group_count: number;
    membership_payload_sha256?: string;
    definition_sha256?: string | null;
    groups: Record<string, {
      group_id: string; name: string; member_count: number; definition?: string | null; parent_category?: string | null;
      inclusion_rules?: string[]; exclusion_rules?: string[]; source_activity_ids?: string[];
      membership?: { version: string; source_as_of: string | null; tickers: string[]; count: number; sha256: string; evidence_sha256: string };
      cohort: { contributors: string[]; count: number; sha256: string };
      members: Array<{ ticker: string; name: string; evidence: Array<{
        relationship: string | null; holder: string | null; ownership_percentage: number | null;
        membership_type: string; source: string | null; source_as_of: string | null;
        control_source: { owner?: string; ticker?: string; relationship?: string; as_of?: string; source?: string; ultimate_holders?: string[] } | null;
      }> }>;
      daily: HistoricalReplayPoint[]; weekly: HistoricalReplayPoint[];
      persistence: { current_leadership_weeks: number; observations: number };
    }>;
  }>;
  sources: Record<string, string>; limitations: string[];
}
export interface HistoricalReplayPoint {
  as_of: string;
  excess_return_5d: number | null; excess_return_20d: number | null;
  excess_return_60d: number | null; excess_return_ytd: number | null;
  relative_momentum: number | null;
  breadth_count: number | null; breadth_denominator: number; breadth_pct: number | null;
  breadth_change_count: number | null; breadth_change_pp: number | null;
  leadership: string; diffusion: string; diffusion_v2: string;
  concentration_top3_pct: number | null; concentration_change_pp: number | null;
  rotation_phase: string; coverage_pct: number;
  leadership_transition?: string | null; diffusion_transition?: string | null; material_shift?: string | null;
}

export interface MarketBreadthAsset {
  schema_version: "market-breadth-v1";
  as_of: string;
  official_daily: {
    scope: string;
    breadth: {
      advancers: number; unchanged: number; decliners: number; net_advances: number;
      advancers_to_decliners_ratio: number | null; advancing_pct_of_moving_stocks: number | null;
      moving_stock_count: number; traded_count: number;
    };
    constituents_by_direction: Record<"advancing" | "unchanged" | "declining", Array<{
      ticker: string; company_name: string; return_1d_pct: number; value_idr: number | null;
    }>>;
    traded_value: {
      unit: string; denominator_idr: number; coverage_count: number;
      advancing_idr: number; unchanged_idr: number; declining_idr: number;
      advancing_pct: number | null; unchanged_pct: number | null; declining_pct: number | null;
      denominator: string;
    };
    activity: {
      turnover_idr: number; volume_shares: number | null; volume_lots: number | null; frequency_trades: number | null;
      traded_stock_count: number; volume_coverage_count: number; frequency_coverage_count: number;
      units: Record<string, string>;
      market_scope_totals: {
        provider: string; scope: string; turnover_idr: number; volume_shares: number; volume_lots: number; frequency_trades: number;
        preceding_20_session_average_turnover_idr: number; current_to_average_turnover_multiple: number | null;
        preceding_sessions: number; daily_totals: Array<{ as_of: string; turnover_idr: number; volume_shares: number; frequency_trades: number; source_file: string; source_sha256: string; published_units: Record<string, string>; scope: string }>;
        precision: Record<string, string>;
      };
    };
    market_foreign_flow: {
      provider: string; scope: string; unit: string; as_of: string; daily_net_idr: number | null;
      preceding_20_session_average_absolute_net_idr: number | null; preceding_20_session_count: number;
      direction: string | null; consecutive_sessions: number; daily_series_start: string | null; daily_series_count: number;
    };
  };
  historical_price_breadth: {
    basis: string; start: string; end: string; cohort_count: number; cohort_tickers: string[]; cohort_sha256: string;
    sessions: Array<{ as_of: string; advancers: number | null; unchanged: number | null; decliners: number | null; net_advances: number | null; moving_count: number; eligible_count: number }>;
  };
  new_highs_lows: {
    price_basis: string; selected_session_traded_only: boolean;
    items: Record<string, {
      eligible_count: number; eligible_scope: string; prior_sessions: number; start: string | null; end: string | null;
      new_high_count: number; new_low_count: number; tie_rule: string;
      new_highs: Array<{ ticker: string; company_name: string; close_adjusted_idr: number; prior_range_high_idr: number; prior_range_low_idr: number; change_from_prior_close_pct: number }>;
      new_lows: Array<{ ticker: string; company_name: string; close_adjusted_idr: number; prior_range_high_idr: number; prior_range_low_idr: number; change_from_prior_close_pct: number }>;
    }>;
  };
  sources: Record<string, string>;
  methodology: string[];
  coverage: { official_traded_count: number; fixed_price_cohort_count: number; analysis_benchmark_sessions: number; excluded_signal_eligible_incomplete_history: number; limits: string[] };
}
export interface RecordedSectorsSample {
  schema_version: "sectors-recorded-sample-v1";
  as_of: string;
  label: "Recorded Sectors sample · 66 stocks";
  scope: string;
  selection: {
    basis: string;
    membership_release_id: string;
    membership_release_session: string;
    membership_as_of: string;
    selected_market_cap_date: string;
    stocks_per_sector: 6;
    stock_count: 66;
    sector_counts: Record<string, number>;
    replacements: Record<string, Array<{ removed: string; selected: string; reason: string }>>;
  };
  price_history: {
    start: string; end: string; basis: string; benchmark: string;
    ihsg: Array<{ date: string; close: number; price_basis: string }>;
  };
  foreign_flow: {
    provider: string; scope: string; unit: string;
    market_ytd: { start: string; end: string; values: Array<{ date: string; net_foreign_inflow_idr: number; reported_cumulative_idr?: number | null }> };
    session_check: { expected_sessions: number; observed_sessions: number; duplicates: number; missing: number; missing_dates: string[]; unexpected: number; unexpected_dates: string[]; ytd_complete: boolean };
    expected_market_sessions: string[];
    complete_quarter: { start: string; end: string; values: Array<{ date: string; net_foreign_inflow_idr: number }>; session_check: { expected_sessions: number; observed_sessions: number; missing: number; missing_dates: string[]; duplicates: number; status: string } };
  };
  foreign_reconciliation: {
    official_source: { sha256: string; observation_date: string; provider: string };
    sectors_source: { market_flow_response_hashes: Record<string, string>; observation_date: string; provider: string };
    official_ytd: { as_of: string; total_idr: number; provider: string };
    sectors_ytd: { start: string; end: string; known_value_sum_idr: number; expected_sessions: number; observed_sessions: number; missing_dates: string[]; status: string };
    complete_quarter: { start: string; end: string; session_count: number; official_sum_idr: number; sectors_sum_idr: number; difference_idr: number; status: string };
    limitations: string[];
  };
  stocks: Array<{
    ticker: string; company_name: string | null; sector: string; membership_as_of: string | null;
    market_cap_as_of: string | null; market_cap_idr: number | null;
    prices: Array<{ date: string; close: number }>;
    corporate_actions: { response: unknown };
  }>;
  validation: Record<string, unknown>;
  sources: Record<string, unknown>;
  limitations: string[];
}
export interface Holder {
  row_id: string; ticker: string; issuer: string; holder: string; classification: string;
  local_foreign: string; shares: number; percentage: number; as_of: string;
  identity_ambiguous: boolean; scripless?: number; scrip?: number;
  previous_shares?: number | null; previous_percentage?: number | null; account_count?: number; account_totals_reconciled?: boolean;
}
export interface HoldingChange {
  ticker: string; holder: string; kind: string; current_shares: number | null; previous_shares: number | null;
  current_percentage: number | null; previous_percentage: number | null; delta_shares: number | null;
}
export interface OwnershipWorkspace {
  schema_version: "idx-ownership-v1"; as_of: string; previous_as_of: string; five_as_of: string;
  registers: { one: Holder[]; five: Holder[] }; changes: HoldingChange[];
  sources: { filename: string; sha256: string; url: string; as_of: string }[];
  coverage: { one_rows: number; one_issuers: number; five_rows: number; five_issuers: number; previous_rows: number }; limitations: string[];
}
export interface ForeignHistory {
  schema_version: "idx-foreign-history-v1"; as_of: string; start: string; scope: string; precision_idr: number;
  daily: { as_of: string; net_foreign_value_idr: number; ytd_net_foreign_value_idr: number; source: { url: string; file: string; sha256: string } }[];
  validation: { session_continuity: boolean; ytd_continuity: boolean; monthly_comparisons: unknown[] }; limitations: string[];
}
export function useWorkspaceAsset<T extends { as_of: string }>(key: ReleaseFamily) {
  const snapshot = useSnapshot();
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean; requestKey: string | null }>({ data: null, error: null, loading: true, requestKey: null });
  useEffect(() => {
    let cancelled = false;
    const release = snapshot.release;
    const asset = release?.manifest.families[key];
    const requestKey = release && asset ? `${release.id}:${asset.sha256}` : null;
    if (!release || !asset || !snapshot.snapshotId) {
      setState({ data: null, error: snapshot.error, loading: snapshot.loading, requestKey: null });
      return;
    }
    setState({ data: null, error: null, loading: true, requestKey });
    loadReleaseAsset<T>(release, asset).then(data => {
      if (cancelled) return;
      if ((key === "market" || key === "rotation") && (data as unknown as MarketWorkspace).snapshot_id !== snapshot.snapshotId) {
        throw new Error(`${key} family belongs to a different snapshot`);
      }
      if (key === "ownership" && (data as unknown as OwnershipWorkspace).five_as_of > release.manifest.target_session) {
        throw new Error("Ownership release is later than the selected target session");
      }
      setState({ data, error: null, loading: false, requestKey });
    }).catch(error => {
      if (!cancelled) setState({ data: null, error: String(error.message ?? error), loading: false, requestKey });
    });
    return () => { cancelled = true; };
  }, [key, snapshot.release, snapshot.snapshotId, snapshot.error, snapshot.loading]);
  const selectedKey = snapshot.release ? `${snapshot.release.id}:${snapshot.release.manifest.families[key].sha256}` : null;
  return state.requestKey === selectedKey ? state : { data: null, error: null, loading: true, requestKey: selectedKey };
}

export function useHistoricalComparison() {
  const snapshot = useSnapshot();
  const [state, setState] = useState<{ data: HistoricalComparison | null; error: string | null; loading: boolean; requestKey: string | null }>({ data: null, error: null, loading: true, requestKey: null });
  useEffect(() => {
    let cancelled = false;
    const release = snapshot.release;
    const entry = release?.manifest.additional_files.find(file => file.file_id === "historical_comparison");
    const requestKey = release && entry ? `${release.id}:${entry.sha256}` : null;
    if (!release || !entry) {
      setState({ data: null, error: null, loading: false, requestKey });
      return;
    }
    setState({ data: null, error: null, loading: true, requestKey });
    loadReleaseAdditionalFile<HistoricalComparison>(release, "historical_comparison").then(data => {
      if (cancelled) return;
      if (!data || !["historical-comparison-v1", "historical-comparison-v2"].includes(data.schema_version) || data.as_of !== release.manifest.target_session) {
        throw new Error("Historical comparison does not belong to the selected release");
      }
      setState({ data, error: null, loading: false, requestKey });
    }).catch(error => {
      if (!cancelled) setState({ data: null, error: String(error.message ?? error), loading: false, requestKey });
    });
    return () => { cancelled = true; };
  }, [snapshot.release]);
  const entry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "historical_comparison");
  const selectedKey = snapshot.release && entry ? `${snapshot.release.id}:${entry.sha256}` : null;
  return state.requestKey === selectedKey ? state : { data: null, error: null, loading: true, requestKey: selectedKey };
}

export function useMarketBreadth() {
  const snapshot = useSnapshot();
  const [state, setState] = useState<{ data: MarketBreadthAsset | null; error: string | null; loading: boolean; requestKey: string | null }>({ data: null, error: null, loading: true, requestKey: null });
  useEffect(() => {
    let cancelled = false;
    const release = snapshot.release;
    const entry = release?.manifest.additional_files.find(file => file.file_id === "market_breadth");
    const requestKey = release && entry ? `${release.id}:${entry.sha256}` : null;
    if (!release || !entry) {
      setState({ data: null, error: null, loading: false, requestKey });
      return;
    }
    setState({ data: null, error: null, loading: true, requestKey });
    loadReleaseAdditionalFile<MarketBreadthAsset>(release, "market_breadth").then(data => {
      if (cancelled) return;
      if (!data || data.schema_version !== "market-breadth-v1" || data.as_of !== release.manifest.target_session) {
        throw new Error("Market breadth does not belong to the selected release");
      }
      setState({ data, error: null, loading: false, requestKey });
    }).catch(error => {
      if (!cancelled) setState({ data: null, error: String(error.message ?? error), loading: false, requestKey });
    });
    return () => { cancelled = true; };
  }, [snapshot.release]);
  const entry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "market_breadth");
  const selectedKey = snapshot.release && entry ? `${snapshot.release.id}:${entry.sha256}` : null;
  return state.requestKey === selectedKey ? state : { data: null, error: null, loading: true, requestKey: selectedKey };
}

export function useRecordedSectorsSample() {
  const snapshot = useSnapshot();
  const [state, setState] = useState<{ data: RecordedSectorsSample | null; error: string | null; loading: boolean; requestKey: string | null }>({ data: null, error: null, loading: true, requestKey: null });
  useEffect(() => {
    let cancelled = false;
    const release = snapshot.release;
    const entry = release?.manifest.additional_files.find(file => file.file_id === "sectors_recorded_sample");
    const requestKey = release && entry ? `${release.id}:${entry.sha256}` : null;
    if (!release || !entry) {
      setState({ data: null, error: null, loading: false, requestKey });
      return;
    }
    setState({ data: null, error: null, loading: true, requestKey });
    loadReleaseAdditionalFile<RecordedSectorsSample>(release, "sectors_recorded_sample").then(async data => {
      if (cancelled) return;
      const parentIdHash = data ? await crypto.subtle.digest("SHA-256", new TextEncoder().encode(data.selection.membership_release_id)) : null;
      const parentIdDigest = parentIdHash ? Array.from(new Uint8Array(parentIdHash), byte => byte.toString(16).padStart(2, "0")).join("") : null;
      if (!data || data.schema_version !== "sectors-recorded-sample-v1" ||
          data.label !== "Recorded Sectors sample · 66 stocks" || data.stocks.length !== 66 ||
          Object.values(data.selection.sector_counts).length !== 11 ||
          Object.values(data.selection.sector_counts).some(count => count !== 6) ||
          data.selection.membership_release_session !== release.manifest.target_session ||
          data.sources.market_release_source_sha256 !== release.manifest.families.market.sha256 ||
          parentIdDigest !== release.manifest.analytical_contracts.recording_parent_release_id_sha256) {
        throw new Error("Recorded sample does not match the selected release and frozen 66-stock membership");
      }
      setState({ data, error: null, loading: false, requestKey });
    }).catch(error => {
      if (!cancelled) setState({ data: null, error: String(error.message ?? error), loading: false, requestKey });
    });
    return () => { cancelled = true; };
  }, [snapshot.release]);
  const entry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "sectors_recorded_sample");
  const selectedKey = snapshot.release && entry ? `${snapshot.release.id}:${entry.sha256}` : null;
  return state.requestKey === selectedKey ? state : { data: null, error: null, loading: true, requestKey: selectedKey };
}
