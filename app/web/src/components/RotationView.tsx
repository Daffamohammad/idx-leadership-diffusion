import { useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { EvidenceBadge } from "./EvidenceModel";
import { useSnapshot } from "../data/SnapshotProvider";
import type { SectorData, TaxonomyGroupData } from "../data/adapter";
import type { TaxonomyKind } from "../data/snapshot";
import { formatCountLabel, formatDateLabel, formatEnumLabel, formatPercent } from "../data/format";
import { placeMapLabels } from "../data/mapLabels";
import {
  classifyRotation,
  relativeMomentum,
  withRotationPhase,
  type RotationGroupInput,
  type RotationPhase,
  type RotationRow,
} from "../data/rotation";

const TAXONOMY_OPTIONS: Array<{ kind: TaxonomyKind; label: string }> = [
  { kind: "SECTOR", label: "Sector" },
  { kind: "KONGLO", label: "Konglo" },
  { kind: "THEMES", label: "Themes" },
];

const DOMAIN = { xMin: -30, xMax: 30, yMin: -30, yMax: 30 };
const PLOT = { left: 86, top: 32, width: 860, height: 360 };
const PLOT_BOUNDS = {
  left: PLOT.left + 8,
  right: PLOT.left + PLOT.width - 8,
  top: PLOT.top + 8,
  bottom: PLOT.top + PLOT.height - 8,
};

const QUADRANTS: Array<{
  phase: RotationPhase;
  x: number;
  y: number;
  color: string;
  fill: string;
  anchor: "start" | "end";
}> = [
  { phase: "IMPROVING", x: -27, y: 25, color: "#54718b", fill: "#edf3f7", anchor: "start" },
  { phase: "LEADING", x: 27, y: 25, color: "#438b82", fill: "#e8f3f0", anchor: "end" },
  { phase: "LAGGING", x: -27, y: -25, color: "#ad6765", fill: "#f8eaea", anchor: "start" },
  { phase: "WEAKENING", x: 27, y: -25, color: "#aa8750", fill: "#f8f0df", anchor: "end" },
];

const DIAGNOSTIC_QUADRANTS = [
  { label: "Negative 20D · rising", x: -27, y: 25, color: "#54718b", anchor: "start" as const },
  { label: "Positive 20D · rising", x: 27, y: 25, color: "#438b82", anchor: "end" as const },
  { label: "Negative 20D · fading", x: -27, y: -25, color: "#ad6765", anchor: "start" as const },
  { label: "Positive 20D · fading", x: 27, y: -25, color: "#aa8750", anchor: "end" as const },
];

function scaleX(value: number): number {
  return PLOT.left + ((value - DOMAIN.xMin) / (DOMAIN.xMax - DOMAIN.xMin)) * PLOT.width;
}

function scaleY(value: number): number {
  return PLOT.top + (1 - (value - DOMAIN.yMin) / (DOMAIN.yMax - DOMAIN.yMin)) * PLOT.height;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function shortName(value: string): string {
  return value.length > 25 ? `${value.slice(0, 23)}…` : value;
}

function sectorToRotationGroup(sector: SectorData, taxonomyId: string): RotationGroupInput {
  return {
    id: sector.id,
    name: sector.name,
    taxonomyId,
    taxonomyKind: "SECTOR",
    constituents: sector.constituents,
    excess20d: sector.excess20d,
    excess60d: sector.excess60d,
    relativeStrength: sector.excessYtd,
    relativeMomentum: relativeMomentum(sector.excess20d, sector.excess60d),
    ytdExcess: sector.excessYtd,
    ytdStartDate: sector.ytdStartDate,
    ytdEligible: sector.ytdEligible,
    dataQuality: sector.dataQuality ?? (sector.excessYtd === null ? "READY_WITH_GAPS" : "READY"),
  };
}

function taxonomyToRotationGroup(group: TaxonomyGroupData): RotationGroupInput {
  return {
    id: group.id,
    name: group.name,
    taxonomyId: group.taxonomyId,
    taxonomyKind: group.taxonomyKind,
    taxonomyVersion: group.taxonomyVersion,
    prototype: group.prototype,
    constituents: group.constituents,
    excess20d: group.excess20d,
    excess60d: group.excess60d,
    relativeStrength: group.excessYtd,
    relativeMomentum: relativeMomentum(group.excess20d, group.excess60d),
    ytdExcess: group.excessYtd,
    ytdStartDate: group.ytdStartDate,
    ytdEligible: group.ytdEligible,
    dataQuality: group.dataQuality,
  };
}

function dataQualityLabel(row: RotationRow): string {
  return row.phase === "DATA_GAP" ? "DATA_GAP" : row.dataQuality;
}

function phaseColor(phase: RotationPhase): string {
  return QUADRANTS.find((quadrant) => quadrant.phase === phase)?.color ?? "#7c858c";
}

function openGroup(navigate: ReturnType<typeof useNavigate>, row: RotationGroupInput, mode: "groups" | "stocks"): void {
  if (mode === "stocks") {
    navigate(`/ticker/${encodeURIComponent(row.id)}`);
    return;
  }
  navigate(`/explorer?taxonomy=${row.taxonomyKind}&group=${encodeURIComponent(row.id)}`);
}

export default function RotationView() {
  const navigate = useNavigate();
  const { data } = useSnapshot();
  const [params, setParams] = useSearchParams();
  const urlTaxonomy = (params.get("taxonomy") ?? "SECTOR").toUpperCase() as TaxonomyKind;
  const taxonomyKind: TaxonomyKind = urlTaxonomy === "KONGLO" || urlTaxonomy === "THEMES" ? urlTaxonomy : "SECTOR";
  const search = params.get("q") ?? "";
  const mode = params.get("mode") === "stocks" ? "stocks" : "groups";
  const setTaxonomyKind = (k: TaxonomyKind) => {
    const next = new URLSearchParams(params);
    next.set("taxonomy", k);
    setParams(next, { replace: true });
  };
  const setSearch = (v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set("q", v); else next.delete("q");
    setParams(next, { replace: true });
  };
  const setMode = (m: "groups" | "stocks") => {
    const next = new URLSearchParams(params);
    next.set("mode", m);
    setParams(next, { replace: true });
  };
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [zoom, setZoom] = useState(1);
  const frameRef = useRef<HTMLDivElement>(null);

  const groups = useMemo<RotationGroupInput[]>(() => {
    if (!data) return [];
    if (mode === "stocks") {
      const seen = new Map<string, RotationGroupInput>();
      const pushTicker = (ticker: string, name: string, excess20d: number | null, excess60d: number | null, ytd: number | null) => {
        if (seen.has(ticker)) return;
        const mom = relativeMomentum(excess20d, excess60d);
        seen.set(ticker, {
          id: ticker, name: name || ticker, taxonomyId: "", taxonomyKind,
          constituents: 1, excess20d, excess60d,
          relativeStrength: ytd, relativeMomentum: mom,
          ytdExcess: ytd, ytdStartDate: null, ytdEligible: ytd !== null ? 1 : 0,
          dataQuality: ytd === null ? "READY_WITH_GAPS" : "READY",
        });
      };
      if (taxonomyKind === "SECTOR") {
        for (const [gid, list] of Object.entries(data.constituentsByGroup ?? {})) {
          void gid;
          for (const c of list) pushTicker(c.ticker, c.name, c.excess20d, c.excess60d, c.excessYtd);
        }
      } else {
        for (const [key, list] of Object.entries(data.constituentsByTaxonomyGroup ?? {})) {
          const g = data.taxonomyGroups[key];
          if (!g || g.taxonomyKind !== taxonomyKind) continue;
          for (const c of list) pushTicker(c.ticker, c.name, c.excess20d, c.excess60d, c.excessYtd);
        }
        if (seen.size === 0) {
          for (const g of Object.values(data.taxonomyGroups).filter((x) => x.taxonomyKind === taxonomyKind)) {
            for (const m of []) pushTicker((m as { ticker: string }).ticker, "", null, null, null);
            void g;
          }
        }
      }
      return [...seen.values()].sort((a, b) => a.id.localeCompare(b.id));
    }
    if (taxonomyKind === "SECTOR") {
      return data.sectors.map((sector) => sectorToRotationGroup(sector, data.activeTaxonomyId ?? "sector"));
    }
    return Object.values(data.taxonomyGroups)
      .filter((group) => group.taxonomyKind === taxonomyKind)
      .map(taxonomyToRotationGroup)
      .sort((left, right) => right.constituents - left.constituents || left.id.localeCompare(right.id));
  }, [data, taxonomyKind, mode]);

  const rows = useMemo<RotationRow[]>(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return groups
      .filter((group) => !normalizedSearch || group.name.toLowerCase().includes(normalizedSearch) || group.id.toLowerCase().includes(normalizedSearch))
      .map(withRotationPhase);
  }, [groups, search]);

  const plottable = rows.filter((row) => row.phase !== "DATA_GAP" && row.relativeStrength !== null && row.relativeMomentum !== null);
  // The current persisted snapshot may not yet contain the prior-year
  // baseline needed for YTD strength. Keep the rotation contract honest, but
  // avoid an empty hero: use the available 20D/60D values as a clearly marked
  // diagnostic view until the YTD baseline is persisted.
  const diagnosticPlottable = rows.filter((row) => row.excess20d !== null && row.relativeMomentum !== null);
  const isDiagnostic = plottable.length === 0 && diagnosticPlottable.length > 0;
  const basePlotted = isDiagnostic ? diagnosticPlottable : plottable;
  const plottedRows = basePlotted.filter((r) => !hidden.has(isDiagnostic ? `diag-${r.id}` : r.phase));
  const togglePhase = (key: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };
  const labelPositions = useMemo(() => {
    const candidates = plottedRows.map((row) => {
      const xValue = isDiagnostic ? row.excess20d : row.relativeStrength;
      return {
      id: row.id,
      text: shortName(row.name),
      x: clamp(scaleX(xValue ?? 0), PLOT_BOUNDS.left, PLOT_BOUNDS.right),
      y: clamp(scaleY(row.relativeMomentum ?? 0), PLOT_BOUNDS.top, PLOT_BOUNDS.bottom),
      radius: 7 + Math.sqrt(Math.max(1, row.constituents)) / 3,
      priority: Math.abs(xValue ?? 0) + Math.abs(row.relativeMomentum ?? 0) + row.constituents / 10,
      };
    });
    return placeMapLabels(candidates, PLOT_BOUNDS, Math.min(candidates.length, 10));
  }, [isDiagnostic, plottedRows]);

  if (!data) return null;
  const snapshotAsOf = formatDateLabel(data.payload.as_of);
  const comparable = data.payload.comparability?.status === "COMPATIBLE";
  const currentTaxonomyLabel = TAXONOMY_OPTIONS.find((option) => option.kind === taxonomyKind)?.label ?? "Sector";

  return (
    <section className="content-shell rotation-page" style={{ padding: "31px var(--page-gutter) 70px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 20, flexWrap: "wrap", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div className="eyebrow-muted" style={{ color: "#438b82" }}>Rotation mapping</div>
            <EvidenceBadge kind={taxonomyKind === "SECTOR" ? "SNAPSHOT" : "PROTOTYPE"} compact />
            {isDiagnostic && (
              <span style={{ border: "1px solid #d5c59d", borderRadius: 20, padding: "4px 9px", color: "#7a5010", fontFamily: "Geist Mono, monospace", fontSize: 10 }}>
                YTD unavailable · diagnostic view
              </span>
            )}
          </div>
          <h1 style={{ margin: "7px 0 8px", fontSize: 31, letterSpacing: "-.045em", fontWeight: 500 }}>Market rotation</h1>
          <p style={{ maxWidth: 760, margin: 0, color: "#686e73", lineHeight: 1.55 }}>
            YTD-strength rotation lens. For the 20D excess × breadth-change lens see What Changed.
          </p>
          <p style={{ maxWidth: 760, margin: "6px 0 0", color: "#686e73", lineHeight: 1.55 }}>
            {isDiagnostic
              ? "The YTD baseline is unavailable in this snapshot. The map below shows available 20D excess return and 20D minus 60D momentum as diagnostics only; no rotation phase is assigned."
              : "Relative strength uses YTD excess return versus IHSG. Relative momentum is 20D excess return minus 60D excess return. Null values remain visible as Not available and are not plotted."}
          </p>
        </div>
        <div style={{ color: "#686e73", fontFamily: "Geist Mono, monospace", fontSize: 11, textAlign: "right" }}>
          <div>Snapshot as of {snapshotAsOf}</div>
          <div style={{ marginTop: 5 }}>{currentTaxonomyLabel} · {mode} · {formatCountLabel(plottedRows.length, "plotted")} of {formatCountLabel(rows.length, mode === "stocks" ? "ticker" : "group")}</div>
        </div>
      </header>

      <div className="rotation-toolbar" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <div role="group" aria-label="Rotation taxonomy" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {TAXONOMY_OPTIONS.map((option) => {
            const active = option.kind === taxonomyKind;
            const available = option.kind === "SECTOR" || Object.values(data.taxonomyGroups).some((group) => group.taxonomyKind === option.kind);
            return (
              <button
                type="button"
                key={option.kind}
                disabled={!available}
                aria-pressed={active}
                onClick={() => setTaxonomyKind(option.kind)}
                style={{ border: `1px solid ${active ? "#438b82" : "#dfe2e1"}`, background: active ? "#e8f3f0" : "#fff", color: available ? "#202325" : "#a3a7a5", padding: "6px 11px", cursor: available ? "pointer" : "not-allowed", fontSize: 11 }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        <div role="group" aria-label="Rotation mode" style={{ display: "flex", gap: 6 }}>
          <button type="button" aria-pressed={mode === "groups"} onClick={() => setMode("groups")} style={{ border: `1px solid ${mode === "groups" ? "#438b82" : "#dfe2e1"}`, background: mode === "groups" ? "#e8f3f0" : "#fff", padding: "6px 11px", fontSize: 11, cursor: "pointer" }}>Groups</button>
          <button type="button" aria-pressed={mode === "stocks"} onClick={() => setMode("stocks")} style={{ border: `1px solid ${mode === "stocks" ? "#438b82" : "#dfe2e1"}`, background: mode === "stocks" ? "#e8f3f0" : "#fff", padding: "6px 11px", fontSize: 11, cursor: "pointer" }}>Stocks</button>
        </div>
        <input
          type="search"
          aria-label="Search rotation groups"
          placeholder={mode === "stocks" ? "Search ticker…" : "Search group…"}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          style={{ marginLeft: "auto", minWidth: 220, border: "1px solid #dfe2e1", padding: "7px 10px", fontSize: 12 }}
        />
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12, fontSize: 11 }}>
        <span className="eyebrow-muted">Show:</span>
        {(isDiagnostic ? ["visible"] : ["LEADING", "IMPROVING", "WEAKENING", "LAGGING", "DATA_GAP"]).map((p) => {
          const key = isDiagnostic ? `diag-all` : p;
          const isHidden = hidden.has(p) || (isDiagnostic && hidden.has(`diag-${p}`));
          void key;
          if (isDiagnostic) return null;
          return (
            <label key={p} style={{ display: "inline-flex", gap: 4, alignItems: "center", border: "1px solid #dfe2e1", padding: "4px 8px", cursor: "pointer" }}>
              <input type="checkbox" checked={!isHidden} onChange={() => togglePhase(p)} aria-label={`Toggle ${p}`} />
              {p === "DATA_GAP" ? "Not available" : p.charAt(0) + p.slice(1).toLowerCase()}
            </label>
          );
        })}
        <span style={{ marginLeft: "auto", display: "inline-flex", gap: 6 }}>
          <button type="button" onClick={() => setZoom((z) => Math.min(3, +(z + 0.5).toFixed(2)))} aria-label="Zoom in" style={{ border: "1px solid #dfe2e1", background: "#fff", padding: "4px 10px", cursor: "pointer" }}>+</button>
          <button type="button" onClick={() => setZoom(1)} aria-label="Reset zoom" style={{ border: "1px solid #dfe2e1", background: "#fff", padding: "4px 10px", cursor: "pointer" }}>Reset</button>
          <button type="button" onClick={() => frameRef.current?.requestFullscreen?.()} aria-label="Fullscreen rotation map" style={{ border: "1px solid #dfe2e1", background: "#fff", padding: "4px 10px", cursor: "pointer" }}>Fullscreen</button>
        </span>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12, fontSize: 11, color: "#686e73" }}>
        <span className="eyebrow-muted">History:</span>
        <button type="button" disabled title="Daily intervals require dated observation series with consistent snapshot/provider/price-basis/membership versions — not persisted in this bundle" style={{ border: "1px solid #dfe2e1", padding: "4px 10px", opacity: 0.5, cursor: "not-allowed" }}>Daily</button>
        <button type="button" disabled title="Weekly sampling does not change the return formula into a weekly formula; weekly series not persisted in this bundle" style={{ border: "1px solid #dfe2e1", padding: "4px 10px", opacity: 0.5, cursor: "not-allowed" }}>Weekly</button>
        <label style={{ display: "inline-flex", gap: 6, alignItems: "center", opacity: 0.6 }} title="Tails require real dated trails; trails are not drawn from repeated points, random coordinates, or forced phases">
          Tail <input type="range" disabled value={0} aria-label="Rotation tail length (unavailable)" />
        </label>
        <span>Plotted {plottedRows.length} of {rows.length} {mode === "stocks" ? "tickers" : "groups"} · table and plot share the same data, method, and period.</span>
      </div>

      <div className="rotation-note" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", padding: "9px 12px", border: "1px solid #dfe2e1", background: "#faf9f6", color: "#686e73", fontSize: 11, marginBottom: 12 }}>
        <strong style={{ color: "#202325" }}>{isDiagnostic ? "YTD signal" : "Current phase"}</strong>
        <span>{isDiagnostic
          ? `Baseline unavailable; ${formatCountLabel(diagnosticPlottable.length, mode === "stocks" ? "ticker" : "group")} remain visible in the diagnostic map and table.`
          : comparable ? "Comparable prior exists; this view still shows the current rotation classification." : "No compatible prior snapshot; no historical phase trail is shown."}</span>
        {taxonomyKind !== "SECTOR" && <span style={{ color: "#315d87" }}>Analyst-defined taxonomy</span>}
      </div>

      <div ref={frameRef} className="rotation-map-frame" style={{ border: "1px solid #dfe2e1", background: "#fff", overflow: "hidden" }}>
        <svg viewBox={(() => { const w = 1000 / zoom; const h = 450 / zoom; return `${(1000 - w) / 2} ${(450 - h) / 2} ${w} ${h}`; })()} role="img" aria-label={isDiagnostic ? "Market rotation diagnostic map" : "Market rotation map"} style={{ display: "block", width: "100%", height: "auto" }}>
          <rect x={PLOT.left} y={PLOT.top} width={PLOT.width / 2} height={PLOT.height / 2} fill="#edf3f7" />
          <rect x={PLOT.left + PLOT.width / 2} y={PLOT.top} width={PLOT.width / 2} height={PLOT.height / 2} fill="#e8f3f0" />
          <rect x={PLOT.left} y={PLOT.top + PLOT.height / 2} width={PLOT.width / 2} height={PLOT.height / 2} fill="#f8eaea" />
          <rect x={PLOT.left + PLOT.width / 2} y={PLOT.top + PLOT.height / 2} width={PLOT.width / 2} height={PLOT.height / 2} fill="#f8f0df" />
          {Array.from({ length: 13 }, (_, index) => {
            const x = PLOT.left + (index / 12) * PLOT.width;
            return <line key={`v-${index}`} x1={x} x2={x} y1={PLOT.top} y2={PLOT.top + PLOT.height} stroke="#dfe5e3" strokeWidth=".75" />;
          })}
          {Array.from({ length: 7 }, (_, index) => {
            const y = PLOT.top + (index / 6) * PLOT.height;
            return <line key={`h-${index}`} x1={PLOT.left} x2={PLOT.left + PLOT.width} y1={y} y2={y} stroke="#dfe5e3" strokeWidth=".75" />;
          })}
          <line x1={scaleX(0)} x2={scaleX(0)} y1={PLOT.top} y2={PLOT.top + PLOT.height} stroke="#9ca9a7" strokeWidth="1.25" />
          <line x1={PLOT.left} x2={PLOT.left + PLOT.width} y1={scaleY(0)} y2={scaleY(0)} stroke="#9ca9a7" strokeWidth="1.25" />
          {(isDiagnostic ? DIAGNOSTIC_QUADRANTS : QUADRANTS).map((quadrant) => (
            <text key={"phase" in quadrant ? quadrant.phase : quadrant.label} x={scaleX(quadrant.x)} y={scaleY(quadrant.y)} textAnchor={quadrant.anchor} fontFamily="Geist Mono, monospace" fontSize="11" fill={quadrant.color} opacity=".8">
              {"phase" in quadrant ? formatEnumLabel(quadrant.phase) : quadrant.label}
            </text>
          ))}
          <text x={PLOT.left} y={PLOT.top + PLOT.height + 18} textAnchor="start" fontFamily="Geist Mono, monospace" fontSize="10" fill="#7c858c">−30%</text>
          <text x={scaleX(0)} y={PLOT.top + PLOT.height + 18} textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="10" fill="#7c858c">0%</text>
          <text x={PLOT.left + PLOT.width} y={PLOT.top + PLOT.height + 18} textAnchor="end" fontFamily="Geist Mono, monospace" fontSize="10" fill="#7c858c">+30%</text>
          <text x={PLOT.left - 10} y={PLOT.top + 4} textAnchor="end" fontFamily="Geist Mono, monospace" fontSize="10" fill="#7c858c">+30%</text>
          <text x={PLOT.left - 10} y={scaleY(0) + 4} textAnchor="end" fontFamily="Geist Mono, monospace" fontSize="10" fill="#7c858c">0%</text>
          <text x={PLOT.left - 10} y={PLOT.top + PLOT.height} textAnchor="end" fontFamily="Geist Mono, monospace" fontSize="10" fill="#7c858c">−30%</text>
          {plottedRows.map((row) => {
            const xValue = isDiagnostic ? row.excess20d : row.relativeStrength;
            const x = clamp(scaleX(xValue ?? 0), PLOT.left, PLOT.left + PLOT.width);
            const y = clamp(scaleY(row.relativeMomentum ?? 0), PLOT.top, PLOT.top + PLOT.height);
            const radius = Math.max(8, Math.min(22, 5 + Math.sqrt(Math.max(1, row.constituents)) * 2));
            const color = isDiagnostic ? "#7c858c" : phaseColor(row.phase);
            return (
              <g
                key={row.id}
                role="button"
                tabIndex={0}
                aria-label={isDiagnostic
                  ? `${row.name}: YTD not available, diagnostic 20D excess ${formatPercent(row.excess20d)} and momentum ${formatPercent(row.relativeMomentum)}`
                  : `${row.name}: ${formatEnumLabel(row.phase)}, ${formatPercent(row.relativeStrength)} relative strength, ${formatPercent(row.relativeMomentum)} relative momentum`}
                onClick={() => openGroup(navigate, row, mode)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openGroup(navigate, row, mode);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                <title>{isDiagnostic ? `${row.name}: YTD not available · diagnostic view` : `${row.name}: ${formatEnumLabel(row.phase)}`}</title>
                <circle cx={x} cy={y} r={radius} fill={color} opacity=".9" stroke="#fff" strokeWidth="1.5" />
                <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontFamily="Geist Mono, monospace" fontSize="10" fill="#fff" pointerEvents="none">{row.constituents}</text>
              </g>
            );
          })}
          {labelPositions.map((label) => (
            <g key={`label-${label.id}`} pointerEvents="none">
              {label.targetX !== undefined && label.targetY !== undefined && Math.hypot(label.x - label.targetX, label.y - label.targetY) > 16 && (
                <line x1={label.targetX} y1={label.targetY} x2={label.x} y2={label.y - 3} stroke="#9aa19f" strokeWidth=".8" />
              )}
              <text x={label.x} y={label.y} textAnchor={label.textAnchor} fontFamily="Geist Mono, monospace" fontSize="10" fill="#202325">{label.text}</text>
            </g>
          ))}
          <text x={PLOT.left + PLOT.width / 2} y="438" textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="10" fill="#686e73">{isDiagnostic ? "20D excess return vs IHSG (%) · diagnostic" : "YTD excess return vs IHSG (%)"}</text>
          <text x="18" y={PLOT.top + PLOT.height / 2} textAnchor="middle" transform={`rotate(-90 18 ${PLOT.top + PLOT.height / 2})`} fontFamily="Geist Mono, monospace" fontSize="10" fill="#686e73">20D excess − 60D excess (%)</text>
        </svg>
      </div>

      {isDiagnostic ? (
        <div
          className="rotation-diagnostic-callout"
          role="status"
          style={{ marginTop: 12, padding: "13px 15px", border: "1px solid #d5c59d", background: "#fffaf0", color: "#686e73" }}
        >
          <div className="eyebrow-muted" style={{ color: "#7a5010" }}>Diagnostic availability</div>
          <strong style={{ display: "block", marginTop: 5, color: "#202325", fontSize: 15 }}>YTD rotation is unavailable for this snapshot.</strong>
          <div style={{ marginTop: 5, fontSize: 12, lineHeight: 1.5 }}>
            {formatCountLabel(diagnosticPlottable.length, "group")} are shown above using available 20D excess and momentum. The phase cards and rotation signal remain unavailable until the prior-year baseline is persisted.
          </div>
        </div>
      ) : (
        <div className="rotation-summary-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 10, marginTop: 12 }}>
          {QUADRANTS.map((quadrant) => {
            const count = plottedRows.filter((row) => row.phase === quadrant.phase).length;
            return (
            <div key={quadrant.phase} style={{ padding: "11px 13px", border: `1px solid ${quadrant.color}44`, background: quadrant.fill, minWidth: 0 }}>
              <div style={{ color: quadrant.color, fontSize: 11, fontWeight: 600 }}>{formatEnumLabel(quadrant.phase)}</div>
              <strong style={{ display: "block", marginTop: 6, fontSize: 21 }}>{count}</strong>
              <div style={{ color: "#686e73", fontSize: 10 }}>{formatCountLabel(count, mode === "stocks" ? "ticker" : "group")}</div>
            </div>
            );
          })}
        </div>
      )}

      <section style={{ marginTop: 22 }} aria-labelledby="rotation-table-title">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", flexWrap: "wrap", marginBottom: 9 }}>
          <h2 id="rotation-table-title" style={{ margin: 0, fontSize: 18, fontWeight: 500 }}>Rotation table</h2>
          <span style={{ color: "#686e73", fontSize: 11 }}>Click a {mode === "stocks" ? "ticker" : "group"} to open its detail · {formatCountLabel(plottedRows.length, "plotted")} of {formatCountLabel(rows.length, "total")}</span>
        </div>
        <div className="table-scroll" style={{ border: "1px solid #dfe2e1" }}>
          <table style={{ width: "100%", minWidth: 920, borderCollapse: "collapse" }} aria-label="Rotation mapping table">
            <thead>
              <tr style={{ background: "#faf9f6", borderBottom: "1px solid #dfe2e1", textAlign: "left" }}>
                {[
                  "Group",
                  "Quadrant",
                  "Relative strength (%)",
                  "Relative momentum (%)",
                  "Phase",
                  "YTD excess (%)",
                  "Data quality",
                ].map((heading) => <th key={heading} style={{ padding: "9px 10px", fontFamily: "Geist Mono, monospace", fontSize: 10, color: "#686e73", whiteSpace: "nowrap" }}>{heading}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`table-${row.id}`} style={{ borderBottom: "1px solid #ececec", background: row.phase === "DATA_GAP" ? "#fafaf8" : "#fff" }}>
                  <td style={{ padding: "9px 10px", fontSize: 12, fontWeight: 600, whiteSpace: "nowrap" }}>
                    <button type="button" onClick={() => openGroup(navigate, row, mode)} style={{ border: 0, borderBottom: "1px dotted #9aa19f", background: "none", padding: 0, color: "#202325", cursor: "pointer", fontWeight: 600 }}>{row.name}</button>
                  </td>
                  <td style={{ padding: "9px 10px", fontFamily: "Geist Mono, monospace", fontSize: 11 }}>{formatEnumLabel(row.phase)}</td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 11, color: phaseColor(row.phase) }}>{formatPercent(row.relativeStrength)}</td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 11, color: phaseColor(row.phase) }}>{formatPercent(row.relativeMomentum)}</td>
                  <td style={{ padding: "9px 10px", fontSize: 11 }}>{formatEnumLabel(row.phase)}</td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 11, color: phaseColor(row.phase) }}>{formatPercent(row.ytdExcess)}</td>
                  <td style={{ padding: "9px 10px", fontSize: 11, color: row.phase === "DATA_GAP" ? "#7a5010" : "#686e73" }}>{formatEnumLabel(dataQualityLabel(row))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="rotation-accessible-list" style={{ marginTop: 18, display: "grid", gap: 7 }} aria-label={`${currentTaxonomyLabel} rotation groups`}>
        <div className="eyebrow-muted">Accessible group list</div>
        {rows.map((row) => (
          <button key={`list-${row.id}`} type="button" onClick={() => openGroup(navigate, row, mode)} style={{ display: "flex", justifyContent: "space-between", gap: 12, minWidth: 0, padding: "8px 10px", border: "1px solid #dfe2e1", background: row.phase === "DATA_GAP" ? "#f4f4f1" : "#fff", color: "#202325", textAlign: "left", cursor: "pointer" }}>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12 }}>{row.name}</span>
            <span style={{ flexShrink: 0, fontFamily: "Geist Mono, monospace", fontSize: 10, color: phaseColor(row.phase) }}>{formatEnumLabel(row.phase)} · {formatCountLabel(row.constituents, "ticker")}</span>
          </button>
        ))}
      </div>

      <footer style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 14, color: "#686e73", fontFamily: "Geist Mono, monospace", fontSize: 10 }}>
        <span>Bubble size ∝ √(constituents)</span>
        <span>·</span>
        <span>Groups with incomplete coverage remain in the table and list</span>
        <span>·</span>
        <span>{isDiagnostic ? "Diagnostic fallback: persisted 20D/60D values only" : "YTD baseline: last trading session of prior year"}</span>
      </footer>
    </section>
  );
}
