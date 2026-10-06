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
import { formatCountLabel, formatEnumLabel, formatPercent } from "../data/format";
import { placeMapLabels } from "../data/mapLabels";
interface TaxonomyMapProps {
  taxonomyGroups: Record<string, TaxonomyGroupData>;
  foreignFlow: { groupSummaries: Array<{ groupId: string; direction: ForeignFlowDirection; netValueIdr: number }> } | null;
  taxonomyKind: TaxonomyKind;
  title: string;
  subtitle?: string;
  asOf?: string;
  onSelectGroup?: (groupId: string) => void;
}

const VIEWBOX = { width: 1000, height: 500 };
const PLOT = { left: 90, top: 32, width: 820, height: 390 };
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
  if (leadership === "LEADING" && diffusion === "BROADENING") return "var(--up)";
  if (leadership === "LEADING") return "var(--up)";
  if (leadership === "LAGGING" && diffusion === "NARROWING") return "var(--down)";
  if (leadership === "LAGGING") return "var(--accent-ink)";
  if (diffusion === "NARROWING") return "var(--accent-ink)";
  if (leadership === "IMPROVING") return "var(--accent-ink)";
  if (leadership === "WEAKENING") return "var(--accent-ink)";
  return "var(--muted)";
}

function shortName(name: string): string {
  return name.length > 22 ? `${name.slice(0, 20)}…` : name;
}

function dataGapReason(group: TaxonomyGroupData): string {
  if (group.constituents === 0) return "No constituents";
  if (group.eligible === 0) return "No eligible history";
  if (group.diffusion === "UNCONFIRMED") return "No comparable prior";
  return "Coverage incomplete";
}

export default function TaxonomyMap({
  taxonomyGroups,
  foreignFlow,
  taxonomyKind,
  title,
  subtitle,
  asOf,
  onSelectGroup,
}: TaxonomyMapProps) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const allGroups = useMemo(
    () =>
      Object.values(taxonomyGroups)
        .filter((group) => group.taxonomyKind === taxonomyKind)
        .sort((a, b) => b.constituents - a.constituents),
    [taxonomyGroups, taxonomyKind],
  );
  const groups = useMemo(
    () => allGroups.filter((group) => group.excess20d !== null && group.breadth !== null),
    [allGroups],
  );
  const labelPositions = useMemo(() => {
    const candidates = groups.map((group) => ({
      id: `${group.taxonomyId}::${group.id}`,
      text: shortName(group.name),
      x: scaleX(group.excess20d ?? 0),
      y: scaleY(group.breadth ?? 0),
      radius: Math.max(8, Math.min(22, Math.sqrt(group.constituents) * 2.4)),
      priority: group.constituents * 10 + Math.abs(group.excess20d ?? 0),
    }));
    return placeMapLabels(candidates, {
      left: PLOT.left + 8,
      right: PLOT.left + PLOT.width - 8,
      top: PLOT.top + 8,
      bottom: PLOT.top + PLOT.height - 8,
    }, candidates.length);
  }, [groups]);
  const activeGroup = groups.find((group) => `${group.taxonomyId}::${group.id}` === hoverId) ?? null;
  const leadingGroups = allGroups
    .filter((group) => group.leadership === "LEADING")
    .sort((a, b) => (b.excess20d ?? -Infinity) - (a.excess20d ?? -Infinity));
  const strongestLeader = leadingGroups[0];
  const foreignByGroup: Record<string, ForeignFlowDirection> = {};
  if (foreignFlow) {
    for (const summary of foreignFlow.groupSummaries) {
      if (summary.netValueIdr !== 0) foreignByGroup[summary.groupId] = summary.direction;
    }
  }

  if (allGroups.length === 0) {
    return (
      <section
        aria-labelledby={`map-${taxonomyKind}-title`}
        style={{
          border: "1px solid var(--line)",
          padding: 22,
          background: "var(--surface-subtle)",
        }}
      >
        <div className="eyebrow-muted" id={`map-${taxonomyKind}-title`}>
          {title}
        </div>
        <h2 style={{ marginTop: 6, marginBottom: 8, fontSize: 22 }}>{title}</h2>
        <p style={{ margin: 0, color: "var(--muted)" }}>
          No plottable groups for this taxonomy at the current snapshot.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby={`map-${taxonomyKind}-title`}
      style={{
        border: "1px solid var(--line)",
        padding: 22,
        background: "var(--surface-subtle)",
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
              color: "var(--muted)",
              fontSize: 13,
              fontFamily: "Geist Mono, monospace",
            }}
          >
            {subtitle}
          </p>
        )}
      </header>

      <div className="taxonomy-map-read" role="note">
        <div className="eyebrow-muted">Current cross-section{asOf ? ` · ${asOf}` : ""}</div>
        <p>
          {leadingGroups.length === 0
            ? "No group currently qualifies as leading."
            : `${leadingGroups.length} leading ${leadingGroups.length === 1 ? "group" : "groups"}: ${leadingGroups.slice(0, 3).map((group) => group.name).join(", ")}${leadingGroups.length > 3 ? ` and ${leadingGroups.length - 3} more` : ""}.`}
          {strongestLeader && strongestLeader.excess20d !== null && strongestLeader.breadth !== null
            ? ` Strongest leader: ${strongestLeader.name}, ${formatPercent(strongestLeader.excess20d)} 20D excess and ${strongestLeader.breadth.toFixed(1)}% current breadth.`
            : ""}
        </p>
        <span>X is 20D excess return vs IHSG; Y is current constituent breadth. Quadrants describe current levels, not a breadth trend.</span>
      </div>

      <div className="taxonomy-map-chart-scroll" role="region" aria-label={`${title} chart`} tabIndex={0}>
      <svg
        role="img"
        aria-label={`${title} map. Horizontal axis is 20-day excess return versus IHSG; vertical axis is current constituent breadth.`}
        viewBox={`0 0 ${VIEWBOX.width} ${VIEWBOX.height}`}
        style={{ width: "100%", height: "auto", display: "block", marginTop: 8 }}
      >
        <rect
          x={PLOT.left}
          y={PLOT.top}
          width={PLOT.width}
          height={PLOT.height}
          fill="var(--surface)"
          stroke="var(--line)"
        />
        {/* Quadrant divider */}
        <line
          x1={scaleX(0)}
          y1={PLOT.top}
          x2={scaleX(0)}
          y2={PLOT.top + PLOT.height}
          stroke="var(--line)"
          strokeDasharray="4 4"
        />
        <line
          x1={PLOT.left}
          y1={scaleY(50)}
          x2={PLOT.left + PLOT.width}
          y2={scaleY(50)}
          stroke="var(--line)"
          strokeDasharray="4 4"
        />
        {/* Axis labels — centered within plot bounds */}
        <text
          x={PLOT.left + PLOT.width / 2}
          y={PLOT.top + PLOT.height + 34}
          textAnchor="middle"
          fontSize={11}
          fontFamily="Geist Mono, monospace"
          fill="var(--muted)"
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
          fill="var(--muted)"
        >
          Breadth (% outperforming)
        </text>
        <text x={PLOT.left - 6} y={PLOT.top + 4} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--muted)" textAnchor="end" dominantBaseline="middle">
          100%
        </text>
        <text x={PLOT.left - 6} y={PLOT.top + PLOT.height + 4} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--muted)" textAnchor="end" dominantBaseline="middle">
          0%
        </text>
        <text x={PLOT.left} y={PLOT.top + PLOT.height + 16} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--muted)" textAnchor="start">
          −15%
        </text>
        <text x={PLOT.left + PLOT.width} y={PLOT.top + PLOT.height + 16} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--muted)" textAnchor="end">
          +15%
        </text>
        <text x={scaleX(0)} y={PLOT.top + PLOT.height + 16} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--muted)" textAnchor="middle">
          0%
        </text>

        {/* Quadrant annotations — centered within each quadrant */}
        <text x={scaleX(7.5)} y={scaleY(78)} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--up)" textAnchor="middle">
          Leading · Higher breadth
        </text>
        <text x={scaleX(7.5)} y={scaleY(22)} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--accent-ink)" textAnchor="middle">
          Leading · Lower breadth
        </text>
        <text x={scaleX(-7.5)} y={scaleY(78)} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--accent-ink)" textAnchor="middle">
          Lagging · Higher breadth
        </text>
        <text x={scaleX(-7.5)} y={scaleY(22)} fontSize={10} fontFamily="Geist Mono, monospace" fill="var(--down)" textAnchor="middle">
          Lagging · Lower breadth
        </text>

        {groups.map((group) => {
          const x = scaleX(group.excess20d ?? 0);
          const y = scaleY(group.breadth ?? 0);
          const radius = Math.max(8, Math.min(22, Math.sqrt(group.constituents) * 2.4));
          const colour = colorFor(group.leadership, group.diffusion);
          const groupKey = `${group.taxonomyId}::${group.id}`;
          const isHover = hoverId === groupKey;
          return (
            <g
              key={groupKey}
              tabIndex={0}
              role="button"
              aria-label={`${group.name}: ${formatEnumLabel(group.leadership)} / ${formatEnumLabel(group.diffusion)}, ${formatCountLabel(group.constituents, "ticker")}`}
              onMouseEnter={() => setHoverId(groupKey)}
              onMouseLeave={() => setHoverId(null)}
              onFocus={() => setHoverId(groupKey)}
              onBlur={() => setHoverId(null)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectGroup?.(group.id);
                }
              }}
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
                stroke={isHover ? "var(--ink)" : "rgba(0,0,0,0.15)"}
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
                fill="var(--on-accent)"
                pointerEvents="none"
              >
                {String(group.constituents)}
              </text>
            </g>
          );
        })}
        {labelPositions.map((label) => {
          const isActive = hoverId === label.id;
          const targetX = label.targetX ?? label.x;
          const targetY = label.targetY ?? label.y;
          const hasLeader = Math.hypot(label.x - targetX, label.y - targetY) > 16;
          return (
            <g key={`label-${label.id}`} pointerEvents="none">
              {hasLeader && (
                <line
                  x1={targetX}
                  y1={targetY}
                  x2={label.x}
                  y2={label.y - 3}
                  stroke={isActive ? "var(--ink)" : "#9aa19f"}
                  strokeWidth={isActive ? 1.2 : 0.8}
                />
              )}
              <text
                x={label.x}
                y={label.y}
                textAnchor={label.textAnchor}
                fontSize={isActive ? 12 : 11}
                fontFamily="Geist Mono, monospace"
                fontWeight={isActive ? 600 : 400}
                fill="var(--ink)"
                dominantBaseline="hanging"
              >
                {label.text}
              </text>
            </g>
          );
        })}
        {activeGroup && (
          <g pointerEvents="none">
            <rect x={PLOT.left + PLOT.width - 286} y={8} width={278} height={48} fill="#121619" opacity={0.96} />
            <text x={PLOT.left + PLOT.width - 272} y={25} fill="#ffffff" fontSize={12} fontFamily="Geist" fontWeight={600}>
              {shortName(activeGroup.name)}
            </text>
            <text x={PLOT.left + PLOT.width - 272} y={43} fill="#b8bdc0" fontSize={10} fontFamily="Geist Mono, monospace">
              {formatEnumLabel(activeGroup.leadership)} · {formatEnumLabel(activeGroup.diffusion)} · {formatCountLabel(activeGroup.constituents, "ticker")}
            </text>
          </g>
        )}
        {groups.length === 0 && (
          <text x={PLOT.left + PLOT.width / 2} y={PLOT.top + PLOT.height / 2} textAnchor="middle" fill="var(--muted)" fontSize={13} fontFamily="Geist">
            No plottable groups in this snapshot
          </text>
        )}
      </svg>
      </div>

      <div
        className="map-summary-grid"
        aria-label={`${KIND_LABEL[taxonomyKind]} groups list`}
        style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, marginTop: 12 }}
      >
        {allGroups.map((group) => {
          const groupKey = `${group.taxonomyId}::${group.id}`;
          const isDataGap = group.excess20d === null || group.breadth === null || group.dataQuality === "DATA_GAP";
          const flow = foreignByGroup[group.id];
          return (
            <button
              key={`summary-${groupKey}`}
              type="button"
              onClick={() => onSelectGroup?.(group.id)}
              onFocus={() => setHoverId(groupKey)}
              onBlur={() => setHoverId(null)}
              style={{ display: "grid", gap: 3, textAlign: "left", padding: "9px 10px", border: "1px solid var(--line)", background: isDataGap ? "var(--surface-subtle)" : "var(--surface)", color: "var(--ink)", cursor: "pointer", minWidth: 0 }}
            >
              <span style={{ fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{group.name}</span>
              <span style={{ fontFamily: "Geist Mono, monospace", fontSize: 10, color: isDataGap ? "var(--muted)" : "var(--muted)" }}>
                {isDataGap ? `Not available · ${dataGapReason(group)}` : `${formatEnumLabel(group.leadership)} · ${formatEnumLabel(group.diffusion)}${flow ? ` · ${formatEnumLabel(flow)} flow` : ""}`}
              </span>
            </button>
          );
        })}
      </div>

      <footer
        style={{
          marginTop: 12,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 12,
          fontSize: 11,
          color: "var(--muted)",
          fontFamily: "Geist Mono, monospace",
        }}
      >
        <span>Bubble size ∝ √(constituents)</span>
        <span>·</span>
        <span>Off-scale = dashed ring at plot boundary</span>
        <span>·</span>
        <span>Use the group list below for keyboard access</span>
        <span>·</span>
        <span>Source: Python taxonomy aggregation</span>
      </footer>
    </section>
  );
}
