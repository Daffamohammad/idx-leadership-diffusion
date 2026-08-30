import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import type { LeadershipState, SectorData } from "../data/adapter";
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
  type MapPlotBounds,
  type LeadershipDiffusionDomain,
  type MapViewMode,
} from "../data/mapGeometry";
import { leadershipColor } from "../components/StatusChips";
import { placeMapLabels } from "../data/mapLabels";

const stateOrder: LeadershipState[] = [
  "LEADING",
  "IMPROVING",
  "WEAKENING",
  "LAGGING",
];
const filterStates: LeadershipState[] = [...stateOrder, "UNCONFIRMED"];
const plot: MapPlotBounds = { left: 64, top: 38, width: 1032, height: 400 };
type Quadrant = "UPPER_LEFT" | "UPPER_RIGHT" | "LOWER_LEFT" | "LOWER_RIGHT";

const quadrantConfig: Record<Quadrant, { label: string; color: string; fill: string }> = {
  UPPER_RIGHT: { label: "Leading", color: "#438b82", fill: "#e8f3f0" },
  UPPER_LEFT: { label: "Improving / Emerging", color: "#54718b", fill: "#eaf1f7" },
  LOWER_RIGHT: { label: "Fading / Decelerating", color: "#aa8750", fill: "#f8f0df" },
  LOWER_LEFT: { label: "Weakening / Breaking", color: "#ad6765", fill: "#f8eaea" },
};

const currentQuadrantConfig: Record<Quadrant, { label: string; color: string; fill: string }> = {
  UPPER_RIGHT: { label: "Strong / Broad", color: "#438b82", fill: "#e8f3f0" },
  UPPER_LEFT: { label: "Weak / Broad", color: "#54718b", fill: "#eaf1f7" },
  LOWER_RIGHT: { label: "Strong / Narrow", color: "#aa8750", fill: "#f8f0df" },
  LOWER_LEFT: { label: "Weak / Narrow", color: "#ad6765", fill: "#f8eaea" },
};

function signedQuadrant(x: number, y: number): Quadrant {
  if (x >= 0 && y >= 0) return "UPPER_RIGHT";
  if (x < 0 && y >= 0) return "UPPER_LEFT";
  if (x >= 0 && y < 0) return "LOWER_RIGHT";
  return "LOWER_LEFT";
}

function leadershipDiffusionDomain(mode: MapViewMode): LeadershipDiffusionDomain {
  // Both map modes use a fixed documented domain. Per-snapshot auto-scaling
  // is intentionally avoided so the Overview and full map stay comparable.
  return mapViewDomain(mode);
}

// Select up to 3 material points for labels to avoid collision.
// Material = large absolute 20D excess return OR large absolute breadth delta.
function labelMaterialPoints(
  sectors: SectorData[],
  mode: MapViewMode,
  plot: MapPlotBounds,
  domain: LeadershipDiffusionDomain,
): SectorData[] {
  const ranked = [...sectors]
    .filter((s) => {
      if (s.excess20d === null) return false;
      const yValue = mapYValue(s, mode);
      return yValue !== null && !isOutOfYBounds(yValue, plot, domain);
    })
    .map((s) => {
      const y = mapYValue(s, mode) ?? 0;
      const baseline = mapYBaseline(mode);
      const materiality =
        Math.abs(s.excess20d ?? 0) + Math.abs(y - baseline) * 0.5;
      return { s, materiality };
    })
    .sort((a, b) => b.materiality - a.materiality)
    .slice(0, 3)
    .map((entry) => entry.s);
  return ranked;
}
const breadthDelta = (s: SectorData): number | null =>
  s.prevBreadth === undefined || s.breadth === null
    ? null
    : s.breadth - s.prevBreadth;

const displayMetric = (value: number | null | undefined, suffix = "%"): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
};

function Detail({ sector, onOpen }: { sector: SectorData; onOpen: () => void }) {
  const d = breadthDelta(sector);
  return (
    <div
      style={{
        position: "absolute",
        right: 18,
        top: 18,
        width: 232,
        padding: 15,
        background: "#faf9f6",
        border: "1px solid #dfe2e1",
        boxShadow: "0 12px 28px #1f252214",
        zIndex: 4,
      }}
    >
      <div className="eyebrow-muted">Selected group</div>
      <div style={{ fontSize: 17, fontWeight: 600, margin: "4px 0 11px" }}>
        {sector.name}
      </div>
      {(
        [
          ["Leadership", sector.leadership],
          ["Diffusion", sector.diffusion],
          ["60D strength", displayMetric(sector.excess60d, "pp")],
          ["20D momentum", displayMetric(sector.excess20d, "pp")],
          ["Breadth", displayMetric(sector.breadth)],
          ["Δ breadth", d === null ? "—" : displayMetric(d, "pp")],
          ["Top-3", displayMetric(sector.concentration)],
        ] as Array<[string, string]>
      ).map(([label, value]) => (
        <div
          key={label}
          style={{
            display: "flex",
            justifyContent: "space-between",
            borderTop: "1px solid #e1e2de",
            padding: "6px 0",
            fontSize: 11,
          }}
        >
          <span style={{ color: "#747a7d" }}>{label}</span>
          <b
            style={{
              fontFamily: "Geist Mono",
              fontSize: 10,
              color: label === "Δ breadth" && d !== null && d > 0 ? "#438b82" : undefined,
            }}
          >
            {value}
          </b>
        </div>
      ))}
      <button
        type="button"
        onClick={onOpen}
        style={{
          width: "100%",
          marginTop: 9,
          padding: "7px 9px",
          background: "#202325",
          color: "#fff",
          border: 0,
          cursor: "pointer",
          fontSize: 11,
        }}
      >
        Open group →
      </button>
    </div>
  );
}

export default function LeadershipMap() {
  const navigate = useNavigate();
  const { data } = useSnapshot();
  const [filter, setFilter] = useState<"ALL" | LeadershipState>("ALL");
  // Trails removed: trajectory data is only available when the
  // comparability record confirms a persisted comparable snapshot.
  // Synthesized trail dots are explicitly disallowed.
  const [selected, setSelected] = useState<SectorData | null>(null);
  const sectors = data?.sectors ?? [];
  const dataSources = data?.dataSources ?? { breadthHistory: false, constituents: false, fundamentals: false, foreignFlow: false, trajectory: false };
  const mapMode: MapViewMode = dataSources.trajectory ? "trajectory" : "current";
  const axisLabels = mapViewLabels(mapMode);
  const domain = useMemo(() => leadershipDiffusionDomain(mapMode), [mapMode]);
  const activeQuadrantConfig = mapMode === "current" ? currentQuadrantConfig : quadrantConfig;
  const yBaseline = mapYBaseline(mapMode);
  const yAxis = mapY(yBaseline, plot, domain);
  const visible = useMemo(
    () => sectors.filter((s) => filter === "ALL" || s.leadership === filter),
    [filter, sectors],
  );
  // The primary trajectory view requires a comparable prior for its breadth
  // delta. A first snapshot uses the emitted current breadth level instead.
  const hasPriorBreadth = dataSources.trajectory;
  const plottable = visible.filter((s) => {
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
  const labelPositions = useMemo(() => {
    const material = labelMaterialPoints(visible, mapMode, plot, domain);
    return placeMapLabels(
      material.flatMap((s) => {
        if (s.excess20d === null) return [];
        const yValue = mapYValue(s, mapMode);
        if (yValue === null) return [];
        const y = clampY(yValue, plot, domain);
        return [
          {
            id: s.id,
            text: s.name,
            x: clampX(s.excess20d, plot, domain),
            y,
            radius: 5 + Math.sqrt(Math.max(1, s.constituents)) / 3.8,
            priority: Math.abs(s.excess20d) + Math.abs(yValue - yBaseline) * 0.5,
          },
        ];
      }),
      {
        left: plot.left + 4,
        right: plot.left + plot.width - 4,
        top: plot.top + 4,
        bottom: plot.top + plot.height - 4,
      },
      3,
    );
  }, [domain, mapMode, visible, yBaseline]);
  if (!data) return null;
  const focus = selected;

  return (
    <div style={{ maxWidth: 1520, margin: "auto", padding: "31px 34px 55px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 22,
        }}
      >
        <div>
          <div className="eyebrow-muted" style={{ color: "#438b82" }}>
            {axisLabels.title}
          </div>
          <h1
            style={{
              fontSize: 31,
              letterSpacing: "-.045em",
              margin: "7px 0 9px",
            }}
          >
            {axisLabels.title}
          </h1>
          <p style={{ maxWidth: 740, margin: 0, lineHeight: 1.55, color: "#747a7d" }}>
            {axisLabels.x} on the X axis; {axisLabels.y} on the Y axis.
            Dot color reflects leadership state; size reflects constituent count.
            {mapMode === "trajectory"
              ? " Points require a comparable prior snapshot for breadth delta."
              : " This first-snapshot view uses current breadth; diffusion change and trajectories require a comparable prior."}
          </p>
        </div>
        <span
          className="eyebrow-muted"
          style={{
            border: "1px solid #bed7e6",
            borderRadius: 20,
            padding: "6px 11px",
            color: "#54718b",
          }}
        >
          Hero visualization
        </span>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 15,
          flexWrap: "wrap",
        }}
      >
        {mapMode === "trajectory" ? (
          <span
            className="eyebrow-muted"
            style={{
              border: "1px solid #bed7e6",
              borderRadius: 20,
              padding: "6px 11px",
              color: "#54718b",
            }}
          >
            Multi-snapshot trajectory available
          </span>
        ) : (
          <span
            className="eyebrow-muted"
            style={{
              border: "1px solid #bed7e6",
              borderRadius: 20,
              padding: "6px 11px",
              color: "#54718b",
            }}
          >
            Current snapshot view · breadth level
          </span>
        )}
        <span style={{ marginLeft: "auto" }} className="eyebrow-muted">
          Colour: leadership / Size: constituents
        </span>
      </div>
      {mapMode === "current" && (
        <p style={{ margin: "-5px 0 12px", color: "#8f8f8f", fontSize: 11 }}>
          Current snapshot: points use the emitted 20D breadth level. Diffusion change and trajectories remain unavailable until a persisted comparable prior snapshot exists.
        </p>
      )}
      <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
        {["ALL", ...filterStates].map((value) => (
          <button
            type="button"
            key={value}
            onClick={() => setFilter(value as "ALL" | LeadershipState)}
            style={{
              border: `1px solid ${filter === value ? "#d97956" : "#dfe2e1"}`,
              background: filter === value ? "#f5e6df" : "#faf9f6",
              color: "#202325",
              padding: "5px 9px",
              fontFamily: "Geist Mono",
              fontSize: 10,
              cursor: "pointer",
            }}
          >
            {value}
          </button>
        ))}
      </div>
      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          margin: "0 0 12px",
          padding: "8px 12px",
          background: "#faf9f6",
          border: "1px solid #dfe2e1",
          fontSize: 11,
          color: "#747a7d",
          flexWrap: "wrap",
        }}
        aria-label="Snapshot coverage"
      >
        <span style={{ fontWeight: 600, color: "#202325" }}>Coverage</span>
        <span>
          Raw: <strong>{data?.coverageHonest?.raw_candidate_constituents ?? 0}</strong>
        </span>
        <span>
          Policy-eligible:{" "}
          <strong>{data?.coverageHonest?.policy_eligible_constituents ?? 0}</strong>
        </span>
        <span>
          Observed: <strong>{data?.coverageHonest?.observed_eligible_features ?? 0}</strong>
        </span>
        <span>
          Acquisition-failed:{" "}
          <strong>{data?.coverageHonest?.acquisition_failed_constituents ?? 0}</strong>
        </span>
        <span>
          {data?.coverageHonest?.coverage_gate_60pct_met ? (
            <span style={{ color: "#178477" }}>60% gate met</span>
          ) : (
            <span style={{ color: "#ad6765" }}>60% gate not met</span>
          )}
        </span>
      </div>
      <div
        className="leadership-map-frame"
        style={{
          position: "relative",
          background: "#fff",
          border: "1px solid #e1e2de",
          overflow: "hidden",
        }}
      >
        {focus && (
          <Detail
            sector={focus}
            onOpen={() => navigate("/explorer", { state: { sectorId: focus.id } })}
          />
        )}
        <svg
          viewBox="0 0 1160 485"
          width="100%"
          style={{ display: "block", minWidth: 760 }}
          aria-label="Relative leadership rotation map"
          onClick={() => setSelected(null)}
        >
          <rect
            x={plot.left}
            y={plot.top}
            width={mapX(0, plot, domain) - plot.left}
            height={yAxis - plot.top}
            fill={activeQuadrantConfig.UPPER_LEFT.fill}
          />
          <rect
            x={mapX(0, plot, domain)}
            y={plot.top}
            width={plot.left + plot.width - mapX(0, plot, domain)}
            height={yAxis - plot.top}
            fill={activeQuadrantConfig.UPPER_RIGHT.fill}
          />
          <rect
            x={plot.left}
            y={yAxis}
            width={mapX(0, plot, domain) - plot.left}
            height={plot.top + plot.height - yAxis}
            fill={activeQuadrantConfig.LOWER_LEFT.fill}
          />
          <rect
            x={mapX(0, plot, domain)}
            y={yAxis}
            width={plot.left + plot.width - mapX(0, plot, domain)}
            height={plot.top + plot.height - yAxis}
            fill={activeQuadrantConfig.LOWER_RIGHT.fill}
          />
          {Array.from({ length: 13 }, (_, i) => (
            <line
              key={`v${i}`}
              x1={plot.left + i * (plot.width / 12)}
              x2={plot.left + i * (plot.width / 12)}
              y1={plot.top}
              y2={plot.top + plot.height}
              stroke="#d8dfde"
              strokeWidth=".75"
            />
          ))}
          {Array.from({ length: 9 }, (_, i) => (
            <line
              key={`h${i}`}
              x1={plot.left}
              x2={plot.left + plot.width}
              y1={plot.top + i * (plot.height / 8)}
              y2={plot.top + i * (plot.height / 8)}
              stroke="#d8dfde"
              strokeWidth=".75"
            />
          ))}
          <line
            x1={mapX(0, plot, domain)}
            x2={mapX(0, plot, domain)}
            y1={plot.top}
            y2={plot.top + plot.height}
            stroke="#9ca9a7"
            strokeWidth="1.25"
          />
          <line
            x1={plot.left}
            x2={plot.left + plot.width}
            y1={yAxis}
            y2={yAxis}
            stroke="#9ca9a7"
            strokeWidth="1.25"
          />
          <text x="85" y="66" fontFamily="Geist" fontWeight="600" fontSize="12" fill={activeQuadrantConfig.UPPER_LEFT.color}>
            {activeQuadrantConfig.UPPER_LEFT.label}
          </text>
          <text x="1035" y="66" fontFamily="Geist" fontWeight="600" fontSize="12" fill={activeQuadrantConfig.UPPER_RIGHT.color} textAnchor="end">
            {activeQuadrantConfig.UPPER_RIGHT.label}
          </text>
          <text x="85" y="418" fontFamily="Geist" fontWeight="600" fontSize="12" fill={activeQuadrantConfig.LOWER_LEFT.color}>
            {activeQuadrantConfig.LOWER_LEFT.label}
          </text>
          <text x="1095" y="418" fontFamily="Geist" fontWeight="600" fontSize="12" fill={activeQuadrantConfig.LOWER_RIGHT.color} textAnchor="end">
            {activeQuadrantConfig.LOWER_RIGHT.label}
          </text>
          {visible.map((s) => {
            if (s.excess20d === null) return null;
            const yValue = mapYValue(s, mapMode);
            if (yValue === null) return null;
            const isOffScaleY = isOutOfYBounds(yValue, plot, domain);
            const isOffScaleX = isOutOfXBounds(s.excess20d, plot, domain);
            const isOffScale = isOffScaleX || isOffScaleY;
            const y = isOffScaleY ? clampY(yValue, plot, domain) : mapY(yValue, plot, domain);
            const x = isOffScaleX ? clampX(s.excess20d, plot, domain) : mapX(s.excess20d, plot, domain);
            // Dot color reflects LEADERSHIP state, not quadrant.
            // The copy and legend say "leadership" so the implementation
            // must match. Quadrant fills stay for the background only.
            const dotColor = leadershipColor(s.leadership);
            const radius = 5 + Math.sqrt(Math.max(1, s.constituents)) / 3.8;
            return (
              <g
                key={s.id}
                role="button"
                tabIndex={0}
                aria-label={`Select ${s.name} group: ${s.leadership} leadership, ${s.diffusion} diffusion${isOffScale ? " (off scale)" : ""}`}
                onClick={(event) => {
                  event.stopPropagation();
                  setSelected(s);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelected(s);
                  }
                }}
                className="map-group"
                style={{ cursor: "pointer" }}
              >
                <title>
                  {s.name}: {s.leadership} leadership / {s.diffusion} diffusion
                  {isOffScale ? " (value outside domain)" : ""}
                </title>
                <circle
                  cx={x}
                  cy={y}
                  r={radius + (selected?.id === s.id ? 3 : 0)}
                  fill="#fff"
                  stroke={selected?.id === s.id ? "#d97956" : dotColor}
                  strokeWidth={selected?.id === s.id ? 3 : 1.6}
                />
                <circle cx={x} cy={y} r="3" fill={dotColor} />
                {isOffScale && (
                  <polygon points={`${x},${y - radius - 6} ${x - 4},${y - radius - 1} ${x + 4},${y - radius - 1}`} fill={dotColor} opacity={0.7} />
                )}
              </g>
            );
          })}
          {labelPositions.map((label) => {
            return (
              <text
                key={`lbl-${label.id}`}
                x={label.x}
                y={label.y}
                textAnchor={label.textAnchor}
                fontFamily="Geist"
                fontSize="10"
                fill="#202325"
                pointerEvents="none"
              >
                {label.text}
              </text>
            );
          })}
          {plottable.length < visible.length && (() => {
            const offScale = visible.length - plottable.length;
            return (
              <text x="580" y="458" fontFamily="Geist Mono" fontSize="9" fill="#8f8f8f" textAnchor="middle">
                {offScale} group(s) off scale — shown at boundary{offScale === 1 ? "" : "s"}
              </text>
            );
          })()}
          <text x="485" y="477" fontFamily="Geist Mono" fontSize="10" fill="#747a7d">
            {axisLabels.x} (clamped if off scale) →
          </text>
          <text
            x="18"
            y="275"
            fontFamily="Geist Mono"
            fontSize="10"
            fill="#747a7d"
            transform="rotate(-90 18 275)"
          >
            {axisLabels.y} (clamped if off scale)
          </text>
        </svg>
      </div>
      <div
        className="map-summary-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 10,
          marginTop: 20,
        }}
      >
        {(["UPPER_RIGHT", "UPPER_LEFT", "LOWER_RIGHT", "LOWER_LEFT"] as Quadrant[]).map((quadrant) => {
          const config = activeQuadrantConfig[quadrant];
          const groups = plottable.filter((s) => {
            if (s.excess20d === null) return false;
            const yValue = mapYValue(s, mapMode);
            return yValue !== null && signedQuadrant(s.excess20d, yValue - yBaseline) === quadrant;
          });
          return (
            <div
              key={quadrant}
              style={{
                textAlign: "left",
                padding: "13px 15px",
                background: config.fill,
                border: `1px solid ${config.color}33`,
                borderRadius: 10,
              }}
            >
              <div style={{ fontSize: 10, fontWeight: 600, color: config.color }}>● {config.label}</div>
              <strong style={{ display: "block", fontSize: 22, margin: "8px 0 3px" }}>{groups.length}</strong>
                <span style={{ fontSize: 10, color: "#747a7d" }}>current groups · IHSG excluded</span>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 11, color: "#747a7d", fontSize: 11 }}>
        <span>Leadership state:</span>
        {filterStates.map((state) => (
          <span key={state} style={{ color: state === "UNCONFIRMED" ? "#7c858c" : "#202325" }}>
            {state} {sectors.filter((s) => s.leadership === state).length}
          </span>
        ))}
      </div>
      {/* Compact table fallback so every group remains inspectable */}
      <div style={{ marginTop: 20, background: "#faf9f6", border: "1px solid #dfe2e1", padding: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          Group table (all {visible.length} groups)
        </div>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 11,
            fontFamily: "Geist Mono",
          }}
          aria-label="All groups table"
        >
          <thead>
            <tr style={{ borderBottom: "1px solid #dfe2e1", textAlign: "left" }}>
              <th style={{ padding: "4px 8px" }}>Group</th>
              <th style={{ padding: "4px 8px" }}>Leadership</th>
              <th style={{ padding: "4px 8px" }}>Diffusion</th>
              <th style={{ padding: "4px 8px", textAlign: "right" }}>20D ex.</th>
              <th style={{ padding: "4px 8px", textAlign: "right" }}>Breadth</th>
              <th style={{ padding: "4px 8px", textAlign: "right" }}>Pol-elig</th>
              <th style={{ padding: "4px 8px", textAlign: "right" }}>Acq-fail</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((s) => (
              <tr key={s.id} style={{ borderBottom: "1px solid #f0f1ef" }}>
                <td style={{ padding: "4px 8px" }}>{s.name}</td>
                <td style={{ padding: "4px 8px" }}>{s.leadership}</td>
                <td style={{ padding: "4px 8px" }}>{s.diffusion}</td>
                <td style={{ padding: "4px 8px", textAlign: "right" }}>
                  {s.excess20d !== null ? s.excess20d.toFixed(1) : "—"}
                </td>
                <td style={{ padding: "4px 8px", textAlign: "right" }}>
                  {s.breadth !== null ? s.breadth.toFixed(1) : "—"}
                </td>
                <td style={{ padding: "4px 8px", textAlign: "right" }}>
                  {s.eligibleConstituents ?? "—"}
                </td>
                <td style={{ padding: "4px 8px", textAlign: "right" }}>
                  {s.missingConstituents ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ color: "#747a7d", fontSize: 12, marginTop: 12 }}>
        {mapMode === "trajectory"
          ? "Latest snapshot. Dots show sector groups with comparable prior breadth; leadership and diffusion states remain separate."
          : "Latest snapshot. Dots show current 20D breadth and relative excess return; diffusion change remains unavailable without a comparable prior."}
      </p>
    </div>
  );
}
