import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import type { BreadthHistoryPoint, SectorData } from "../data/adapter";
import { LeadershipChip, DiffusionChip, leadershipColor } from "../components/StatusChips";
import { EmptyState } from "../components/EmptyState";
import {
  clampX,
  clampY,
  classifyMapPoint,
  isOutOfXBounds,
  isOutOfYBounds,
  mapX,
  mapY,
  mapViewDomain,
  mapViewLabels,
  mapYBaseline,
  mapYValue,
  type MapClassification,
  type MapViewMode,
  type MapPlotBounds,
} from "../data/mapGeometry";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, CartesianGrid } from "recharts";
import { placeMapLabels } from "../data/mapLabels";
import { formatDateLabel, formatEnumLabel, formatPercent, formatSnapshotId } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";


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
        color: unavailable ? "#686e73" : v > 0 ? "#178477" : v < 0 ? "#b34e4c" : "#686e73",
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

function MiniMap({
  sectors,
  onSelect,
  trajectoryAvailable,
}: {
  sectors: SectorData[];
  onSelect: (s: SectorData) => void;
  trajectoryAvailable: boolean;
}) {
  const plot: MapPlotBounds = { left: 46, top: 22, width: 630, height: 270 };
  const mapMode: MapViewMode = trajectoryAvailable ? "trajectory" : "current";
  const axisLabels = mapViewLabels(mapMode);
  const domain = mapViewDomain(mapMode);
  const yBaseline = mapYBaseline(mapMode);
  const yAxis = mapY(yBaseline, plot, domain);
  // The primary trajectory view requires a comparable prior observation.
  // A first snapshot uses the emitted current breadth level instead.
  const hasPriorBreadth = trajectoryAvailable;
  const plottable = sectors.filter((s) => {
    if (s.excess20d === null) return false;
    const yValue = mapYValue(s, mapMode);
    if (yValue === null) return false;
    const cls = classifyMapPoint(
      { ...s, excess20d: s.excess20d, breadth: s.breadth, prevBreadth: s.prevBreadth },
      plot,
      domain,
      hasPriorBreadth,
      mapMode,
    );
    return cls.classification === "plottable";
  });
  const classifications = sectors.map((s) =>
    classifyMapPoint(
      { ...s, excess20d: s.excess20d, breadth: s.breadth, prevBreadth: s.prevBreadth },
      plot,
      domain,
      hasPriorBreadth,
      mapMode,
    ).classification,
  );
  const offScaleCount = classifications.filter(
    (classification) => classification === "off-scale-x" || classification === "off-scale-y",
  ).length;
  const missingMetricCount = classifications.filter(
    (classification) => classification === "missing-metric",
  ).length;
  const missingPriorCount = classifications.filter(
    (classification) => classification === "missing-prior",
  ).length;
  return (
    <div style={{ background: "#fff", border: "1px solid #dfe2e1", minHeight: 412, position: "relative", overflow: "hidden" }}>
      <div style={{ padding: "17px 20px 0", display: "flex", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: 17, fontWeight: 600 }}>{axisLabels.title}</div>
          <div className="eyebrow-muted">{axisLabels.subtitle}</div>
        </div>
        <span className="eyebrow-muted">Latest snapshot</span>
      </div>
        <svg viewBox="0 0 720 348" width="100%" height="348" style={{ display: "block", marginTop: 3 }} aria-label={axisLabels.title}>
        <rect x="46" y="22" width="630" height="270" fill="#fafaf8" />
        <rect
          x={mapX(0, plot, domain)}
          y={plot.top}
          width={plot.left + plot.width - mapX(0, plot, domain)}
          height={yAxis - plot.top}
          fill="#f6f8f8"
        />
        <rect
          x={plot.left}
          y={yAxis}
          width={mapX(0, plot, domain) - plot.left}
          height={plot.top + plot.height - yAxis}
          fill="#f9f7f5"
        />
        {[46, 151, 256, 361, 466, 571, 676].map((n) => (
          <line key={n} x1={n} x2={n} y1="22" y2="292" stroke="#dfe2e1" strokeWidth="1" />
        ))}
        {[22, 89, 157, 224, 292].map((n) => (
          <line key={n} x1="46" x2="676" y1={n} y2={n} stroke="#dfe2e1" strokeWidth="1" />
        ))}
        <line x1={mapX(0, plot, domain)} x2={mapX(0, plot, domain)} y1={plot.top} y2={plot.top + plot.height} stroke="#b9c0be" />
        <line x1={plot.left} x2={plot.left + plot.width} y1={yAxis} y2={yAxis} stroke="#b9c0be" />
        <text x="60" y="43" fill="#778089" fontSize="10" fontFamily="Geist Mono">
          {mapMode === "current" ? "Weak / broad" : "Improving"}
        </text>
        <text x="570" y="43" fill="#315d87" fontSize="10" fontFamily="Geist Mono">
          {mapMode === "current" ? "Strong / broad" : "Leading"}
        </text>
        <text x="60" y="278" fill="#778089" fontSize="10" fontFamily="Geist Mono">
          {mapMode === "current" ? "Weak / narrow" : "Lagging"}
        </text>
        <text x="560" y="278" fill="#b34e4c" fontSize="10" fontFamily="Geist Mono">
          {mapMode === "current" ? "Strong / narrow" : "Weakening"}
        </text>
        {sectors.map((s) => {
          if (s.excess20d === null) return null;
          const yValue = mapYValue(s, mapMode);
          if (yValue === null) return null;
          const isOffScaleY = isOutOfYBounds(yValue, plot, domain);
          const isOffScaleX = isOutOfXBounds(s.excess20d, plot, domain);
          const isOffScale = isOffScaleX || isOffScaleY;
          const py = isOffScaleY ? clampY(yValue, plot, domain) : mapY(yValue, plot, domain);
          const px = isOffScaleX ? clampX(s.excess20d, plot, domain) : mapX(s.excess20d, plot, domain);
          const r = 7 + Math.sqrt(Math.max(1, s.constituents)) / 2.2;
          const c = leadershipColor(s.leadership);
          return (
            <g
              key={s.id}
              role="button"
              tabIndex={0}
              aria-label={`${s.name}: ${formatEnumLabel(s.leadership)} leadership, ${formatEnumLabel(s.diffusion)} diffusion, 20D excess return ${formatPercent(s.excess20d)}${isOffScale ? " (off scale)" : ""}`}
              onClick={() => onSelect(s)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(s);
                }
              }}
              className="map-group"
              style={{ cursor: "pointer" }}
            >
              <title>{`${s.name}: ${formatEnumLabel(s.leadership)} / ${formatEnumLabel(s.diffusion)}, 20D excess ${formatPercent(s.excess20d)}${isOffScale ? " (off scale: value outside domain)" : ""}`}</title>
              <circle cx={px} cy={py} r={r} fill="#fff" stroke={c} strokeWidth={1.5} />
              <circle cx={px} cy={py} r={3} fill={c} />
              {isOffScale && (
                <polygon points={`${px},${py - r - 8} ${px - 5},${py - r - 2} ${px + 5},${py - r - 2}`} fill={c} opacity={0.7} />
              )}
            </g>
          );
        })}
        {(() => {
          const candidates = plottable.flatMap((s) => {
            const yValue = mapYValue(s, mapMode);
            if (yValue === null || s.excess20d === null) return [];
            return [
              {
                id: s.id,
                text: s.name,
                x: clampX(s.excess20d, plot, domain),
                y: clampY(yValue, plot, domain),
                radius: 7 + Math.sqrt(Math.max(1, s.constituents)) / 2.2,
                priority: Math.abs(s.excess20d) + Math.abs(yValue - mapYBaseline(mapMode)) * 0.5,
              },
            ];
          });
          const maxLabels = candidates.length <= 10 ? candidates.length : 5;
          const positions = placeMapLabels(candidates, {
            left: plot.left + 4,
            right: plot.left + plot.width - 4,
            top: plot.top + 4,
            bottom: plot.top + plot.height - 4,
          }, maxLabels);
          return positions.map((label) => (
            <text key={`lbl-${label.id}`} x={label.x} y={label.y} textAnchor={label.textAnchor} fill="#16191c" fontSize="10" fontFamily="Geist" pointerEvents="none">
              {label.text}
            </text>
          ));
        })()}
        {(offScaleCount > 0 || missingMetricCount > 0 || missingPriorCount > 0) && (() => {
          const notes = [
            offScaleCount > 0 ? `${offScaleCount} group(s) off scale — shown at boundary${offScaleCount === 1 ? "" : "s"}` : "",
            missingMetricCount > 0 ? `${missingMetricCount} group(s) not plotted — missing metric` : "",
            missingPriorCount > 0 ? `${missingPriorCount} group(s) not plotted — missing comparable prior` : "",
          ].filter(Boolean).join(" · ");
          return (
            <text x="335" y="318" fill="#8f8f8f" fontSize="9" fontFamily="Geist Mono" textAnchor="middle">
              {notes}
            </text>
          );
        })()}
        <text x="335" y="335" fill="#686e73" fontSize="10" fontFamily="Geist Mono">{axisLabels.x} (clamped if off scale)</text>
        <text x="14" y="178" fill="#686e73" fontSize="10" fontFamily="Geist Mono" transform="rotate(-90 14 178)">{axisLabels.y} (clamped if off scale)</text>
      </svg>
      <div
        className="eyebrow-muted"
        style={{ padding: "0 20px 12px", fontSize: 10 }}
      >
        {mapMode === "current"
          ? "Current snapshot view: points use current breadth; diffusion change awaits comparable prior."
          : "Comparable snapshot view: points use breadth delta."}
      </div>
    </div>
  );
}

function ShiftFeed({ items, onSelect }: { items: SectorData[]; onSelect: (s: SectorData) => void }) {
  return (
    <div style={{ borderTop: "2px solid #16191c" }}>
      <div style={{ padding: "12px 0", display: "flex", justifyContent: "space-between" }}>
        <div style={{ fontSize: 17, fontWeight: 600 }}>Material shifts</div>
        <span className="eyebrow-muted">Ranked</span>
      </div>
      {items.length === 0 && (
        <p style={{ color: "#686e73", fontSize: 12, padding: "20px 0" }}>
          No leadership or diffusion transitions detected in this snapshot.
        </p>
      )}
      {items.slice(0, 5).map((s, i) => {
        const breadthChange = delta(s);
        return (
        <button
          key={s.id}
          onClick={() => onSelect(s)}
          style={{
            width: "100%",
            display: "grid",
            gridTemplateColumns: "29px 1fr auto",
            gap: 8,
            textAlign: "left",
            background: "transparent",
            border: 0,
            borderTop: "1px solid #dfe2e1",
            padding: "13px 0",
            cursor: "pointer",
          }}
        >
          <span className="eyebrow-muted">{String(i + 1).padStart(2, "0")}</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{s.name}</div>
            <div style={{ fontFamily: "Geist Mono", fontSize: 10, color: "#686e73", marginTop: 4 }}>
              {formatEnumLabel(s.prevLeadership || s.leadership)} <span style={{ color: "#f26a3d" }}>→</span> {formatEnumLabel(s.leadership)}
              <br />
              {formatEnumLabel(s.prevDiffusion || s.diffusion)} <span style={{ color: "#f26a3d" }}>→</span> {formatEnumLabel(s.diffusion)}
            </div>
          </div>
          <div style={{ textAlign: "right", fontFamily: "Geist Mono", fontSize: 10 }}>
            {num(s.excess20d)}
            <br />
            <span
              style={{
                color:
                  breadthChange === null
                    ? "#686e73"
                    : breadthChange >= 0
                      ? "#178477"
                      : "#b34e4c",
              }}
            >
              {formatPercent(breadthChange)}
            </span>
          </div>
        </button>
        );
      })}
    </div>
  );
}

function buildMarketRead(sectors: SectorData[], hasComparable: boolean): string {
  if (sectors.length === 0) return "Snapshot contains no groups.";
  const broadening = sectors.filter((s) => s.diffusion === "BROADENING");
  const narrowing = sectors.filter((s) => s.diffusion === "NARROWING");
  const leading = sectors.filter((s) => s.leadership === "LEADING");
  if (!hasComparable) {
    return `Current snapshot has ${leading.length} leading group${leading.length === 1 ? "" : "s"}; diffusion change is unavailable until a compatible prior is available.`;
  }
  if (broadening.length === 0 && narrowing.length === 0) {
    return `The snapshot has ${leading.length} leading group${leading.length === 1 ? "" : "s"}; diffusion change is not confirmed across the universe.`;
  }
  return `Leadership is broadening in ${broadening.length} group${broadening.length === 1 ? "" : "s"} and narrowing in ${narrowing.length} group${narrowing.length === 1 ? "" : "s"}; ${leading.length} group${leading.length === 1 ? "" : "s"} are leading.`;
}

function summaryStats(sectors: SectorData[], hasComparable: boolean): Array<[string, string]> {
  const unavailableChange = hasComparable ? null : "Unavailable";
  if (sectors.length === 0) {
    return [
      ["IDX leadership", "—"],
      ["Breadth", "—"],
      ["Broadening groups", unavailableChange ?? "0"],
      ["Narrowing groups", unavailableChange ?? "0"],
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
    ["Broadening groups", unavailableChange ?? String(broadening)],
    ["Narrowing groups", unavailableChange ?? String(narrowing)],
    ["Data coverage", `${sectors.reduce((a, s) => a + s.eligibleConstituents, 0)} eligible`],
  ];
}

function leadershipCounts(sectors: SectorData[]) {
  return {
    LEADING: sectors.filter((s) => s.leadership === "LEADING").length,
    IMPROVING: sectors.filter((s) => s.leadership === "IMPROVING").length,
    WEAKENING: sectors.filter((s) => s.leadership === "WEAKENING").length,
    LAGGING: sectors.filter((s) => s.leadership === "LAGGING").length,
    UNCONFIRMED: sectors.filter((s) => s.leadership === "UNCONFIRMED").length,
  };
}

function diffusionCounts(sectors: SectorData[]) {
  const broadening = sectors.filter((s) => String(s.diffusion).startsWith("BROADENING")).length;
  const stable = sectors.filter((s) => s.diffusion === "STABLE").length;
  const narrowing = sectors.filter((s) => String(s.diffusion).startsWith("NARROWING")).length;
  const unconfirmed = sectors.filter((s) => s.diffusion === "UNCONFIRMED").length;
  return { BROADENING: broadening, STABLE: stable, NARROWING: narrowing, UNCONFIRMED: unconfirmed };
}

function confirmationCounts(sectors: SectorData[]) {
  // Foreign flow confirmation is DATA_GAP in prototype; surface honest counts
  const confirming = sectors.filter((s) => s.foreignFlow === "CONFIRMING").length;
  const against = sectors.filter((s) => s.foreignFlow === "AGAINST").length;
  const neutral = sectors.filter((s) => s.foreignFlow === "NEUTRAL").length;
  const gap = sectors.filter((s) => s.foreignFlow === "DATA_GAP").length;
  return { CONFIRMING: confirming, AGAINST: against, NEUTRAL: neutral, DATA_GAP: gap };
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
      style={{ border: "1px solid #dfe2e1", background: "#fafaf8", padding: "5px 14px" }}
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
  const navigate = useNavigate();
  const [sort, setSort] = useState<"rank" | "delta">("rank");
  const sectors = data?.sectors ?? [];
  const materialChanges = data?.materialChanges ?? [];
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
  const marketRead = buildMarketRead(sectors, hasComparable);
  const stats = summaryStats(sectors, hasComparable);
  const leadCounts = leadershipCounts(sectors);
  const diffCounts = diffusionCounts(sectors);
  const confCounts = confirmationCounts(sectors);
  const changes = categorizeChanges(sectors);

  return (
    <div className="content-shell-wide" style={{ maxWidth: "var(--content-wide-max)", padding: "28px var(--page-gutter) 64px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", marginBottom: 16 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div className="eyebrow-muted">Indonesian Equities · Market Intelligence</div>
            <EvidenceBadge kind="SNAPSHOT" compact />
          </div>
          <h1 style={{ fontSize: 30, letterSpacing: "-.045em", margin: "5px 0 0" }}>{hasComparable ? "What changed" : "Current snapshot"}</h1>
        </div>
        <span className="eyebrow-muted">EOD research / {asOf} · {hasComparable ? "comparable prior available" : "change comparison unavailable"}</span>
      </div>
      <section
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
          style={{
            fontSize: 25,
            letterSpacing: "-.03em",
            maxWidth: 820,
            lineHeight: 1.2,
            margin: "9px 0 25px",
          }}
        >
          {marketRead}
        </div>
        {!hasComparable && (
          <div style={{ margin: "0 0 20px", padding: "10px 12px", border: "1px solid #ffffff33", color: "#f6d4b9", fontSize: 12, lineHeight: 1.5 }}>
            Change comparison unavailable. This view reports current levels only until a second compatible snapshot is persisted.
          </div>
        )}
        <div className="market-read-stats" style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", borderTop: "1px solid #ffffff22" }}>
          {stats.map(([l, v]) => (
            <div key={l} style={{ padding: "12px 0 15px", borderRight: "1px solid #ffffff18" }}>
              <div className="eyebrow-muted" style={{ color: "#abb2b3" }}>{l}</div>
              <div style={{ fontFamily: "Geist Mono", fontSize: 13, marginTop: 3 }}>{v}</div>
            </div>
          ))}
        </div>
      </section>
      {/* Compact market-level summary strips — master §8 */}
      <section className="summary-strips" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, marginBottom: 18 }}>
        <div style={{ background: "#faf9f6", border: "1px solid #dfe2e1", padding: "12px 14px" }}>
          <div className="eyebrow-muted" style={{ marginBottom: 8 }}>Leadership states</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, fontFamily: "Geist Mono", fontSize: 11 }}>
            <span>Leading <b>{leadCounts.LEADING}</b></span>
            <span>Improving <b>{leadCounts.IMPROVING}</b></span>
            <span>Weakening <b>{leadCounts.WEAKENING}</b></span>
            <span>Lagging <b>{leadCounts.LAGGING}</b></span>
            <span style={{ gridColumn: "1 / -1", color: "#686e73" }}>Unconfirmed <b>{leadCounts.UNCONFIRMED}</b></span>
          </div>
        </div>
        <div style={{ background: "#faf9f6", border: "1px solid #dfe2e1", padding: "12px 14px" }}>
          <div className="eyebrow-muted" style={{ marginBottom: 8 }}>Diffusion</div>
          {hasComparable ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, fontFamily: "Geist Mono", fontSize: 11 }}>
              <span>Broadening <b>{diffCounts.BROADENING}</b></span>
              <span>Stable <b>{diffCounts.STABLE}</b></span>
              <span>Narrowing <b>{diffCounts.NARROWING}</b></span>
              <span>Unconfirmed <b>{diffCounts.UNCONFIRMED}</b></span>
            </div>
          ) : (
            <div style={{ fontSize: 11, lineHeight: 1.45, color: "#686e73" }}>
              Current diffusion state is unconfirmed for {diffCounts.UNCONFIRMED} groups. A compatible prior is required to measure broadening or narrowing.
            </div>
          )}
          {!hasComparable && <div style={{ marginTop: 6, fontSize: 10, color: "#7a5010" }}>Diffusion change unavailable without comparable prior</div>}
        </div>
        <div style={{ background: "#faf9f6", border: "1px solid #dfe2e1", padding: "12px 14px" }}>
          <div className="eyebrow-muted" style={{ marginBottom: 8 }}>Confirmation</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, fontFamily: "Geist Mono", fontSize: 11 }}>
            <span>Confirming <b>{confCounts.CONFIRMING}</b></span>
            <span>Against <b>{confCounts.AGAINST}</b></span>
            <span>Neutral <b>{confCounts.NEUTRAL}</b></span>
            <span style={{ color: "#7a5010" }}>Data gap <b>{confCounts.DATA_GAP}</b></span>
          </div>
          <div style={{ marginTop: 6, fontSize: 10, color: "#7a5010" }}>Foreign flow: sample only, not full universe</div>
        </div>
      </section>
      {/* WHAT CHANGED categorical digest */}
      <section style={{ background: "#fff", border: "1px solid #dfe2e1", padding: "16px 18px", marginBottom: 22 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
          <div className="eyebrow-muted">{hasComparable ? "What changed since prior snapshot" : "What is available now"}</div>
          <span className="eyebrow-muted">{hasComparable ? `vs ${formatSnapshotId(payload?.previous_snapshot_id)}` : "Current levels only"}</span>
        </div>
        {!hasComparable ? (
          <div className="current-levels-grid" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16, fontSize: 12, lineHeight: 1.5 }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>You can use this snapshot for</div>
              <div>Current leadership, breadth, excess return, and concentration levels.</div>
            </div>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Still unavailable</div>
              <div>No comparable change set available. Broadening, narrowing, and material change versus a prior snapshot remain unavailable.</div>
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
      <section
        className="overview-grid"
        style={{ display: "grid", gridTemplateColumns: "minmax(0,1.85fr) minmax(280px,.85fr)", gap: 24, marginBottom: 38 }}
      >
        <MiniMap
          sectors={sectors}
          onSelect={select}
          trajectoryAvailable={dataSources.trajectory}
        />
        <ShiftFeed items={materialChanges} onSelect={select} />
      </section>
      <section style={{ marginBottom: 38 }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            borderTop: "2px solid #16191c",
            paddingTop: 12,
          }}
        >
          <div>
            <h2 style={{ fontSize: 18, margin: 0 }}>Leadership tape</h2>
            <span className="eyebrow-muted">Cross-sectional monitor</span>
          </div>
          <button
            type="button"
            onClick={() => setSort(sort === "rank" ? "delta" : "rank")}
            style={{ border: "1px solid #dfe2e1", background: "#fafaf8", padding: "6px 9px", fontSize: 11, cursor: "pointer" }}
          >
            Sort: {sort === "rank" ? "Rank" : "Δ Breadth"} ↕
          </button>
        </div>
        <div style={{ overflowX: "auto", marginTop: 12, borderTop: "1px solid #dfe2e1" }}>
          <table style={{ width: "100%", minWidth: 920, borderCollapse: "collapse" }}>
            <thead style={{ position: "sticky", top: 0, background: "#f3f3f0" }}>
              <tr>
                {["Rank", "Group", "Lead", "Diff", "20D Excess", "60D Excess", "Breadth", "Δ Breadth", "Conc.", "Persistence", "Confirmation"].map(
                  (x, i) => (
                    <th
                      key={x}
                      style={{
                        padding: "9px 8px",
                        textAlign: i < 2 ? "left" : "right",
                        fontFamily: "Geist Mono",
                        fontSize: 9,
                        color: "#686e73",
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
                <tr key={s.id} onClick={() => select(s)} style={{ borderTop: "1px solid #dfe2e1", cursor: "pointer" }}>
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
                  <td
                    style={{
                      padding: "10px 8px",
                      textAlign: "right",
                      fontFamily: "Geist Mono",
                      fontSize: 10,
                      color: s.foreignFlow === "CONFIRMING" ? "#178477" : "#686e73",
                    }}
                  >
                    {formatEnumLabel(s.foreignFlow)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section style={{ borderTop: "2px solid #16191c", paddingTop: 12 }}>
        <div className="surface-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1.1fr .82fr", gap: 28 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>Under the surface</h2>
            <div className="eyebrow-muted">Average group breadth history</div>
            <div style={{ marginTop: 12 }}>
              {dataSources.breadthHistory && averageHistory.length > 0 ? (
                <ResponsiveContainer width="100%" height={175}>
                  <AreaChart data={averageHistory} margin={{ top: 18, right: 5, bottom: 0, left: -25 }}>
                    <CartesianGrid stroke="#dfe2e1" vertical={false} />
                    <XAxis dataKey="as_of" tickFormatter={(value) => String(value).slice(0, 10)} tick={{ fontFamily: "Geist Mono", fontSize: 9, fill: "#686e73" }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontFamily: "Geist Mono", fontSize: 9, fill: "#686e73" }} axisLine={false} tickLine={false} />
                    <Area dataKey="breadth" stroke="#178477" fill="#178477" fillOpacity={0.12} strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState
                  label="NO TIME SERIES"
                  title="Per-group breadth history not emitted by the snapshot writer"
                  body="The current snapshot contains only the latest breadth level. A comparable prior snapshot is required before a per-group time series can be shown safely."
                  height={175}
                />
              )}
            </div>
          </div>
          <div>
            <div className="eyebrow-muted" style={{ marginTop: 2 }}>Constituent participation matrix</div>
            {dataSources.constituents ? (
              <ConstituentCoverage sectors={sectors} constituentsByGroup={constituentsByGroup} />
            ) : (
              <EmptyState
                label="NO CONSTITUENTS"
                title="Constituent rows are not available in this snapshot"
                body="The current payload has no feature rows joined to its security master, so participation cannot be shown here."
                height={175}
              />
            )}
          </div>
          <div style={{ borderLeft: "1px solid #dfe2e1", paddingLeft: 20 }}>
            <div className="eyebrow-muted">Evidence stack</div>
            {dataSources.foreignFlow ? (
              sectors.slice(0, 5).map((s) => (
                <div key={s.id} style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #dfe2e1", padding: "8px 0", fontSize: 12 }}>
                  <span style={{ color: "#686e73" }}>{s.name} leadership</span>
                  <b style={{ fontFamily: "Geist Mono", fontSize: 10, color: "#315d87" }}>{formatEnumLabel(s.leadership)}</b>
                </div>
              ))
            ) : (
              <>
                <EmptyState
                  label="NO FOREIGN FLOW"
                  title="Foreign-flow data is not part of the prototype snapshot"
                  body="The live Sectors flow capability is gated on a credential; offline prototype data does not include it."
                  height={120}
                />
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
