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
  LeadershipState,
  SnapshotPayload,
  SnapshotBreadthHistoryPoint,
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
}

export interface AdaptedSnapshot {
  payload: SnapshotPayload;
  sectors: SectorData[];
  materialChanges: SectorData[];
  breadthHistory: BreadthHistoryPoint[];
  trajectoryData: Record<string, Array<{ x: number; y: number; label?: string }>>;
  dataSources: DataSources;
  trajectoryAvailable: boolean;
  coverageHonest: CoverageHonest;
  constituentsByGroup: Record<string, ConstituentData[]>;
  featureLookup: Record<string, FeatureRow>;
  securityLookup: Record<string, { name: string; group_id: string; sector: string }>;
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

  return {
    payload,
    sectors,
    materialChanges,
    breadthHistory,
    trajectoryData: {},
    dataSources: {
      breadthHistory: breadthHistory.length > 0,
      constituents: Object.values(constituentsByGroup).some((list) => list.length > 0),
      fundamentals: false,
      foreignFlow: false,
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
    },
    constituentsByGroup,
    featureLookup,
    securityLookup,
  };
}
