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

const TAXONOMY_ORDER: TaxonomyKind[] = ["SECTOR", "KONGLO", "THEMES"];


export type HeatmapMetric = "excess20d" | "excess60d" | "breadth" | "leadership";

interface MarketHeatmapProps {
  taxonomyGroups: Record<string, TaxonomyGroupData>;
  taxonomyNames: Record<TaxonomyKind, string>;
  taxonomyKindsById: Record<string, TaxonomyKind>;
  foreignFlow: ForeignFlowAdapted | null;
  asOf: string | null;
  onSelectGroup?: (taxonomyKind: TaxonomyKind, taxonomyId: string, groupId: string) => void;
}

function formatSigned(value: number | null, places = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const rounded = value.toFixed(places);
  return value >= 0 ? `+${rounded}` : rounded;
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
  }
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
    const ids = Object.keys(taxonomyKindsById);
    return ids.length ? ids[0] : "";
  });
  const [metric, setMetric] = useState<HeatmapMetric>("excess20d");

  const taxonomyKind: TaxonomyKind | undefined = taxonomyKindsById[taxonomyId];

  const filteredGroups = useMemo(() => {
    if (!taxonomyKind) return [];
    return Object.values(taxonomyGroups)
      .filter((group) => group.taxonomyKind === taxonomyKind)
      .sort((a, b) => b.constituents - a.constituents);
  }, [taxonomyGroups, taxonomyKind]);

  if (!taxonomyKind || filteredGroups.length === 0) {
    return (
      <section
        aria-labelledby="heatmap-title"
        style={{
          border: "1px solid #dfe2e1",
          background: "#faf9f6",
          padding: 28,
        }}
      >
        <div className="eyebrow-muted" id="heatmap-title">
          Market heatmap
        </div>
        <h2 style={{ marginTop: 6, marginBottom: 12, fontSize: 22 }}>
          No taxonomy groups available
        </h2>
        <p style={{ margin: 0, color: "#686e73", lineHeight: 1.5 }}>
          The exporter did not emit a taxonomy view for this snapshot. The
          heatmap will render once a taxonomy YAML is registered and the
          snapshot is rebuilt.
        </p>
      </section>
    );
  }

  const asOfLabel = asOf ?? "snapshot";
  const foreignByGroup = useMemo(() => {
    const map = new Map<string, ForeignFlowDirection>();
    if (foreignFlow) {
      for (const summary of foreignFlow.groupSummaries) {
        if (summary.netValueIdr !== 0) {
          map.set(summary.groupId, summary.direction);
        }
      }
    }
    return map;
  }, [foreignFlow]);

  return (
    <section
      aria-labelledby="heatmap-title"
      style={{
        border: "1px solid #dfe2e1",
        background: "#faf9f6",
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
          <div className="eyebrow-muted" id="heatmap-title">
            Market heatmap
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
              color: "#686e73",
              fontFamily: "Geist Mono, monospace",
            }}
          >
            <span>As of {asOfLabel}</span>
            <span>·</span>
            <span>Prototype taxonomy (analyst-defined)</span>
            <span>·</span>
            <span>No recommendation language</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <fieldset
            style={{
              border: "1px solid #b9c0be",
              padding: "8px 12px",
              background: "#fff",
              minWidth: 220,
            }}
          >
            <legend
              style={{
                fontSize: 11,
                color: "#686e73",
                fontFamily: "Geist Mono, monospace",
                padding: "0 6px",
              }}
            >
              Taxonomy
            </legend>
            <div role="radiogroup" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {TAXONOMY_ORDER.map((kind) => {
                const id = kind.toLowerCase();
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
                      borderColor: isActive ? "#202325" : "#dfe2e1",
                      background: isActive ? "#202325" : "#fff",
                      color: isActive ? "#fff" : available ? "#202325" : "#7c858c",
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
              background: "#fff",
              minWidth: 240,
            }}
          >
            <legend
              style={{
                fontSize: 11,
                color: "#686e73",
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
                      borderColor: isActive ? "#202325" : "#dfe2e1",
                      background: isActive ? "#202325" : "#fff",
                      color: isActive ? "#fff" : "#202325",
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
          const ariaLabel = `${group.name}: ${metricLabel(metric)} ${formatSigned(value)}, leadership ${group.leadership}, diffusion ${group.diffusion}, ${group.constituents} constituents.`;
          return (
            <button
              key={`${group.taxonomyId}::${group.id}`}
              role="gridcell"
              aria-label={ariaLabel}
              onClick={() =>
                onSelectGroup?.(group.taxonomyKind, group.taxonomyId, group.id)
              }
              style={{
                background: colorFor(value, metric),
                border: "1px solid rgba(0,0,0,0.08)",
                padding: "12px 12px 10px",
                minHeight: 96,
                textAlign: "left",
                color: "#101215",
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
                  color: "rgba(16,18,21,0.75)",
                }}
              >
                <span>{group.taxonomyKind.toLowerCase()}</span>
                {isPrototype && (
                  <span
                    title="Analyst-defined prototype taxonomy"
                    style={{
                      background: "rgba(255,255,255,0.7)",
                      padding: "1px 6px",
                      border: "1px solid rgba(0,0,0,0.15)",
                    }}
                  >
                    prototype
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
                {value === null || value === undefined ? (
                  <span style={{ color: "#686e73", fontSize: 12, fontWeight: 400 }}>
                    data gap
                  </span>
                ) : metric === "leadership" ? (
                  group.leadership.toLowerCase()
                ) : metric === "breadth" ? (
                  `${value.toFixed(0)}%`
                ) : (
                  `${value >= 0 ? "+" : ""}${value.toFixed(1)}pp`
                )}
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 11,
                  fontFamily: "Geist Mono, monospace",
                  color: "rgba(16,18,21,0.75)",
                }}
              >
                <span>{group.constituents} tickers</span>
                <span>{group.leadership.toLowerCase()}</span>
              </div>
              {flow && (
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: "Geist Mono, monospace",
                    color: "rgba(16,18,21,0.85)",
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
          color: "#686e73",
          fontFamily: "Geist Mono, monospace",
        }}
      >
        <span>Source: Python-aggregated taxonomy_views (no frontend recompute)</span>
        <span>·</span>
        <span>Provider mode: PUBLIC_PROTOTYPE</span>
        <span>·</span>
        <span>Negative values mean the group is underperforming IHSG; no recommendation language.</span>
      </footer>
    </section>
  );
}