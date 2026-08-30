// TaxonomyMap — quadrant map for sector, Konglo, and themes.
//
// Reuses the canonical map geometry contract from `data/mapGeometry.ts`
// rather than implementing a parallel coordinate space.
//
// Each cell represents a taxonomy group (sector, Konglo, or theme) at the
// current snapshot:
//   X axis: 20-day excess return vs IHSG (leadership signal)
//   Y axis: 20-day breadth % (diffusion signal)
// Cell colour encodes leadership state (no red/green-only encoding).
// Off-scale groups are placed at the boundary with an explicit marker.

import { useMemo, useState } from "react";
import type { TaxonomyGroupData } from "../data/adapter";
import type { ForeignFlowDirection, TaxonomyKind } from "../data/snapshot";
interface TaxonomyMapProps {
  taxonomyGroups: Record<string, TaxonomyGroupData>;
  foreignFlow: { groupSummaries: Array<{ groupId: string; direction: ForeignFlowDirection; netValueIdr: number }> } | null;
  taxonomyKind: TaxonomyKind;
  title: string;
  subtitle?: string;
  onSelectGroup?: (groupId: string) => void;
}

const PLOT = { left: 60, top: 30, width: 540, height: 320 };
const DOMAIN = { xMin: -15, xMax: 15, yMin: 0, yMax: 100 };
const KIND_LABEL: Record<TaxonomyKind, string> = {
  SECTOR: "Sector",
  KONGLO: "Konglo",
  THEMES: "Themes",
};

function scaleX(value: number): number {
  const ratio = (value - DOMAIN.xMin) / (DOMAIN.xMax - DOMAIN.xMin);
  return PLOT.left + Math.max(0, Math.min(1, ratio)) * PLOT.width;
}
function scaleY(value: number): number {
  const ratio = (value - DOMAIN.yMin) / (DOMAIN.yMax - DOMAIN.yMin);
  return PLOT.top + (1 - Math.max(0, Math.min(1, ratio))) * PLOT.height;
}

function colorFor(leadership: string, diffusion: string): string {
  if (leadership === "LEADING" && diffusion === "BROADENING") return "#178477";
  if (leadership === "LEADING") return "#3f9985";
  if (leadership === "LAGGING" && diffusion === "NARROWING") return "#8f2424";
  if (leadership === "LAGGING") return "#a35535";
  if (diffusion === "NARROWING") return "#c69f4a";
  if (leadership === "IMPROVING") return "#c69f4a";
  if (leadership === "WEAKENING") return "#a35535";
  return "#7c858c";
}

export default function TaxonomyMap({
  taxonomyGroups,
  foreignFlow,
  taxonomyKind,
  title,
  subtitle,
  onSelectGroup,
}: TaxonomyMapProps) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const groups = useMemo(
    () =>
      Object.values(taxonomyGroups)
        .filter((group) => group.taxonomyKind === taxonomyKind)
        .filter((group) => group.excess20d !== null && group.breadth !== null)
        .sort((a, b) => b.constituents - a.constituents),
    [taxonomyGroups, taxonomyKind],
  );
  const foreignByGroup: Record<string, ForeignFlowDirection> = {};
  if (foreignFlow) {
    for (const summary of foreignFlow.groupSummaries) {
      if (summary.netValueIdr !== 0) foreignByGroup[summary.groupId] = summary.direction;
    }
  }

  if (groups.length === 0) {
    return (
      <section
        aria-labelledby={`map-${taxonomyKind}-title`}
        style={{
          border: "1px solid #dfe2e1",
          padding: 22,
          background: "#faf9f6",
        }}
      >
        <div className="eyebrow-muted" id={`map-${taxonomyKind}-title`}>
          {title}
        </div>
        <h2 style={{ marginTop: 6, marginBottom: 8, fontSize: 22 }}>{title}</h2>
        <p style={{ margin: 0, color: "#686e73" }}>
          No plottable groups for this taxonomy at the current snapshot.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby={`map-${taxonomyKind}-title`}
      style={{
        border: "1px solid #dfe2e1",
        padding: 22,
        background: "#faf9f6",
      }}
    >
      <header>
        <div className="eyebrow-muted" id={`map-${taxonomyKind}-title`}>
          {KIND_LABEL[taxonomyKind]} map
        </div>
        <h2 style={{ marginTop: 6, marginBottom: 8, fontSize: 22 }}>{title}</h2>
        {subtitle && (
          <p
            style={{
              margin: 0,
              color: "#686e73",
              fontSize: 13,
              fontFamily: "Geist Mono, monospace",
            }}
          >
            {subtitle}
          </p>
        )}
      </header>

      <svg
        role="img"
        aria-label={`${title} map`}
        viewBox={`0 0 ${PLOT.left + PLOT.width + 30} ${PLOT.top + PLOT.height + 50}`}
        style={{ width: "100%", maxWidth: 720, height: "auto" }}
      >
        <rect
          x={PLOT.left}
          y={PLOT.top}
          width={PLOT.width}
          height={PLOT.height}
          fill="#ffffff"
          stroke="#dfe2e1"
        />
        {/* Quadrant divider */}
        <line
          x1={scaleX(0)}
          y1={PLOT.top}
          x2={scaleX(0)}
          y2={PLOT.top + PLOT.height}
          stroke="#b9c0be"
          strokeDasharray="4 4"
        />
        <line
          x1={PLOT.left}
          y1={scaleY(50)}
          x2={PLOT.left + PLOT.width}
          y2={scaleY(50)}
          stroke="#b9c0be"
          strokeDasharray="4 4"
        />
        {/* Axis labels — centered within plot bounds */}
        <text
          x={PLOT.left + PLOT.width / 2}
          y={PLOT.top + PLOT.height + 34}
          textAnchor="middle"
          fontSize={11}
          fontFamily="Geist Mono, monospace"
          fill="#686e73"
        >
          20D excess return vs IHSG
        </text>
        <text
          transform={`rotate(-90 ${PLOT.left - 36} ${PLOT.top + PLOT.height / 2})`}
          x={PLOT.left - 36}
          y={PLOT.top + PLOT.height / 2}
          textAnchor="middle"
          fontSize={11}
          fontFamily="Geist Mono, monospace"
          fill="#686e73"
        >
          Breadth (% outperforming)
        </text>
        <text x={PLOT.left - 6} y={PLOT.top + 4} fontSize={10} fontFamily="Geist Mono, monospace" fill="#7c858c" textAnchor="end" dominantBaseline="middle">
          100%
        </text>
        <text x={PLOT.left - 6} y={PLOT.top + PLOT.height + 4} fontSize={10} fontFamily="Geist Mono, monospace" fill="#7c858c" textAnchor="end" dominantBaseline="middle">
          0%
        </text>
        <text x={PLOT.left} y={PLOT.top + PLOT.height + 16} fontSize={10} fontFamily="Geist Mono, monospace" fill="#7c858c" textAnchor="start">
          -15pp
        </text>
        <text x={PLOT.left + PLOT.width} y={PLOT.top + PLOT.height + 16} fontSize={10} fontFamily="Geist Mono, monospace" fill="#7c858c" textAnchor="end">
          +15pp
        </text>
        <text x={scaleX(0)} y={PLOT.top + PLOT.height + 16} fontSize={10} fontFamily="Geist Mono, monospace" fill="#7c858c" textAnchor="middle">
          0
        </text>

        {/* Quadrant annotations — centered within each quadrant */}
        <text x={scaleX(7.5)} y={scaleY(78)} fontSize={10} fontFamily="Geist Mono, monospace" fill="#178477" opacity={0.7} textAnchor="middle">
          leading · broadening
        </text>
        <text x={scaleX(7.5)} y={scaleY(22)} fontSize={10} fontFamily="Geist Mono, monospace" fill="#a35535" opacity={0.7} textAnchor="middle">
          leading · narrowing
        </text>
        <text x={scaleX(-7.5)} y={scaleY(78)} fontSize={10} fontFamily="Geist Mono, monospace" fill="#a35535" opacity={0.7} textAnchor="middle">
          lagging · broadening
        </text>
        <text x={scaleX(-7.5)} y={scaleY(22)} fontSize={10} fontFamily="Geist Mono, monospace" fill="#8f2424" opacity={0.7} textAnchor="middle">
          lagging · narrowing
        </text>

        {groups.map((group) => {
          const x = scaleX(group.excess20d ?? 0);
          const y = scaleY(group.breadth ?? 0);
          const radius = Math.max(8, Math.min(22, Math.sqrt(group.constituents) * 2.4));
          const colour = colorFor(group.leadership, group.diffusion);
          const flow = foreignByGroup[group.id];
          const isHover = hoverId === `${group.taxonomyId}::${group.id}`;
          // Label alignment: keep within plot horizontal bounds and flip
          // vertically when the bubble sits near the bottom edge so the
          // name does not collide with x-axis tick labels.
          const isNearBottom = y + radius + 14 > PLOT.top + PLOT.height;
          const labelY = isNearBottom ? y - radius - 8 : y + radius + 14;
          const flowLabelY = isNearBottom ? y - radius - 20 : y + radius + 26;
          const labelX = Math.max(PLOT.left + 36, Math.min(PLOT.left + PLOT.width - 36, x));
          const labelAnchor = x < PLOT.left + 44 ? "start" : x > PLOT.left + PLOT.width - 44 ? "end" : "middle";
          return (
            <g
              key={`${group.taxonomyId}::${group.id}`}
              tabIndex={0}
              role="button"
              aria-label={`${group.name}: ${group.leadership.toLowerCase()} / ${group.diffusion.toLowerCase()}, ${group.constituents} tickers`}
              onMouseEnter={() => setHoverId(`${group.taxonomyId}::${group.id}`)}
              onMouseLeave={() => setHoverId(null)}
              onFocus={() => setHoverId(`${group.taxonomyId}::${group.id}`)}
              onBlur={() => setHoverId(null)}
              onClick={() => onSelectGroup?.(group.id)}
              style={{ cursor: "pointer", outline: "none" }}
            >
              {group.offScale && (
                <circle
                  cx={Math.max(PLOT.left + 4, Math.min(PLOT.left + PLOT.width - 4, x))}
                  cy={Math.max(PLOT.top + 4, Math.min(PLOT.top + PLOT.height - 4, y))}
                  r={radius}
                  fill="none"
                  stroke={colour}
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                />
              )}
              <circle
                cx={x}
                cy={y}
                r={radius}
                fill={colour}
                opacity={isHover ? 1 : 0.85}
                stroke={isHover ? "#202325" : "rgba(0,0,0,0.15)"}
                strokeWidth={isHover ? 1.5 : 1}
              />
              <text
                x={x}
                y={y}
                dy="0.35em"
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={11}
                fontFamily="Geist Mono, monospace"
                fill="#fff"
                pointerEvents="none"
              >
                {String(group.constituents)}
              </text>
              <text
                x={labelX}
                y={labelY}
                textAnchor={labelAnchor}
                fontSize={11}
                fontFamily="Geist Mono, monospace"
                fill="#202325"
                dominantBaseline={isNearBottom ? "auto" : "hanging"}
              >
                {group.name.length > 18 ? `${group.name.slice(0, 16)}…` : group.name}
              </text>
              {flow && (
                <text
                  x={labelX}
                  y={flowLabelY}
                  textAnchor={labelAnchor}
                  fontSize={10}
                  fontFamily="Geist Mono, monospace"
                  fill={flow === "NET_BUY" ? "#178477" : flow === "NET_SELL" ? "#8f2424" : "#7c858c"}
                >
                  {flow === "NET_BUY" ? "▲" : flow === "NET_SELL" ? "▼" : "≈"} flow sample
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <footer
        style={{
          marginTop: 12,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 12,
          fontSize: 11,
          color: "#686e73",
          fontFamily: "Geist Mono, monospace",
        }}
      >
        <span>Bubble size ∝ √(constituents)</span>
        <span>·</span>
        <span>Off-scale = dashed ring at plot boundary</span>
        <span>·</span>
        <span>Source: Python taxonomy aggregation</span>
      </footer>
    </section>
  );
}