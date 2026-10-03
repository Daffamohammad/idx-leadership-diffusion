// MarketHeatmap — landing-page market heatmap.
//
// Visualises equal-weight excess return over a configurable horizon per
// taxonomy group. Supports switching between Sector / Konglo / Themes.
//
// Values come from the Python-aggregated `taxonomy_views` payload. The
// component never recomputes metrics.
//
// Colour scale uses OKLCH-inspired perceptually-uniform hues. Empty or
// data-gap groups are rendered explicitly muted rather than as zero.

import { useMemo, useState } from "react";
import type {
  ForeignFlowAdapted,
  TaxonomyGroupData,
} from "../data/adapter";
import type { ForeignFlowDirection, TaxonomyKind } from "../data/snapshot";
import { formatCountLabel, formatDateLabel, formatEnumLabel, formatPercent } from "../data/format";
import { EvidenceBadge } from "./EvidenceModel";

const TAXONOMY_ORDER: TaxonomyKind[] = ["SECTOR", "KONGLO", "THEMES"];


export type HeatmapMetric = "excess20d" | "excess60d" | "breadth" | "leadership" | "diffusion";

interface MarketHeatmapProps {
  taxonomyGroups: Record<string, TaxonomyGroupData>;
  taxonomyNames: Record<TaxonomyKind, string>;
  taxonomyKindsById: Record<string, TaxonomyKind>;
  foreignFlow: ForeignFlowAdapted | null;
  asOf: string | null;
  onSelectGroup?: (taxonomyKind: TaxonomyKind, taxonomyId: string, groupId: string) => void;
}

function colorFor(value: number | null, metric: HeatmapMetric): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "#f1f2f0";
  }
  // Each metric uses a domain-appropriate scale.
  if (metric === "leadership") {
    switch (value) {
      case 1: return "#178477"; // LEADING
      case 0.66: return "#3f9985";
      case 0.33: return "#c69f4a"; // IMPROVING
      case -0.33: return "#a35535"; // WEAKENING
      case -1: return "#8f2424"; // LAGGING
      default: return "#7c858c";
    }
  }
  if (metric === "breadth") {
    if (value >= 65) return "#178477";
    if (value >= 50) return "#3f9985";
    if (value >= 35) return "#c69f4a";
    return "#8f2424";
  }
  if (metric === "diffusion") {
    if (value > 0) return "#178477";
    if (value < 0) return "#8f2424";
    return "#7c858c";
  }
  // Excess return — symmetric scale.
  const clamped = Math.max(-15, Math.min(15, value));
  if (clamped >= 0) {
    const t = clamped / 15;
    const green = Math.round(120 + t * 100);
    const red = Math.round(80 + (1 - t) * 60);
    return `rgb(${red}, ${green}, ${Math.round(110 + t * 50)})`;
  }
  const t = -clamped / 15;
  const red = Math.round(110 + t * 130);
  const green = Math.round(80 + (1 - t) * 80);
  return `rgb(${red}, ${green}, ${Math.round(110 + t * 60)})`;
}

function relativeLuminance(r: number, g: number, b: number): number {
  const chan = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b);
}

function contrastRatio(bg: [number, number, number], ink: [number, number, number]): number {
  const l1 = relativeLuminance(...bg);
  const l2 = relativeLuminance(...ink);
  const hi = Math.max(l1, l2);
  const lo = Math.min(l1, l2);
  return (hi + 0.05) / (lo + 0.05);
}

const NEAR_BLACK: [number, number, number] = [11, 13, 15];
const WHITE: [number, number, number] = [255, 255, 255];

/** Near-black or white, whichever reads better on `color`. Always >= 4.58:1. */
function inkOn(color: string): string {
  const rgb = color.startsWith("#")
    ? (() => {
        const h = color.slice(1);
        const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
        return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
      })()
    : /^rgb\(/.test(color)
      ? color.match(/\d+/g)!.slice(0, 3).map(Number)
      : null;
  if (!rgb) return "#101215";
  const bg = rgb as [number, number, number];
  return contrastRatio(bg, NEAR_BLACK) >= contrastRatio(bg, WHITE)
    ? "rgb(11, 13, 15)"
    : "rgb(255, 255, 255)";
}

function metricLabel(metric: HeatmapMetric): string {
  switch (metric) {
    case "excess20d":
      return "20D excess return vs IHSG";
    case "excess60d":
      return "60D excess return vs IHSG";
    case "breadth":
      return "Breadth (% constituents outperforming)";
    case "leadership":
      return "Leadership state";
    case "diffusion":
      return "Diffusion state";
  }
}

function metricValue(group: TaxonomyGroupData, metric: HeatmapMetric): number | null {
  switch (metric) {
    case "excess20d":
      return group.excess20d;
    case "excess60d":
      return group.excess60d;
    case "breadth":
      return group.breadth;
    case "leadership": {
      switch (group.leadership) {
        case "LEADING": return 1;
        case "IMPROVING": return 0.33;
        case "WEAKENING": return -0.33;
        case "LAGGING": return -1;
        default: return 0;
      }
    }
    case "diffusion": {
      switch (group.diffusion) {
        case "BROADENING": return 1;
        case "NARROWING": return -1;
        case "STABLE": return 0;
        default: return null;
      }
    }
  }
}

function legendForMetric(metric: HeatmapMetric): Array<{ label: string; color: string }> {
  switch (metric) {
    case "excess20d":
    case "excess60d":
      return [
        { label: "−15%", color: colorFor(-15, metric) },
        { label: "0%", color: colorFor(0, metric) },
        { label: "+15%", color: colorFor(15, metric) },
      ];
    case "breadth":
      return [
        { label: "Low", color: colorFor(20, metric) },
        { label: "Mid", color: colorFor(50, metric) },
        { label: "High", color: colorFor(80, metric) },
      ];
    case "leadership":
      return [
        { label: "Leading", color: colorFor(1, metric) },
        { label: "Improving", color: colorFor(0.33, metric) },
        { label: "Weakening", color: colorFor(-0.33, metric) },
        { label: "Lagging", color: colorFor(-1, metric) },
        { label: "Unconfirmed", color: colorFor(null, metric) },
      ];
    case "diffusion":
      return [
        { label: "Broadening", color: colorFor(1, metric) },
        { label: "Stable", color: colorFor(0, metric) },
        { label: "Narrowing", color: colorFor(-1, metric) },
        { label: "Unconfirmed", color: colorFor(null, metric) },
      ];
  }
}

function dataGapReason(group: TaxonomyGroupData): string {
  if (group.constituents === 0) return "No constituents";
  if (group.eligible === 0) return "No eligible history";
  if (group.diffusion === "UNCONFIRMED") return "No comparable prior";
  return "Coverage incomplete";
}

function metricDisplay(group: TaxonomyGroupData, metric: HeatmapMetric, value: number | null): string {
  if (metric === "leadership") return formatEnumLabel(group.leadership);
  if (metric === "diffusion") return formatEnumLabel(group.diffusion);
  if (metric === "breadth") return value === null ? "Not available" : `${value.toFixed(0)}%`;
  return value === null ? "Not available" : formatPercent(value);
}

function directionBadge(direction: ForeignFlowDirection | null): string {
  switch (direction) {
    case "NET_BUY":
      return "▲ Net buy";
    case "NET_SELL":
      return "▼ Net sell";
    case "FLAT":
      return "≈ Flat";
    default:
      return "—";
  }
}

export default function MarketHeatmap({
  taxonomyGroups,
  taxonomyNames,
  taxonomyKindsById,
  foreignFlow,
  asOf,
  onSelectGroup,
}: MarketHeatmapProps) {
  const [taxonomyId, setTaxonomyId] = useState<string>(() => {
    const ids = Object.entries(taxonomyKindsById);
    return ids.find(([, kind]) => kind === "SECTOR")?.[0] ?? ids[0]?.[0] ?? "";
  });
  const [metric, setMetric] = useState<HeatmapMetric>("excess20d");

  const taxonomyKind: TaxonomyKind | undefined = taxonomyKindsById[taxonomyId];

  const filteredGroups = useMemo(() => {
    if (!taxonomyKind) return [];
    return Object.values(taxonomyGroups)
      .filter((group) => group.taxonomyKind === taxonomyKind)
      .sort((a, b) => b.constituents - a.constituents);
  }, [taxonomyGroups, taxonomyKind]);

  const foreignByGroup = useMemo(() => {
    const map = new Map<string, ForeignFlowDirection>();
    if (foreignFlow) {
      for (const summary of foreignFlow.groupSummaries) {
        if (summary.netValueIdr !== 0) map.set(summary.groupId, summary.direction);
      }
    }
    return map;
  }, [foreignFlow]);

  if (!taxonomyKind || filteredGroups.length === 0) {
    return (
      <section
        aria-labelledby="heatmap-title"
        style={{
          border: "1px solid var(--line)",
          background: "var(--surface-subtle)",
          padding: 28,
        }}
      >
        <div className="eyebrow-muted" id="heatmap-title">
          Market heatmap
        </div>
        <h2 style={{ marginTop: 6, marginBottom: 12, fontSize: 22 }}>
          No taxonomy groups available
        </h2>
        <p style={{ margin: 0, color: "var(--muted)", lineHeight: 1.5 }}>
          The exporter did not emit a taxonomy view for this snapshot. The
          heatmap will render once a taxonomy YAML is registered and the
          snapshot is rebuilt.
        </p>
      </section>
    );
  }

  const asOfLabel = asOf ? formatDateLabel(asOf) : "snapshot";
  const legend = legendForMetric(metric);
  const evidenceKind = taxonomyKind === "SECTOR" ? "SNAPSHOT" : "PROTOTYPE";

  return (
    <section
      aria-labelledby="heatmap-title"
      style={{
        border: "1px solid var(--line)",
        background: "var(--surface-subtle)",
        padding: 24,
        display: "grid",
        gap: 18,
      }}
    >
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div className="eyebrow-muted" id="heatmap-title">
              Market heatmap
            </div>
            <EvidenceBadge kind={evidenceKind} compact />
          </div>
          <h2 style={{ margin: "6px 0 4px", fontSize: 22, letterSpacing: "-.02em" }}>
            {taxonomyNames[taxonomyKind] ?? taxonomyKind}
          </h2>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
              fontSize: 11,
              color: "var(--muted)",
              fontFamily: "Geist Mono, monospace",
            }}
          >
            <span>As of {asOfLabel}</span>
            <span>·</span>
            <span>
              {taxonomyKind === "SECTOR"
                ? "Real persisted market observations"
                : "Static membership definition · current snapshot aggregates"}
            </span>
            <span>·</span>
            <span>No recommendation language</span>
          </div>
          <p style={{ margin: "12px 0 0", fontSize: 12, color: "var(--ink)" }}>
            Click a tile to open group detail.
          </p>
        </div>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <fieldset
            style={{
              border: "1px solid #b9c0be",
              padding: "8px 12px",
              background: "var(--surface)",
              minWidth: 220,
            }}
          >
            <legend
              style={{
                fontSize: 11,
                color: "var(--muted)",
                fontFamily: "Geist Mono, monospace",
                padding: "0 6px",
              }}
            >
              Taxonomy
            </legend>
            <div role="radiogroup" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {TAXONOMY_ORDER.map((kind) => {
                const id = Object.entries(taxonomyKindsById).find(
                  ([, availableKind]) => availableKind === kind,
                )?.[0] ?? kind.toLowerCase();
                const available = Object.values(taxonomyGroups).some(
                      (group) => group.taxonomyKind === kind,
                    );
                const isActive = taxonomyKind === kind;
                return (
                  <button
                    key={kind}
                    type="button"
                    role="radio"
                    aria-checked={isActive}
                    disabled={!available}
                    onClick={() => setTaxonomyId(id)}
                    style={{
                      padding: "4px 10px",
                      fontSize: 12,
                      border: "1px solid",
                      borderColor: isActive ? "var(--ink)" : "var(--line)",
                      background: isActive ? "var(--ink)" : "var(--surface)",
                      color: isActive ? "var(--bg)" : available ? "var(--ink)" : "var(--muted)",
                      cursor: available ? "pointer" : "not-allowed",
                    }}
                  >
                    {taxonomyNames[kind] ?? kind}
                  </button>
                );
              })}
            </div>
          </fieldset>
          <fieldset
            style={{
              border: "1px solid #b9c0be",
              padding: "8px 12px",
              background: "var(--surface)",
              minWidth: 240,
            }}
          >
            <legend
              style={{
                fontSize: 11,
                color: "var(--muted)",
                fontFamily: "Geist Mono, monospace",
                padding: "0 6px",
              }}
            >
              Metric
            </legend>
            <div role="radiogroup" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {(
                [
                  ["excess20d", "20D excess"],
                  ["excess60d", "60D excess"],
                  ["breadth", "Breadth"],
                  ["leadership", "Leadership"],
                  ["diffusion", "Diffusion"],
                ] as Array<[HeatmapMetric, string]>
              ).map(([key, label]) => {
                const isActive = metric === key;
                return (
                  <button
                    key={key}
                    type="button"
                    role="radio"
                    aria-checked={isActive}
                    onClick={() => setMetric(key)}
                    style={{
                      padding: "4px 10px",
                      fontSize: 12,
                      border: "1px solid",
                      borderColor: isActive ? "var(--ink)" : "var(--line)",
                      background: isActive ? "var(--ink)" : "var(--surface)",
                      color: isActive ? "var(--bg)" : "var(--ink)",
                      cursor: "pointer",
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </fieldset>
        </div>
      </header>

      <div
        aria-label={`${metricLabel(metric)} legend`}
        style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, fontSize: 11, color: "var(--muted)" }}
      >
        <span style={{ fontFamily: "Geist Mono, monospace", color: "var(--ink)" }}>Legend · {metricLabel(metric)}</span>
        {legend.map((item) => (
          <span key={item.label} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span aria-hidden="true" style={{ width: 12, height: 12, background: item.color, border: "1px solid rgba(0,0,0,.12)" }} />
            {item.label}
          </span>
        ))}
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span aria-hidden="true" style={{ width: 12, height: 12, background: "var(--surface-subtle)", border: "1px dashed #9aa19f" }} />
          Not available
        </span>
      </div>

      <div
        role="grid"
        aria-label={`Heatmap of ${taxonomyKind} groups by ${metricLabel(metric)}`}
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 10,
        }}
      >
        {filteredGroups.map((group) => {
          const value = metricValue(group, metric);
          const flow = foreignByGroup.get(group.id);
          const isPrototype = group.prototype;
          const isDataGap = group.dataQuality === "DATA_GAP" || value === null;
          const gapReason = dataGapReason(group);
          const cellBg = isDataGap ? "var(--surface-subtle)" : colorFor(value, metric);
          const cellInk = isDataGap ? "var(--muted)" : inkOn(colorFor(value, metric));
          const ariaLabel = `${group.name}: ${metricLabel(metric)} ${isDataGap ? `not available, ${gapReason.toLowerCase()}` : metricDisplay(group, metric, value)}, leadership ${formatEnumLabel(group.leadership)}, diffusion ${formatEnumLabel(group.diffusion)}, ${formatCountLabel(group.constituents, "ticker")}.`;
          return (
            <button
              key={`${group.taxonomyId}::${group.id}`}
              role="gridcell"
              aria-label={ariaLabel}
              onClick={() =>
                onSelectGroup?.(group.taxonomyKind, group.taxonomyId, group.id)
              }
              style={{
                background: cellBg,
                border: isDataGap ? "1px dashed #a7afac" : "1px solid rgba(0,0,0,0.08)",
                padding: "12px 12px 10px",
                minHeight: 96,
                textAlign: "left",
                color: cellInk,
                cursor: "pointer",
                display: "grid",
                gap: 4,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: 11,
                  fontFamily: "Geist Mono, monospace",
                  color: cellInk,
                }}
              >
                <span>{formatEnumLabel(group.taxonomyKind)}</span>
                {isPrototype && (
                  <span
                    title="Analyst-defined prototype taxonomy"
                    style={{
                      background: "rgba(255,255,255,0.7)",
                      padding: "1px 6px",
                      border: "1px solid rgba(0,0,0,0.15)",
                    }}
                  >
                    Prototype
                  </span>
                )}
              </div>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  letterSpacing: "-.01em",
                  lineHeight: 1.2,
                }}
              >
                {group.name}
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 600,
                  fontFamily: "Geist Mono, monospace",
                  letterSpacing: "-.02em",
                }}
              >
                {isDataGap ? (
                  <span style={{ color: "var(--muted)", fontSize: 12, fontWeight: 400 }}>
                    Not available · {gapReason}
                  </span>
                ) : (
                  metricDisplay(group, metric, value)
                )}
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 11,
                  fontFamily: "Geist Mono, monospace",
                  color: cellInk,
                }}
              >
                <span>{formatCountLabel(group.constituents, "ticker")}</span>
                <span>{formatEnumLabel(group.leadership)}</span>
              </div>
              {flow && (
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: "Geist Mono, monospace",
                    color: cellInk,
                  }}
                  title="Foreign-flow sample context (latest published market date)"
                >
                  {directionBadge(flow)} · sample
                </div>
              )}
            </button>
          );
        })}
      </div>

      <footer
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          fontSize: 11,
          color: "var(--muted)",
          fontFamily: "Geist Mono, monospace",
        }}
      >
        <span>Source: Python-aggregated taxonomy views (no frontend recompute)</span>
        <span>·</span>
        <span>Source: snapshot-backed aggregation</span>
        <span>·</span>
        <span>Negative values mean the group is underperforming IHSG; no recommendation language.</span>
      </footer>
    </section>
  );
}
