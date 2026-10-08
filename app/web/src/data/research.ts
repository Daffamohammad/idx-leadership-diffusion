import { useSearchParams } from "react-router";
import { useHistoricalComparison, useRecordedSectorsSample, useSectorsSignalAnalysis, type HistoricalReplayPoint } from "./marketWorkspace";

export type ResearchScope = "sectors" | "market";
export type ResearchGroup = {
  id: string; name: string; taxonomy: string; scope: ResearchScope;
  members: Array<{ticker: string; name: string; evidence?: Array<{source: string | null; source_as_of: string | null; relationship: string | null}>}>;
  daily: HistoricalReplayPoint[]; weekly: HistoricalReplayPoint[];
  cohorts: Record<string, string[]>; coverageReasons: Record<string, string>;
  definition?: string | null;
};
export const rotationPhase = (x: number | null | undefined, y: number | null | undefined) =>
  x == null || y == null || !Number.isFinite(x) || !Number.isFinite(y) ? "UNAVAILABLE" : y >= 0 ? (x >= 0 ? "LEADING" : "IMPROVING") : (x >= 0 ? "WEAKENING" : "LAGGING");

export function groupHref(group: Pick<ResearchGroup, "id" | "taxonomy" | "scope">, date?: string, cadence?: string, horizon = "60d") {
  const params = new URLSearchParams({taxonomy: group.taxonomy, group: group.id, scope: group.scope, horizon});
  if (date) params.set("date", date);
  if (cadence) params.set("cadence", cadence);
  return `/explorer?${params}`;
}

export function useResearch(defaultScope: ResearchScope = "market") {
  const [params, setParams] = useSearchParams();
  const scope: ResearchScope = params.get("scope") === "sectors" ? "sectors" : params.get("scope") === "market" ? "market" : defaultScope;
  const context = useHistoricalComparison(scope === "market");
  const native = useSectorsSignalAnalysis(scope === "sectors");
  const source = useRecordedSectorsSample(scope === "sectors");
  const state = scope === "sectors" ? native : context;
  const cadence: "daily" | "weekly" = params.get("cadence") === "daily" || (!params.get("cadence") && scope === "sectors") ? "daily" : "weekly";
  const horizon = params.get("horizon") === "ytd" ? "ytd" : "60d";
  const taxonomy = params.get("taxonomy") === "THEMES" ? "IDXIC" : params.get("taxonomy") ?? "SECTOR";
  const groups: ResearchGroup[] = [];
  if (scope === "market") {
    for (const [kind, catalog] of Object.entries(context.data?.taxonomies ?? {})) {
      for (const group of Object.values(catalog.groups)) groups.push({id: group.group_id, name: group.name, taxonomy: kind, scope,
        members: group.members, daily: group.daily, weekly: group.weekly,
        cohorts: group.cohorts ?? {"20d": group.cohort.contributors, map: group.cohort.contributors},
        coverageReasons: group.coverage_reasons ?? {}, definition: group.definition});
    }
  } else if (native.data) {
    const adapt = (mode: "daily" | "weekly", sector: string): HistoricalReplayPoint[] => native.data![mode].flatMap(day => {
      const group = day.groups.find(row => row.sector === sector);
      if (!group) return [];
      const map = group.descriptive_map ?? group.map;
      const value = (key: "5d" | "20d" | "60d") => group.returns[key].excess_return_pct ?? group.descriptive_returns?.[key].excess_return_pct ?? null;
      const count = group.diffusion.eligible_count;
      return [{as_of: day.date, excess_return_5d: value("5d"), excess_return_20d: value("20d"), excess_return_60d: value("60d"), excess_return_ytd: null,
        map_x_60d: map?.x_60d_excess_pct ?? null, map_x_ytd: null, map_y_ytd: null,
        relative_momentum: map?.y_relative_momentum_pct ?? null, map_contributors: map?.eligible_contributors ?? 0,
        breadth_count: group.diffusion.outperforming_count, breadth_denominator: count,
        breadth_pct: group.diffusion.breadth_pct, breadth_change_count: group.diffusion.change_count,
        breadth_change_pp: group.diffusion.breadth_pct != null && group.diffusion.previous_breadth_pct != null ? group.diffusion.breadth_pct - group.diffusion.previous_breadth_pct : null,
        leadership: group.leadership_state, diffusion: group.diffusion.state, diffusion_v2: group.diffusion.state,
        concentration_top3_pct: group.concentration_v2?.top3_abs_share != null ? group.concentration_v2.top3_abs_share * 100 : null,
        concentration_change_pp: null, rotation_phase: rotationPhase(map?.x_60d_excess_pct, map?.y_relative_momentum_pct),
        coverage_pct: group.contributor_counts["20d"] / 6 * 100, contributor_counts: group.contributor_counts}];
    });
    for (const group of native.data.daily.at(-1)?.groups ?? []) groups.push({id: group.sector, name: group.sector, taxonomy: "SECTOR", scope,
      members: group.contributors.map(row => ({ticker: row.ticker, name: row.company_name ?? row.ticker})),
      daily: adapt("daily", group.sector), weekly: adapt("weekly", group.sector),
      cohorts: {"20d": group.contributors.filter(row => row.contributes_20d).map(row => row.ticker), map: group.comparison_cohorts.map_tickers},
      coverageReasons: Object.fromEntries(group.contributors.filter(row => !row.contributes_20d).map(row => [row.ticker, row.returns["20d"].exclusion_reason ?? "Unavailable"]))});
  }
  const filtered = groups.filter(group => group.taxonomy === taxonomy);
  const dates = scope === "sectors" ? (native.data?.[cadence].map(row => row.date) ?? []) : cadence === "daily" ? context.data?.analysis_dates ?? [] : context.data?.comparison_dates ?? [];
  const requestedDate = params.get("date");
  const date = dates.includes(requestedDate ?? "") ? requestedDate! : dates.at(-1) ?? "";
  const histories = scope === "sectors" ? Object.fromEntries((source.data?.stocks ?? []).map(stock => [stock.ticker, stock.prices])) : context.data?.price_histories ?? {};
  const benchmark = scope === "sectors" ? source.data?.price_history.ihsg ?? [] : context.data?.benchmark_history ?? [];
  const reading = (group: ResearchGroup) => group[cadence].find(point => point.as_of === date);
  const set = (key: string, value: string) => {const next = new URLSearchParams(params); next.set(key, value); setParams(next, {replace: true});};
  return {params, setParams, set, scope, cadence, horizon, taxonomy, groups: filtered, allGroups: groups, dates, date, reading, histories, benchmark,
    loading: state.loading || (scope === "sectors" && source.loading), error: state.error ?? (scope === "sectors" ? source.error : null),
    native: native.data, context: context.data, source: source.data};
}
