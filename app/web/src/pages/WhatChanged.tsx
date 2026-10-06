import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import type { BreadthHistoryPoint, SectorData } from "../data/adapter";
import { LeadershipChip, DiffusionChip } from "../components/StatusChips";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, CartesianGrid } from "recharts";
import { formatDateLabel, formatPercent, formatSnapshotId } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";
import { useHistoricalComparison } from "../data/marketWorkspace";


function averageBreadthHistory(
  points: BreadthHistoryPoint[],
): Array<{ as_of: string; breadth: number }> {
  const byDate = new Map<string, number[]>();
  for (const point of points) {
    const values = byDate.get(point.as_of) ?? [];
    values.push(point.breadth);
    byDate.set(point.as_of, values);
  }
  return [...byDate.entries()]
    .map(([as_of, values]) => ({
      as_of,
      breadth: values.reduce((sum, value) => sum + value, 0) / values.length,
    }))
    .sort((a, b) => a.as_of.localeCompare(b.as_of));
}

const num = (v: number | null | undefined, suffix = "%") => {
  const unavailable = v === null || v === undefined || !Number.isFinite(v);
  return (
    <span
      style={{
        color: unavailable ? "var(--muted)" : v > 0 ? "var(--up)" : v < 0 ? "var(--down)" : "var(--muted)",
        fontFamily: "Geist Mono",
        fontSize: 12,
      }}
    >
      {unavailable ? "—" : suffix === "%" ? formatPercent(v) : `${v > 0 ? "+" : ""}${v.toFixed(1)}${suffix}`}
    </span>
  );
};

const delta = (s: SectorData) =>
  s.prevBreadth === undefined || s.breadth === null
    ? null
    : s.breadth - s.prevBreadth;

function formatAsOf(asOf: string | null | undefined): string {
  return formatDateLabel(asOf);
}

function summaryStats(sectors: SectorData[], hasComparable: boolean): Array<[string, string]> {
  if (sectors.length === 0) {
    return [
      ["IDX leadership", "—"],
      ["Breadth", "—"],
      ["Broadening vs prior", "—"],
      ["Narrowing vs prior", "—"],
      ["Data coverage", "—"],
    ];
  }
  const breadthValues = sectors
    .map((s) => s.breadth)
    .filter((v): v is number => v !== null && Number.isFinite(v));
  const breadth = breadthValues.length
    ? `${Math.round(breadthValues.reduce((a, b) => a + b, 0) / breadthValues.length)}%`
    : "—";
  const broadening = sectors.filter((s) => s.diffusion === "BROADENING").length;
  const narrowing = sectors.filter((s) => s.diffusion === "NARROWING").length;
  const classified = sectors.filter(
    (s) => s.leadership !== "UNCONFIRMED",
  ).length;
  return [
    ["IDX leadership", `${classified}/${sectors.length} classified`],
    ["Breadth", breadth],
    ["Broadening vs prior", hasComparable ? String(broadening) : "—"],
    ["Narrowing vs prior", hasComparable ? String(narrowing) : "—"],
    ["Data coverage", `${sectors.reduce((a, s) => a + s.eligibleConstituents, 0)} eligible`],
  ];
}

function leadershipCounts(sectors: SectorData[]) {
  return {
    LEADING: sectors.filter((s) => s.leadership === "LEADING").length,
    IMPROVING: sectors.filter((s) => s.leadership === "IMPROVING").length,
    WEAKENING: sectors.filter((s) => s.leadership === "WEAKENING").length,
    LAGGING: sectors.filter((s) => s.leadership === "LAGGING").length,
  };
}

function diffusionCounts(sectors: SectorData[]) {
  const broadening = sectors.filter((s) => String(s.diffusion).startsWith("BROADENING")).length;
  const stable = sectors.filter((s) => s.diffusion === "STABLE").length;
  const narrowing = sectors.filter((s) => String(s.diffusion).startsWith("NARROWING")).length;
  return { BROADENING: broadening, STABLE: stable, NARROWING: narrowing };
}

function categorizeChanges(sectors: SectorData[]) {
  const newLeaders = sectors.filter((s) => s.prevLeadership && s.prevLeadership !== "LEADING" && s.leadership === "LEADING");
  const lostLeaders = sectors.filter((s) => s.prevLeadership === "LEADING" && s.leadership !== "LEADING");
  const improvingToLeading = sectors.filter((s) => s.prevLeadership === "IMPROVING" && s.leadership === "LEADING");
  const leadingToWeakening = sectors.filter((s) => s.prevLeadership === "LEADING" && s.leadership === "WEAKENING");
  const withDelta = sectors.filter((s) => delta(s) !== null) as Array<SectorData & { breadth: number }>;
  const fastestExpansion = [...withDelta].sort((a,b) => (delta(b) ?? -Infinity) - (delta(a) ?? -Infinity)).slice(0,3);
  const fastestContraction = [...withDelta].sort((a,b) => (delta(a) ?? Infinity) - (delta(b) ?? Infinity)).slice(0,3);
  const withConc = sectors.filter((s) => s.concentration !== null).sort((a,b) => (b.concentration ?? 0) - (a.concentration ?? 0));
  const highConcentration = withConc.slice(0,3);
  return { newLeaders, lostLeaders, improvingToLeading, leadingToWeakening, fastestExpansion, fastestContraction, highConcentration };
}

function ConstituentCoverage({
  sectors,
  constituentsByGroup,
}: {
  sectors: SectorData[];
  constituentsByGroup: Record<string, Array<{ participating: boolean | null; return20d: number | null }> >;
}) {
  const visibleSectors = sectors.slice(0, 5);
  return (
    <div
      aria-label="Constituent participation by group"
      style={{ border: "1px solid var(--line)", background: "var(--surface-subtle)", padding: "5px 14px" }}
    >
      {visibleSectors.map((sector, index) => {
        const rows = constituentsByGroup[sector.id] ?? [];
        const available = rows.filter((row) => row.return20d !== null).length;
        const participating = rows.filter((row) => row.participating === true).length;
        return (
          <div
            key={sector.id}
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 12,
              padding: "8px 0",
              borderBottom: index < visibleSectors.length - 1 ? "1px solid #dfe2e1" : "none",
              fontSize: 12,
            }}
          >
            <span style={{ fontWeight: 600 }}>{sector.name}</span>
            <span className="eyebrow-muted">
              {available > 0 ? `${participating}/${available} outperforming` : "—"}
            </span>
          </div>
        );
      })}
      {sectors.length > visibleSectors.length && (
        <div className="eyebrow-muted" style={{ padding: "8px 0 4px" }}>
          + {sectors.length - visibleSectors.length} additional groups
        </div>
      )}
    </div>
  );
}

export default function WhatChanged() {
  const { data, payload } = useSnapshot();
  const historical = useHistoricalComparison();
  const navigate = useNavigate();
  const [sort, setSort] = useState<"rank" | "delta">("rank");
  const sectors = data?.sectors ?? [];
  const breadthHistory = data?.breadthHistory ?? [];
  const averageHistory = useMemo(
    () => averageBreadthHistory(breadthHistory),
    [breadthHistory],
  );
  const dataSources = data?.dataSources ?? { breadthHistory: false, constituents: false, fundamentals: false, foreignFlow: false, trajectory: false };
  const constituentsByGroup = data?.constituentsByGroup ?? {};
  const ordered = useMemo(
    () =>
      [...sectors].sort((a, b) =>
        sort === "rank"
          ? (a.rank ?? Number.POSITIVE_INFINITY) -
            (b.rank ?? Number.POSITIVE_INFINITY)
          : (delta(b) ?? Number.NEGATIVE_INFINITY) -
            (delta(a) ?? Number.NEGATIVE_INFINITY),
      ),
    [sort, sectors],
  );
  if (!data) return null;
  const select = (s: SectorData) => navigate(`/explorer?taxonomy=SECTOR&group=${encodeURIComponent(s.id)}`);

  const asOf = formatAsOf(payload?.as_of);
  const hasComparable = dataSources.trajectory;
  const currentLeaders = [...sectors].filter((sector) => sector.leadership === "LEADING")
    .sort((a, b) => (b.excess20d ?? -Infinity) - (a.excess20d ?? -Infinity)).slice(0, 3);
  const currentBreadth = sectors.map((sector) => sector.breadth)
    .filter((value): value is number => value !== null && Number.isFinite(value));
  const currentMeanBreadth = currentBreadth.length
    ? currentBreadth.reduce((sum, value) => sum + value, 0) / currentBreadth.length
    : null;
  const currentLargestBreadthMove = [...sectors].filter((sector) => delta(sector) !== null)
    .sort((a, b) => Math.abs(delta(b) ?? 0) - Math.abs(delta(a) ?? 0))[0];
  const stats = summaryStats(sectors, hasComparable);
  const leadCounts = leadershipCounts(sectors);
  const diffCounts = diffusionCounts(sectors);
  const changes = categorizeChanges(sectors);
  const replay = historical.data;
  const replayCurrent = replay?.weekly.at(-1)?.groups ?? [];
  const replayPrevious = replay?.weekly.at(-2)?.groups ?? [];
  const replayBreadth = replayCurrent.length
    ? replayCurrent.reduce((sum, group) => sum + group.breadth_pct * group.cohort_count, 0) /
      replayCurrent.reduce((sum, group) => sum + group.cohort_count, 0)
    : null;
  const largestBreadthMove = [...replayCurrent].filter(group => group.breadth_change_pp !== null)
    .sort((a, b) => Math.abs(b.breadth_change_pp ?? 0) - Math.abs(a.breadth_change_pp ?? 0))[0];
  const replayLeader = [...replayCurrent]
    .filter(group => group.leadership === "LEADING")
    .sort((a, b) => b.excess_return_20d - a.excess_return_20d)[0];
  const materialShifts = replayCurrent.filter(group => group.material_shift);
  const replayLeadership = Object.fromEntries(["LEADING", "IMPROVING", "WEAKENING", "LAGGING"].map(state => [state, replayCurrent.filter(group => group.leadership === state).length]));
  const replayDiffusion = {
    BROADENING: replayCurrent.filter(group => group.diffusion.startsWith("BROADENING")).length,
    STABLE: replayCurrent.filter(group => group.diffusion === "STABLE").length,
    NARROWING: replayCurrent.filter(group => group.diffusion.startsWith("NARROWING")).length,
  };
  const replayMeanBreadth = replay?.weekly.map((week) => {
    const denominator = week.groups.reduce((sum, group) => sum + group.cohort_count, 0);
    return {
      as_of: week.as_of,
      breadth: denominator > 0
        ? week.groups.reduce((sum, group) => sum + group.breadth_pct * group.cohort_count, 0) / denominator
        : 0,
    };
  }) ?? [];
  const priorById = new Map(replayPrevious.map(group => [group.group_id, group]));
  const mostConcentrated = [...replayCurrent].sort((a, b) => (b.concentration_top3_pct ?? -Infinity) - (a.concentration_top3_pct ?? -Infinity))[0];

  return (
    <div className="content-shell-wide" style={{ maxWidth: "var(--content-wide-max)", padding: "28px var(--page-gutter) 64px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", marginBottom: 16 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div className="eyebrow-muted">Indonesian Equities · Market Intelligence</div>
            <EvidenceBadge kind="SNAPSHOT" compact />
          </div>
            <h1 style={{ fontSize: 30, letterSpacing: "-.045em", margin: "5px 0 0" }}>{replay ? "Weekly market changes" : hasComparable ? "What changed" : "Current snapshot"}</h1>
        </div>
        <span className="eyebrow-muted">EOD research / {asOf} · {replay ? `${formatDateLabel(replay.comparison_dates[0])}–${formatDateLabel(replay.comparison_dates.at(-1)!)} · Historical price replay using current membership` : hasComparable ? "compatible prior" : "current levels"}</span>
      </div>
      <section
        className="market-read-panel"
        style={{
          background: "#121619",
          color: "white",
          borderLeft: "3px solid #f26a3d",
          padding: "24px 27px 0",
          marginBottom: 22,
        }}
      >
        <div className="eyebrow-muted" style={{ color: "#abb2b3" }}>Market read</div>
        <div
          style={{ fontSize: 15, letterSpacing: "-.01em", maxWidth: 900, lineHeight: 1.45, margin: "9px 0 25px" }}
        >
          {replay ? (
            <ul className="market-read-bullets">
              <li><strong>Leadership</strong><span>{replayLeader ? `${replayLeader.name} ahead of IHSG by ${Math.abs(replayLeader.excess_return_20d).toFixed(1)}% over 20 trading sessions` : "No sector ahead of IHSG on the 20D lens"}</span></li>
              <li><strong>Participation</strong><span>{replayBreadth === null ? "—" : `${replayBreadth.toFixed(1)}% of the fixed cohort beat IHSG over 20 sessions`}</span></li>
              <li><strong>Weekly move</strong><span>{largestBreadthMove ? `${largestBreadthMove.name} breadth ${largestBreadthMove.breadth_change_pp! >= 0 ? "increased" : "decreased"} by ${Math.abs(largestBreadthMove.breadth_change_pp!).toFixed(1)} pp since ${formatDateLabel(replay.weekly.at(-2)!.as_of)}` : "No weekly breadth change exceeded the reporting threshold"}</span></li>
            </ul>
          ) : (
            <ul className="market-read-bullets">
              <li><strong>Leadership</strong><span>{currentLeaders.length ? currentLeaders.map((group) => group.name).join(", ") : "No sector ahead of IHSG on the 20D lens"}</span></li>
              <li><strong>Participation</strong><span>{currentMeanBreadth === null ? "—" : `${currentMeanBreadth.toFixed(1)}% mean current sector breadth`}</span></li>
              <li><strong>Weekly move</strong><span>{currentLargestBreadthMove && hasComparable ? `${currentLargestBreadthMove.name} breadth ${delta(currentLargestBreadthMove)! >= 0 ? "increased" : "decreased"} by ${Math.abs(delta(currentLargestBreadthMove)!).toFixed(1)} pp` : "—"}</span></li>
            </ul>
          )}
        </div>
        {replay && <p className="eyebrow-muted" style={{ margin: "0 0 8px", color: "#cbd3d3" }}>Historical price replay using current membership</p>}
        <div className="market-read-stats" style={{ display: "grid", gridTemplateColumns: `repeat(${replay ? 3 : 5}, minmax(0, 1fr))`, borderTop: "1px solid #ffffff22" }}>
          {(replay ? [["Fixed cohort", `${replay.cohort.count.toLocaleString()} stocks`], ["Current mean breadth", replayBreadth === null ? "—" : `${replayBreadth.toFixed(1)}%`], ["Material weekly shifts", String(materialShifts.length)]] as Array<[string, string]> : stats).map(([l, v]) => (
            <div key={l} style={{ padding: "12px 0 15px", borderRight: "1px solid #ffffff18" }}>
              <div className="eyebrow-muted" style={{ color: "#abb2b3" }}>{l}</div>
              <div style={{ fontFamily: "Geist Mono", fontSize: 13, marginTop: 3 }}>{v}</div>
            </div>
          ))}
        </div>
      </section>
      {/* Compact market-level summary strips — master §8 */}
      <section className="summary-strips" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, marginBottom: 18 }}>
        <div style={{ background: "var(--surface-subtle)", border: "1px solid var(--line)", padding: "12px 14px" }}>
          <div className="eyebrow-muted" style={{ marginBottom: 8 }}>Leadership states</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, fontFamily: "Geist Mono", fontSize: 11 }}>
            <span>Leading <b>{replay ? replayLeadership.LEADING : leadCounts.LEADING}</b></span>
            <span>Improving <b>{replay ? replayLeadership.IMPROVING : leadCounts.IMPROVING}</b></span>
            <span>Weakening <b>{replay ? replayLeadership.WEAKENING : leadCounts.WEAKENING}</b></span>
            <span>Lagging <b>{replay ? replayLeadership.LAGGING : leadCounts.LAGGING}</b></span>
          </div>
        </div>
        <div style={{ background: "var(--surface-subtle)", border: "1px solid var(--line)", padding: "12px 14px" }}>
          <div className="eyebrow-muted" style={{ marginBottom: 8 }}>Diffusion</div>
          {replay ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, fontFamily: "Geist Mono", fontSize: 11 }}>
              <span>Broadening <b>{replayDiffusion.BROADENING}</b></span><span>Stable <b>{replayDiffusion.STABLE}</b></span><span>Narrowing <b>{replayDiffusion.NARROWING}</b></span><span>Comparison <b>weekly matched cohort</b></span>
            </div>
          ) : hasComparable ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, fontFamily: "Geist Mono", fontSize: 11 }}>
              <span>Broadening <b>{diffCounts.BROADENING}</b></span>
              <span>Stable <b>{diffCounts.STABLE}</b></span>
              <span>Narrowing <b>{diffCounts.NARROWING}</b></span>
              <span>Compared groups <b>{sectors.length}</b></span>
            </div>
          ) : (
            <div style={{ fontSize: 11, lineHeight: 1.45, color: "var(--muted)" }}>
              Current breadth levels are shown in the sector map and leadership tape. Weekly matched-cohort readings are presented separately above.
            </div>
          )}
        </div>
        <div style={{ background: "var(--surface-subtle)", border: "1px solid var(--line)", padding: "12px 14px" }}>
          <div className="eyebrow-muted" style={{ marginBottom: 8 }}>Concentration</div>
          {replay && mostConcentrated ? <div style={{ fontSize: 12, lineHeight: 1.6 }}><strong>{mostConcentrated.name}</strong><br />Top-three contribution {mostConcentrated.concentration_top3_pct?.toFixed(1) ?? "—"}%{mostConcentrated.concentration_change_pp !== null && mostConcentrated.concentration_change_pp !== undefined ? ` · ${mostConcentrated.concentration_change_pp >= 0 ? "+" : ""}${mostConcentrated.concentration_change_pp.toFixed(1)} pp week over week` : ""}</div> : <div style={{ color: "var(--muted)", fontSize: 11 }}>Concentration is shown with the current sector readings.</div>}
        </div>
      </section>
      {/* WHAT CHANGED categorical digest */}
      <section className="measured-shifts-panel" style={{ background: "var(--surface)", border: "1px solid var(--line)", padding: "16px 18px", marginBottom: 22 }}>
        <div className="measured-shifts-heading" style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
          <div className="eyebrow-muted">{replay ? "Measured weekly shifts" : hasComparable ? "What changed since prior snapshot" : "Current readings"}</div>
          <span className="eyebrow-muted">{replay ? `${formatDateLabel(replay.weekly.at(-2)!.as_of)} → ${formatDateLabel(replay.weekly.at(-1)!.as_of)}` : hasComparable ? `vs ${formatSnapshotId(payload?.previous_snapshot_id)}` : "Selected release"}</span>
        </div>
        {replay ? (
          materialShifts.length ? <div className="replay-shift-list">{materialShifts.map(group => <button key={group.group_id} type="button" onClick={() => navigate(`/map?taxonomy=SECTOR&mode=groups&q=${encodeURIComponent(group.name)}`)}><strong>{group.name}</strong><span>{group.material_shift}</span><small>{group.leadership_transition ?? group.diffusion_transition ?? "Measured movement"}</small></button>)}</div> : <p className="meta">No sector crossed the preserved materiality thresholds in the latest weekly interval.</p>
        ) : !hasComparable ? (
          <div className="current-levels-grid" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16, fontSize: 12, lineHeight: 1.5 }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Current sector readings</div>
              <div>Current leadership, breadth, excess return, and concentration levels.</div>
            </div>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Historical price replay</div>
              <div>The weekly matched-cohort analysis is shown in the market read above.</div>
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16, fontSize: 12, lineHeight: 1.5 }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Leadership transitions</div>
              <div>New leadership: {changes.newLeaders.length ? changes.newLeaders.map((s) => s.name).join(", ") : "—"}</div>
              <div>Leadership lost: {changes.lostLeaders.length ? changes.lostLeaders.map((s) => s.name).join(", ") : "—"}</div>
              <div>Improving → Leading: {changes.improvingToLeading.length ? changes.improvingToLeading.map((s) => s.name).join(", ") : "—"}</div>
              <div>Leading → Weakening: {changes.leadingToWeakening.length ? changes.leadingToWeakening.map((s) => s.name).join(", ") : "—"}</div>
            </div>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Breadth & concentration movers</div>
              <div>Fastest breadth expansion: {changes.fastestExpansion.length ? changes.fastestExpansion.map((s) => `${s.name} (${formatPercent(delta(s))})`).join(", ") : "—"}</div>
              <div>Fastest breadth contraction: {changes.fastestContraction.length ? changes.fastestContraction.map((s) => `${s.name} (${formatPercent(delta(s))})`).join(", ") : "—"}</div>
              <div>Highest concentration: {changes.highConcentration.length ? changes.highConcentration.map((s) => `${s.name} ${s.concentration}%`).join(", ") : "—"}</div>
            </div>
          </div>
        )}
      </section>
      <section style={{ marginBottom: 38 }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            borderTop: "2px solid var(--ink)",
            paddingTop: 12,
          }}
        >
          <div>
          <h2 style={{ fontSize: 18, margin: 0 }}>Current market readings</h2>
            <span className="eyebrow-muted">Selected release · market-wide view</span>
          </div>
          <button
            type="button"
            onClick={() => setSort(sort === "rank" ? "delta" : "rank")}
            style={{ border: "1px solid var(--line)", background: "var(--surface-subtle)", padding: "6px 9px", fontSize: 11, cursor: "pointer" }}
          >
            Sort: {sort === "rank" ? "Rank" : "Δ Breadth"} ↕
          </button>
        </div>
        <div style={{ overflowX: "auto", marginTop: 12, borderTop: "1px solid var(--line)" }}>
          <table style={{ width: "100%", minWidth: 920, borderCollapse: "collapse" }}>
            <thead style={{ position: "sticky", top: 0, background: "var(--surface-subtle)" }}>
              <tr>
                {["Rank", "Group", "Lead", "Diff", "20D Excess", "60D Excess", "Breadth", "Δ Breadth", "Conc.", "Persistence"].map(
                  (x, i) => (
                    <th
                      key={x}
                      style={{
                        padding: "9px 8px",
                        textAlign: i < 2 ? "left" : "right",
                        fontFamily: "Geist Mono",
                        fontSize: 9,
                        color: "var(--muted)",
                        fontWeight: 500,
                        letterSpacing: ".06em",
                        textTransform: "uppercase",
                      }}
                    >
                      {x}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {ordered.map((s) => (
                <tr key={s.id} onClick={() => select(s)} style={{ borderTop: "1px solid var(--line)", cursor: "pointer" }}>
                  <td style={{ padding: "10px 8px", fontFamily: "Geist Mono", fontSize: 11 }}>{s.rank ?? "—"}</td>
                  <td style={{ padding: "10px 8px", fontWeight: 600 }}>
                    <button
                      type="button"
                      onClick={() => select(s)}
                      style={{ border: 0, padding: 0, background: "transparent", color: "inherit", fontWeight: 600, cursor: "pointer", textAlign: "left" }}
                    >
                      {s.name}
                    </button>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <LeadershipChip state={s.leadership} small />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <DiffusionChip state={s.diffusion} small />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>{num(s.excess20d)}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>{num(s.excess60d)}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "Geist Mono", fontSize: 12 }}>{s.breadth === null ? "—" : `${s.breadth}%`}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    {num(delta(s)!)}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "Geist Mono", fontSize: 12 }}>{s.concentration === null ? "—" : `${s.concentration}%`}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "Geist Mono", fontSize: 12 }}>{s.persistence} obs.</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section style={{ borderTop: "2px solid var(--ink)", paddingTop: 12 }}>
        <div className="surface-grid" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 28 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>Under the surface</h2>
            <div className="eyebrow-muted">Average group breadth history</div>
            <div style={{ marginTop: 12 }}>
              {replay ? (
                <ResponsiveContainer width="100%" height={230}>
                  <AreaChart data={replayMeanBreadth} margin={{ top: 18, right: 12, bottom: 0, left: -15 }}>
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis dataKey="as_of" tickFormatter={(value) => String(value).slice(0, 10)} tick={{ fontFamily: "Geist Mono", fontSize: 9, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontFamily: "Geist Mono", fontSize: 9, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                    <Area dataKey="breadth" name="Matched-cohort breadth" stroke="#178477" fill="#178477" fillOpacity={0.12} strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : dataSources.breadthHistory && averageHistory.length > 0 ? (
                <ResponsiveContainer width="100%" height={230}>
                  <AreaChart data={averageHistory} margin={{ top: 18, right: 12, bottom: 0, left: -15 }}>
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis dataKey="as_of" tickFormatter={(value) => String(value).slice(0, 10)} tick={{ fontFamily: "Geist Mono", fontSize: 9, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontFamily: "Geist Mono", fontSize: 9, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                    <Area dataKey="breadth" name="Average group breadth" stroke="#178477" fill="#178477" fillOpacity={0.12} strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div role="img" aria-label="No dated breadth series in this release" style={{ height: 230, display: "grid", placeItems: "center", color: "var(--muted)" }}>—</div>
              )}
            </div>
          </div>
          <div>
            <div className="eyebrow-muted" style={{ marginTop: 2 }}>Fixed cohort by sector</div>
            {replay ? (
              <div aria-label="Matched stock cohort by sector" style={{ border: "1px solid var(--line)", background: "var(--surface-subtle)", padding: "5px 14px" }}>
                {replayCurrent.map((group) => (
                  <div key={group.group_id} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "7px 0", borderBottom: "1px solid var(--line)", fontSize: 12 }}>
                    <span style={{ fontWeight: 600 }}>{group.name}</span>
                    <span className="eyebrow-muted">{group.cohort_count} stocks · {group.breadth_pct.toFixed(1)}% breadth</span>
                  </div>
                ))}
              </div>
            ) : dataSources.constituents ? (
              <ConstituentCoverage sectors={sectors} constituentsByGroup={constituentsByGroup} />
            ) : (
              <div aria-label="Fixed constituent cohorts" style={{ minHeight: 120, display: "grid", placeItems: "center", color: "var(--muted)" }}>—</div>
            )}
          </div>
        </div>
        <div className="summary-strips" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12, marginTop: 18 }}>
          <div style={{ borderTop: "1px solid var(--line)", paddingTop: 12 }}>
            <div className="eyebrow-muted">Confirmation</div>
            <p style={{ margin: "6px 0 8px", fontSize: 12, lineHeight: 1.5, color: "var(--muted)" }}>
              Official investor flow is a market-level measure. The recorded company-flow sample is reported separately.
            </p>
            <Link to="/foreign" style={{ fontSize: 12 }}>Open official market flow</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
