import { useEffect, useMemo, useState } from "react";
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
  Bar,
} from "recharts";
import type { BarShapeProps } from "recharts";
import { formatDateLabel, formatEnumLabel } from "../data/format";
// ── Data types ────────────────────────────────────────────────────────

export interface PricePoint {
  date: string;
  value?: number | null;
  close?: number | null;
  adjusted_close?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
}

export interface GroupPricePoint {
  date: string;
  value: number;
  benchmark: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
}

export type PriceBasis = "close" | "adjusted_close" | "open" | "high" | "low";
export type ChartRange = "1M" | "3M" | "6M" | "1Y" | "YTD" | "2Y" | "5Y" | "ALL";

// Every period the product offers. Availability is decided from the persisted
// series; anything the snapshot cannot support renders disabled with a reason
// instead of silently disappearing.
export const CHART_PERIODS: ChartRange[] = ["1M", "3M", "6M", "1Y", "YTD", "2Y", "5Y", "ALL"];

const PERIOD_MIN_DAYS: Record<Exclude<ChartRange, "YTD" | "ALL">, number> = {
  "1M": 30,
  "3M": 90,
  "6M": 180,
  "1Y": 365,
  "2Y": 730,
  "5Y": 1825,
};

export interface PriceChartProps {
  ticker?: string;
  groupName?: string;
  title?: string;
  points?: PricePoint[];
  benchmarkPoints?: PricePoint[];
  groupPoints?: GroupPricePoint[];
  asOf?: string;
  source?: string;
  metricLabel?: string;
  referenceValue?: number | null;
  height?: number | string;
  providerMode?: string;
  priceBasis?: string;
  dataStatus?: string;
  showVolume?: boolean;
  // Optional deep-link support so a group/period URL stays shareable. The chart
  // stays uncontrolled when these are omitted (existing call sites unchanged).
  initialRange?: ChartRange;
  onRangeChange?: (range: ChartRange) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────

function safeNumber(v: number | null | undefined): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  return v;
}

function safePositiveNumber(v: number | null | undefined): number | null {
  const value = safeNumber(v);
  return value !== null && value > 0 ? value : null;
}

function pointValue(point: PricePoint): number | null {
  return safePositiveNumber(point.value ?? point.adjusted_close ?? point.close);
}

function formatCompactDate(date: string): string {
  const d = new Date(date + "T00:00:00");
  if (isNaN(d.getTime())) return date;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[d.getMonth()]} ${d.getDate()}`;
}

// Source context shared by every disabled-period explanation: this app reads
// persisted snapshot history only, and Sectors API refreshes stay on hold.
const PERIOD_SOURCE_NOTE =
  "Only persisted snapshot prices are used here — Sectors API refreshes are on hold and were not attempted to extend the window.";

function spanDays(dates: string[]): number {
  if (dates.length === 0) return 0;
  const sorted = [...dates].sort();
  const first = new Date(sorted[0] + "T00:00:00").getTime();
  const last = new Date(sorted[sorted.length - 1] + "T00:00:00").getTime();
  if (!Number.isFinite(first) || !Number.isFinite(last)) return 0;
  return Math.max(0, (last - first) / 86400000);
}

function crossesYearBoundary(dates: string[]): boolean {
  if (dates.length === 0) return false;
  const sorted = [...dates].sort();
  const firstYear = Number(sorted[0].slice(0, 4));
  const lastYear = Number(sorted[sorted.length - 1].slice(0, 4));
  return Number.isFinite(firstYear) && Number.isFinite(lastYear) && firstYear < lastYear;
}

// Returns null when the period is usable, otherwise the reason it is disabled.
export function periodDisabledReason(period: ChartRange, dates: string[]): string | null {
  if (period === "ALL") return null;
  const days = spanDays(dates);
  if (days === 0) {
    return `No persisted price history is available for this series. ${PERIOD_SOURCE_NOTE}`;
  }
  if (period === "YTD") {
    return crossesYearBoundary(dates)
      ? null
      : `The persisted series does not cross a year boundary, so a YTD slice would equal the full window. ${PERIOD_SOURCE_NOTE}`;
  }
  const minDays = PERIOD_MIN_DAYS[period];
  if (days >= minDays) return null;
  const actual = days < 1 ? "under a day" : `${Math.floor(days)} days`;
  return `Needs at least ${minDays} days of history; this snapshot holds ${actual}. ${PERIOD_SOURCE_NOTE}`;
}

function getAvailableRanges(dates: string[]): ChartRange[] {
  return CHART_PERIODS.filter((period) => periodDisabledReason(period, dates) === null);
}

function filterByRange(dates: string[], range: ChartRange): Set<string> {
  const sorted = [...dates].sort();
  if (range === "ALL") return new Set(dates);
  if (sorted.length === 0) return new Set();
  const lastDate = sorted[sorted.length - 1];
  const last = new Date(lastDate + "T00:00:00");
  let first: Date;
  switch (range) {
    case "1M": first = new Date(last.getTime() - 30 * 86400000); break;
    case "3M": first = new Date(last.getTime() - 90 * 86400000); break;
    case "6M": first = new Date(last.getTime() - 180 * 86400000); break;
    case "1Y": first = new Date(last.getTime() - 365 * 86400000); break;
    case "2Y": first = new Date(last.getTime() - 730 * 86400000); break;
    case "5Y": first = new Date(last.getTime() - 1825 * 86400000); break;
    case "YTD": first = new Date(`${lastDate.slice(0, 4)}-01-01T00:00:00`); break;
    default: first = new Date(0);
  }
  return new Set(dates.filter((d) => new Date(d + "T00:00:00") >= first));
}

// ── Custom Tooltip ────────────────────────────────────────────────────

interface ChartDataPoint {
  date: string;
  price: number | null;
  bench: number | null;
  volume: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
}

interface TooltipEntry {
  name?: string;
  value?: unknown;
  color?: string;
  payload?: ChartDataPoint;
}

function formatTooltipValue(value: number | null | undefined, volume = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return volume ? value.toLocaleString("en-US") : value.toFixed(2);
}

function CandlestickWick({ x, y, width, height, payload }: BarShapeProps) {
  const point = payload as ChartDataPoint | undefined;
  if (!point || point.open == null || point.high == null || point.low == null || point.close == null) {
    return null;
  }
  const center = x + width / 2;
  return (
    <line
      x1={center}
      y1={y}
      x2={center}
      y2={y + height}
      stroke={point.close >= point.open ? "#178477" : "#d97956"}
      strokeWidth={1}
    />
  );
}

function CandlestickBody({ x, y, width, height, payload }: BarShapeProps) {
  const point = payload as ChartDataPoint | undefined;
  if (!point || point.open == null || point.close == null) return null;
  const bodyWidth = Math.max(3, Math.min(10, width * 0.7));
  const bodyHeight = Math.max(1, height);
  const color = point.close >= point.open ? "#178477" : "#d97956";
  return (
    <rect
      x={x + (width - bodyWidth) / 2}
      y={y}
      width={bodyWidth}
      height={bodyHeight}
      fill={color}
      fillOpacity={0.82}
      stroke={color}
      strokeWidth={0.75}
    />
  );
}

function CustomTooltip({ active, payload, label, metricLabel, ticker, groupName, showOHLC = false, showVolume = false }: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  metricLabel?: string;
  ticker?: string;
  groupName?: string;
  showOHLC?: boolean;
  showVolume?: boolean;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const date = label ? String(label) : "";
  const point = payload.find((entry) => entry.payload)?.payload;
  const rows = point
    ? [
        { name: metricLabel || ticker || groupName || "Price", value: point.price, color: "#d97956" },
        { name: "IHSG (^JKSE)", value: point.bench, color: "#54718b" },
        ...(showOHLC
          ? [
              { name: "Open (index)", value: point.open ?? null, color: "#178477" },
              { name: "High (index)", value: point.high ?? null, color: "#178477" },
              { name: "Low (index)", value: point.low ?? null, color: "#d97956" },
              { name: "Close (index)", value: point.close ?? null, color: "#d97956" },
            ]
          : []),
        ...(showVolume && point.volume !== null && point.volume !== undefined
          ? [{ name: "Volume", value: point.volume, color: "#8f8f8f" }]
          : []),
      ]
    : payload
        .filter((entry) => !String(entry.name || "").startsWith("OHLC"))
        .map((entry) => ({
          name: entry.name || "Value",
          value: typeof entry.value === "number" ? entry.value : null,
          color: entry.color || "#686e73",
        }));
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #dfe2e1",
        borderRadius: 8,
        padding: "10px 12px",
        fontFamily: "Geist Mono, monospace",
        fontSize: 11,
        boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
        minWidth: 160,
      }}
    >
      <div style={{ fontWeight: 600, color: "#202325", marginBottom: 6, borderBottom: "1px solid #f0f1ef", paddingBottom: 4 }}>
        {date ? formatDateLabel(date) : date}
      </div>
      {rows.map((entry, i) => {
        const valStr = formatTooltipValue(entry.value, entry.name === "Volume");
        return (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 2 }}>
            <span style={{ color: entry.color || "#686e73" }}>{entry.name}</span>
            <span style={{ fontWeight: 600, color: "#202325" }}>{valStr}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Accessible Table Fallback ─────────────────────────────────────────

function PriceTable({
  data,
  ticker,
  metricLabel,
  showOHLC,
  showVolume,
}: {
  data: ChartDataPoint[];
  ticker?: string;
  metricLabel?: string;
  showOHLC: boolean;
  showVolume: boolean;
}) {
  const name = ticker || "Security";
  return (
    <table
      style={{
        width: "100%",
        borderCollapse: "collapse",
        fontFamily: "Geist Mono, monospace",
        fontSize: 11,
      }}
      aria-label={`Price data table for ${name}`}
      role="table"
    >
      <thead>
        <tr style={{ borderBottom: "1px solid #dfe2e1" }}>
          <th style={{ textAlign: "left", padding: "6px 8px", fontWeight: 600, color: "#686e73", fontSize: 10 }}>Date</th>
          <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, color: "#686e73", fontSize: 10 }}>{metricLabel}</th>
          <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, color: "#686e73", fontSize: 10 }}>Benchmark</th>
          {showOHLC && <>
            <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, color: "#686e73", fontSize: 10 }}>Open (index)</th>
            <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, color: "#686e73", fontSize: 10 }}>High (index)</th>
            <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, color: "#686e73", fontSize: 10 }}>Low (index)</th>
            <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, color: "#686e73", fontSize: 10 }}>Close (index)</th>
          </>}
          {showVolume && <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, color: "#686e73", fontSize: 10 }}>Volume</th>}
        </tr>
      </thead>
      <tbody>
        {data.slice(-60).map((row, i) => (
          <tr key={row.date + i} style={{ borderBottom: "1px solid #f0f1ef" }}>
            <td style={{ padding: "4px 8px", color: "#202325" }}>{formatDateLabel(row.date)}</td>
            <td style={{ textAlign: "right", padding: "4px 8px", color: "#202325", fontWeight: 500 }}>
              {row.price !== null ? row.price.toFixed(2) : "—"}
            </td>
            <td style={{ textAlign: "right", padding: "4px 8px", color: "#54718b" }}>
              {row.bench !== null ? row.bench.toFixed(2) : "—"}
            </td>
            {showOHLC && <>
              <td style={{ textAlign: "right", padding: "4px 8px", color: "#178477" }}>{formatTooltipValue(row.open)}</td>
              <td style={{ textAlign: "right", padding: "4px 8px", color: "#178477" }}>{formatTooltipValue(row.high)}</td>
              <td style={{ textAlign: "right", padding: "4px 8px", color: "#d97956" }}>{formatTooltipValue(row.low)}</td>
              <td style={{ textAlign: "right", padding: "4px 8px", color: "#d97956" }}>{formatTooltipValue(row.close)}</td>
            </>}
            {showVolume && (
              <td style={{ textAlign: "right", padding: "4px 8px", color: "#686e73" }}>
                {row.volume !== null ? row.volume.toLocaleString() : "—"}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Main Component ────────────────────────────────────────────────────

export default function PriceChart({
  ticker,
  groupName,
  title,
  points = [],
  benchmarkPoints = [],
  groupPoints = [],
  asOf,
  source = "yfinance (cached)",
  metricLabel = "Adjusted close",
  referenceValue = 0,
  height = 320,
  providerMode,
  priceBasis,
  dataStatus,
  showVolume = true,
  initialRange,
  onRangeChange,
}: PriceChartProps) {
  const [activeRange, setActiveRange] = useState<ChartRange>(initialRange ?? "ALL");
  useEffect(() => {
    if (initialRange) setActiveRange(initialRange);
  }, [initialRange]);
  const selectRange = (range: ChartRange) => {
    setActiveRange(range);
    onRangeChange?.(range);
  };

  // Build series from PricePoint[] (legacy path) or GroupPricePoint[]
  const series = useMemo(() => {
    const merged = new Map<string, ChartDataPoint>();

    if (groupPoints.length > 0) {
      for (const p of groupPoints) {
        const price = safePositiveNumber(p.value);
        const bench = safePositiveNumber(p.benchmark);
        merged.set(p.date, {
          date: p.date,
          price,
          bench,
          volume: safeNumber(p.volume),
          open: safeNumber(p.open),
          high: safeNumber(p.high),
          low: safeNumber(p.low),
          close: safeNumber(p.close),
        });
      }
    } else {
      for (const p of points) {
        const price = pointValue(p);
        const bench = benchmarkPoints.find((b) => b.date === p.date)
          ? pointValue(benchmarkPoints.find((b) => b.date === p.date)!)
          : null;
        merged.set(p.date, {
          date: p.date,
          price,
          bench,
          volume: safeNumber(p.volume),
          open: safeNumber(p.open),
          high: safeNumber(p.high),
          low: safeNumber(p.low),
          close: safeNumber(p.close),
        });
      }
      for (const b of benchmarkPoints) {
        if (!merged.has(b.date)) {
          merged.set(b.date, {
            date: b.date,
            price: null,
            bench: pointValue(b),
            volume: null,
          });
        } else {
          const existing = merged.get(b.date)!;
          existing.bench = pointValue(b) ?? existing.bench;
        }
      }
    }

    const sorted = Array.from(merged.values()).sort((a, b) => a.date.localeCompare(b.date));
    return sorted.filter((s) => s.price !== null || s.bench !== null);
  }, [points, benchmarkPoints, groupPoints]);

  const dates = useMemo(() => series.map((s) => s.date), [series]);
  const availableRanges = getAvailableRanges(dates);
  const effectiveRange = availableRanges.includes(activeRange) ? activeRange : "ALL";

  const filteredSeries = useMemo(() => {
    if (effectiveRange === "ALL" || dates.length === 0) return series;
    const rangeDates = filterByRange(dates, effectiveRange);
    return series.filter((s) => rangeDates.has(s.date));
  }, [series, dates, effectiveRange]);

  const hasOHLC = series.some(
    (p) => p.open != null || p.high != null || p.low != null
  );
  const hasRenderableOHLC = series.some(
    (p) => p.open != null && p.high != null && p.low != null && p.close != null
  );
  const hasVolume = series.some((p) => p.volume != null);

  const qualityBadgeLabel = (() => {
    switch (dataStatus) {
      case "DATA_GAP":
        return "Data gap";
      case "PARTIAL":
        return "Partial data";
      case "STALE":
        return "Stale";
      case "READY_WITH_GAPS":
        return "Partial coverage";
      case "FAILED":
        return "Failed";
      case "UNAVAILABLE":
        return "Unavailable";
      default:
        return null;
    }
  })();
  const isDataGap = qualityBadgeLabel !== null;
  const isEmpty = series.length === 0;
  const chartHeight = typeof height === "number" ? height - (isEmpty ? 0 : 48) : "calc(100% - 48px)";

  if (isEmpty) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: "1px solid #e1e2de",
          borderRadius: 10,
          background: "#faf9f6",
          color: "#747a7d",
          fontSize: 12,
          fontFamily: "Geist Mono",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontWeight: 600, color: "#202325", marginBottom: 4 }}>
            Chart unavailable
          </div>
          <div>
            {ticker ? `No price data for ${ticker}` : "No price data for this group"}
          </div>
          <div style={{ fontSize: 10, marginTop: 4, color: "#8f8f8f" }}>
            Source: {source}
          </div>
          {asOf && (
            <div style={{ fontSize: 10, marginTop: 2, color: "#8f8f8f" }}>
              As of {formatDateLabel(asOf)}
            </div>
          )}
          {isDataGap && (
            <div style={{ fontSize: 10, marginTop: 4, color: "#8f2424", fontWeight: 600 }}>
              Coverage is incomplete — some values may be missing
            </div>
          )}
        </div>
      </div>
    );
  }

  const label = title || (ticker ? `${ticker}` : groupName ? `${groupName}` : "Security");

  return (
    <div
      style={{
        width: "100%",
        maxWidth: "100%",
        minWidth: 0,
        border: "1px solid #e1e2de",
        borderRadius: 10,
        background: "#faf9f6",
        overflow: "hidden",
        boxSizing: "border-box",
      }}
      role="figure"
      aria-label={`Price chart for ${label} as of ${formatDateLabel(asOf)}`}
    >
      {/* ── Compact Header ── */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          padding: "10px 14px",
          borderBottom: "1px solid #e1e2de",
          background: "#fff",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: "#202325" }}>{label}</div>
          {providerMode && (
            <span style={{ fontSize: 9, fontFamily: "Geist Mono", color: "#686e73", background: "#f0f1ef", padding: "2px 6px", borderRadius: 4 }}>
              {formatEnumLabel(providerMode)}
            </span>
          )}
          {priceBasis && (
            <span style={{ fontSize: 9, fontFamily: "Geist Mono", color: "#686e73", background: "#f0f1ef", padding: "2px 6px", borderRadius: 4 }}>
              {formatEnumLabel(priceBasis)} basis
            </span>
          )}
          {qualityBadgeLabel && (
            <span style={{ fontSize: 9, fontFamily: "Geist Mono", color: "#8f2424", background: "#fdeaea", padding: "2px 6px", borderRadius: 4 }}>
              {qualityBadgeLabel}
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", minWidth: 0, fontSize: 10, color: "#747a7d", fontFamily: "Geist Mono" }}>
          <span>As of {formatDateLabel(asOf)}</span>
          <span>Source: {source}</span>
          {hasOHLC && <span>OHLC (index) available</span>}
          {hasVolume && <span>Volume available</span>}
        </div>
      </div>

      {/* ── Range Tabs ── */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 0,
          borderBottom: "1px solid #e1e2de",
          background: "#fff",
          padding: "0 14px",
          maxWidth: "100%",
          minWidth: 0,
          overflowX: "auto",
        }}
        role="tablist"
        aria-label="Chart range selector"
      >
        {CHART_PERIODS.map((range) => {
          const disabledReason = periodDisabledReason(range, dates);
          const disabled = disabledReason !== null;
          const selected = effectiveRange === range;
          return (
            <button
              key={range}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-disabled={disabled}
              title={disabled ? disabledReason ?? undefined : undefined}
              onClick={() => { if (!disabled) selectRange(range); }}
              style={{
                background: "none",
                border: "none",
                borderBottom: selected ? "2px solid #d97956" : "2px solid transparent",
                color: disabled ? "#b6b6b6" : selected ? "#202325" : "#747a7d",
                fontFamily: "Geist Mono, monospace",
                fontSize: 11,
                fontWeight: selected ? 600 : 400,
                padding: "8px 12px",
                cursor: disabled ? "not-allowed" : "pointer",
                textDecoration: disabled ? "line-through" : "none",
                transition: "border-color 0.15s ease, color 0.15s ease",
              }}
            >
              {range}
            </button>
          );
        })}
      </div>
      {activeRange !== effectiveRange && (
        <div
          role="status"
          style={{
            padding: "7px 14px",
            borderBottom: "1px solid #e1e2de",
            background: "#faf9f6",
            fontSize: 11,
            lineHeight: 1.5,
            color: "#7a5010",
          }}
        >
          Requested period <strong>{activeRange}</strong> is unavailable for this series —
          showing <strong>{effectiveRange}</strong> instead. {periodDisabledReason(activeRange, dates)}
        </div>
      )}

      {/* ── Chart Area ── */}
      <div
        style={{
          height: chartHeight,
          position: "relative",
          background: "#fff",
          minWidth: 0,
          maxWidth: "100%",
          overflow: "hidden",
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={filteredSeries}
            margin={{ top: 8, right: 8, bottom: 8, left: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f1ef" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 9, fill: "#747a7d" }}
              tickMargin={4}
              tickFormatter={formatCompactDate}
            />
            <YAxis
              yAxisId="left"
              domain={["auto", "auto"]}
              tick={{ fontSize: 9, fill: "#747a7d" }}
              tickFormatter={(v: number) =>
                typeof v === "number" ? v.toFixed(2) : String(v)
              }
              width={40}
            />
            {showVolume && hasVolume && (
              <YAxis
                yAxisId="right"
                orientation="right"
                domain={[0, "auto"]}
                tick={{ fontSize: 9, fill: "#747a7d" }}
                tickFormatter={(v: number) =>
                  typeof v === "number" ? v.toLocaleString("en-US") : String(v)
                }
                width={52}
              />
            )}
            <Tooltip
              content={
                <CustomTooltip
                  metricLabel={metricLabel}
                  ticker={ticker}
                  groupName={groupName}
                  showOHLC={hasOHLC}
                  showVolume={showVolume && hasVolume}
                />
              }
              cursor={{ stroke: "#d97956", strokeWidth: 1, strokeDasharray: "3 3" }}
            />
            {referenceValue !== null && (
              <ReferenceLine yAxisId="left" y={referenceValue} stroke="#9ca9a7" strokeWidth={0.75} strokeDasharray="2 2" />
            )}
            {hasRenderableOHLC && (
              <>
                <Bar
                  dataKey={(point: ChartDataPoint) =>
                    point.low != null && point.high != null ? [point.low, point.high] : null
                  }
                  name="OHLC range"
                  yAxisId="left"
                  fill="transparent"
                  legendType="none"
                  shape={CandlestickWick}
                  isAnimationActive={false}
                  barSize={8}
                />
                <Bar
                  dataKey={(point: ChartDataPoint) =>
                    point.open != null && point.close != null
                      ? [Math.min(point.open, point.close), Math.max(point.open, point.close)]
                      : null
                  }
                  name="OHLC body"
                  yAxisId="left"
                  fill="transparent"
                  legendType="none"
                  shape={CandlestickBody}
                  isAnimationActive={false}
                  barSize={8}
                />
              </>
            )}
            <Line
              type="monotone"
              dataKey="price"
              yAxisId="left"
              name={metricLabel}
              stroke="#d97956"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              activeDot={{ r: 4, fill: "#d97956", stroke: "#fff", strokeWidth: 2 }}
            />
            <Line
              type="monotone"
              dataKey="bench"
              yAxisId="left"
              name="IHSG (^JKSE)"
              stroke="#54718b"
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={false}
              connectNulls={false}
              activeDot={{ r: 3, fill: "#54718b", stroke: "#fff", strokeWidth: 1.5 }}
            />
            {showVolume && hasVolume && (
              <Bar
                dataKey="volume"
                name="Volume"
                fill="#d97956"
                fillOpacity={0.15}
                yAxisId="right"
                barSize={4}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* ── Metadata Strip ── */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          padding: "6px 14px",
          borderTop: "1px solid #e1e2de",
          background: "#fff",
          fontSize: 9,
          fontFamily: "Geist Mono",
          color: "#747a7d",
        }}
      >
        <span>Range: {effectiveRange}</span>
        <span>Points: {filteredSeries.length}</span>
        <span>Metric: {metricLabel}</span>
        {hasOHLC && <span>OHLC: available</span>}
        {hasVolume && <span>Volume: available</span>}
      </div>

      {/* ── Accessible Table Fallback ── */}
      <details style={{ borderTop: "1px solid #e1e2de", background: "#fff" }}>
        <summary
          style={{
            padding: "8px 14px",
            fontSize: 10,
            fontFamily: "Geist Mono",
            color: "#747a7d",
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          Show accessible data table ({filteredSeries.length} rows)
        </summary>
        <div style={{ padding: "0 14px 12px", maxHeight: 300, overflowY: "auto" }}>
          <PriceTable
            data={filteredSeries}
            ticker={ticker}
            metricLabel={metricLabel}
            showOHLC={hasOHLC}
            showVolume={showVolume && hasVolume}
          />
        </div>
      </details>
    </div>
  );
}
