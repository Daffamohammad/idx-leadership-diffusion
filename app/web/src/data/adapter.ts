// Adapter from real snapshot JSON (SnapshotPayload) into the shapes the
// Figma-designed pages consume (SectorData, materialChanges, etc.).
//
// The snapshot carries the fields needed for the leadership tape. Optional
// history and enrichment remain empty unless the exporter emits real source
// observations. Constituent rows are derived from the exported feature and
// security-master tables at this presentation boundary.

import type {
  DiffusionState,
  FeatureRow,
  ForeignFlowDirection,
  ForeignFlowObservation,
  ForeignFlowSample,
  LeadershipState,
  ResearchEventBundle,
  ResearchEventRow,
  SnapshotPayload,
  SnapshotBreadthHistoryPoint,
  GroupPriceHistoryPoint,
  TaxonomyGroupAggregate,
  TaxonomyMembershipData,
  TaxonomyMembershipType,
  TaxonomyKind,
  TaxonomyView,
} from "./snapshot";

export type { DiffusionState, LeadershipState } from "./snapshot";

export type FlowState = "CONFIRMING" | "NEUTRAL" | "AGAINST" | "DATA_GAP";
export interface SectorData {
  id: string;
  name: string;
  parent?: string;
  leadership: LeadershipState;
  prevLeadership?: LeadershipState;
  diffusion: DiffusionState;
  prevDiffusion?: DiffusionState;
  excess20d: number | null;
  excess60d: number | null;
  breadth: number | null;
  prevBreadth?: number;
  concentration: number | null;
  persistence: number;
  constituents: number;
  eligibleConstituents: number;
  missingConstituents: number;
  rank: number | null;
  prevRank?: number;
  fundamentals: "SUPPORTIVE" | "NEUTRAL" | "MIXED" | "WEAK" | "DATA_GAP";
  foreignFlow: FlowState;
  interpretation: string;
}

export interface ConstituentData {
  ticker: string;
  name: string;
  return20d: number | null;
  excess20d: number | null;
  excess60d: number | null;
  participating: boolean | null;
  contribution: number | null;
  foreignFlow: FlowState;
}

export type BreadthHistoryPoint = SnapshotBreadthHistoryPoint;
export type GroupPricePoint = GroupPriceHistoryPoint;

export interface DataSources {
  breadthHistory: boolean;
  constituents: boolean;
  fundamentals: boolean;
  foreignFlow: boolean;
  trajectory: boolean;
}

export interface CoverageHonest {
  raw_candidate_constituents: number;
  policy_eligible_constituents: number;
  observed_eligible_features: number;
  acquisition_failed_constituents: number;
  coverage_pct: number;
  coverage_gate_60pct_met: boolean;
  taxonomy_coverage_pct?: number;
}

export interface TaxonomyGroupData {
  id: string;
  name: string;
  taxonomyId: string;
  taxonomyName: string;
  taxonomyKind: TaxonomyKind;
  taxonomyVersion: string;
  sourceKind: string;
  prototype: boolean;
  leadership: string;
  diffusion: string;
  excess20d: number | null;
  excess60d: number | null;
  breadth: number | null;
  prevBreadth: number | null;
  breadthDelta: number | null;
  constituents: number;
  eligible: number;
  coveragePct: number;
  concentration: number | null;
  mapX: number | null;
  mapY: number | null;
  offScale: boolean;
  dataQuality: string;
  sampleForeignFlowIdr: number | null;
  sampleForeignFlowDirection: ForeignFlowDirection | null;
  breakdown: Record<string, number>;
  memberships: TaxonomyMembershipData[];
}

export interface ForeignFlowMarketSummary {
  asOf: string;
  netValueIdr: number;
  direction: ForeignFlowDirection;
  coverageScope: string;
  sourceUrl: string;
  sourceName: string;
}

export interface ForeignFlowCompanySummary {
  asOf: string;
  ticker: string;
  groupId: string | null;
  netValueIdr: number;
  direction: ForeignFlowDirection;
  sourceUrl: string;
  sourceName: string;
}

export interface ForeignFlowGroupSummaryRow {
  asOf: string;
  groupId: string;
  netValueIdr: number;
  direction: ForeignFlowDirection;
  observedCompanyCount: number;
  positiveCompanyCount: number;
  negativeCompanyCount: number;
}

export interface ForeignFlowAdapted {
  schemaVersion: string;
  providerMode: string;
  status: string;
  asOfMin: string;
  asOfMax: string;
  coverageLabel: string;
  marketDayCount: number;
  companyObservationCount: number;
  mappedCompanyObservationPct: number;
  uniqueCompanyTickerCount: number;
  unmappedTickers: string[];
  signalEligible: boolean;
  coverageGateMet: boolean;
  regimeDiversity: boolean;
  lastSampleDirection: ForeignFlowDirection;
  lastMarketDirection: ForeignFlowDirection;
  marketSampleAligned: boolean;
  breadth: {
    samplePositiveDayCount: number;
    sampleNegativeDayCount: number;
    marketPositiveDayCount: number;
    marketNegativeDayCount: number;
  };
  marketDaily: ForeignFlowMarketSummary[];
  companyDaily: ForeignFlowSampleDaily[];
  groupSummaries: ForeignFlowGroupSummaryRow[];
  rolling: Array<{
    asOf: string;
    rollingNetIdr: number;
    windowSize: number;
    direction: ForeignFlowDirection;
  }>;
  provenance: Array<{ sourceUrl: string; sourceName: string; observedRows: number }>;
  topBuys: ForeignFlowCompanySummary[];
  topSells: ForeignFlowCompanySummary[];
  limitations: string[];
}

export interface ForeignFlowSampleDaily {
  asOf: string;
  sampleNetIdr: number;
  direction: ForeignFlowDirection;
  observedCompanyCount: number;
  mappedCompanyCount: number;
  positiveCompanyCount: number;
  negativeCompanyCount: number;
  coverageScope: string;
}

export interface ResearchEventView {
  eventId: string;
  eventDate: string;
  publishedAt: string;
  ticker: string;
  category: string;
  title: string;
  summary: string;
  sourceUrl: string;
  sourceName: string;
  provider: string;
  quantitativeUse: boolean;
  kongloId: string | null;
  themeIds: string[];
}

export interface AdaptedSnapshot {
  payload: SnapshotPayload;
  sectors: SectorData[];
  materialChanges: SectorData[];
  breadthHistory: BreadthHistoryPoint[];
  groupPriceHistory: Record<string, GroupPricePoint[]>;
  tickerPriceHistory: Record<string, GroupPricePoint[]>;
  trajectoryData: Record<string, Array<{ x: number; y: number; label?: string }>>;
  dataSources: DataSources;
  trajectoryAvailable: boolean;
  coverageHonest: CoverageHonest;
  constituentsByGroup: Record<string, ConstituentData[]>;
  featureLookup: Record<string, FeatureRow>;
  securityLookup: Record<string, { name: string; group_id: string; sector: string }>;
  taxonomyViews: Record<string, TaxonomyView>;
  taxonomyGroups: Record<string, TaxonomyGroupData>;
  activeTaxonomyId: string | null;
  foreignFlow: ForeignFlowAdapted | null;
  researchEvents: ResearchEventView[];
}

function normalizeBreadthHistory(value: unknown): BreadthHistoryPoint[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const candidate = item as Record<string, unknown>;
    const groupId = candidate.group_id;
    const asOf = candidate.as_of;
    const breadth = candidate.breadth;
    const excess = candidate.group_excess_return_20d;
    if (
      typeof groupId !== "string" ||
      groupId.length === 0 ||
      typeof asOf !== "string" ||
      asOf.length === 0 ||
      typeof breadth !== "number" ||
      !Number.isFinite(breadth) ||
      breadth < 0 ||
      breadth > 100
    ) {
      return [];
    }
    if (
      excess !== null &&
      excess !== undefined &&
      (typeof excess !== "number" || !Number.isFinite(excess))
    ) {
      return [];
    }
    return [
      {
        group_id: groupId,
        as_of: asOf,
        breadth,
        group_excess_return_20d: excess ?? null,
      },
    ];
  });
}

function normalizeGroupPriceHistory(value: unknown): Record<string, GroupPricePoint[]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const output: Record<string, GroupPricePoint[]> = {};
  for (const [groupId, rawPoints] of Object.entries(value)) {
    if (!Array.isArray(rawPoints)) continue;
    const points = rawPoints.flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const candidate = item as Record<string, unknown>;
      const date = candidate.date;
      const value = candidate.value;
      const benchmark = candidate.benchmark;
      if (
        typeof date !== "string" ||
        date.length === 0 ||
        typeof value !== "number" ||
        !Number.isFinite(value) ||
        value <= 0
      ) {
        return [];
      }
      if (
        benchmark !== null &&
        benchmark !== undefined &&
        (typeof benchmark !== "number" || !Number.isFinite(benchmark) || benchmark <= 0)
      ) {
        return [];
      }
      return [{ date, value, benchmark: benchmark ?? null }];
    });
    if (points.length > 0) output[groupId] = points;
  }
  return output;
}

function normalizeTaxonomyGroupAggregate(
  value: unknown,
  fallbackView: TaxonomyView | null,
): TaxonomyGroupAggregate | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const id = raw.taxonomy_group_id;
  if (typeof id !== "string" || id.length === 0) return null;
  const number = (v: unknown): number | null =>
    typeof v === "number" && Number.isFinite(v) ? v : null;
  const string = (v: unknown, fallback = ""): string =>
    typeof v === "string" && v.length > 0 ? v : fallback;
  const boolean = (v: unknown, fallback = false): boolean =>
    typeof v === "boolean" ? v : fallback;
  return {
    taxonomy_group_id: id,
    taxonomy_group_name: string(raw.taxonomy_group_name, id),
    constituent_count:
      typeof raw.constituent_count === "number" ? raw.constituent_count : 0,
    eligible_constituent_count:
      typeof raw.eligible_constituent_count === "number"
        ? raw.eligible_constituent_count
        : 0,
    coverage_pct:
      typeof raw.coverage_pct === "number" ? raw.coverage_pct : 0,
    equal_weight_return_20d: number(raw.equal_weight_return_20d),
    equal_weight_return_60d: number(raw.equal_weight_return_60d),
    excess_return_20d: number(raw.excess_return_20d),
    excess_return_60d: number(raw.excess_return_60d),
    benchmark_return_20d: number(raw.benchmark_return_20d),
    benchmark_return_60d: number(raw.benchmark_return_60d),
    breadth_outperforming: number(raw.breadth_outperforming),
    prev_breadth_outperforming: number(raw.prev_breadth_outperforming),
    breadth_delta: number(raw.breadth_delta),
    leadership_state: string(raw.leadership_state, "UNCONFIRMED"),
    diffusion_state: string(raw.diffusion_state, "UNCONFIRMED"),
    concentration_top3: number(raw.concentration_top3),
    map_x: number(raw.map_x),
    map_y: number(raw.map_y),
    off_scale: boolean(raw.off_scale),
    data_quality: string(raw.data_quality, "DATA_GAP"),
    prototype: boolean(raw.prototype, fallbackView?.taxonomy_kind !== "SECTOR"),
    membership_kind_breakdown:
      typeof raw.membership_kind_breakdown === "object" &&
      raw.membership_kind_breakdown !== null
        ? (raw.membership_kind_breakdown as Record<string, number>)
        : {},
    sample_foreign_flow_idr: number(raw.sample_foreign_flow_idr),
    sample_foreign_flow_direction:
      typeof raw.sample_foreign_flow_direction === "string"
        ? (raw.sample_foreign_flow_direction as ForeignFlowDirection)
        : null,
  };
}

function normalizeTaxonomyView(value: unknown): TaxonomyView | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  if (typeof raw.taxonomy_id !== "string") return null;
  const groups = Array.isArray(raw.groups)
    ? raw.groups
        .map((group) =>
          normalizeTaxonomyGroupAggregate(group, raw as unknown as TaxonomyView),
        )
        .filter((group): group is TaxonomyGroupAggregate => group !== null)
    : [];
  const kindRaw = typeof raw.taxonomy_kind === "string"
    ? raw.taxonomy_kind.toUpperCase()
    : "SECTOR";
  const memberships = Array.isArray(raw.memberships)
    ? raw.memberships.flatMap((membership): TaxonomyMembershipData[] => {
        if (!membership || typeof membership !== "object") return [];
        const item = membership as Record<string, unknown>;
        if (typeof item.ticker !== "string" || typeof item.taxonomy_group_id !== "string") {
          return [];
        }
        const membershipType = typeof item.membership_type === "string"
          ? item.membership_type.toUpperCase()
          : "PRIMARY";
        return [{
          ticker: item.ticker,
          taxonomy_group_id: item.taxonomy_group_id,
          taxonomy_group_name:
            typeof item.taxonomy_group_name === "string"
              ? item.taxonomy_group_name
              : item.taxonomy_group_id,
          membership_type: (["PRIMARY", "SECONDARY", "EXCLUDED"].includes(membershipType)
            ? membershipType
            : "PRIMARY") as TaxonomyMembershipType,
          confidence:
            typeof item.confidence === "number" && Number.isFinite(item.confidence)
              ? item.confidence
              : 1,
          source: typeof item.source === "string" ? item.source : "",
          source_as_of: typeof item.source_as_of === "string" ? item.source_as_of : null,
        }];
      })
    : [];
  return {
    schema_version: typeof raw.schema_version === "string" ? raw.schema_version : "taxonomy-view-v1",
    taxonomy_id: raw.taxonomy_id,
    taxonomy_name:
      typeof raw.taxonomy_name === "string" ? raw.taxonomy_name : raw.taxonomy_id,
    taxonomy_version:
      typeof raw.taxonomy_version === "string"
        ? raw.taxonomy_version
        : "prototype-v1",
    taxonomy_kind: (["SECTOR", "KONGLO", "THEMES"].includes(kindRaw)
      ? kindRaw
      : "SECTOR") as TaxonomyKind,
    source_kind:
      typeof raw.source_kind === "string"
        ? (raw.source_kind as TaxonomyView["source_kind"])
        : "PROTOTYPE_CONFIG",
    membership_policy:
      typeof raw.membership_policy === "string"
        ? raw.membership_policy
        : "PRIMARY_ONLY",
    provider_mode:
      typeof raw.provider_mode === "string" ? raw.provider_mode : "PUBLIC_PROTOTYPE",
    snapshot_provider_mode:
      typeof raw.snapshot_provider_mode === "string"
        ? raw.snapshot_provider_mode
        : undefined,
    taxonomy_definition_provider_mode:
      typeof raw.taxonomy_definition_provider_mode === "string"
        ? raw.taxonomy_definition_provider_mode
        : undefined,
    source_snapshot_id:
      typeof raw.source_snapshot_id === "string"
        ? raw.source_snapshot_id
        : undefined,
    source_snapshot_price_basis:
      typeof raw.source_snapshot_price_basis === "string"
        ? raw.source_snapshot_price_basis
        : undefined,
    previous_snapshot_id:
      typeof raw.previous_snapshot_id === "string"
        ? raw.previous_snapshot_id
        : null,
    point_in_time_eligible:
      typeof raw.point_in_time_eligible === "boolean"
        ? raw.point_in_time_eligible
        : undefined,
    benchmark_id: typeof raw.benchmark_id === "string" ? raw.benchmark_id : "^JKSE",
    as_of: typeof raw.as_of === "string" ? raw.as_of : null,
    coverage:
      typeof raw.coverage === "object" && raw.coverage !== null
        ? (raw.coverage as Record<string, unknown>)
        : undefined,
    calculation:
      typeof raw.calculation === "object" && raw.calculation !== null
        ? (raw.calculation as Record<string, unknown>)
        : undefined,
    calculation_coverage:
      typeof raw.calculation_coverage === "object" &&
      raw.calculation_coverage !== null
        ? (raw.calculation_coverage as Record<string, unknown>)
        : undefined,
    comparability:
      typeof raw.comparability === "object" && raw.comparability !== null
        ? (raw.comparability as Record<string, unknown>)
        : undefined,
    memberships,
    groups,
  };
}

function adaptTaxonomyView(view: TaxonomyView): {
  groupData: Record<string, TaxonomyGroupData>;
  primary: TaxonomyGroupData | null;
} {
  const groupData: Record<string, TaxonomyGroupData> = {};
  let primary: TaxonomyGroupData | null = null;
  for (const group of view.groups) {
    const memberships = (view.memberships ?? []).filter(
      (membership) => membership.taxonomy_group_id === group.taxonomy_group_id,
    );
    const data: TaxonomyGroupData = {
      id: group.taxonomy_group_id,
      name: group.taxonomy_group_name,
      taxonomyId: view.taxonomy_id,
      taxonomyName: view.taxonomy_name,
      taxonomyKind: view.taxonomy_kind,
      taxonomyVersion: view.taxonomy_version,
      sourceKind: view.source_kind,
      prototype: group.prototype,
      leadership: group.leadership_state,
      diffusion: group.diffusion_state,
      excess20d: group.excess_return_20d,
      excess60d: group.excess_return_60d,
      breadth: group.breadth_outperforming,
      prevBreadth: group.prev_breadth_outperforming,
      breadthDelta: group.breadth_delta,
      constituents: group.constituent_count,
      eligible: group.eligible_constituent_count,
      coveragePct: group.coverage_pct,
      concentration: group.concentration_top3,
      mapX: group.map_x,
      mapY: group.map_y,
      offScale: group.off_scale,
      dataQuality: group.data_quality,
      sampleForeignFlowIdr:
        typeof group.sample_foreign_flow_idr === "number"
          ? group.sample_foreign_flow_idr
          : null,
      sampleForeignFlowDirection: group.sample_foreign_flow_direction ?? null,
      breakdown: group.membership_kind_breakdown ?? {},
      memberships,
    };
    groupData[group.taxonomy_group_id] = data;
    if (!primary || data.constituents > primary.constituents) {
      primary = data;
    }
  }
  return { groupData, primary };
}

const FOREIGN_FLOW_DIRECTIONS: ForeignFlowDirection[] = [
  "NET_BUY",
  "NET_SELL",
  "FLAT",
  "UNCONFIRMED",
];

function normalizeForeignDirection(value: unknown): ForeignFlowDirection {
  if (typeof value !== "string") return "UNCONFIRMED";
  const upper = value.toUpperCase() as ForeignFlowDirection;
  return FOREIGN_FLOW_DIRECTIONS.includes(upper) ? upper : "UNCONFIRMED";
}

function adaptForeignFlow(
  payload: ForeignFlowSample | undefined,
): ForeignFlowAdapted | null {
  if (!payload) return null;
  const coverage = payload.coverage ?? {
    market_observation_count: 0,
    market_day_count: 0,
    company_observation_count: 0,
    unique_company_ticker_count: 0,
    mapped_company_observation_count: 0,
    mapped_ticker_count: 0,
    unmapped_tickers: [],
    mapped_company_observation_pct: 0,
    coverage_label: "SAMPLE_ONLY_NOT_FULL_UNIVERSE",
    synthetic_test_rows: 0,
  };
  const breadth = payload.breadth_observed ?? {
    sample_positive_day_count: 0,
    sample_negative_day_count: 0,
    market_positive_day_count: 0,
    market_negative_day_count: 0,
    last_sample_direction: "UNCONFIRMED",
    last_market_direction: "UNCONFIRMED",
    market_sample_aligned: false,
  };
  const signal = payload.signal_eligibility ?? {
    market_day_count: coverage.market_day_count,
    company_observation_count: coverage.company_observation_count,
    mapped_company_observation_pct: coverage.mapped_company_observation_pct,
    coverage_gate_met: false,
    regime_diversity: false,
    signal_eligible: false,
    missing_dates: [],
    stale_dates: [],
    market_days_meets_threshold: false,
    company_rows_meets_threshold: false,
    mapped_pct_meets_threshold: false,
  };
  const companyRows = Array.isArray(payload.company_observations)
    ? payload.company_observations
    : [];
  const latestCompanyAsOf = companyRows.reduce(
    (latest, row) => (row.as_of > latest ? row.as_of : latest),
    "",
  );
  const topBuys: ForeignFlowCompanySummary[] = companyRows
    .filter((row) => row.as_of === latestCompanyAsOf)
    .filter((row) => (row.net_value_idr ?? 0) > 0)
    .sort(
      (a, b) =>
        (b.net_value_idr ?? 0) - (a.net_value_idr ?? 0),
    )
    .slice(0, 5)
    .map((row) => ({
      asOf: row.as_of,
      ticker: row.ticker ?? "",
      groupId: row.group_id,
      netValueIdr: row.net_value_idr ?? 0,
      direction: normalizeForeignDirection(row.direction),
      sourceUrl: row.source_url,
      sourceName: row.source_name,
    }));
  const topSells: ForeignFlowCompanySummary[] = companyRows
    .filter((row) => row.as_of === latestCompanyAsOf)
    .filter((row) => (row.net_value_idr ?? 0) < 0)
    .sort(
      (a, b) =>
        (a.net_value_idr ?? 0) - (b.net_value_idr ?? 0),
    )
    .slice(0, 5)
    .map((row) => ({
      asOf: row.as_of,
      ticker: row.ticker ?? "",
      groupId: row.group_id,
      netValueIdr: row.net_value_idr ?? 0,
      direction: normalizeForeignDirection(row.direction),
      sourceUrl: row.source_url,
      sourceName: row.source_name,
    }));
  return {
    schemaVersion: payload.schema_version,
    providerMode: payload.provider_mode,
    status: payload.status,
    asOfMin: payload.as_of?.min ?? "",
    asOfMax: payload.as_of?.max ?? "",
    coverageLabel: coverage.coverage_label,
    marketDayCount: coverage.market_day_count,
    companyObservationCount: coverage.company_observation_count,
    mappedCompanyObservationPct: coverage.mapped_company_observation_pct,
    uniqueCompanyTickerCount: coverage.unique_company_ticker_count,
    unmappedTickers: coverage.unmapped_tickers,
    signalEligible: signal.signal_eligible,
    coverageGateMet: signal.coverage_gate_met,
    regimeDiversity: signal.regime_diversity,
    lastSampleDirection: normalizeForeignDirection(breadth.last_sample_direction),
    lastMarketDirection: normalizeForeignDirection(breadth.last_market_direction),
    marketSampleAligned: breadth.market_sample_aligned,
    breadth: {
      samplePositiveDayCount: breadth.sample_positive_day_count,
      sampleNegativeDayCount: breadth.sample_negative_day_count,
      marketPositiveDayCount: breadth.market_positive_day_count,
      marketNegativeDayCount: breadth.market_negative_day_count,
    },
    marketDaily: (payload.daily_market_totals ?? []).map((row) => ({
      asOf: row.as_of,
      netValueIdr: row.net_value_idr,
      direction: normalizeForeignDirection(row.direction),
      coverageScope: row.coverage_scope,
      sourceUrl:
        (payload.market_observations ?? []).find((r) => r.as_of === row.as_of)
          ?.source_url ?? "",
      sourceName:
        (payload.market_observations ?? []).find((r) => r.as_of === row.as_of)
          ?.source_name ?? "",
    })),
    companyDaily: (payload.daily_company_samples ?? []).map((row) => ({
      asOf: row.as_of,
      sampleNetIdr: row.sample_net_value_idr,
      direction: normalizeForeignDirection(row.direction),
      observedCompanyCount: row.observed_company_count,
      mappedCompanyCount: row.mapped_company_count,
      positiveCompanyCount: row.positive_company_count,
      negativeCompanyCount: row.negative_company_count,
      coverageScope: row.coverage_scope,
    })),
    groupSummaries: (payload.group_summaries ?? []).map((row) => ({
      asOf: row.as_of,
      groupId: row.group_id,
      netValueIdr: row.net_value_idr,
      direction: normalizeForeignDirection(row.direction),
      observedCompanyCount: row.observed_company_count,
      positiveCompanyCount: row.positive_company_count,
      negativeCompanyCount: row.negative_company_count,
    })),
    rolling: (payload.rolling_sample_flow ?? []).map((row) => ({
      asOf: row.as_of,
      rollingNetIdr: row.rolling_3d_sample_net_value_idr,
      windowSize: row.window_size,
      direction: normalizeForeignDirection(row.direction),
    })),
    provenance: (payload.provenance ?? []).map((row) => ({
      sourceUrl: row.source_url,
      sourceName: row.source_name,
      observedRows: row.observed_rows,
    })),
    topBuys,
    topSells,
    limitations: payload.limitations ?? [],
  };
}

function adaptResearchEvents(
  bundle: ResearchEventBundle | undefined,
): ResearchEventView[] {
  if (!bundle || !Array.isArray(bundle.events)) return [];
  return bundle.events
    .map((row: ResearchEventRow) => ({
      eventId: row.event_id,
      eventDate: row.event_date,
      publishedAt: row.published_at,
      ticker: row.ticker,
      category: row.category,
      title: row.title,
      summary: row.summary,
      sourceUrl: row.source_url,
      sourceName: row.source_name,
      provider: row.provider,
      quantitativeUse: row.quantitative_use,
      kongloId: row.konglo_id,
      themeIds: Array.isArray(row.theme_ids) ? row.theme_ids : [],
    }))
    .sort((a, b) => b.eventDate.localeCompare(a.eventDate));
}

// `previousLeader` and `previousDiff` carry domain intent ("return the
// previous state only if it is a real transition, otherwise undefined") and
// are reused in every row build, so they stay as named functions.
function previousLeader(
  current: LeadershipState,
  previous: LeadershipState | null | undefined,
): LeadershipState | undefined {
  if (!previous || previous === current) return undefined;
  return previous;
}

function previousDiff(
  current: DiffusionState,
  previous: DiffusionState | null | undefined,
): DiffusionState | undefined {
  if (!previous || previous === current) return undefined;
  return previous;
}

function buildInterpretation(input: {
  leadership_state: LeadershipState;
  diffusion_state: DiffusionState;
  breadth_delta: number | null | undefined;
  group_excess_return_20d: number | null | undefined;
}): string {
  const { leadership_state, diffusion_state, breadth_delta, group_excess_return_20d } =
    input;
  const performance =
    group_excess_return_20d === null || group_excess_return_20d === undefined
      ? "20D performance is unavailable"
      : `20D excess return was ${group_excess_return_20d >= 0 ? "+" : ""}${group_excess_return_20d.toFixed(1)}pp`;
  const breadthMove =
    breadth_delta === null || breadth_delta === undefined
      ? "breadth change is unavailable"
      : breadth_delta > 0
        ? `breadth expanded by ${breadth_delta.toFixed(1)}pp`
        : breadth_delta < 0
          ? `breadth narrowed by ${Math.abs(breadth_delta).toFixed(1)}pp`
          : "breadth held flat";
  return `${performance}; ${breadthMove}; classified ${leadership_state} / ${diffusion_state}.`;
}

export function adaptSnapshot(payload: SnapshotPayload): AdaptedSnapshot {
  const comparability = payload.comparability;
  const transitionsByGroup: Record<string, (typeof payload.transitions)[number]> = {};
  for (const t of payload.transitions) {
    transitionsByGroup[t.group_id] = t;
  }

  const sortedGroups = [...payload.groups].sort((a, b) => {
    const ra = typeof a.leadership_rank === "number" ? a.leadership_rank : Infinity;
    const rb = typeof b.leadership_rank === "number" ? b.leadership_rank : Infinity;
    if (ra === rb) return a.group_id.localeCompare(b.group_id);
    return ra - rb;
  });

  // When comparability is INCOMPARABLE, suppress fabricated previous
  // states. The "no previous snapshot" reason in the transition frame
  // must not surface as a real UNCONFIRMED -> LEADING transition.
  const isComparable = comparability?.status === "COMPATIBLE";
  const sectors: SectorData[] = sortedGroups.map((g) => {
    const transition = transitionsByGroup[g.group_id];
    const excess20d = g.group_excess_return_20d;
    const excess60d = g.group_excess_return_60d;
    const breadth = g.breadth_outperforming;
    const concentration =
      g.top3_contribution_share === null || g.top3_contribution_share === undefined
        ? null
        : Math.round(g.top3_contribution_share * 100);

    return {
      id: g.group_id,
      name: g.group_name ?? g.group_id,
      leadership: g.leadership_state,
      prevLeadership: isComparable
        ? previousLeader(
            g.leadership_state,
            transition?.previous_leadership_state,
          )
        : undefined,
      diffusion: g.diffusion_state,
      prevDiffusion: isComparable
        ? previousDiff(
            g.diffusion_state,
            transition?.previous_diffusion_state,
          )
        : undefined,
      excess20d,
      excess60d,
      breadth,
      prevBreadth:
        isComparable && transition?.breadth_delta !== null && transition?.breadth_delta !== undefined && breadth !== null
          ? breadth - transition.breadth_delta
          : undefined,
      concentration,
      persistence: g.leadership_persistence ?? 1,
      constituents: g.constituent_count,
      eligibleConstituents: g.eligible_count,
      missingConstituents: g.missing_count,
      rank: g.leadership_rank,
      prevRank:
        isComparable &&
        transition?.rank_delta !== null &&
        transition?.rank_delta !== undefined &&
        g.leadership_rank !== null
          ? g.leadership_rank - transition.rank_delta
          : undefined,
      fundamentals: "DATA_GAP",
      foreignFlow: "DATA_GAP",
      interpretation: buildInterpretation({
        leadership_state: g.leadership_state,
        diffusion_state: g.diffusion_state,
        breadth_delta: g.breadth_delta,
        group_excess_return_20d: g.group_excess_return_20d,
      }),
    };
  });

  // Material changes require a persisted comparable prior snapshot.
  // When comparability is INCOMPARABLE, the previous state is fabricated
  // (UNCONFIRMED) and must not surface as a real "Material shift".
  const materialChanges = isComparable
    ? sectors.filter((s) => {
        const transition = transitionsByGroup[s.id];
        return Boolean(
          s.prevLeadership ||
            s.prevDiffusion ||
            (transition && transition.materiality_label !== "STABLE"),
        );
      })
    : [];

  const securityMaster = Array.isArray(payload.security_master)
    ? (payload.security_master as Array<{
        ticker: string;
        company_name?: string;
        group_id?: string;
        sector?: string;
      }>)
    : [];
  const securityLookup: Record<
    string,
    { name: string; group_id: string; sector: string }
  > = {};
  for (const s of securityMaster) {
    securityLookup[s.ticker] = {
      name: s.company_name ?? s.ticker,
      group_id: s.group_id ?? "Unknown",
      sector: s.sector ?? "Unknown",
    };
  }
  const featureLookup: Record<string, FeatureRow> = {};
  for (const f of payload.features) {
    featureLookup[f.ticker] = f;
  }
  const constituentsByGroup: Record<string, ConstituentData[]> = {};
  for (const f of payload.features) {
    const sm = securityLookup[f.ticker];
    if (!sm) continue;
    const bucket = constituentsByGroup[sm.group_id] ?? [];
    bucket.push({
      ticker: f.ticker,
      name: sm.name,
      return20d: f.return_20d,
      excess20d: f.excess_return_20d,
      excess60d: f.excess_return_60d,
      participating:
        f.excess_return_20d === null || f.excess_return_20d === undefined
          ? null
          : f.excess_return_20d > 0,
      contribution: null,
      foreignFlow: "DATA_GAP",
    });
    constituentsByGroup[sm.group_id] = bucket;
  }
  for (const groupId of Object.keys(constituentsByGroup)) {
    const list = constituentsByGroup[groupId];
    const totalAbs = list.reduce(
      (acc, c) => acc + (c.return20d === null ? 0 : Math.abs(c.return20d)),
      0,
    );
    for (const c of list) {
      c.contribution =
        c.return20d !== null && totalAbs > 0
          ? Math.round((Math.abs(c.return20d) / totalAbs) * 100)
          : null;
    }
  }

  // A transition delta is not an absolute breadth level. Only consume the
  // exporter-owned history array, which is built from persisted group rows.
  const breadthHistory = normalizeBreadthHistory(payload.breadth_history);
  const groupPriceHistory = normalizeGroupPriceHistory(payload.group_price_history);
  const tickerPriceHistory = normalizeGroupPriceHistory(payload.ticker_price_history);

  // New sections: taxonomy views, foreign flow, research events.
  const taxonomyViews: Record<string, TaxonomyView> = {};
  const taxonomyGroups: Record<string, TaxonomyGroupData> = {};
  let activeTaxonomyId: string | null = null;
  if (payload.taxonomy_views) {
    for (const [taxonomyId, raw] of Object.entries(payload.taxonomy_views)) {
      const view = normalizeTaxonomyView(raw);
      if (!view) continue;
      taxonomyViews[view.taxonomy_id] = view;
      const { groupData } = adaptTaxonomyView(view);
      for (const [gid, group] of Object.entries(groupData)) {
        taxonomyGroups[`${view.taxonomy_id}::${gid}`] = group;
      }
      if (!activeTaxonomyId) activeTaxonomyId = view.taxonomy_id;
    }
  }
  const foreignFlowAdapted = adaptForeignFlow(payload.foreign_flow_sample);
  const researchEvents = adaptResearchEvents(payload.research_events);

  // Wire foreign flow sample context into the existing sector cells so
  // downstream pages can surface "Sample NET_BUY / NET_SELL" without
  // recomputing.
  const foreignByGroup: Record<
    string,
    { direction: ForeignFlowDirection; net_value_idr: number | null }
  > = {};
  if (foreignFlowAdapted?.signalEligible) {
    for (const summary of foreignFlowAdapted.groupSummaries) {
      foreignByGroup[summary.groupId] = {
        direction: summary.direction,
        net_value_idr: summary.netValueIdr,
      };
    }
  }

  for (const sector of sectors) {
    const flow = foreignByGroup[sector.id];
    if (flow) {
      sector.foreignFlow =
        flow.direction === "NET_BUY"
          ? "CONFIRMING"
          : flow.direction === "NET_SELL"
            ? "AGAINST"
            : "NEUTRAL";
    }
  }

  return {
    payload,
    sectors,
    materialChanges,
    breadthHistory,
    groupPriceHistory,
    tickerPriceHistory,
    trajectoryData: {},
    dataSources: {
      breadthHistory: breadthHistory.length > 0,
      constituents: Object.values(constituentsByGroup).some((list) => list.length > 0),
      fundamentals: false,
      foreignFlow: Boolean(
        foreignFlowAdapted && foreignFlowAdapted.companyObservationCount > 0,
      ),
      trajectory: comparability?.status === "COMPATIBLE" && !!comparability?.selected_previous,
    },
    trajectoryAvailable: comparability?.status === "COMPATIBLE" && !!comparability?.selected_previous,
    coverageHonest: {
      raw_candidate_constituents: payload.coverage?.raw_candidate_constituents ?? 0,
      policy_eligible_constituents: payload.coverage?.policy_eligible_constituents ?? 0,
      observed_eligible_features: payload.coverage?.observed_eligible_features ?? 0,
      acquisition_failed_constituents: payload.coverage?.acquisition_failed_constituents ?? 0,
      coverage_pct: payload.coverage?.coverage_pct ?? 0,
      coverage_gate_60pct_met: payload.coverage?.coverage_gate_60pct_met ?? false,
      taxonomy_coverage_pct: payload.coverage?.taxonomy_coverage_pct,
    },
    constituentsByGroup,
    featureLookup,
    securityLookup,
    taxonomyViews,
    taxonomyGroups,
    activeTaxonomyId,
    foreignFlow: foreignFlowAdapted,
    researchEvents,
  };
}
