import { useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { EvidenceBadge } from "./EvidenceModel";
import { useSnapshot } from "../data/SnapshotProvider";
import { useWorkspaceAsset } from "../data/marketWorkspace";
import { replaySelection, type RotationReplay } from "../data/rotationReplay";
import type { SectorData, TaxonomyGroupData } from "../data/adapter";
import type { TaxonomyKind } from "../data/snapshot";
import { formatCountLabel, formatDateLabel, formatEnumLabel, formatPercent } from "../data/format";
import { placeMapLabels } from "../data/mapLabels";
import {
  buildRotationTrail,
  classifyRotation,
  relativeMomentum,
  sampleRotationHistory,
  withRotationPhase,
  MIN_ROTATION_TRAIL_POINTS,
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
  { phase: "IMPROVING", x: -27, y: 25, color: "var(--color-leading)", fill: "var(--quad-improving)", anchor: "start" },
  { phase: "LEADING", x: 27, y: 25, color: "var(--color-improving)", fill: "var(--quad-leading)", anchor: "end" },
  { phase: "LAGGING", x: -27, y: -25, color: "var(--color-weakening)", fill: "var(--quad-lagging)", anchor: "start" },
  { phase: "WEAKENING", x: 27, y: -25, color: "var(--color-warning)", fill: "var(--quad-weakening)", anchor: "end" },
];

const DIAGNOSTIC_QUADRANTS = [
  { label: "Negative 20D · rising", x: -27, y: 25, color: "var(--color-leading)", anchor: "start" as const },
  { label: "Positive 20D · rising", x: 27, y: 25, color: "var(--color-improving)", anchor: "end" as const },
  { label: "Negative 20D · fading", x: -27, y: -25, color: "var(--color-weakening)", anchor: "start" as const },
  { label: "Positive 20D · fading", x: 27, y: -25, color: "var(--color-warning)", anchor: "end" as const },
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
  return QUADRANTS.find((quadrant) => quadrant.phase === phase)?.color ?? "var(--muted)";
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
  const { data, snapshotId } = useSnapshot();
  const rotationAsset = useWorkspaceAsset<RotationReplay>("rotation");
  const [params, setParams] = useSearchParams();
  const urlTaxonomy = (params.get("taxonomy") ?? "SECTOR").toUpperCase() as TaxonomyKind;
  const taxonomyKind: TaxonomyKind = urlTaxonomy === "KONGLO" || urlTaxonomy === "THEMES" ? urlTaxonomy : "SECTOR";
  const search = params.get("q") ?? "";
  const mode = params.get("mode") === "stocks" ? "stocks" : "groups";
  const interval = params.get("interval") === "daily" ? "daily" : "weekly";
  const setInterval = (value: "daily" | "weekly") => {
    const next = new URLSearchParams(params);
    next.set("interval", value);
    setParams(next, { replace: true });
  };
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
  const [tailLength, setTailLength] = useState(0);
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
  // Diagnostic mode has no rotation phases to toggle, so visibility is grouped
  // by the same per-row data-quality value the table already shows. Derived
  // from the plotted rows themselves, so the controls never disappear when a
  // bucket is fully hidden.
  const diagnosticKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const row of basePlotted) keys.add(dataQualityLabel(row));
    return [...keys].sort();
  }, [basePlotted]);
  const plottedRows = basePlotted.filter((r) => !hidden.has(isDiagnostic ? `diag-${dataQualityLabel(r)}` : r.phase));
  const togglePhase = (key: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  // Daily replay is separate from the canonical comparison snapshots. Cadence
  // is available only with complete benchmark sessions for every plotted group.
  const dailyHistoryByGroup = useMemo(() => {
    const out = new Map<string, NonNullable<typeof data>["rotationHistory"]>();
    if (!data || isDiagnostic || mode !== "groups" || taxonomyKind !== "SECTOR") return out;
    for (const point of data.rotationDailyHistory?.points ?? []) {
      const list = out.get(point.group_id) ?? [];
      list.push(point);
      out.set(point.group_id, list);
    }
    return out;
  }, [data, isDiagnostic, mode, taxonomyKind]);
  const sessions = data?.rotationDailyHistory?.sessions ?? [];
  const replay = !isDiagnostic && mode === "groups" ? rotationAsset.data : null;
  const selections = useMemo(() => {
    const out = new Map<string, { daily: ReturnType<typeof replaySelection>; weekly: ReturnType<typeof replaySelection> }>();
    if (replay) for (const row of plottedRows) out.set(row.id, {
      daily: replaySelection(replay, taxonomyKind, row.id, "daily", row),
      weekly: replaySelection(replay, taxonomyKind, row.id, "weekly", row),
    });
    return out;
  }, [replay, taxonomyKind, plottedRows]);
  const dailyAvailable = replay ? [...selections.values()].some(s => s.daily.points.length > 0)
    : plottable.some(row => sampleRotationHistory(dailyHistoryByGroup.get(row.id) ?? [], sessions, "daily").length > 0);
  const weeklyAvailable = replay ? [...selections.values()].some(s => s.weekly.points.length > 0)
    : plottable.some(row => sampleRotationHistory(dailyHistoryByGroup.get(row.id) ?? [], sessions, "weekly").length > 0);
  const effectiveInterval = dailyAvailable ? (interval === "daily" || !weeklyAvailable ? "daily" : "weekly") : null;

  // Older bundles retain their real dated tails; no cadence is inferred from
  // sparse snapshots. Analyst taxonomies and stocks have no comparable series.
  const historyByGroup = useMemo(() => {
    const out = new Map<string, Array<{ as_of: string; group_excess_return_ytd: number; relative_momentum: number | null }>>();
    if (replay) {
      if (effectiveInterval) for (const [id, selection] of selections) out.set(id, selection[effectiveInterval].points);
      return out;
    }
    if (!data || isDiagnostic || mode !== "groups" || taxonomyKind !== "SECTOR") return out;
    if (effectiveInterval) {
      for (const [groupId, history] of dailyHistoryByGroup) {
        out.set(groupId, sampleRotationHistory(history, data.rotationDailyHistory?.sessions ?? [], effectiveInterval));
      }
      return out;
    }
    for (const point of data.rotationHistory ?? []) {
      const list = out.get(point.group_id) ?? [];
      list.push(point);
      out.set(point.group_id, list);
    }
    return out;
  }, [data, isDiagnostic, mode, taxonomyKind, dailyHistoryByGroup, effectiveInterval, replay, selections]);
  const maxTrailLength = useMemo(() => {
    let max = 0;
    for (const list of historyByGroup.values()) {
      max = Math.max(max, list.length - 1);
    }
    return Math.min(max, 20);
  }, [historyByGroup]);
  const tailAvailable = !isDiagnostic && mode === "groups" && maxTrailLength >= MIN_ROTATION_TRAIL_POINTS - 1;
  const effectiveTailLength = tailAvailable ? Math.min(tailLength, maxTrailLength) : 0;
  const trails = useMemo(() => {
    if (!tailAvailable || effectiveTailLength <= 0) return [];
    return plottedRows
      .map((row) => {
        const history = historyByGroup.get(row.id);
        if (!history) return null;
        const points = buildRotationTrail(history, effectiveTailLength);
        if (points.length < 2) return null;
        return { id: row.id, name: row.name, phase: row.phase, points };
      })
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null);
  }, [historyByGroup, plottedRows, tailAvailable, effectiveTailLength]);
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
  const historyDatesLabel = useMemo(() => {
    const dates = new Set<string>();
    for (const list of historyByGroup.values()) {
      for (const point of list.slice(-(effectiveTailLength + 1))) dates.add(point.as_of);
    }
    const ordered = [...dates].sort();
    return ordered.length > 6
      ? `${formatDateLabel(ordered[0])} – ${formatDateLabel(ordered[ordered.length - 1])}`
      : ordered.join(", ");
  }, [historyByGroup, effectiveTailLength]);

  if (!data) return null;
  const snapshotAsOf = formatDateLabel(data.payload.as_of);
  const currentTaxonomyLabel = TAXONOMY_OPTIONS.find((option) => option.kind === taxonomyKind)?.label ?? "Sector";

  return (
    <section className="content-shell rotation-page" style={{ padding: "31px var(--page-gutter) 70px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 20, flexWrap: "wrap", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div className="eyebrow-muted" style={{ color: "var(--color-improving)" }}>Rotation mapping</div>
            <EvidenceBadge kind={taxonomyKind === "SECTOR" ? "SNAPSHOT" : "PROTOTYPE"} compact />
            {isDiagnostic && (
              <span style={{ border: "1px solid #d5c59d", borderRadius: 20, padding: "4px 9px", color: "var(--accent-ink)", fontFamily: "Geist Mono, monospace", fontSize: 10 }}>
                YTD unavailable · diagnostic view
              </span>
            )}
          </div>
          <h1 style={{ margin: "7px 0 8px", fontSize: 31, letterSpacing: "-.045em", fontWeight: 500 }}>Market rotation</h1>
          <p style={{ maxWidth: 760, margin: 0, color: "var(--muted)", lineHeight: 1.55 }}>
            YTD-strength rotation lens. For the 20D excess × breadth-change lens see What Changed.
          </p>
          <p style={{ maxWidth: 760, margin: "6px 0 0", color: "var(--muted)", lineHeight: 1.55 }}>
            {isDiagnostic
              ? "The YTD baseline is unavailable in this snapshot. The map below shows available 20D excess return and 20D minus 60D momentum as diagnostics only; no rotation phase is assigned."
              : "Relative strength uses YTD excess return versus IHSG. Relative momentum is 20D excess return minus 60D excess return. Null values remain visible as Not available and are not plotted."}
          </p>
        </div>
        <div style={{ color: "var(--muted)", fontFamily: "Geist Mono, monospace", fontSize: 11, textAlign: "right" }}>
          <div>Snapshot as of {snapshotAsOf}</div>
          <div style={{ marginTop: 5 }}>{currentTaxonomyLabel} · {mode} · {plottedRows.length} of {rows.length} {mode === "stocks" ? "tickers" : "groups"} plotted</div>
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
                style={{ border: `1px solid ${active ? "var(--color-improving)" : "var(--line)"}`, background: active ? "var(--surface-subtle)" : "var(--surface)", color: available ? "var(--ink)" : "#a3a7a5", padding: "6px 11px", cursor: available ? "pointer" : "not-allowed", fontSize: 11 }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        <div role="group" aria-label="Rotation mode" style={{ display: "flex", gap: 6 }}>
          <button type="button" aria-pressed={mode === "groups"} onClick={() => setMode("groups")} style={{ border: `1px solid ${mode === "groups" ? "var(--color-improving)" : "var(--line)"}`, background: mode === "groups" ? "var(--surface-subtle)" : "var(--surface)", padding: "6px 11px", fontSize: 11, cursor: "pointer" }}>Groups</button>
          <button type="button" aria-pressed={mode === "stocks"} onClick={() => setMode("stocks")} style={{ border: `1px solid ${mode === "stocks" ? "var(--color-improving)" : "var(--line)"}`, background: mode === "stocks" ? "var(--surface-subtle)" : "var(--surface)", padding: "6px 11px", fontSize: 11, cursor: "pointer" }}>Stocks</button>
        </div>
        <input
          type="search"
          aria-label="Search rotation groups"
          placeholder={mode === "stocks" ? "Search ticker…" : "Search group…"}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          style={{ marginLeft: "auto", minWidth: 220, border: "1px solid var(--line)", padding: "7px 10px", fontSize: 12 }}
        />
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12, fontSize: 11 }}>
        <span className="eyebrow-muted">Show:</span>
        {(isDiagnostic ? diagnosticKeys : ["LEADING", "IMPROVING", "WEAKENING", "LAGGING", "DATA_GAP"]).map((p) => {
          const key = isDiagnostic ? `diag-${p}` : p;
          const isHidden = hidden.has(key);
          return (
            <label key={p} style={{ display: "inline-flex", gap: 4, alignItems: "center", border: "1px solid var(--line)", padding: "4px 8px", cursor: "pointer" }}>
              <input type="checkbox" checked={!isHidden} onChange={() => togglePhase(key)} aria-label={`Toggle ${isDiagnostic ? formatEnumLabel(p) : p}`} />
              {isDiagnostic
                ? formatEnumLabel(p)
                : p === "DATA_GAP" ? "Not available" : p.charAt(0) + p.slice(1).toLowerCase()}
            </label>
          );
        })}
        <span style={{ marginLeft: "auto", display: "inline-flex", gap: 6 }}>
          <button type="button" onClick={() => setZoom((z) => Math.min(3, +(z + 0.5).toFixed(2)))} aria-label="Zoom in" style={{ border: "1px solid var(--line)", background: "var(--surface)", padding: "4px 10px", cursor: "pointer" }}>+</button>
          <button type="button" onClick={() => setZoom(1)} aria-label="Reset zoom" style={{ border: "1px solid var(--line)", background: "var(--surface)", padding: "4px 10px", cursor: "pointer" }}>Reset</button>
          <button type="button" onClick={() => frameRef.current?.requestFullscreen?.()} aria-label="Fullscreen rotation map" style={{ border: "1px solid var(--line)", background: "var(--surface)", padding: "4px 10px", cursor: "pointer" }}>Fullscreen</button>
        </span>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12, fontSize: 11, color: "var(--muted)" }}>
        <span className="eyebrow-muted">History:</span>
        {(["daily", "weekly"] as const).map((cadence) => {
          const available = cadence === "daily" ? dailyAvailable : weeklyAvailable;
          const selected = effectiveInterval === cadence;
          return (
            <button key={cadence} type="button" disabled={!available} aria-pressed={selected}
              onClick={() => setInterval(cadence)}
              title={available
                ? cadence === "daily" ? "Every persisted trading session; YTD strength and 20D − 60D momentum are unchanged"
                  : "Last persisted session each week, including the current partial week; return formulas are unchanged"
                : "Requires complete comparable daily observations for this selection (at least three points per trail)"}
              style={{ border: "1px solid var(--line)", padding: "4px 10px", opacity: available ? 1 : 0.5,
                cursor: available ? "pointer" : "not-allowed", background: selected ? "var(--surface-subtle)" : "var(--surface)",
                color: selected ? "var(--ink)" : "var(--muted)", fontWeight: selected ? 600 : 400 }}>
              {cadence === "daily" ? "Daily" : "Weekly"}
            </button>
          );
        })}
        <label
          style={{ display: "inline-flex", gap: 6, alignItems: "center", opacity: tailAvailable ? 1 : 0.6 }}
          title={tailAvailable
            ? `Trail through up to ${maxTrailLength} real dated observations per group (oldest to newest)`
            : `Trails require at least ${MIN_ROTATION_TRAIL_POINTS} real dated observations per group from comparable snapshots — not available for this selection`}
        >
          Tail{" "}
          <input
            type="range"
            min={0}
            max={Math.max(1, maxTrailLength)}
            step={1}
            disabled={!tailAvailable}
            value={effectiveTailLength}
            onChange={(event) => setTailLength(Number(event.target.value))}
            aria-label={tailAvailable ? "Rotation trail length in dated observations" : "Rotation trail length (unavailable)"}
            aria-valuetext={tailAvailable ? `${effectiveTailLength} dated observations` : "unavailable"}
          />
          {tailAvailable && (
            <span className="tabnum" style={{ color: "var(--muted)", fontFamily: "Geist Mono, monospace", fontSize: 11 }}>
              {effectiveTailLength === 0 ? "off" : `${effectiveTailLength} obs`}
            </span>
          )}
        </label>
        <span>Plotted {plottedRows.length} of {rows.length} {mode === "stocks" ? "tickers" : "groups"} · table and plot share the same data, method, and period.</span>
      </div>

      <div className="rotation-note" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", padding: "9px 12px", border: "1px solid var(--line)", background: "var(--surface-subtle)", color: "var(--muted)", fontSize: 11, marginBottom: 12 }}>
        <strong style={{ color: "var(--ink)" }}>{isDiagnostic ? "YTD signal" : "Current phase"}</strong>
        <span>{isDiagnostic
          ? `Baseline unavailable; ${formatCountLabel(diagnosticPlottable.length, mode === "stocks" ? "ticker" : "group")} remain visible in the diagnostic map and table.`
          : tailAvailable
            ? effectiveTailLength > 0
              ? `Trails connect up to ${effectiveTailLength + 1} real dated observations in each group's current comparable segment (${historyDatesLabel}).`
              : "Enable Tail to connect real dated observations per group."
            : "Dated rotation history is unavailable for this selection."}</span>
        {taxonomyKind !== "SECTOR" && <span style={{ color: "var(--link)" }}>Analyst-defined taxonomy</span>}
      </div>

      {replay && mode === "groups" && <details style={{ marginBottom: 12, fontSize: 12 }}>
        <summary>History coverage · {[...selections.values()].filter(s => s[effectiveInterval ?? "daily"].points.length > 0).length} of {plottedRows.length} plotted groups have {effectiveInterval ?? "daily"} trails</summary>
        <p>Point-in-time membership and eligibility · {formatDateLabel(replay.start)}–{formatDateLabel(replay.as_of)}. Lines stop at membership, eligibility or data gaps. Earlier segments are retained in the evidence; they are not connected to current points.</p>
        <p>Membership uses the latest evidenced disclosure available by each close. Historical prices were retrieved later; this is not an archived real-time feed.</p>
        {effectiveInterval === "weekly" && <p>Weekly endpoints use the last observed session. Current week is shown through {formatDateLabel(replay.as_of)}{new Date(`${replay.as_of}T00:00:00Z`).getUTCDay() < 5 ? " (week to date)" : ""}.</p>}
        <ul>{plottedRows.map(row => {
          const selection = selections.get(row.id)?.[effectiveInterval ?? "daily"];
          return <li key={row.id}>{row.name}: {selection?.reason ?? `${selection?.points.length ?? 0} dated observations (${formatDateLabel(selection!.points[0].as_of)}–${formatDateLabel(selection!.points[selection!.points.length - 1].as_of)})`}</li>;
        })}</ul>
      </details>}
      {!replay && rotationAsset.error && snapshotId?.startsWith("snap_public_market") && <p role="status">Rotation history could not be verified. Current points remain available.</p>}

      <div ref={frameRef} className="rotation-map-frame" style={{ border: "1px solid var(--line)", background: "var(--surface)", overflow: "hidden" }}>
        <svg viewBox={(() => { const w = 1000 / zoom; const h = 450 / zoom; return `${(1000 - w) / 2} ${(450 - h) / 2} ${w} ${h}`; })()} role="img" aria-label={isDiagnostic ? "Market rotation diagnostic map" : "Market rotation map"} style={{ display: "block", width: "100%", height: "auto" }}>
          <rect x={PLOT.left} y={PLOT.top} width={PLOT.width / 2} height={PLOT.height / 2} fill="var(--quad-improving)" />
          <rect x={PLOT.left + PLOT.width / 2} y={PLOT.top} width={PLOT.width / 2} height={PLOT.height / 2} fill="var(--quad-leading)" />
          <rect x={PLOT.left} y={PLOT.top + PLOT.height / 2} width={PLOT.width / 2} height={PLOT.height / 2} fill="var(--quad-lagging)" />
          <rect x={PLOT.left + PLOT.width / 2} y={PLOT.top + PLOT.height / 2} width={PLOT.width / 2} height={PLOT.height / 2} fill="var(--quad-weakening)" />
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
          <text x={PLOT.left} y={PLOT.top + PLOT.height + 18} textAnchor="start" fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--muted)">−30%</text>
          <text x={scaleX(0)} y={PLOT.top + PLOT.height + 18} textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--muted)">0%</text>
          <text x={PLOT.left + PLOT.width} y={PLOT.top + PLOT.height + 18} textAnchor="end" fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--muted)">+30%</text>
          <text x={PLOT.left - 10} y={PLOT.top + 4} textAnchor="end" fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--muted)">+30%</text>
          <text x={PLOT.left - 10} y={scaleY(0) + 4} textAnchor="end" fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--muted)">0%</text>
          <text x={PLOT.left - 10} y={PLOT.top + PLOT.height} textAnchor="end" fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--muted)">−30%</text>
          {trails.map((trail) => (
            <g key={`trail-${trail.id}`} pointerEvents="none">
              <polyline
                points={trail.points.map((p) => `${clamp(scaleX(p.x), PLOT.left, PLOT.left + PLOT.width)},${clamp(scaleY(p.y), PLOT.top, PLOT.top + PLOT.height)}`).join(" ")}
                fill="none"
                stroke={phaseColor(trail.phase)}
                strokeWidth="1.75"
                strokeOpacity=".55"
                strokeDasharray="4 3"
                strokeLinejoin="round"
              />
              {trail.points.slice(0, -1).map((p) => (
                <circle
                  key={`trail-point-${trail.id}-${p.asOf}`}
                  cx={clamp(scaleX(p.x), PLOT.left, PLOT.left + PLOT.width)}
                  cy={clamp(scaleY(p.y), PLOT.top, PLOT.top + PLOT.height)}
                  r="2.75"
                  fill={phaseColor(trail.phase)}
                  fillOpacity=".7"
                />
              ))}
              <title>{`${trail.name}: trail through ${trail.points.length} dated observations (${trail.points.map((p) => p.asOf).join(" → ")})`}</title>
            </g>
          ))}
          {plottedRows.map((row) => {
            const xValue = isDiagnostic ? row.excess20d : row.relativeStrength;
            const x = clamp(scaleX(xValue ?? 0), PLOT.left, PLOT.left + PLOT.width);
            const y = clamp(scaleY(row.relativeMomentum ?? 0), PLOT.top, PLOT.top + PLOT.height);
            const radius = Math.max(8, Math.min(22, 5 + Math.sqrt(Math.max(1, row.constituents)) * 2));
            const color = isDiagnostic ? "var(--muted)" : phaseColor(row.phase);
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
                <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--on-accent)" pointerEvents="none">{row.constituents}</text>
              </g>
            );
          })}
          {labelPositions.map((label) => (
            <g key={`label-${label.id}`} pointerEvents="none">
              {label.targetX !== undefined && label.targetY !== undefined && Math.hypot(label.x - label.targetX, label.y - label.targetY) > 16 && (
                <line x1={label.targetX} y1={label.targetY} x2={label.x} y2={label.y - 3} stroke="#9aa19f" strokeWidth=".8" />
              )}
              <text x={label.x} y={label.y} textAnchor={label.textAnchor} fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--ink)" stroke="var(--surface)" strokeWidth="3" strokeLinejoin="round" paintOrder="stroke">{label.text}</text>
            </g>
          ))}
          <text x={PLOT.left + PLOT.width / 2} y="438" textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--muted)">{isDiagnostic ? "20D excess return vs IHSG (%) · diagnostic" : "YTD excess return vs IHSG (%)"}</text>
          <text x="18" y={PLOT.top + PLOT.height / 2} textAnchor="middle" transform={`rotate(-90 18 ${PLOT.top + PLOT.height / 2})`} fontFamily="Geist Mono, monospace" fontSize="10" fill="var(--muted)">20D excess − 60D excess (%)</text>
        </svg>
      </div>

      {isDiagnostic ? (
        <div
          className="rotation-diagnostic-callout"
          role="status"
          style={{ marginTop: 12, padding: "13px 15px", border: "1px solid #d5c59d", background: "var(--tint-cream)", color: "var(--muted)" }}
        >
          <div className="eyebrow-muted" style={{ color: "var(--accent-ink)" }}>Diagnostic availability</div>
          <strong style={{ display: "block", marginTop: 5, color: "var(--ink)", fontSize: 15 }}>YTD rotation is unavailable for this snapshot.</strong>
          <div style={{ marginTop: 5, fontSize: 12, lineHeight: 1.5 }}>
            {formatCountLabel(diagnosticPlottable.length, mode === "stocks" ? "ticker" : "group")} are shown above using available 20D excess and momentum. The phase cards and rotation signal remain unavailable until the prior-year baseline is persisted.
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
              <div style={{ color: "var(--muted)", fontSize: 10 }}>{formatCountLabel(count, mode === "stocks" ? "ticker" : "group")}</div>
            </div>
            );
          })}
        </div>
      )}

      <section style={{ marginTop: 22 }} aria-labelledby="rotation-table-title">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", flexWrap: "wrap", marginBottom: 9 }}>
          <h2 id="rotation-table-title" style={{ margin: 0, fontSize: 18, fontWeight: 500 }}>Rotation table</h2>
          <span style={{ color: "var(--muted)", fontSize: 11 }}>Click a {mode === "stocks" ? "ticker" : "group"} to open its detail · {plottedRows.length} of {rows.length} {mode === "stocks" ? "tickers" : "groups"}</span>
        </div>
        <div className="table-scroll" style={{ border: "1px solid var(--line)" }}>
          <table style={{ width: "100%", minWidth: 920, borderCollapse: "collapse" }} aria-label="Rotation mapping table">
            <thead>
              <tr style={{ background: "var(--surface-subtle)", borderBottom: "1px solid var(--line)", textAlign: "left" }}>
                {[
                  "Group",
                  "Quadrant",
                  "Relative strength (%)",
                  "Relative momentum (%)",
                  "Phase",
                  "YTD excess (%)",
                  "Data quality",
                ].map((heading) => <th key={heading} style={{ padding: "9px 10px", fontFamily: "Geist Mono, monospace", fontSize: 10, color: "var(--muted)", whiteSpace: "nowrap" }}>{heading}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`table-${row.id}`} style={{ borderBottom: "1px solid var(--line)", background: row.phase === "DATA_GAP" ? "var(--surface-subtle)" : "var(--surface)" }}>
                  <td style={{ padding: "9px 10px", fontSize: 12, fontWeight: 600, whiteSpace: "nowrap" }}>
                    <button type="button" onClick={() => openGroup(navigate, row, mode)} style={{ border: 0, borderBottom: "1px dotted #9aa19f", background: "none", padding: 0, color: "var(--ink)", cursor: "pointer", fontWeight: 600 }}>{row.name}</button>
                  </td>
                  <td style={{ padding: "9px 10px", fontFamily: "Geist Mono, monospace", fontSize: 11 }}>{formatEnumLabel(row.phase)}</td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 11, color: phaseColor(row.phase) }}>{formatPercent(row.relativeStrength)}</td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 11, color: phaseColor(row.phase) }}>{formatPercent(row.relativeMomentum)}</td>
                  <td style={{ padding: "9px 10px", fontSize: 11 }}>{formatEnumLabel(row.phase)}</td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 11, color: phaseColor(row.phase) }}>{formatPercent(row.ytdExcess)}</td>
                  <td style={{ padding: "9px 10px", fontSize: 11, color: row.phase === "DATA_GAP" ? "var(--accent-ink)" : "var(--muted)" }}>{formatEnumLabel(dataQualityLabel(row))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="rotation-accessible-list" style={{ marginTop: 18, display: "grid", gap: 7 }} aria-label={`${currentTaxonomyLabel} rotation groups`}>
        <div className="eyebrow-muted">Accessible group list</div>
        {rows.map((row) => (
          <button key={`list-${row.id}`} type="button" onClick={() => openGroup(navigate, row, mode)} style={{ display: "flex", justifyContent: "space-between", gap: 12, minWidth: 0, padding: "8px 10px", border: "1px solid var(--line)", background: row.phase === "DATA_GAP" ? "var(--surface-subtle)" : "var(--surface)", color: "var(--ink)", textAlign: "left", cursor: "pointer" }}>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12 }}>{row.name}</span>
            <span style={{ flexShrink: 0, fontFamily: "Geist Mono, monospace", fontSize: 10, color: phaseColor(row.phase) }}>{formatEnumLabel(row.phase)} · {formatCountLabel(row.constituents, "ticker")}</span>
          </button>
        ))}
      </div>

      <footer style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 14, color: "var(--muted)", fontFamily: "Geist Mono, monospace", fontSize: 10 }}>
        <span>Bubble size ∝ √(constituents)</span>
        <span>·</span>
        <span>Groups with incomplete coverage remain in the table and list</span>
        <span>·</span>
        <span>{isDiagnostic ? "Diagnostic fallback: persisted 20D/60D values only" : "YTD baseline: last trading session of prior year"}</span>
      </footer>
    </section>
  );
}
