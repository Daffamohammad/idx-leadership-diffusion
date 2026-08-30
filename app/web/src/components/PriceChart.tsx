import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

export interface PricePoint {
  date: string;
  value?: number | null;
  close?: number | null;
  adjusted_close?: number | null;
}

export interface PriceChartProps {
  ticker?: string;
  groupName?: string;
  title?: string;
  points?: PricePoint[];
  benchmarkPoints?: PricePoint[];
  asOf?: string;
  source?: string;
  metricLabel?: string;
  referenceValue?: number | null;
  height?: number | string;
}

function safeNumber(v: number | null | undefined): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  return v > 0 ? v : null;
}

function pointValue(point: PricePoint): number | null {
  return safeNumber(point.value ?? point.adjusted_close ?? point.close);
}

export default function PriceChart({
  ticker,
  groupName,
  title,
  points = [],
  benchmarkPoints = [],
  asOf,
  source = "yfinance (cached)",
  metricLabel = "Adjusted close",
  referenceValue = 0,
  height = 320,
}: PriceChartProps) {
  const series = useMemo(() => {
    const merged = new Map<string, { date: string; price: number | null; bench: number | null }>();
    for (const p of points) {
      const price = pointValue(p);
      if (merged.has(p.date)) {
        const existing = merged.get(p.date)!;
        merged.set(p.date, { ...existing, price: price ?? existing.price });
      } else {
        merged.set(p.date, { date: p.date, price, bench: null });
      }
    }
    for (const b of benchmarkPoints) {
      const bench = pointValue(b);
      if (merged.has(b.date)) {
        const existing = merged.get(b.date)!;
        merged.set(b.date, { ...existing, bench: bench ?? existing.bench });
      } else {
        merged.set(b.date, { date: b.date, price: null, bench });
      }
    }
    const sorted = Array.from(merged.values()).sort((a, b) => a.date.localeCompare(b.date));
    return sorted.filter((s) => s.price !== null || s.bench !== null);
  }, [points, benchmarkPoints]);

  if (series.length === 0) {
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
              As of: {asOf}
            </div>
          )}
        </div>
      </div>
    );
  }

  const label = title || (ticker ? `${ticker}` : groupName ? `${groupName}` : "Security");

  return (
    <div style={{ width: "100%", height }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <div>
          <div style={{ fontWeight: 600, fontSize: 13, color: "#202325" }}>{label}</div>
          <div style={{ fontSize: 10, color: "#747a7d", fontFamily: "Geist Mono" }}>
            {source} · As of {asOf || "—"}
          </div>
        </div>
        <div style={{ fontSize: 10, color: "#747a7d" }}>Read-only · {metricLabel}</div>
      </div>
      <div style={{ height: height ? (typeof height === "number" ? height - 48 : "calc(100% - 48px)") : 272, border: "1px solid #e1e2de", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={series} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f1ef" />
            <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#747a7d" }} tickMargin={4} />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 9, fill: "#747a7d" }}
              tickFormatter={(v: number) =>
                typeof v === "number" ? v.toFixed(2) : String(v)
              }
              width={40}
            />
            <Tooltip
              labelFormatter={(label: unknown) =>
                typeof label === "string" ? `Date: ${label}` : `Date: ${String(label)}`
              }
              formatter={(value: unknown, name: unknown) => {
                const valStr = typeof value === "number" ? value.toFixed(2) : String(value);
                const nameStr = typeof name === "string" ? name : String(name);
                const displayName = nameStr === "price" ? (ticker || groupName || "Security") : "IHSG (^JKSE)";
                return [valStr, displayName] as [string, string];
              }}
            />
            {referenceValue !== null && (
              <ReferenceLine y={referenceValue} stroke="#9ca9a7" strokeWidth={0.75} />
            )}
            <Line
              type="monotone"
              dataKey="price"
              name={ticker || groupName || "Security"}
              stroke="#d97956"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="bench"
              name="IHSG (^JKSE)"
              stroke="#54718b"
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
