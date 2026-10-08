import { useEffect, useState } from "react";
import { useSnapshot } from "./SnapshotProvider";
import { loadReleaseAdditionalFile, loadReleaseAsset, type ReleaseFamily } from "./release";

export interface MarketStock {
  ticker: string; company_name: string; instrument_type: string; analysis_requested: boolean;
  as_of?: string; last_trade_date?: string;
  close: number | null; previous_close: number | null; return_1d: number | null; return_1w: number | null;
  market_cap: number | null; traded: boolean; signal_eligible: boolean; history_status: string;
  volume_shares: number | null; value_idr: number | null; frequency_trades: number | null;
  foreign_buy_shares: number | null; foreign_sell_shares: number | null; foreign_net_shares: number | null;
  taxonomy: { sector?: string; subindustry?: string }; classification_as_of: string | null; listing_board: string | null;
}
export interface OwnershipEdge {
  group_id: string; group_name: string; holder: string; ticker: string; percentage: number | null;
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
  reading_contract_version?: number;
  price_histories?: Record<string, Array<{date: string; close: number}>>;
  benchmark_history?: Array<{date: string; close: number}>;
  title: string; replay_basis: string; membership_as_of: string;
  cohort: { count: number; sha256: string; group_cohorts: Record<string, { count: number; sha256: string }> };
  weekly: { as_of: string; groups: Array<{
    group_id: string; name: string; cohort_count: number; cohort_hash: string;
    excess_return_20d: number | null; excess_return_60d: number | null; excess_return_ytd: number | null;
    relative_momentum: number | null; breadth_pct: number | null; breadth_change_pp: number | null;
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
      cohorts?: Record<string, string[]>;
      coverage_reasons?: Record<string, string>;
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
  map_x_60d?: number | null; map_x_ytd?: number | null; map_y_ytd?: number | null;
  map_contributors?: number; ytd_map_contributors?: number;
  contributor_counts?: Record<string, number>;
  rotation_phase_ytd?: string;
  breadth_count: number | null; breadth_denominator: number; breadth_pct: number | null;
  breadth_change_count: number | null; breadth_change_pp: number | null;
  leadership: string; diffusion: string; diffusion_v2: string;
  concentration_top3_pct: number | null; concentration_change_pp: number | null;
  concentration_detail?: Array<{ticker: string; return_pct: number; absolute_share_pct: number | null}>;
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
  schema_version: "sectors-recorded-sample-v1" | "sectors-expanded-universe-v1";
  as_of: string;
  label: string;
  scope: string;
  selection: {
    basis: string;
    membership_release_id: string;
    membership_release_session: string;
    membership_as_of: string;
    selected_market_cap_date: string;
    stocks_per_sector: number;
    stock_count: number;
    sector_counts: Record<string, number>;
    replacements: Record<string, Array<{ removed: string; selected: string; reason: string }>>;
    ytd_tickers?: string[];
    expansion_plan_sha256?: string;
  };
  price_history: {
    start: string; end: string; basis: string; benchmark: string;
    ihsg: Array<{ date: string; close: number; price_basis: string }>;
  };
  foreign_flow: {
    provider: string; scope: string; unit: string;
    stock_recent_start: string;
    market_ytd: { start: string; end: string; values: Array<{ date: string; net_foreign_inflow_idr: number; reported_cumulative_idr?: number | null }> };
    session_check: { expected_sessions: number; observed_sessions: number; duplicates: number; missing: number; missing_dates: string[]; unexpected: number; unexpected_dates: string[]; ytd_complete: boolean };
    expected_market_sessions: string[];
    complete_quarter: { start: string; end: string; values: Array<{ date: string; net_foreign_inflow_idr: number }>; session_check: { expected_sessions: number; observed_sessions: number; missing: number; missing_dates: string[]; duplicates: number; status: string } };
    company_flow_coverage?: { stock_count: number; tickers: string[]; start_date: string; end_date: string };
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
    price_sources?: Array<{ window: string[]; path: string; sha256?: string | null }>;
    history_coverage?: { requested_start: string; requested_end: string; observed_start: string | null; observed_end: string | null; window_count: number; price_windows: Array<{ window: string[]; path: string; sha256?: string | null }> };
    corporate_actions: { response: unknown };
    foreign_flow?: unknown;
  }>;
  coverage?: {
    price_history: {
      stock_count: number; stocks_per_sector: number; first_replay_date: string;
      first_required_price_date: string; end_date: string; daily_dates: string[];
      weekly_dates: string[]; per_stock: Record<string, {
        requested_start: string; requested_end: string; observed_start: string | null;
        observed_end: string | null; window_count: number; price_windows: Array<{ window: string[]; path: string; sha256?: string | null }>;
      }>;
    };
    ytd: { stock_count: number; tickers: string[]; baseline_date: string | null; end_date: string; baseline_asset_sha256: string };
    company_flow: { stock_count: number; tickers: string[]; start_date: string; end_date: string };
  };
  validation: Record<string, unknown>;
  sources: Record<string, unknown>;
  limitations: string[];
}
export interface SectorSignalWindow {
  return_pct: number | null;
  excess_return_pct: number | null;
  start_date: string | null;
  end_date: string | null;
  exclusion_reason: string | null;
}
export interface SectorSignalGroup {
  sector: string;
  requested_constituents: number;
  eligible_contributors: number;
  contributor_counts: Record<"5d" | "20d" | "60d", number>;
  comparison_cohorts: {
    leadership_tickers: string[];
    map_tickers: string[];
    diffusion_tickers: string[];
  };
  signal_status: string;
  returns: Record<"5d" | "20d" | "60d", {
    stock_return_pct: number | null;
    benchmark_return_pct: number | null;
    excess_return_pct: number | null;
    eligible_contributors: number;
  }>;
  descriptive_returns?: Record<"5d" | "20d" | "60d", {stock_return_pct: number | null; excess_return_pct: number | null; eligible_contributors: number}>;
  descriptive_map?: SectorSignalGroup["map"];
  map: { cohort_tickers: string[]; eligible_contributors: number; x_60d_excess_pct: number; y_relative_momentum_pct: number } | null;
  diffusion: {
    outperforming_count: number | null;
    previous_outperforming_count: number | null;
    change_count: number | null;
    eligible_count: number;
    breadth_pct: number | null;
    previous_breadth_pct: number | null;
    state: string;
  };
  leadership_state: string;
  concentration_v2: {
    top1_abs_share: number | null; top3_abs_share: number | null; top5_abs_share: number | null;
    hhi: number | null; contributor_count: number; requested_constituent_count: number;
    missing_constituent_count: number; top_absolute_contributor: string | null;
    net_signed_return: number | null; gross_absolute_return: number | null; status: string;
  } | null;
  contributors: Array<{
    ticker: string; company_name: string | null; contributes_20d: boolean;
    contributes_to_leadership: boolean; contributes_to_60d_map: boolean;
    contributes_to_diffusion_comparison: boolean;
    returns: Record<"5d" | "20d" | "60d", SectorSignalWindow>;
  }>;
}
export interface SectorsSignalAnalysis {
  schema_version: "sectors-signal-analysis-v1";
  as_of: string;
  label: string;
  action_events?: Record<string, Array<{date: string; type: string}>>;
  sources: {
    recorded_sample_sha256: string;
    selection_market_source_sha256: string;
    provider: string;
    price_basis: string;
    benchmark: string;
  };
  selection: {
    stock_count: number; stocks_per_sector: number; membership_release_session: string;
    membership_as_of: string; selected_market_cap_date: string; retrospective: boolean;
  };
  coverage?: Record<string, unknown>;
  contract: Record<string, unknown>;
  corporate_action_exclusions: Record<string, Array<{
    ticker: string; first_unavailable_date: string; horizon: string; reason: string;
  }>>;
  comparison_cohort_rule: string;
  ytd: {
    status: string; baseline_date: string | null; source_asset_sha256?: string; reason?: string;
    end_date?: string; benchmark_return_pct?: number | null;
    groups?: Array<{ sector: string; eligible_contributors: number; requested_constituents: number;
      stock_return_pct: number | null; benchmark_return_pct: number | null; excess_return_pct: number | null;
      status: string; contributors: Array<{ ticker: string; return_pct: number | null;
        excess_return_pct: number | null; eligible: boolean; exclusion_reason: string | null }> }>;
  };
  daily: Array<{ date: string; mode: "daily"; previous_date: string | null; groups: SectorSignalGroup[] }>;
  weekly: Array<{ date: string; mode: "weekly"; previous_date: string | null; groups: SectorSignalGroup[] }>;
  methodology: string[];
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
  registers: { one: Holder[]; five: Holder[]; previous_one?: Holder[] }; changes: HoldingChange[];
  sources: { filename: string; sha256: string; url: string; as_of: string }[];
  coverage: { one_rows: number; one_issuers: number; five_rows: number; five_issuers: number; previous_rows: number }; limitations: string[];
}
export interface ForeignHistory {
  schema_version: "idx-foreign-history-v1"; as_of: string; start: string; scope: string; precision_idr: number;
  daily: { as_of: string; net_foreign_value_idr: number; ytd_net_foreign_value_idr: number; source: { url: string; file: string; sha256: string } }[];
  validation: { session_continuity: boolean; ytd_continuity: boolean; monthly_comparisons: unknown[] }; limitations: string[];
}
type WorkspaceAssetState<T> = { data: T | null; error: string | null; loading: boolean; requestKey: string | null };

export function currentWorkspaceState<T>(snapshot: { loading: boolean; error: string | null }, state: WorkspaceAssetState<T>, selectedKey: string | null): WorkspaceAssetState<T> {
  if (snapshot.error || snapshot.loading) return { data: null, error: snapshot.error, loading: snapshot.loading, requestKey: selectedKey };
  return state.requestKey === selectedKey ? state : { data: null, error: null, loading: true, requestKey: selectedKey };
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
  return currentWorkspaceState(snapshot, state, selectedKey);
}

export function useHistoricalComparison(enabled = true) {
  const snapshot = useSnapshot();
  const [state, setState] = useState<{ data: HistoricalComparison | null; error: string | null; loading: boolean; requestKey: string | null }>({ data: null, error: null, loading: true, requestKey: null });
  useEffect(() => {
    let cancelled = false;
    if (!enabled) {setState({data: null, error: null, loading: false, requestKey: null}); return;}
    const release = snapshot.release;
    const entry = release?.manifest.additional_files.find(file => file.file_id === "historical_comparison");
    const requestKey = release && entry ? `${release.id}:${entry.sha256}` : null;
    if (!release || !entry) {
      setState({ data: null, error: snapshot.error, loading: snapshot.loading, requestKey });
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
  }, [enabled, snapshot.release, snapshot.error, snapshot.loading]);
  const entry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "historical_comparison");
  const selectedKey = snapshot.release && entry ? `${snapshot.release.id}:${entry.sha256}` : null;
  return enabled ? currentWorkspaceState(snapshot, state, selectedKey) : {data: null, error: null, loading: false};
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
      setState({ data: null, error: snapshot.error, loading: snapshot.loading, requestKey });
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
  }, [snapshot.release, snapshot.error, snapshot.loading]);
  const entry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "market_breadth");
  const selectedKey = snapshot.release && entry ? `${snapshot.release.id}:${entry.sha256}` : null;
  return currentWorkspaceState(snapshot, state, selectedKey);
}

export function useRecordedSectorsSample(enabled = true) {
  const snapshot = useSnapshot();
  const [state, setState] = useState<{ data: RecordedSectorsSample | null; error: string | null; loading: boolean; requestKey: string | null }>({ data: null, error: null, loading: true, requestKey: null });
  useEffect(() => {
    let cancelled = false;
    if (!enabled) {setState({data: null, error: null, loading: false, requestKey: null}); return;}
    const release = snapshot.release;
    const entry = release?.manifest.additional_files.find(file => file.file_id === "sectors_recorded_sample");
    const selectionEntry = release?.manifest.additional_files.find(file => file.file_id === "sectors_selection_market");
    const requestKey = release && entry ? `${release.id}:${entry.sha256}:${selectionEntry?.sha256 ?? "missing-selection"}` : null;
    if (!release || !entry) {
      setState({ data: null, error: null, loading: false, requestKey });
      return;
    }
    if (!selectionEntry) {
      setState({ data: null, error: "The frozen selection-market asset is missing from this release.", loading: false, requestKey });
      return;
    }
    setState({ data: null, error: null, loading: true, requestKey });
    Promise.all([
      loadReleaseAdditionalFile<RecordedSectorsSample>(release, "sectors_recorded_sample"),
      loadReleaseAdditionalFile<MarketWorkspace>(release, "sectors_selection_market"),
    ]).then(async ([data, selectionMarket]) => {
      if (cancelled) return;
      const parentIdHash = data ? await crypto.subtle.digest("SHA-256", new TextEncoder().encode(data.selection.membership_release_id)) : null;
      const parentIdDigest = parentIdHash ? Array.from(new Uint8Array(parentIdHash), byte => byte.toString(16).padStart(2, "0")).join("") : null;
      const expectedCount = Number(data?.selection?.stock_count ?? 0);
      const stocksPerSector = Number(data?.selection?.stocks_per_sector ?? 0);
      const supportedSchema = data?.schema_version === "sectors-recorded-sample-v1" || data?.schema_version === "sectors-expanded-universe-v1";
      if (!data || !supportedSchema ||
          !selectionMarket || selectionMarket.schema_version !== "market-workspace-v1" ||
          ![66, 132].includes(expectedCount) || data.stocks.length !== expectedCount ||
          stocksPerSector * 11 !== expectedCount ||
          (data.schema_version === "sectors-recorded-sample-v1" && expectedCount !== 66) ||
          (data.schema_version === "sectors-expanded-universe-v1" && expectedCount !== 132) ||
          Object.values(data.selection.sector_counts).length !== 11 ||
          Object.values(data.selection.sector_counts).some(count => count !== stocksPerSector) ||
          data.selection.membership_release_session !== release.manifest.target_session ||
          data.selection.selected_market_cap_date !== selectionMarket.as_of ||
          data.sources.market_release_source_sha256 !== selectionEntry.sha256 ||
          parentIdDigest !== release.manifest.analytical_contracts.recording_parent_release_id_sha256) {
        throw new Error("The Sectors stock set does not match its market ranking and source files");
      }
      const eligibleBySector = new Map<string, MarketStock[]>();
      for (const row of selectionMarket.records) {
        const sector = row.taxonomy?.sector;
        const ticker = row.ticker.toUpperCase();
        if (!sector || row.instrument_type !== "LISTED_STOCK" || row.signal_eligible !== true ||
            row.traded !== true || row.last_trade_date !== selectionMarket.as_of ||
            !Number.isFinite(row.close) || Number(row.close) <= 0 ||
            !Number.isFinite(row.market_cap) || Number(row.market_cap) <= 0 ||
            !/^[A-Z]{4,6}\.JK$/.test(ticker)) continue;
        eligibleBySector.set(sector, [...(eligibleBySector.get(sector) ?? []), row]);
      }
      const actualBySector = new Map<string, Set<string>>();
      for (const stock of data.stocks) {
        const members = actualBySector.get(stock.sector) ?? new Set<string>();
        members.add(stock.ticker.toUpperCase());
        actualBySector.set(stock.sector, members);
      }
      if (eligibleBySector.size !== 11 || actualBySector.size !== 11) {
        throw new Error("The pinned market source does not contain all 11 sectors");
      }
      for (const [sector, rows] of eligibleBySector) {
        const ranked = [...rows].sort((left, right) =>
          (Number(right.market_cap) - Number(left.market_cap)) || left.ticker.localeCompare(right.ticker));
        const selected = new Set(ranked.slice(0, stocksPerSector).map(row => row.ticker.toUpperCase()));
        for (const replacement of data.selection.replacements[sector] ?? []) {
          if (!selected.has(replacement.removed.toUpperCase()) ||
              !ranked.slice(stocksPerSector).some(row => row.ticker.toUpperCase() === replacement.selected.toUpperCase())) {
            throw new Error(`The selected replacement is not supported by market evidence for ${sector}`);
          }
          selected.delete(replacement.removed.toUpperCase());
          selected.add(replacement.selected.toUpperCase());
        }
        const actual = actualBySector.get(sector);
        if (!actual || actual.size !== stocksPerSector || [...actual].some(ticker => !selected.has(ticker)) || selected.size !== actual.size) {
          throw new Error(`Stock membership does not match the frozen ${stocksPerSector}-stock selection for ${sector}`);
        }
      }
      if (data.schema_version === "sectors-expanded-universe-v1") {
        const perStock = data.coverage?.price_history?.per_stock;
        const stockTickers = new Set(data.stocks.map(stock => stock.ticker));
        const ytdTickers = new Set(data.coverage?.ytd?.tickers ?? []);
        const flowTickers = new Set(data.coverage?.company_flow?.tickers ?? []);
        if (!perStock || Object.keys(perStock).length !== expectedCount ||
            data.selection.ytd_tickers?.length !== 66 || new Set(data.selection.ytd_tickers).size !== 66 ||
            data.coverage?.ytd?.stock_count !== 66 || ytdTickers.size !== 66 ||
            data.coverage?.company_flow?.stock_count !== 66 ||
            flowTickers.size !== 66 ||
            data.coverage.price_history.stock_count !== expectedCount ||
            Object.keys(perStock).some(ticker => !stockTickers.has(ticker)) ||
            [...stockTickers].some(ticker => !perStock[ticker]) ||
            [...ytdTickers].some(ticker => !stockTickers.has(ticker)) ||
            [...flowTickers].some(ticker => !stockTickers.has(ticker)) ||
            Object.values(perStock).some(dates => !dates.requested_start || dates.requested_end !== data.as_of)) {
          throw new Error("Expanded coverage dates or the narrower YTD and company-flow coverage are incomplete");
        }
      }
      setState({ data, error: null, loading: false, requestKey });
    }).catch(error => {
      if (!cancelled) setState({ data: null, error: String(error.message ?? error), loading: false, requestKey });
    });
    return () => { cancelled = true; };
  }, [enabled, snapshot.release]);
  const entry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "sectors_recorded_sample");
  const selectionEntry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "sectors_selection_market");
  const selectedKey = snapshot.release && entry ? `${snapshot.release.id}:${entry.sha256}:${selectionEntry?.sha256 ?? "missing-selection"}` : null;
  return enabled ? currentWorkspaceState(snapshot, state, selectedKey) : {data: null, error: null, loading: false};
}

export function useSectorsSignalAnalysis(enabled = true) {
  const snapshot = useSnapshot();
  const sampleState = useRecordedSectorsSample(enabled);
  const [state, setState] = useState<{ data: SectorsSignalAnalysis | null; error: string | null; loading: boolean; requestKey: string | null }>({ data: null, error: null, loading: true, requestKey: null });
  useEffect(() => {
    let cancelled = false;
    if (!enabled) {setState({data: null, error: null, loading: false, requestKey: null}); return;}
    const release = snapshot.release;
    const entry = release?.manifest.additional_files.find(file => file.file_id === "sectors_signal_analysis");
    const sampleEntry = release?.manifest.additional_files.find(file => file.file_id === "sectors_recorded_sample");
    const selectionEntry = release?.manifest.additional_files.find(file => file.file_id === "sectors_selection_market");
    const ytdEntry = release?.manifest.additional_files.find(file => file.file_id === "sectors_ytd_baseline");
    const selectedSample = sampleState.data;
    const requestKey = release && entry ? `${release.id}:${entry.sha256}:${sampleEntry?.sha256 ?? "missing-sample"}:${selectionEntry?.sha256 ?? "missing-selection"}:${ytdEntry?.sha256 ?? "no-ytd-baseline"}` : null;
    if (!release || sampleState.loading) {
      setState({ data: null, error: null, loading: true, requestKey });
      return;
    }
    if (sampleState.error) {
      setState({ data: null, error: sampleState.error, loading: false, requestKey });
      return;
    }
    if (!selectedSample) {
      setState({ data: null, error: null, loading: false, requestKey });
      return;
    }
    if (!entry) {
      setState({ data: null, error: null, loading: false, requestKey });
      return;
    }
    if (!sampleEntry || !selectionEntry) {
      setState({ data: null, error: "One of the Sectors analysis frozen source assets is missing.", loading: false, requestKey });
      return;
    }
    setState({ data: null, error: null, loading: true, requestKey });
    Promise.all([
      loadReleaseAdditionalFile<SectorsSignalAnalysis>(release, "sectors_signal_analysis"),
      ytdEntry ? loadReleaseAdditionalFile<Record<string, unknown>>(release, "sectors_ytd_baseline") : Promise.resolve(null),
    ]).then(([data, ytdBaseline]) => {
      if (cancelled) return;
      if (!data || data.schema_version !== "sectors-signal-analysis-v1" ||
          data.as_of !== release.manifest.target_session ||
          data.sources.recorded_sample_sha256 !== sampleEntry.sha256 ||
          data.sources.selection_market_source_sha256 !== selectionEntry.sha256 ||
          data.selection.stock_count !== selectedSample.selection.stock_count ||
          data.selection.stocks_per_sector !== selectedSample.selection.stocks_per_sector ||
          data.selection.retrospective !== true ||
          !Array.isArray(data.daily) || !data.daily.length || !Array.isArray(data.weekly) || !data.weekly.length) {
          throw new Error("Sectors analysis does not match the selected release, stock set, and market source");
      }
      if (ytdEntry) {
        if (!ytdBaseline || ytdBaseline.schema_version !== "sectors-ytd-baseline-v1" ||
            data.ytd.status === "NOT_AVAILABLE" || data.ytd.source_asset_sha256 !== ytdEntry.sha256 ||
            data.ytd.baseline_date !== ytdBaseline.baseline_date ||
            (ytdBaseline.ihsg as Record<string, unknown> | undefined)?.date !== data.ytd.baseline_date) {
          throw new Error("Sectors YTD analysis does not match its hash-bound native baseline asset");
        }
      } else if (data.ytd.status !== "NOT_AVAILABLE" || data.ytd.source_asset_sha256) {
        throw new Error("Sectors analysis contains YTD readings without a hash-bound baseline asset");
      }
      setState({ data, error: null, loading: false, requestKey });
    }).catch(error => {
      if (!cancelled) setState({ data: null, error: String(error.message ?? error), loading: false, requestKey });
    });
    return () => { cancelled = true; };
  }, [enabled, snapshot.release, sampleState.data, sampleState.error, sampleState.loading]);
  const entry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "sectors_signal_analysis");
  const sampleEntry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "sectors_recorded_sample");
  const selectionEntry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "sectors_selection_market");
  const ytdEntry = snapshot.release?.manifest.additional_files.find(file => file.file_id === "sectors_ytd_baseline");
  const selectedKey = snapshot.release && entry
    ? `${snapshot.release.id}:${entry.sha256}:${sampleEntry?.sha256 ?? "missing-sample"}:${selectionEntry?.sha256 ?? "missing-selection"}:${ytdEntry?.sha256 ?? "no-ytd-baseline"}`
    : null;
  return enabled ? currentWorkspaceState(snapshot, state, selectedKey) : {data: null, error: null, loading: false};
}
