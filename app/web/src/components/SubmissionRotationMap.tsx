import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useSnapshot } from "../data/SnapshotProvider";
import { useHistoricalComparison, useWorkspaceAsset, type HistoricalComparison } from "../data/marketWorkspace";
import { AssetLoadState } from "./AssetLoadState";
import { rotationPlotRanges, rotationTrailSegments, validRotationPoint } from "../data/mapGeometry";
import { replaySelection, type RotationReplay } from "../data/rotationReplay";
import type { SectorData, TaxonomyGroupData } from "../data/adapter";
import type { TaxonomyKind } from "../data/snapshot";
import { formatDateLabel, formatEnumLabel, formatPercent } from "../data/format";

type ReplayTaxonomy = "SECTOR" | "KONGLO" | "IDXIC" | "CURATED_THEMES";
const TAXONOMIES: Array<{ id: ReplayTaxonomy; label: string }> = [
  { id: "SECTOR", label: "Sectors" }, { id: "KONGLO", label: "Konglo" },
  { id: "CURATED_THEMES", label: "Curated themes" }, { id: "IDXIC", label: "IDXIC activities" },
];
const COLORS = ["#167f72", "#4278bd", "#d1713d", "#7865b3", "#bd547f", "#219caa", "#b58a21", "#d64b4b", "#637c9a", "#3eaa66", "#728d38", "#a05e8d"];
const SECTOR_ORDER = ["Basic Materials", "Consumer Cyclicals", "Consumer Non-Cyclicals", "Energy", "Financials", "Healthcare", "Industrials", "Infrastructures", "Properties & Real Estate", "Technology", "Transportation & Logistic"];
const PLOT = { left: 82, right: 956, top: 38, bottom: 614 };
type Point = { as_of: string; x: number | null; y: number | null; breadth?: number | null; breadthChange?: number | null; leadership?: string; diffusion?: string; rotationPhase?: string; concentration?: number | null; cohort_count?: number };
type MemberEvidence = { relationship: string | null; holder: string | null; ownership_percentage: number | null; membership_type: string; source: string | null; source_as_of: string | null; control_source: { owner?: string; ticker?: string; relationship?: string; as_of?: string; source?: string; ultimate_holders?: string[] } | null };
type Item = { id: string; name: string; kind: ReplayTaxonomy; members: number; memberList: Array<{ ticker: string; name: string; evidence?: MemberEvidence[] }>; x: number | null; y: number | null; excess20d: number | null; excess60d: number | null; breadth: number | null; leadership: string | null; diffusion: string | null; rotationPhase: string | null; concentration: number | null; breadthChange: number | null; definition: string | null; parentCategory: string | null; inclusionRules: string[]; exclusionRules: string[]; cohortCount: number; eligible: boolean; history: Point[]; color: string };

function colorFor(id: string): string {
  const sectorIndex = SECTOR_ORDER.indexOf(id);
  if (sectorIndex >= 0) return COLORS[sectorIndex];
  let hash = 0;
  for (const c of id) hash = (hash * 31 + c.charCodeAt(0)) >>> 0;
  return COLORS[hash % COLORS.length];
}

function currentAnalysis(comparison: HistoricalComparison | null, id: string) {
  return comparison?.weekly.at(-1)?.groups.find(group => group.group_id === id);
}

function LeadershipReading({ state }: { state: string | null | undefined }) {
  if (state === "UNCONFIRMED") return <span aria-label="No classified leadership state">—</span>;
  return <>{formatEnumLabel(state)}</>;
}

function DiffusionReading({ state }: { state: string | null | undefined }) {
  if (state === "UNCONFIRMED") return <span aria-label="No comparable diffusion reading">—</span>;
  return <>{formatEnumLabel(state)}</>;
}

function xScale(value: number, range: [number, number]) { return PLOT.left + (value - range[0]) / (range[1] - range[0]) * (PLOT.right - PLOT.left); }
function yScale(value: number, range: [number, number]) { return PLOT.bottom - (value - range[0]) / (range[1] - range[0]) * (PLOT.bottom - PLOT.top); }

function sectorHistory(comparison: HistoricalComparison | null, id: string): Point[] {
  if (!comparison) return [];
  return comparison.weekly.flatMap(week => week.groups.filter(row => row.group_id === id).map(row => ({
    as_of: week.as_of,
    x: row.excess_return_ytd,
    y: row.relative_momentum,
    breadth: row.breadth_pct,
    leadership: row.leadership,
    diffusion: row.diffusion,
    concentration: row.concentration_top3_pct,
    cohort_count: row.cohort_count,
  })));
}

function BasketChart({ comparison }: { comparison: HistoricalComparison }) {
  const [visible, setVisible] = useState<Set<string>>(() => new Set(comparison.sector_baskets.groups.map(row => row.group_id)));
  const [showBenchmark, setShowBenchmark] = useState(true);
  const basket = comparison.sector_baskets;
  const chartRows = useMemo(() => basket.series.map(point => {
    const row: Record<string, string | number> = { as_of: point.as_of, IHSG: point.return_pct };
    for (const group of basket.groups) {
      const value = group.values.find(item => item.as_of === point.as_of)?.return_pct;
      if (value !== undefined) row[group.group_id] = value;
    }
    return row;
  }), [basket]);
  const toggle = (id: string) => setVisible(previous => {
    const next = new Set(previous);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  return (
    <section className="dash-card submission-basket-card" aria-labelledby="basket-title">
      <div className="eyebrow-muted">Computed stock baskets</div>
      <h2 id="basket-title" style={{ margin: "4px 0 4px", fontSize: 20, fontWeight: 500 }}>Sector baskets vs IHSG</h2>
      <p className="meta">Equal-weight current-member adjusted-price returns, rebased to zero · {formatDateLabel(basket.start)}–{formatDateLabel(basket.end)}. These are computed baskets, not IDX sector indices.</p>
      <div className="submission-basket-chart" role="img" aria-label="Computed sector stock baskets and IHSG, rebased to zero">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows} margin={{ top: 12, right: 18, left: 2, bottom: 4 }}>
            <XAxis dataKey="as_of" minTickGap={45} tickFormatter={value => formatDateLabel(String(value)).slice(0, 6)} tick={{ fontSize: 10 }} />
            <YAxis tickFormatter={value => `${Number(value).toFixed(0)}%`} width={48} tick={{ fontSize: 10 }} />
            <Tooltip labelFormatter={value => formatDateLabel(String(value))} formatter={(value, name) => [`${Number(value).toFixed(2)}%`, name === "IHSG" ? "IHSG" : basket.groups.find(row => row.group_id === name)?.name ?? name]} />
            <Line type="monotone" dataKey="IHSG" hide={!showBenchmark} stroke="#20272e" strokeDasharray="7 5" dot={false} strokeWidth={2.5} isAnimationActive={false} />
            {basket.groups.map(group => <Line key={group.group_id} type="monotone" dataKey={group.group_id} hide={!visible.has(group.group_id)} stroke={colorFor(group.group_id)} dot={false} strokeWidth={1.7} isAnimationActive={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="submission-basket-legend" aria-label="Select sector basket series">
        {basket.groups.map(group => {
          const last = group.values.at(-1)?.return_pct;
          return <button key={group.group_id} type="button" aria-pressed={visible.has(group.group_id)} onClick={() => toggle(group.group_id)} style={{ color: visible.has(group.group_id) ? colorFor(group.group_id) : "var(--muted)" }}><i style={{ background: colorFor(group.group_id) }} />{group.name}<strong>{formatPercent(last ?? null)}</strong></button>;
        })}
        <button type="button" aria-pressed={showBenchmark} onClick={() => setShowBenchmark(value => !value)}><i className="basket-ihsg-key" />IHSG<strong>{formatPercent(basket.series.at(-1)?.return_pct ?? null)}</strong></button>
      </div>
      <details className="submission-source-details"><summary>Basket method and coverage</summary><p>{basket.basis}. IHSG uses the benchmark close series and the same start session. Coverage varies by sector and is listed below.</p><ul>{basket.groups.map(row => <li key={row.group_id}>{row.name}: {row.contributor_count} of its matched cohort names have a full Q3 price trail.</li>)}</ul></details>
    </section>
  );
}

export default function SubmissionRotationMap() {
  const snapshot = useSnapshot();
  const { data } = snapshot;
  const comparison = useHistoricalComparison();
  const replay = useWorkspaceAsset<RotationReplay>("rotation");
  const [params, setParams] = useSearchParams();
  const rawTaxonomy = params.get("taxonomy")?.toUpperCase();
  const kind: ReplayTaxonomy = rawTaxonomy === "KONGLO" || rawTaxonomy === "CURATED_THEMES" || rawTaxonomy === "IDXIC"
    ? rawTaxonomy : rawTaxonomy === "THEMES" ? "IDXIC" : "SECTOR";
  const search = params.get("q") ?? "";
  const [showAll, setShowAll] = useState(false);
  const [cadence, setCadence] = useState<"weekly" | "daily">("weekly");
  const [replayIndex, setReplayIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const selectedId = params.get("group");
  const taxonomy = comparison.data?.taxonomies?.[kind];
  const taxonomyName = kind === "SECTOR" ? "IDX sector classification"
    : kind === "KONGLO" ? "Documented corporate portfolios"
      : kind === "CURATED_THEMES" ? "Curated business themes"
        : "IDXIC subindustries";
  const membershipBasis = kind === "SECTOR" ? "Captured IDXIC sector classification"
    : taxonomy?.membership_source_basis === "DOCUMENTED_HOLDINGS" ? "Dated documented holdings"
      : taxonomy?.membership_source_basis === "CLASSIFICATION_CAPTURE" ? "Captured IDXIC classification"
        : taxonomy?.membership_source_basis === "ANALYST_DEFINED_FROM_DATED_IDXIC_ACTIVITIES" ? "Curated from dated IDXIC activities"
          : "Selected-release membership";
  const replayDates = taxonomy
    ? cadence === "daily" ? (comparison.data?.analysis_dates ?? []) : (comparison.data?.comparison_dates ?? [])
    : kind === "SECTOR" ? (comparison.data?.comparison_dates ?? []) : [];
  const activeIndex = replayDates.length ? (replayIndex < 0 ? replayDates.length - 1 : Math.min(replayIndex, replayDates.length - 1)) : -1;
  const currentDate = activeIndex >= 0 ? replayDates[activeIndex] : data?.payload.as_of;

  useEffect(() => {
    if (params.get("mode") === "stocks") {
      const next = new URLSearchParams(params); next.set("mode", "groups"); setParams(next, { replace: true });
    }
  }, [params, setParams]);
  useEffect(() => { setReplayIndex(-1); setPlaying(false); }, [kind, cadence, comparison.data?.as_of]);
  useEffect(() => {
    if (!playing || activeIndex < 0) return;
    if (activeIndex >= replayDates.length - 1) { setPlaying(false); return; }
    const timer = window.setInterval(() => setReplayIndex(index => Math.min((index < 0 ? 0 : index) + 1, replayDates.length - 1)), 850);
    return () => window.clearInterval(timer);
  }, [playing, activeIndex, replayDates.length]);

  const items = useMemo<Item[]>(() => {
    if (!data) return [];
    if (taxonomy && activeIndex >= 0) {
      return Object.values(taxonomy.groups).map(group => {
        const series = cadence === "daily" ? group.daily : group.weekly;
        const current = series[activeIndex];
        const history = series.map(point => ({
          as_of: point.as_of,
          x: point.excess_return_ytd,
          y: point.relative_momentum,
          breadth: point.breadth_pct,
          breadthChange: point.breadth_change_pp,
          leadership: point.leadership,
          diffusion: point.diffusion_v2,
          rotationPhase: point.rotation_phase,
          concentration: point.concentration_top3_pct,
          cohort_count: point.breadth_denominator,
        }));
        return {
          id: group.group_id, name: group.name, kind,
          members: group.member_count, memberList: group.members,
          x: current?.excess_return_ytd ?? null, y: current?.relative_momentum ?? null,
          excess20d: current?.excess_return_20d ?? null, excess60d: current?.excess_return_60d ?? null,
          breadth: current?.breadth_pct ?? null, leadership: current?.leadership ?? null,
          diffusion: current?.diffusion_v2 ?? null, rotationPhase: current?.rotation_phase ?? null,
          concentration: current?.concentration_top3_pct ?? null, breadthChange: current?.breadth_change_pp ?? null,
          definition: group.definition ?? null, parentCategory: group.parent_category ?? null,
          inclusionRules: group.inclusion_rules ?? [], exclusionRules: group.exclusion_rules ?? [],
          cohortCount: group.cohort.count, eligible: group.cohort.count >= 5, history, color: colorFor(group.group_id),
        };
      }).sort((a, b) => b.cohortCount - a.cohortCount || a.name.localeCompare(b.name));
    }
    if (kind === "SECTOR") {
      return data.sectors.map((group: SectorData) => {
        const calc = currentAnalysis(comparison.data, group.id) ?? currentAnalysis(comparison.data, group.name);
        const sectorTaxonomy = Object.values(data.taxonomyGroups).find(candidate => candidate.taxonomyKind === "SECTOR" && candidate.name === group.name);
        const memberRows = (sectorTaxonomy && data.constituentsByTaxonomyGroup[`${sectorTaxonomy.taxonomyId}::${sectorTaxonomy.id}`]) ?? data.constituentsByGroup[group.id] ?? [];
        const history = sectorHistory(comparison.data, group.id).length ? sectorHistory(comparison.data, group.id) : sectorHistory(comparison.data, group.name);
        const x = calc?.excess_return_ytd ?? group.excessYtd;
        const y = calc?.relative_momentum ?? (group.excess20d !== null && group.excess60d !== null ? group.excess20d - group.excess60d : null);
        return {
          id: group.id, name: group.name, kind, members: memberRows.length || group.eligibleConstituents,
          memberList: memberRows.map(row => ({ ticker: row.ticker, name: row.name })).sort((a, b) => a.ticker.localeCompare(b.ticker)),
          x, y, excess20d: calc?.excess_return_20d ?? group.excess20d, excess60d: calc?.excess_return_60d ?? group.excess60d,
          breadth: calc?.breadth_pct ?? group.breadth, leadership: calc?.leadership ?? group.leadership,
          diffusion: calc?.diffusion ?? group.diffusion, rotationPhase: x !== null && y !== null ? (x >= 0 ? y >= 0 ? "LEADING" : "WEAKENING" : y >= 0 ? "IMPROVING" : "LAGGING") : null,
          concentration: calc?.concentration_top3_pct ?? group.concentration, breadthChange: calc?.breadth_change_pp ?? null,
          definition: null, parentCategory: null, inclusionRules: [], exclusionRules: [],
          cohortCount: calc?.cohort_count ?? group.eligibleConstituents, eligible: (calc?.cohort_count ?? group.eligibleConstituents) >= 5,
          history, color: colorFor(group.id),
        };
      }).sort((a, b) => b.cohortCount - a.cohortCount || a.name.localeCompare(b.name));
    }
    if (kind === "CURATED_THEMES") return [];
    const legacyKind: TaxonomyKind = kind === "IDXIC" ? "THEMES" : "KONGLO";
    return Object.values(data.taxonomyGroups).filter((group: TaxonomyGroupData) => group.taxonomyKind === legacyKind).map((group: TaxonomyGroupData) => {
      const selection = replay.data ? replaySelection(replay.data, legacyKind, group.id, "weekly", { relativeStrength: group.excessYtd, excess20d: group.excess20d, excess60d: group.excess60d }) : { points: [], reason: null };
      const memberRows = data.constituentsByTaxonomyGroup[`${group.taxonomyId}::${group.id}`] ?? [];
      const history = selection.points.map(point => ({ as_of: point.as_of, x: point.group_excess_return_ytd, y: point.relative_momentum }));
      return {
        id: group.id, name: group.name, kind, members: memberRows.length || group.eligible || group.constituents,
        memberList: memberRows.map(row => ({ ticker: row.ticker, name: row.name })).sort((a, b) => a.ticker.localeCompare(b.ticker)),
        x: group.excessYtd, y: group.excess20d !== null && group.excess60d !== null ? group.excess20d - group.excess60d : null,
        excess20d: group.excess20d, excess60d: group.excess60d, breadth: group.breadth,
        leadership: group.leadership, diffusion: group.diffusion, rotationPhase: null, concentration: group.concentration,
        breadthChange: group.breadthDelta, definition: null, parentCategory: null, inclusionRules: [], exclusionRules: [],
        cohortCount: group.eligible || group.constituents, eligible: (group.eligible || group.constituents) >= 5, history, color: colorFor(group.id),
      };
    }).sort((a, b) => b.cohortCount - a.cohortCount || a.name.localeCompare(b.name));
  }, [data, comparison.data, replay.data, taxonomy, activeIndex, cadence, kind]);

  const normalizedSearch = search.trim().toLowerCase();
  const searched = items.filter(item => !normalizedSearch || `${item.name} ${item.id}`.toLowerCase().includes(normalizedSearch));
  const limited = !showAll && !normalizedSearch && kind !== "SECTOR" ? searched.filter(item => item.eligible).slice(0, 12) : searched;
  const plotted = limited.filter(item => item.eligible && item.x !== null && item.y !== null && Number.isFinite(item.x) && Number.isFinite(item.y));
  const { x: xRange, y: yRange } = rotationPlotRanges(plotted);
  const selected = limited.find(item => item.id === selectedId) ?? plotted[0] ?? null;
  const q = (key: string, value: string) => { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); setParams(next, { replace: true }); };
  const choose = (id: string) => q("group", id);
  const analysisAvailable = Boolean(taxonomy && replayDates.length);
  const trailLength = 4;
  const dateLabel = currentDate ? formatDateLabel(currentDate) : "";
  const taxonomyCount = taxonomy?.group_count ?? items.length;

  if (!data || snapshot.error || snapshot.loading || comparison.loading || comparison.error || (!comparison.data && kind !== "SECTOR" && (replay.loading || replay.error))) {
    return <main className="workspace-page"><h1>Group rotation</h1><AssetLoadState label="Rotation replay" loading={snapshot.loading || comparison.loading || replay.loading} error={snapshot.error ?? comparison.error ?? replay.error} absentMessage="No snapshot is included in this release." /></main>;
  }

  return (
    <main className="workspace-page submission-rotation-page">
      <header className="submission-page-heading">
        <div><div className="eyebrow-muted">Market structure · {dateLabel}</div><h1>Group rotation</h1><p>YTD excess versus IHSG on the horizontal axis; 20D minus 60D excess on the vertical axis. Select a point, legend item, or row to inspect its dated path.</p></div>
        <div className="submission-heading-links"><Link to="/groups">Catalog</Link><Link to="/methodology">Methodology</Link></div>
      </header>
      <nav className="submission-tabs" aria-label="Rotation taxonomy">
        {TAXONOMIES.map(option => <button key={option.id} type="button" aria-pressed={kind === option.id} onClick={() => {
          const next = new URLSearchParams(params);
          next.set("taxonomy", option.id);
          next.delete("group");
          setParams(next, { replace: true });
          setShowAll(false);
          setReplayIndex(-1);
        }}>{option.label}<span>{comparison.data?.taxonomies?.[option.id]?.group_count ?? (option.id === "SECTOR" ? data?.sectors.length ?? 0 : option.id === "KONGLO" ? Object.values(data?.taxonomyGroups ?? {}).filter(group => group.taxonomyKind === "KONGLO").length : option.id === "IDXIC" ? Object.values(data?.taxonomyGroups ?? {}).filter(group => group.taxonomyKind === "THEMES").length : 0)}</span></button>)}
      </nav>
      <div className="submission-controls">
        <label className="submission-search"><span className="sr-only">Search groups</span><input type="search" placeholder={`Search ${kind === "SECTOR" ? "sector" : kind === "IDXIC" ? "IDXIC activity" : kind === "CURATED_THEMES" ? "curated theme" : "Konglo"}…`} value={search} onChange={event => q("q", event.target.value)} /></label>
        {kind !== "SECTOR" && <button type="button" className="btn btn-outline" onClick={() => setShowAll(value => !value)}>{showAll ? "Show largest 12" : `Show all ${taxonomyCount}`}</button>}
        <span>{plotted.length} groups on map · {limited.length} listed{kind !== "SECTOR" && !showAll && !normalizedSearch ? " · largest eligible groups" : ""}</span>
      </div>
      <div className="replay-strip"><strong>Historical price replay using current membership</strong><span>{comparison.data ? `${formatDateLabel(comparison.data.comparison_dates[0])} → ${formatDateLabel(comparison.data.comparison_dates.at(-1)!)} · ${taxonomyName} · membership dated ${formatDateLabel(taxonomy?.membership_as_of ?? comparison.data.membership_as_of)}` : "Dated comparison data is not attached to this release."}</span><details><summary>Replay basis</summary><p>{taxonomy ? `Membership recorded as of ${formatDateLabel(taxonomy.membership_as_of ?? comparison.data?.membership_as_of ?? "")}: ${membershipBasis}. ${comparison.data?.replay_basis ?? ""}` : comparison.data?.replay_basis}</p><p>{comparison.data?.limitations.join(" ")}</p></details></div>
      {analysisAvailable && <div className="replay-controls" aria-label="Historical replay controls">
        <div className="replay-cadence" role="group" aria-label="Replay cadence"><button type="button" aria-pressed={cadence === "weekly"} onClick={() => setCadence("weekly")}>Weekly</button><button type="button" aria-pressed={cadence === "daily"} onClick={() => setCadence("daily")}>Daily</button></div>
        <button type="button" className="btn btn-outline" disabled={activeIndex <= 0} onClick={() => { setPlaying(false); setReplayIndex(Math.max(0, activeIndex - 1)); }}>Previous</button>
        <button type="button" className="btn btn-outline" disabled={activeIndex >= replayDates.length - 1} onClick={() => { setPlaying(false); setReplayIndex(Math.min(replayDates.length - 1, activeIndex + 1)); }}>Next</button>
        <button type="button" className="btn btn-primary" onClick={() => { if (activeIndex >= replayDates.length - 1) setReplayIndex(0); setPlaying(value => !value); }}>{playing ? "Pause" : "Play"}</button>
        <strong>{dateLabel}</strong><span>{trailLength} trail intervals · {cadence}</span>
      </div>}
      <section className="submission-map-layout" aria-label="Group rotation map and inspector">
        <div className="submission-map-card">
          <div className="submission-axis-note"><span>Relative momentum</span><span>Up = 20D excess minus 60D excess</span></div>
          <div className="submission-map-scroll">
            {plotted.length === 0 && <p className="meta" role="status">No matching eligible groups have both axis readings for this date. Use the table to inspect available readings and coverage.</p>}
            {plotted.length > 0 && <svg className="submission-map-svg" viewBox="0 0 1000 700" preserveAspectRatio="none" role="img" aria-label={`${kind} rotation plot: YTD excess return versus IHSG against 20D minus 60D excess momentum`}>
              <rect x={PLOT.left} y={PLOT.top} width={xScale(0, xRange) - PLOT.left} height={yScale(0, yRange) - PLOT.top} fill="#e8eff5" />
              <rect x={xScale(0, xRange)} y={PLOT.top} width={PLOT.right - xScale(0, xRange)} height={yScale(0, yRange) - PLOT.top} fill="#e6f1ef" />
              <rect x={PLOT.left} y={yScale(0, yRange)} width={xScale(0, xRange) - PLOT.left} height={PLOT.bottom - yScale(0, yRange)} fill="#f3e9eb" />
              <rect x={xScale(0, xRange)} y={yScale(0, yRange)} width={PLOT.right - xScale(0, xRange)} height={PLOT.bottom - yScale(0, yRange)} fill="#f3f0e7" />
              {Array.from({ length: 7 }, (_, index) => { const x = PLOT.left + index / 6 * (PLOT.right - PLOT.left); return <line key={`x${index}`} x1={x} x2={x} y1={PLOT.top} y2={PLOT.bottom} stroke="#d5dddf" />; })}
              {Array.from({ length: 7 }, (_, index) => { const y = PLOT.top + index / 6 * (PLOT.bottom - PLOT.top); return <line key={`y${index}`} x1={PLOT.left} x2={PLOT.right} y1={y} y2={y} stroke="#d5dddf" />; })}
              <line x1={xScale(0, xRange)} x2={xScale(0, xRange)} y1={PLOT.top} y2={PLOT.bottom} stroke="#758487" strokeWidth="1.6" />
              <line x1={PLOT.left} x2={PLOT.right} y1={yScale(0, yRange)} y2={yScale(0, yRange)} stroke="#758487" strokeWidth="1.6" />
              <text x={PLOT.left} y={PLOT.bottom + 25} textAnchor="start">{xRange[0].toFixed(0)}%</text><text x={xScale(0, xRange)} y={PLOT.bottom + 25} textAnchor="middle">0%</text><text x={PLOT.right} y={PLOT.bottom + 25} textAnchor="end">{xRange[1].toFixed(0)}%</text>
              <text x={PLOT.left - 12} y={PLOT.top + 4} textAnchor="end">{yRange[1].toFixed(0)}%</text><text x={PLOT.left - 12} y={yScale(0, yRange) + 4} textAnchor="end">0%</text><text x={PLOT.left - 12} y={PLOT.bottom} textAnchor="end">{yRange[0].toFixed(0)}%</text>
              <text x={(PLOT.left + PLOT.right) / 2} y="680" textAnchor="middle" className="map-axis-title">YTD excess return vs IHSG (%)</text>
              <text x="18" y={(PLOT.top + PLOT.bottom) / 2} textAnchor="middle" className="map-axis-title" transform={`rotate(-90 18 ${(PLOT.top + PLOT.bottom) / 2})`}>20D excess − 60D excess (%)</text>
              {plotted.map(item => {
                const trail = item.history.slice(Math.max(0, activeIndex - trailLength), activeIndex + 1);
                return rotationTrailSegments(trail).filter(segment => segment.length > 1).map((segment, index) => <g key={`trail-${item.id}-${index}`}><polyline points={segment.map(point => `${xScale(point.x, xRange)},${yScale(point.y, yRange)}`).join(" ")} fill="none" stroke={item.color} strokeWidth={selected?.id === item.id ? 3 : 1.8} opacity={selected?.id === item.id ? .9 : .3} /><circle cx={xScale(segment[0].x, xRange)} cy={yScale(segment[0].y, yRange)} r="3" fill={item.color} opacity=".36" /></g>);
              })}
              {plotted.map(item => <g key={item.id} role="button" tabIndex={0} aria-label={`${item.name}: ${formatPercent(item.x)} YTD excess, ${formatPercent(item.y)} relative momentum`} onClick={() => choose(item.id)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") choose(item.id); }} style={{ cursor: "pointer" }}><circle cx={xScale(item.x!, xRange)} cy={yScale(item.y!, yRange)} r={selected?.id === item.id ? 9 : 6.5} fill={item.color} stroke={selected?.id === item.id ? "#17212a" : "#fff"} strokeWidth={selected?.id === item.id ? 2.5 : 1.5} /><title>{item.name} · {formatPercent(item.x)} YTD excess · {formatPercent(item.y)} relative momentum</title></g>)}
              {selected && plotted.some(item => item.id === selected.id) && validRotationPoint(selected) && <text x={Math.min(PLOT.right - 6, xScale(selected.x, xRange) + 12)} y={Math.max(PLOT.top + 12, yScale(selected.y, yRange) - 10)} className="selected-point-label">{selected.name}</text>}
              <text x={PLOT.left + 12} y={PLOT.top + 19} className="quadrant-label">Improving</text><text x={PLOT.right - 12} y={PLOT.top + 19} textAnchor="end" className="quadrant-label">Leading</text><text x={PLOT.left + 12} y={PLOT.bottom - 12} className="quadrant-label">Lagging</text><text x={PLOT.right - 12} y={PLOT.bottom - 12} textAnchor="end" className="quadrant-label">Weakening</text>
            </svg>}
          </div>
          <div className="submission-legend" aria-label="Select a group">
            {plotted.map(item => <button key={item.id} type="button" aria-pressed={selected?.id === item.id} onClick={() => choose(item.id)}><i style={{ background: item.color }} /><span>{item.name}</span><small>{formatPercent(item.x)}</small></button>)}
          </div>
        </div>
        <aside className="submission-inspector" aria-live="polite">
          {selected ? <>
            <div className="eyebrow-muted">Selected group · {dateLabel}</div>
            <h2 style={{ borderColor: selected.color }}>{selected.name}</h2>
            {selected.parentCategory && <p className="inspector-parent">{selected.parentCategory}</p>}
            <div className="inspector-lead">{selected.x !== null && selected.y !== null ? `${selected.x >= 0 ? "Ahead" : "Behind"} IHSG · ${selected.y >= 0 ? "gaining" : "losing"} relative momentum` : "Metrics are not available for this date"}</div>
            <dl><div><dt>YTD excess</dt><dd>{formatPercent(selected.x)}</dd></div><div><dt>20D excess</dt><dd>{formatPercent(selected.excess20d)}</dd></div><div><dt>60D excess</dt><dd>{formatPercent(selected.excess60d)}</dd></div><div><dt>Breadth</dt><dd>{selected.breadth === null ? "—" : `${selected.breadth.toFixed(1)}%`}</dd></div><div><dt>Breadth change</dt><dd>{selected.breadthChange === null ? "—" : `${selected.breadthChange > 0 ? "+" : ""}${selected.breadthChange.toFixed(1)}pp`}</dd></div><div><dt>Leadership</dt><dd><LeadershipReading state={selected.leadership} /></dd></div><div><dt>Rotation phase</dt><dd>{selected.cohortCount >= 5 ? selected.rotationPhase ?? "—" : "—"}</dd></div><div><dt>Diffusion</dt><dd>{selected.cohortCount >= 5 ? <DiffusionReading state={selected.diffusion} /> : "—"}</dd></div><div><dt>Top-three concentration</dt><dd>{selected.concentration === null ? "—" : `${selected.concentration.toFixed(1)}%`}</dd></div><div><dt>Contributors / members</dt><dd>{selected.cohortCount.toLocaleString()} / {selected.members.toLocaleString()}</dd></div></dl>
            {selected.definition && <p className="inspector-definition">{selected.definition}</p>}
            {selected.memberList.length > 0 && <details className="inspector-members"><summary>Members · {selected.memberList.length}</summary><ul>{selected.memberList.map(member => <li key={member.ticker}><Link to={`/ticker/${encodeURIComponent(member.ticker.replace(/\.JK$/i, ""))}`}>{member.ticker.replace(/\.JK$/i, "")}</Link><span>{member.name}</span>{member.evidence?.map((evidence, index) => <small key={`${member.ticker}-${index}`}>{evidence.relationship ?? "Relationship not separately specified"}{evidence.holder ? ` · holder: ${evidence.holder}` : ""}{evidence.ownership_percentage !== null ? ` · ${evidence.ownership_percentage.toFixed(2)}%` : ""}{evidence.source_as_of ? ` · ${formatDateLabel(evidence.source_as_of)}` : ""}{evidence.source?.startsWith("https://") ? <> · <a href={evidence.source} target="_blank" rel="noreferrer">evidence</a></> : evidence.source ? ` · ${evidence.source}` : ""}{evidence.control_source?.relationship ? ` · ${evidence.control_source.relationship} as of ${evidence.control_source.as_of ?? ""}` : ""}{evidence.control_source?.ultimate_holders?.length ? ` · ultimate holders: ${evidence.control_source.ultimate_holders.join(", ")}` : ""}{evidence.control_source?.source?.startsWith("https://") ? <> · <a href={evidence.control_source.source} target="_blank" rel="noreferrer">issuer control disclosure</a></> : ""}</small>)}</li>)}</ul></details>}
            {(selected.inclusionRules.length > 0 || selected.exclusionRules.length > 0) && <details className="inspector-members"><summary>Theme definition</summary><strong>Included by</strong><ul>{selected.inclusionRules.map(rule => <li key={rule}>{rule}</li>)}</ul><strong>Excluded by</strong><ul>{selected.exclusionRules.map(rule => <li key={rule}>{rule}</li>)}</ul></details>}
            {selected.history.length > 0 && <div className="inspector-history"><h3>Measured {cadence} path</h3>{selected.history.slice(Math.max(0, activeIndex - trailLength), activeIndex + 1).map(point => <div key={point.as_of}><time>{formatDateLabel(point.as_of)}</time><span>{formatPercent(point.x)} / {formatPercent(point.y)}</span><small>{point.breadth?.toFixed(1) ?? "—"}% breadth · Leadership <LeadershipReading state={point.leadership} /> · Rotation {selected.cohortCount >= 5 ? point.rotationPhase ?? "—" : "—"}</small></div>)}</div>}
          </> : <p>Select a group point, legend entry, or table row.</p>}
        </aside>
      </section>
      <section className="submission-rotation-table"><h2>Group readings · {dateLabel}</h2><div className="table-scroll"><table><thead><tr><th>Group</th><th>Leadership</th><th>Rotation phase</th><th>YTD excess</th><th>Momentum</th><th>Breadth</th><th>Contributors</th><th>Members</th></tr></thead><tbody>{limited.map(item => <tr key={item.id} onClick={() => choose(item.id)}><td><button type="button" style={{ color: item.color }}>{item.name}</button></td><td><LeadershipReading state={item.leadership} /></td><td>{item.cohortCount >= 5 ? item.rotationPhase ?? "—" : "—"}</td><td>{formatPercent(item.x)}</td><td>{formatPercent(item.y)}</td><td>{item.breadth === null ? "—" : `${item.breadth.toFixed(1)}%`}</td><td>{item.cohortCount.toLocaleString()}</td><td>{item.members.toLocaleString()}</td></tr>)}</tbody></table></div></section>
      {kind === "SECTOR" && comparison.data && <BasketChart comparison={comparison.data} />}
    </main>
  );
}
