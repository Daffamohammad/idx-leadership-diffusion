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
  IDXDailyStatistics,
  OfficialMarketContext,
  ListingRegistryRecord,
  IDXInvestorFlowDirection,
  IDXInvestorRelease,
  LeadershipState,
  ResearchEventBundle,
  ResearchEventRow,
  GroupEvidenceRow,
  EvidenceContradictionRow,
  EvidenceInvalidationRow,
  HistoryDiagnostics,
  SnapshotPayload,
  SnapshotBreadthHistoryPoint,
  GroupPriceHistoryPoint,
  TaxonomyGroupAggregate,
  TaxonomyMembershipData,
  TaxonomyMembershipType,
  TaxonomyKind,
  TaxonomyView,
} from "./snapshot";
import { formatEnumLabel, formatPercent } from "./format";

export type { DiffusionState, LeadershipState } from "./snapshot";

export type FlowState = "CONFIRMING" | "NEUTRAL" | "AGAINST" | "DATA_GAP";

export interface EvidenceContradiction {
  metric: string;
  label: string;
  severity: string;
  evidence: string | null;
}

export interface EvidenceInvalidation {
  condition: string;
  threshold: string | null;
}

export interface SectorData {
  id: string;
  name: string;
  parent?: string;
  leadership: LeadershipState;
  prevLeadership?: LeadershipState;
  diffusion: DiffusionState;
  prevDiffusion?: DiffusionState;
  // Diffusion v2 detail (e.g. BROADENING_FIRM) where the backend emitted it.
  diffusionV2?: string | null;
  excess20d: number | null;
  excess60d: number | null;
  returnYtd: number | null;
  excessYtd: number | null;
  benchmarkYtd: number | null;
  ytdStartDate: string | null;
  ytdEligible: number;
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
  dataQuality?: string;
  interpretation: string;
  contradictions: EvidenceContradiction[];
  invalidation: EvidenceInvalidation[];
}

export interface ConstituentData {
  ticker: string;
  name: string;
  return20d: number | null;
  returnYtd: number | null;
  benchmarkYtd: number | null;
  excessYtd: number | null;
  ytdStartDate: string | null;
  ytdEndDate: string | null;
  excess20d: number | null;
  excess60d: number | null;
  participating: boolean | null;
  contribution: number | null;
  foreignFlow: FlowState;
  membershipType?: TaxonomyMembershipType;
  confidence?: number;
  source?: string;
  sourceAsOf?: string | null;
  dataQuality?: string;
  priceHistoryAvailable?: boolean;
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
  returnYtd: number | null;
  excessYtd: number | null;
  benchmarkYtd: number | null;
  ytdStartDate: string | null;
  ytdEligible: number;
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
  marketDaysMeetsThreshold: boolean;
  companyRowsMeetsThreshold: boolean;
  mappedPctMeetsThreshold: boolean;
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

export interface IDXInvestorReleaseAdapted {
  schemaVersion: string;
  providerMode: string;
  status: string;
  quantitativeUse: boolean;
  scope: string;
  title: string;
  periodLabel: string;
  asOfMin: string;
  asOfMax: string;
  tradingDayCount: number;
  daily: Array<{
    asOf: string;
    foreignToDomesticIdr: number;
    domesticToForeignIdr: number;
    netForeignIdr: number;
    direction: IDXInvestorFlowDirection;
  }>;
  totals: {
    foreignToForeignIdr: number | null;
    foreignToDomesticIdr: number;
    domesticToForeignIdr: number;
    domesticToDomesticIdr: number | null;
    netForeignIdr: number;
    direction: IDXInvestorFlowDirection;
  };
  quality: IDXInvestorRelease["quality"];
  source: IDXInvestorRelease["source"];
  limitations: string[];
}

export interface IDXDailyStatisticsAdapted {
  schemaVersion: string;
  providerMode: string;
  status: string;
  quantitativeUse: boolean;
  scope: string;
  asOf: string;
  ihsg: IDXDailyStatistics["metrics"]["ihsg"];
  netForeign: IDXDailyStatistics["metrics"]["net_foreign"];
  fundamental: IDXDailyStatistics["metrics"]["fundamental"];
  quality: IDXDailyStatistics["quality"];
  llama: IDXDailyStatistics["llama"];
  source: IDXDailyStatistics["source"];
  limitations: string[];
}

export interface OfficialMarketContextAdapted {
  schemaVersion: string;
  providerMode: string;
  status: string;
  quantitativeUse: boolean;
  scope: string;
  releaseDate: string;
  periodEnd: string;
  metrics: OfficialMarketContext["metrics"];
  source: OfficialMarketContext["source"];
  limitations: string[];
}

export interface ListingRegistryAdapted {
  schemaVersion: string;
  status: string;
  providerMode: string;
  asOf: string | null;
  scopeLabel: string;
  fullAccessibleUniverseListed: boolean;
  discoveredCount: number;
  persistedCount: number;
  listedCount: number;
  duplicateTickerCount: number;
  analysisRequestedCount: number;
  observedFeatureCount: number;
  taxonomyCompleteCount: number;
  taxonomyCoveragePct: number;
  kongloMappedCount: number;
  themeMappedCount: number;
  records: ListingRegistryRecord[];
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
  // Bundle-completeness sentinel: true = atomic bundle verified,
  // false = stale partial bundle (pre-sentinel write), null = the export
  // predates completeness forwarding (unknown — never authoritative).
  bundleComplete: boolean | null;
  // True only when the backend explicitly reports incomplete pagination.
  paginationIncomplete: boolean;
  // True only when the backend explicitly reports a 90-day history cap.
  windowCapped90d: boolean;
  windowCapNote: string | null;
  acquisitionDiagnostics: {
    failed: string[];
    empty: string[];
    requestedSymbols: number | null;
    returnedSymbols: number | null;
    returnedRows: number | null;
  };
  materialChanges: SectorData[];
  breadthHistory: BreadthHistoryPoint[];
  groupPriceHistory: Record<string, GroupPricePoint[]>;
  tickerPriceHistory: Record<string, GroupPricePoint[]>;
  trajectoryData: Record<string, Array<{ x: number; y: number; label?: string }>>;
  dataSources: DataSources;
  trajectoryAvailable: boolean;
  coverageHonest: CoverageHonest;
  constituentsByGroup: Record<string, ConstituentData[]>;
  constituentsByTaxonomyGroup: Record<string, ConstituentData[]>;
  taxonomyGroupPriceHistory: Record<string, GroupPricePoint[]>;
  featureLookup: Record<string, FeatureRow>;
  securityLookup: Record<string, { name: string; group_id: string; sector: string }>;
  taxonomyViews: Record<string, TaxonomyView>;
  taxonomyGroups: Record<string, TaxonomyGroupData>;
  activeTaxonomyId: string | null;
  foreignFlow: ForeignFlowAdapted | null;
  idxInvestorRelease: IDXInvestorReleaseAdapted | null;
  idxDailyStatistics: IDXDailyStatisticsAdapted | null;
  officialMarketContext: OfficialMarketContextAdapted | null;
  listingRegistry: ListingRegistryAdapted | null;
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
function safeNullableNumber(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v !== "string" || v.trim() === "") return null;
  const parsed = Number(v);
  return Number.isFinite(parsed) ? parsed : null;
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
      const open = safeNullableNumber(candidate.open);
      const high = safeNullableNumber(candidate.high);
      const low = safeNullableNumber(candidate.low);
      const close = safeNullableNumber(candidate.close);
      const volume = safeNullableNumber(candidate.volume);
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
      return [{ date, value, benchmark: benchmark ?? null, open, high, low, close, volume }];
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
    equal_weight_return_ytd: number(raw.equal_weight_return_ytd),
    excess_return_20d: number(raw.excess_return_20d),
    excess_return_60d: number(raw.excess_return_60d),
    excess_return_ytd: number(raw.excess_return_ytd),
    benchmark_return_20d: number(raw.benchmark_return_20d),
    benchmark_return_60d: number(raw.benchmark_return_60d),
    benchmark_return_ytd: number(raw.benchmark_return_ytd),
    ytd_start_date: typeof raw.ytd_start_date === "string" ? raw.ytd_start_date : null,
    ytd_eligible_constituent_count:
      typeof raw.ytd_eligible_constituent_count === "number"
        ? raw.ytd_eligible_constituent_count
        : 0,
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
          relationship: typeof item.relationship === "string" && item.relationship.trim()
            ? item.relationship
            : null,
          relationship_as_of: typeof item.relationship_as_of === "string"
            ? item.relationship_as_of
            : null,
          relationship_source: typeof item.relationship_source === "string" && item.relationship_source.trim()
            ? item.relationship_source
            : null,
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
      returnYtd: group.equal_weight_return_ytd ?? null,
      excessYtd: group.excess_return_ytd ?? null,
      benchmarkYtd: group.benchmark_return_ytd ?? null,
      ytdStartDate: group.ytd_start_date ?? null,
      ytdEligible: group.ytd_eligible_constituent_count ?? 0,
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

const IDX_INVESTOR_DIRECTIONS: IDXInvestorFlowDirection[] = [
  "NET_BUY",
  "NET_SELL",
  "FLAT",
];

function normalizeIDXInvestorDirection(value: unknown): IDXInvestorFlowDirection {
  if (typeof value !== "string") return "FLAT";
  const upper = value.toUpperCase() as IDXInvestorFlowDirection;
  return IDX_INVESTOR_DIRECTIONS.includes(upper) ? upper : "FLAT";
}

function normalizeIDXInvestorRelease(
  value: unknown,
): IDXInvestorReleaseAdapted | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  const release = raw.release;
  const period = release && typeof release === "object" && !Array.isArray(release)
    ? (release as Record<string, unknown>).period
    : null;
  const source = raw.source;
  const totals = raw.totals;
  const quality = raw.quality;
  if (
    typeof raw.schema_version !== "string" ||
    typeof raw.provider_mode !== "string" ||
    !release ||
    typeof release !== "object" ||
    Array.isArray(release) ||
    !period ||
    typeof period !== "object" ||
    Array.isArray(period) ||
    !source ||
    typeof source !== "object" ||
    Array.isArray(source) ||
    !totals ||
    typeof totals !== "object" ||
    Array.isArray(totals) ||
    !quality ||
    typeof quality !== "object" ||
    Array.isArray(quality)
  ) {
    return null;
  }
  const releaseRaw = release as Record<string, unknown>;
  const periodRaw = period as Record<string, unknown>;
  const sourceRaw = source as Record<string, unknown>;
  const totalsRaw = totals as Record<string, unknown>;
  const qualityRaw = quality as Record<string, unknown>;
  const number = (input: unknown): number | null =>
    typeof input === "number" && Number.isFinite(input) ? input : null;
  const requiredNumber = (input: unknown): number | null => number(input);
  const rawDaily = Array.isArray(raw.daily) ? raw.daily : [];
  const daily = rawDaily.flatMap((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const row = item as Record<string, unknown>;
    const asOf = row.as_of;
    const foreignToDomestic = requiredNumber(row.foreign_to_domestic_value_idr);
    const domesticToForeign = requiredNumber(row.domestic_to_foreign_value_idr);
    const netForeign = requiredNumber(row.net_foreign_value_idr);
    if (
      typeof asOf !== "string" ||
      !asOf ||
      foreignToDomestic === null ||
      domesticToForeign === null ||
      netForeign === null
    ) {
      return [];
    }
    return [{
      asOf,
      foreignToDomesticIdr: foreignToDomestic,
      domesticToForeignIdr: domesticToForeign,
      netForeignIdr: netForeign,
      direction: normalizeIDXInvestorDirection(row.direction),
    }];
  });
  const requiredTotals = {
    foreignToDomesticIdr: number(totalsRaw.foreign_to_domestic_value_idr),
    domesticToForeignIdr: number(totalsRaw.domestic_to_foreign_value_idr),
    netForeignIdr: number(totalsRaw.net_foreign_value_idr),
  };
  if (
    !daily.length ||
    Object.values(requiredTotals).some((entry) => entry === null) ||
    typeof releaseRaw.title !== "string" ||
    typeof periodRaw.year !== "number" ||
    typeof periodRaw.month !== "number" ||
    typeof periodRaw.label !== "string" ||
    typeof releaseRaw.trading_day_count !== "number" ||
    typeof raw.as_of !== "object" ||
    !raw.as_of ||
    Array.isArray(raw.as_of) ||
    typeof sourceRaw.publisher !== "string" ||
    typeof sourceRaw.url !== "string"
  ) {
    return null;
  }
  const asOfRaw = raw.as_of as Record<string, unknown>;
  const reconciliation =
    qualityRaw.reconciliation &&
    typeof qualityRaw.reconciliation === "object" &&
    !Array.isArray(qualityRaw.reconciliation)
      ? (qualityRaw.reconciliation as Record<string, boolean>)
      : {};
  return {
    schemaVersion: raw.schema_version,
    providerMode: raw.provider_mode,
    status: typeof raw.status === "string" ? raw.status : "READY_WITH_GAPS",
    quantitativeUse: raw.quantitative_use === true,
    scope: typeof raw.scope === "string" ? raw.scope : "",
    title: releaseRaw.title,
    periodLabel: periodRaw.label,
    asOfMin: typeof asOfRaw.min === "string" ? asOfRaw.min : daily[0].asOf,
    asOfMax:
      typeof asOfRaw.max === "string" ? asOfRaw.max : daily[daily.length - 1].asOf,
    tradingDayCount: releaseRaw.trading_day_count,
    daily,
    totals: {
      foreignToForeignIdr: number(totalsRaw.foreign_to_foreign_value_idr),
      foreignToDomesticIdr: requiredTotals.foreignToDomesticIdr as number,
      domesticToForeignIdr: requiredTotals.domesticToForeignIdr as number,
      domesticToDomesticIdr: number(totalsRaw.domestic_to_domestic_value_idr),
      netForeignIdr: requiredTotals.netForeignIdr as number,
      direction: normalizeIDXInvestorDirection(totalsRaw.direction),
    },
    quality: {
      source_table_count:
        typeof qualityRaw.source_table_count === "number"
          ? qualityRaw.source_table_count
          : 0,
      daily_rows:
        typeof qualityRaw.daily_rows === "number" ? qualityRaw.daily_rows : daily.length,
      positive_day_count:
        typeof qualityRaw.positive_day_count === "number"
          ? qualityRaw.positive_day_count
          : undefined,
      negative_day_count:
        typeof qualityRaw.negative_day_count === "number"
          ? qualityRaw.negative_day_count
          : undefined,
      reconciliation,
      search_agent_role:
        typeof qualityRaw.search_agent_role === "string"
          ? qualityRaw.search_agent_role
          : "DISCOVERY_ONLY",
      full_month_release: qualityRaw.full_month_release === true,
    },
    source: {
      publisher: sourceRaw.publisher,
      url: sourceRaw.url,
      retrieved_at:
        typeof sourceRaw.retrieved_at === "string" ? sourceRaw.retrieved_at : "",
      parser: typeof sourceRaw.parser === "string" ? sourceRaw.parser : "",
      table_endpoints: Array.isArray(sourceRaw.table_endpoints)
        ? sourceRaw.table_endpoints.filter((entry): entry is string => typeof entry === "string")
        : undefined,
    },
    limitations: Array.isArray(raw.limitations)
      ? raw.limitations.filter((entry): entry is string => typeof entry === "string")
      : [],
  };
}

function normalizeIDXDailyStatistics(
  value: unknown,
): IDXDailyStatisticsAdapted | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  const metrics = raw.metrics;
  const ihsg = metrics && typeof metrics === "object" && !Array.isArray(metrics)
    ? (metrics as Record<string, unknown>).ihsg
    : null;
  const netForeign = metrics && typeof metrics === "object" && !Array.isArray(metrics)
    ? (metrics as Record<string, unknown>).net_foreign
    : null;
  const fundamental = metrics && typeof metrics === "object" && !Array.isArray(metrics)
    ? (metrics as Record<string, unknown>).fundamental
    : null;
  const asRecord = (input: unknown): Record<string, unknown> | null =>
    input && typeof input === "object" && !Array.isArray(input)
      ? (input as Record<string, unknown>)
      : null;
  const ihsgRaw = asRecord(ihsg);
  const flowRaw = asRecord(netForeign);
  const todayRaw = asRecord(flowRaw?.today);
  const ytdRaw = asRecord(flowRaw?.ytd);
  const fundamentalRaw = asRecord(fundamental);
  const qualityRaw = asRecord(raw.quality);
  const llamaRaw = asRecord(raw.llama);
  const sourceRaw = asRecord(raw.source);
  const finite = (input: unknown): number | null =>
    typeof input === "number" && Number.isFinite(input) ? input : null;
  const requiredFlow = (input: Record<string, unknown> | null) =>
    input &&
    finite(input.idr_billion) !== null &&
    finite(input.usd_million) !== null &&
    typeof input.usd_approximate === "boolean" &&
    typeof input.direction === "string"
      ? {
          idr_billion: finite(input.idr_billion) as number,
          usd_million: finite(input.usd_million) as number,
          usd_approximate: input.usd_approximate,
          direction: input.direction,
        }
      : null;
  const today = requiredFlow(todayRaw);
  const ytd = requiredFlow(ytdRaw);
  const checks = qualityRaw?.checks;
  const warnings = Array.isArray(qualityRaw?.warnings)
    ? qualityRaw.warnings.filter((entry): entry is string => typeof entry === "string")
    : [];
  if (
    typeof raw.schema_version !== "string" ||
    typeof raw.provider_mode !== "string" ||
    typeof raw.as_of !== "string" ||
    !ihsgRaw ||
    finite(ihsgRaw.close) === null ||
    finite(ihsgRaw.previous) === null ||
    finite(ihsgRaw.change) === null ||
    finite(ihsgRaw.change_pct) === null ||
    !today ||
    !ytd ||
    !fundamentalRaw ||
    finite(fundamentalRaw.market_per) === null ||
    finite(fundamentalRaw.market_pbv) === null ||
    !qualityRaw ||
    !llamaRaw ||
    !sourceRaw ||
    typeof sourceRaw.publisher !== "string" ||
    (sourceRaw.url !== null && typeof sourceRaw.url !== "string")
  ) {
    return null;
  }
  const normalizedChecks: Record<string, boolean> = {};
  if (checks && typeof checks === "object" && !Array.isArray(checks)) {
    for (const [key, entry] of Object.entries(checks)) {
      if (typeof entry === "boolean") normalizedChecks[key] = entry;
    }
  }
  return {
    schemaVersion: raw.schema_version,
    providerMode: raw.provider_mode,
    status: typeof raw.status === "string" ? raw.status : "READY_WITH_GAPS",
    quantitativeUse: raw.quantitative_use === true,
    scope: typeof raw.scope === "string" ? raw.scope : "",
    asOf: raw.as_of,
    ihsg: {
      close: finite(ihsgRaw.close) as number,
      previous: finite(ihsgRaw.previous) as number,
      change: finite(ihsgRaw.change) as number,
      change_pct: finite(ihsgRaw.change_pct) as number,
      raw_change: typeof ihsgRaw.raw_change === "string" ? ihsgRaw.raw_change : undefined,
    },
    netForeign: {
      today,
      ytd,
    },
    fundamental: {
      market_per: finite(fundamentalRaw.market_per) as number,
      market_pbv: finite(fundamentalRaw.market_pbv) as number,
    },
    quality: {
      checks: normalizedChecks,
      warnings,
      warning_count:
        typeof qualityRaw.warning_count === "number"
          ? qualityRaw.warning_count
          : warnings.length,
      markdown_sha256:
        typeof qualityRaw.markdown_sha256 === "string" ? qualityRaw.markdown_sha256 : "",
      parsed_page_count:
        typeof qualityRaw.parsed_page_count === "number"
          ? qualityRaw.parsed_page_count
          : undefined,
      parsed_page_numbers: Array.isArray(qualityRaw.parsed_page_numbers)
        ? qualityRaw.parsed_page_numbers.filter(
            (entry): entry is number => typeof entry === "number",
          )
        : undefined,
    },
    llama: {
      job_id: typeof llamaRaw.job_id === "string" ? llamaRaw.job_id : null,
      file_id: typeof llamaRaw.file_id === "string" ? llamaRaw.file_id : null,
      tier: typeof llamaRaw.tier === "string" ? llamaRaw.tier : "",
      version: typeof llamaRaw.version === "string" ? llamaRaw.version : "",
      estimated_credit_cost: finite(llamaRaw.estimated_credit_cost),
      actual_credit_cost: finite(llamaRaw.actual_credit_cost),
      actual_credit_cost_known: llamaRaw.actual_credit_cost_known === true,
    },
    source: {
      publisher: sourceRaw.publisher,
      url: sourceRaw.url === null ? null : (sourceRaw.url as string),
      retrieved_at: typeof sourceRaw.retrieved_at === "string" ? sourceRaw.retrieved_at : "",
      parser: typeof sourceRaw.parser === "string" ? sourceRaw.parser : "",
      parser_version:
        typeof sourceRaw.parser_version === "string" ? sourceRaw.parser_version : undefined,
      tier: typeof sourceRaw.tier === "string" ? sourceRaw.tier : undefined,
      file_name: typeof sourceRaw.file_name === "string" ? sourceRaw.file_name : undefined,
    },
    limitations: Array.isArray(raw.limitations)
      ? raw.limitations.filter((entry): entry is string => typeof entry === "string")
      : [],
  };
}

function normalizeOfficialMarketContext(
  value: unknown,
): OfficialMarketContextAdapted | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  const metrics = raw.metrics;
  const source = raw.source;
  if (
    typeof raw.schema_version !== "string" ||
    typeof raw.provider_mode !== "string" ||
    typeof raw.release_date !== "string" ||
    typeof raw.period_end !== "string" ||
    !metrics ||
    typeof metrics !== "object" ||
    Array.isArray(metrics) ||
    !source ||
    typeof source !== "object" ||
    Array.isArray(source)
  ) {
    return null;
  }
  const metricsRaw = metrics as Record<string, unknown>;
  const sourceRaw = source as Record<string, unknown>;
  const finite = (input: unknown): number | null =>
    typeof input === "number" && Number.isFinite(input) ? input : null;
  const required = {
    ihsg_close: finite(metricsRaw.ihsg_close),
    ihsg_ytd_pct: finite(metricsRaw.ihsg_ytd_pct),
    equity_net_foreign_idr_trillion: finite(metricsRaw.equity_net_foreign_idr_trillion),
    equity_flow_ytd_idr_trillion: finite(metricsRaw.equity_flow_ytd_idr_trillion),
    equity_rnth_idr_trillion: finite(metricsRaw.equity_rnth_idr_trillion),
    local_ownership_pct: finite(metricsRaw.local_ownership_pct),
    market_cap_idr_trillion: finite(metricsRaw.market_cap_idr_trillion),
  };
  if (
    Object.values(required).some((entry) => entry === null) ||
    typeof metricsRaw.equity_net_foreign_direction !== "string" ||
    typeof sourceRaw.publisher !== "string" ||
    typeof sourceRaw.url !== "string"
  ) {
    return null;
  }
  return {
    schemaVersion: raw.schema_version,
    providerMode: raw.provider_mode,
    status: typeof raw.status === "string" ? raw.status : "READY",
    quantitativeUse: raw.quantitative_use === true,
    scope: typeof raw.scope === "string" ? raw.scope : "",
    releaseDate: raw.release_date,
    periodEnd: raw.period_end,
    metrics: {
      ihsg_close: required.ihsg_close as number,
      ihsg_ytd_pct: required.ihsg_ytd_pct as number,
      equity_net_foreign_idr_trillion:
        required.equity_net_foreign_idr_trillion as number,
      equity_net_foreign_direction: metricsRaw.equity_net_foreign_direction,
      equity_flow_ytd_idr_trillion: required.equity_flow_ytd_idr_trillion as number,
      equity_rnth_idr_trillion: required.equity_rnth_idr_trillion as number,
      local_ownership_pct: required.local_ownership_pct as number,
      market_cap_idr_trillion: required.market_cap_idr_trillion as number,
    },
    source: {
      publisher: sourceRaw.publisher,
      url: sourceRaw.url,
      published_at:
        typeof sourceRaw.published_at === "string" ? sourceRaw.published_at : undefined,
      retrieved_at:
        typeof sourceRaw.retrieved_at === "string" ? sourceRaw.retrieved_at : undefined,
      parser_agent:
        typeof sourceRaw.parser_agent === "string" ? sourceRaw.parser_agent : undefined,
      parser_version:
        typeof sourceRaw.parser_version === "string" ? sourceRaw.parser_version : undefined,
      parsed_pages: Array.isArray(sourceRaw.parsed_pages)
        ? sourceRaw.parsed_pages.filter((entry): entry is number => typeof entry === "number")
        : undefined,
    },
    limitations: Array.isArray(raw.limitations)
      ? raw.limitations.filter((entry): entry is string => typeof entry === "string")
      : [],
  };
}

function normalizeListingRegistry(value: unknown): ListingRegistryAdapted | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  if (!Array.isArray(raw.records) || typeof raw.schema_version !== "string") return null;
  const number = (entry: unknown, fallback = 0): number =>
    typeof entry === "number" && Number.isFinite(entry) ? entry : fallback;
  const text = (entry: unknown, fallback = ""): string =>
    typeof entry === "string" ? entry : fallback;
  const nullableText = (entry: unknown): string | null =>
    typeof entry === "string" ? entry : null;
  const records: ListingRegistryRecord[] = raw.records.flatMap((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return [];
    const item = entry as Record<string, unknown>;
    const taxonomyRaw = item.taxonomy;
    const taxonomy = taxonomyRaw && typeof taxonomyRaw === "object" && !Array.isArray(taxonomyRaw)
      ? taxonomyRaw as Record<string, unknown>
      : {};
    if (typeof item.ticker !== "string" || !item.ticker.trim()) return [];
    const memberships = (input: unknown): Array<Record<string, unknown>> =>
      Array.isArray(input)
        ? input.filter((candidate): candidate is Record<string, unknown> =>
            !!candidate && typeof candidate === "object" && !Array.isArray(candidate),
          )
        : [];
    return [{
      ticker: item.ticker,
      company_name: text(item.company_name, item.ticker),
      exchange: text(item.exchange, "IDX"),
      listing_board: nullableText(item.listing_board),
      listing_status: nullableText(item.listing_status),
      active: item.active !== false,
      common_equity_status: nullableText(item.common_equity_status),
      market_cap: typeof item.market_cap === "number" && Number.isFinite(item.market_cap)
        ? item.market_cap
        : null,
      taxonomy: {
        sector: nullableText(taxonomy.sector),
        subsector: nullableText(taxonomy.subsector),
        industry: nullableText(taxonomy.industry),
        subindustry: nullableText(taxonomy.subindustry),
      },
      taxonomy_status: text(item.taxonomy_status, "MISSING_CLASSIFICATION"),
      group_id: nullableText(item.group_id),
      analysis_requested: item.analysis_requested === true,
      analysis_status: text(item.analysis_status, "NOT_REPORTED"),
      konglo_memberships: memberships(item.konglo_memberships),
      theme_memberships: memberships(item.theme_memberships),
      source: nullableText(item.source),
      source_as_of: nullableText(item.source_as_of),
    }];
  });
  return {
    schemaVersion: raw.schema_version,
    status: text(raw.status, "UNAVAILABLE"),
    providerMode: text(raw.provider_mode, "UNAVAILABLE"),
    asOf: nullableText(raw.as_of),
    scopeLabel: text(raw.scope_label, "Persisted listing"),
    fullAccessibleUniverseListed: raw.full_accessible_universe_listed === true,
    discoveredCount: number(raw.discovered_count),
    persistedCount: number(raw.persisted_count),
    listedCount: number(raw.listed_count),
    duplicateTickerCount: number(raw.duplicate_ticker_count),
    analysisRequestedCount: number(raw.analysis_requested_count),
    observedFeatureCount: number(raw.observed_feature_count),
    taxonomyCompleteCount: number(raw.taxonomy_complete_count),
    taxonomyCoveragePct: number(raw.taxonomy_coverage_pct),
    kongloMappedCount: number(raw.konglo_mapped_count),
    themeMappedCount: number(raw.theme_mapped_count),
    records,
  };
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
    marketDaysMeetsThreshold: signal.market_days_meets_threshold === true,
    companyRowsMeetsThreshold: signal.company_rows_meets_threshold === true,
    mappedPctMeetsThreshold: signal.mapped_pct_meets_threshold === true,
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
    limitations: (payload.limitations ?? []).map(formatVisibleNote),
  };
}

function formatVisibleNote(value: string): string {
  return value.replace(/\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b/g, (token) =>
    token.split("_").join(" "),
  );
}

type SecurityLookupEntry = { name: string; group_id: string; sector: string };

function buildConstituentRow(
  ticker: string,
  feature: FeatureRow | undefined,
  security: SecurityLookupEntry | undefined,
  tickerPriceHistory: Record<string, GroupPricePoint[]>,
  membership?: TaxonomyMembershipData,
): ConstituentData {
  const hasPrimaryMetric =
    feature?.return_20d !== null && feature?.return_20d !== undefined &&
    feature?.excess_return_20d !== null && feature?.excess_return_20d !== undefined;
  return {
    ticker,
    name: security?.name ?? "—",
    return20d: feature?.return_20d ?? null,
    returnYtd: feature?.return_ytd ?? null,
    benchmarkYtd: feature?.benchmark_return_ytd ?? null,
    excessYtd: feature?.excess_return_ytd ?? null,
    ytdStartDate: feature?.return_ytd_start_date ?? null,
    ytdEndDate: feature?.return_ytd_end_date ?? null,
    excess20d: feature?.excess_return_20d ?? null,
    excess60d: feature?.excess_return_60d ?? null,
    participating:
      feature?.excess_return_20d === null || feature?.excess_return_20d === undefined
        ? null
        : feature.excess_return_20d > 0,
    contribution: null,
    foreignFlow: "DATA_GAP",
    membershipType: membership?.membership_type,
    confidence: membership?.confidence,
    source: membership?.source,
    sourceAsOf: membership?.source_as_of ?? null,
    dataQuality: !feature || !hasPrimaryMetric ? "DATA_GAP" : feature.excess_return_ytd == null ? "READY_WITH_GAPS" : "READY",
    priceHistoryAvailable: (tickerPriceHistory[ticker] ?? []).length > 0,
  };
}

function assignContributions(rows: ConstituentData[]): void {
  const totalAbs = rows.reduce(
    (total, row) => total + (row.return20d === null ? 0 : Math.abs(row.return20d)),
    0,
  );
  for (const row of rows) {
    row.contribution =
      row.return20d !== null && totalAbs > 0
        ? Math.round((Math.abs(row.return20d) / totalAbs) * 100)
        : null;
  }
}

function buildTaxonomyGroupPriceSeries(
  tickers: string[],
  tickerPriceHistory: Record<string, GroupPricePoint[]>,
): GroupPricePoint[] {
  const byDate = new Map<string, { values: number[]; benchmarks: number[] }>();
  for (const ticker of tickers) {
    for (const point of tickerPriceHistory[ticker] ?? []) {
      if (!Number.isFinite(point.value) || point.value <= 0) continue;
      const bucket = byDate.get(point.date) ?? { values: [], benchmarks: [] };
      bucket.values.push(point.value);
      if (point.benchmark !== null && Number.isFinite(point.benchmark) && point.benchmark > 0) {
        bucket.benchmarks.push(point.benchmark);
      }
      byDate.set(point.date, bucket);
    }
  }
  return [...byDate.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .flatMap(([date, bucket]) => {
      if (bucket.values.length === 0) return [];
      return [{
        date,
        value: bucket.values.reduce((sum, value) => sum + value, 0) / bucket.values.length,
        benchmark: bucket.benchmarks.length > 0
          ? bucket.benchmarks.reduce((sum, value) => sum + value, 0) / bucket.benchmarks.length
          : null,
      }];
    });
}

function adaptResearchEvents(
  bundle: ResearchEventBundle | undefined,
): ResearchEventView[] {
  if (!bundle || !Array.isArray(bundle.events)) return [];
  const safeHttpUrl = (value: unknown): string | null => {
    if (typeof value !== "string" || !value.trim()) return null;
    try {
      const url = new URL(value);
      return url.protocol === "http:" || url.protocol === "https:"
        ? url.toString()
        : null;
    } catch {
      return null;
    }
  };
  return bundle.events
    .map((row: ResearchEventRow) => {
      const url = safeHttpUrl(row.source_url);
      if (!url) return null;
      return {
      eventId: row.event_id,
      eventDate: row.event_date,
      publishedAt: row.published_at,
      ticker: row.ticker,
      category: row.category,
      title: row.title,
      summary: row.summary,
      sourceUrl: url,
      sourceName: row.source_name,
      provider: row.provider,
      quantitativeUse: row.quantitative_use,
      kongloId: row.konglo_id,
      themeIds: Array.isArray(row.theme_ids) ? row.theme_ids : [],
      };
    })
    .filter((row): row is ResearchEventView => row !== null)
    .sort((a, b) => b.eventDate.localeCompare(a.eventDate));
}

// Fail-closed projection of the new backend acquisition diagnostics.
// Unknown / absent backend state yields empty sets — never fabricated rows.
function normalizeHistoryTickers(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const out: string[] = [];
  for (const item of value) {
    if (typeof item === "string" && item.trim()) {
      out.push(item.trim().toUpperCase());
    } else if (item && typeof item === "object" && !Array.isArray(item)) {
      const row = item as Record<string, unknown>;
      const ticker = row.ticker ?? row.symbol;
      if (typeof ticker === "string" && ticker.trim()) {
        out.push(ticker.trim().toUpperCase());
      }
    }
  }
  return [...new Set(out)].sort();
}

function adaptAcquisitionDiagnostics(
  value: HistoryDiagnostics | undefined,
): AdaptedSnapshot["acquisitionDiagnostics"] {
  const finite = (input: unknown): number | null =>
    typeof input === "number" && Number.isFinite(input) ? input : null;
  return {
    failed: normalizeHistoryTickers(value?.failed_symbols),
    empty: normalizeHistoryTickers(value?.empty_symbols),
    requestedSymbols: finite(value?.requested_symbols),
    returnedSymbols: finite(value?.returned_symbols),
    returnedRows: finite(value?.returned_rows),
  };
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
      : `20D excess return was ${formatPercent(group_excess_return_20d)}`;
  const breadthMove =
    breadth_delta === null || breadth_delta === undefined
      ? "breadth change is unavailable"
      : breadth_delta > 0
        ? `breadth expanded by ${formatPercent(breadth_delta)}`
        : breadth_delta < 0
          ? `breadth narrowed by ${formatPercent(Math.abs(breadth_delta))}`
          : "breadth held flat";
  return `${performance}; ${breadthMove}; classified ${formatEnumLabel(leadership_state)} / ${formatEnumLabel(diffusion_state)}.`;
}

export function adaptSnapshot(
  payload: SnapshotPayload,
  idxInvestorRelease?: unknown,
  idxDailyStatistics?: unknown,
): AdaptedSnapshot {
  const comparability = payload.comparability;
  const transitionsByGroup: Record<string, (typeof payload.transitions)[number]> = {};
  for (const t of payload.transitions) {
    transitionsByGroup[t.group_id] = t;
  }
  const evidenceByGroup: Record<string, GroupEvidenceRow> = {};
  if (Array.isArray(payload.evidence)) {
    for (const row of payload.evidence as GroupEvidenceRow[]) {
      if (row && typeof row.group_id === "string") evidenceByGroup[row.group_id] = row;
    }
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
    const evidenceRow = evidenceByGroup[g.group_id];
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
      diffusionV2:
        typeof g.diffusion_state_v2 === "string" && g.diffusion_state_v2.trim()
          ? g.diffusion_state_v2.trim().toUpperCase()
          : null,
      prevDiffusion: isComparable
        ? previousDiff(
            g.diffusion_state,
            transition?.previous_diffusion_state,
          )
        : undefined,
      excess20d,
      excess60d,
      returnYtd: g.group_return_ytd ?? null,
      excessYtd: g.group_excess_return_ytd ?? null,
      benchmarkYtd: g.benchmark_return_ytd ?? null,
      ytdStartDate: g.ytd_start_date ?? null,
      ytdEligible: g.ytd_eligible_count ?? 0,
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
      dataQuality:
        g.group_excess_return_ytd === null || g.group_excess_return_ytd === undefined
          ? "READY_WITH_GAPS"
          : "READY",
      interpretation: buildInterpretation({
        leadership_state: g.leadership_state,
        diffusion_state: g.diffusion_state,
        breadth_delta: g.breadth_delta,
        group_excess_return_20d: g.group_excess_return_20d,
      }),
      contradictions: Array.isArray(evidenceRow?.contradictions)
        ? (evidenceRow.contradictions as EvidenceContradictionRow[]).map((c) => ({
            metric: String(c.metric),
            label: String(c.label),
            severity: String(c.severity),
            evidence: c.evidence == null ? null : String(c.evidence),
          }))
        : [],
      invalidation: Array.isArray(evidenceRow?.invalidation)
        ? (evidenceRow.invalidation as EvidenceInvalidationRow[]).map((row) => ({
            condition: String(row.condition),
            threshold: row.threshold == null ? null : String(row.threshold),
          }))
        : [],
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
  const tickerPriceHistory = normalizeGroupPriceHistory(payload.ticker_price_history);
  const constituentsByGroup: Record<string, ConstituentData[]> = {};
  const sectorTickersByGroup: Record<string, Set<string>> = {};
  for (const security of securityMaster) {
    if (!security.group_id) continue;
    const bucket = sectorTickersByGroup[security.group_id] ?? new Set<string>();
    bucket.add(security.ticker);
    sectorTickersByGroup[security.group_id] = bucket;
  }
  for (const feature of payload.features) {
    const security = securityLookup[feature.ticker];
    if (!security) continue;
    const bucket = sectorTickersByGroup[security.group_id] ?? new Set<string>();
    bucket.add(feature.ticker);
    sectorTickersByGroup[security.group_id] = bucket;
  }
  for (const [groupId, tickers] of Object.entries(sectorTickersByGroup)) {
    const rows = [...tickers]
      .sort()
      .map((ticker) => buildConstituentRow(
        ticker,
        featureLookup[ticker],
        securityLookup[ticker],
        tickerPriceHistory,
      ));
    assignContributions(rows);
    constituentsByGroup[groupId] = rows;
  }

  // A transition delta is not an absolute breadth level. Only consume the
  // exporter-owned history array, which is built from persisted group rows.
  const breadthHistory = normalizeBreadthHistory(payload.breadth_history);
  const groupPriceHistory = normalizeGroupPriceHistory(payload.group_price_history);

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
      if (!activeTaxonomyId || view.taxonomy_kind === "SECTOR") {
        activeTaxonomyId = view.taxonomy_id;
      }
    }
  }
  const constituentsByTaxonomyGroup: Record<string, ConstituentData[]> = {};
  const taxonomyGroupPriceHistory: Record<string, GroupPricePoint[]> = {};
  for (const view of Object.values(taxonomyViews)) {
    for (const group of view.groups) {
      const key = `${view.taxonomy_id}::${group.taxonomy_group_id}`;
      const memberships = (view.memberships?.length
        ? view.memberships
        : payload.memberships ?? []
      ).filter(
        (membership) =>
          membership.taxonomy_group_id === group.taxonomy_group_id &&
          membership.membership_type !== "EXCLUDED",
      );
      const uniqueMemberships = memberships.filter(
        (membership, index, all) =>
          all.findIndex(
            (candidate) =>
              candidate.ticker === membership.ticker &&
              candidate.membership_type === membership.membership_type,
          ) === index,
      );
      let rows: ConstituentData[];
      if (uniqueMemberships.length > 0) {
        rows = uniqueMemberships
          .map((membership) => buildConstituentRow(
            membership.ticker.toUpperCase(),
            featureLookup[membership.ticker] ?? featureLookup[membership.ticker.toUpperCase()],
            securityLookup[membership.ticker] ?? securityLookup[membership.ticker.toUpperCase()],
            tickerPriceHistory,
            membership,
          ));
      } else if (view.taxonomy_kind === "SECTOR") {
        // taxonomy-view-v1 has no root membership list. Reuse the sector
        // resolver only for that legacy view; do not invent prototype members.
        rows = (constituentsByGroup[group.taxonomy_group_id] ?? []).map((row) => ({ ...row }));
      } else {
        rows = [];
      }
      assignContributions(rows);
      constituentsByTaxonomyGroup[key] = rows;
      const priceSeries = buildTaxonomyGroupPriceSeries(
        rows.map((row) => row.ticker),
        tickerPriceHistory,
      );
      if (priceSeries.length > 0) taxonomyGroupPriceHistory[key] = priceSeries;
    }
  }
  const foreignFlowAdapted = adaptForeignFlow(payload.foreign_flow_sample);
  const officialMarketContext = normalizeOfficialMarketContext(
    payload.official_market_context,
  );
  const listingRegistry = normalizeListingRegistry(payload.listing_registry);
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
    bundleComplete:
      payload.complete === true ? true : payload.complete === false ? false : null,
    paginationIncomplete: payload.coverage?.pagination_incomplete === true,
    windowCapped90d:
      payload.coverage?.history_window_capped_90d === true ||
      payload.history_diagnostics?.window_capped_to_90_calendar_days === true,
    windowCapNote:
      typeof payload.coverage?.history_window_capped_note === "string" &&
      payload.coverage.history_window_capped_note.trim()
        ? payload.coverage.history_window_capped_note.trim()
        : null,
    acquisitionDiagnostics: adaptAcquisitionDiagnostics(payload.history_diagnostics),
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
    constituentsByTaxonomyGroup,
    taxonomyGroupPriceHistory,
    featureLookup,
    securityLookup,
    taxonomyViews,
    taxonomyGroups,
    activeTaxonomyId,
    foreignFlow: foreignFlowAdapted,
    idxInvestorRelease: normalizeIDXInvestorRelease(
      idxInvestorRelease ?? payload.idx_investor_release,
    ),
    idxDailyStatistics: normalizeIDXDailyStatistics(
      idxDailyStatistics ?? payload.idx_daily_statistics,
    ),
    officialMarketContext,
    listingRegistry,
    researchEvents,
  };
}
