import type { IDXDailyStatisticsAdapted } from "../data/adapter";
import { formatDateLabel, formatEnumLabel } from "../data/format";
import { EvidenceBadge } from "./EvidenceModel";

interface IDXDailyStatisticsProps {
  statistics: IDXDailyStatisticsAdapted | null;
}

function formatSigned(value: number, fractionDigits = 2): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })}`;
}

function flowColour(direction: string): string {
  if (direction === "NET_BUY") return "#178477";
  if (direction === "NET_SELL") return "#8f2424";
  return "#686e73";
}

export default function IDXDailyStatistics({ statistics }: IDXDailyStatisticsProps) {
  if (!statistics) return null;
  const { ihsg, netForeign, fundamental, quality, source } = statistics;
  const hasWarnings = quality.warnings.length > 0;

  return (
    <section
      aria-labelledby="idx-daily-statistics-title"
      style={{
        border: "1px solid #ead39b",
        padding: 22,
        background: "#fffdf7",
        display: "grid",
        gap: 18,
      }}
    >
      <header style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div className="eyebrow-muted">Daily statistics</div>
          <EvidenceBadge kind="OFFICIAL_RELEASE" compact />
          {hasWarnings && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "3px 8px",
                border: "1px solid #ead39b",
                borderRadius: 999,
                color: "#6e5a24",
                background: "#fff8e8",
                fontFamily: "Geist Mono, ui-monospace, monospace",
                fontSize: 10,
              }}
            >
              Review notes
            </span>
          )}
        </div>
        <h2 id="idx-daily-statistics-title" style={{ margin: 0, fontSize: 22, letterSpacing: "-.02em" }}>
          Official IDX market cards
        </h2>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            color: "#686e73",
            fontFamily: "Geist Mono, ui-monospace, monospace",
            fontSize: 11,
          }}
        >
          <span>As of {formatDateLabel(statistics.asOf)}</span>
          <span>·</span>
          <span>PDF parsed with LlamaParse</span>
          <span>·</span>
          <span>{hasWarnings ? "Review warning attached" : "Validation checks passed"}</span>
        </div>
        <p style={{ margin: 0, color: "#6e5a24", fontSize: 12, lineHeight: 1.5 }}>
          Market-level evidence from the official Daily Statistics release. It does not create per-ticker or group ownership-flow data.
        </p>
      </header>

      <div
        className="idx-daily-statistics-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 10,
        }}
      >
        <MetricCard
          label="IHSG close"
          value={ihsg.close.toLocaleString("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 3 })}
          detail={`${formatSigned(ihsg.change, 3)} · ${formatSigned(ihsg.change_pct, 2)}%`}
          colour={flowColour(ihsg.change < 0 ? "NET_SELL" : ihsg.change > 0 ? "NET_BUY" : "FLAT")}
        />
        <MetricCard
          label="Market PER"
          value={fundamental.market_per.toFixed(2)}
          detail="times"
          colour="#202325"
        />
        <MetricCard
          label="Market PBV"
          value={fundamental.market_pbv.toFixed(2)}
          detail="times"
          colour="#202325"
        />
      </div>

      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Net foreign</h3>
        <div
          className="idx-daily-flow-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 10,
          }}
        >
          <FlowCard label="Today" flow={netForeign.today} />
          <FlowCard label="YTD" flow={netForeign.ytd} />
        </div>
      </div>

      {hasWarnings && (
        <details>
          <summary style={{ cursor: "pointer", color: "#6e5a24", fontSize: 12 }}>
            Show parser review notes
          </summary>
          <ul style={{ margin: "10px 0 0", paddingLeft: 18, color: "#6e5a24", fontSize: 12, lineHeight: 1.5 }}>
            {quality.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </details>
      )}

      <footer
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          alignItems: "center",
          color: "#686e73",
          fontFamily: "Geist Mono, ui-monospace, monospace",
          fontSize: 10,
        }}
      >
        <span>Source: {source.publisher}</span>
        <span>·</span>
        {source.url &&
        (source.url.startsWith("https://") ||
          source.url.startsWith("http://")) ? (
          <a href={source.url} target="_blank" rel="noopener noreferrer">Open source PDF</a>
        ) : (
          <span>Local source PDF</span>
        )}
        <span>·</span>
        <span>{formatEnumLabel(statistics.status)}</span>
      </footer>
    </section>
  );
}

function MetricCard({
  label,
  value,
  detail,
  colour,
}: {
  label: string;
  value: string;
  detail: string;
  colour: string;
}) {
  return (
    <article style={{ minWidth: 0, background: "#ffffff", border: "1px solid #ead39b", padding: 14 }}>
      <div className="eyebrow-muted">{label}</div>
      <div style={{ marginTop: 6, color: colour, fontFamily: "Geist Mono, ui-monospace, monospace", fontSize: 22, lineHeight: 1.2 }}>
        {value}
      </div>
      <div style={{ marginTop: 5, color: "#686e73", fontSize: 11 }}>{detail}</div>
    </article>
  );
}

function FlowCard({
  label,
  flow,
}: {
  label: string;
  flow: IDXDailyStatisticsAdapted["netForeign"]["today"];
}) {
  const colour = flowColour(flow.direction);
  return (
    <article style={{ minWidth: 0, background: "#ffffff", border: "1px solid #ead39b", padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "baseline" }}>
        <h4 style={{ margin: 0, fontSize: 14 }}>{label}</h4>
        <span style={{ color: colour, fontFamily: "Geist Mono, ui-monospace, monospace", fontSize: 11 }}>
          {formatEnumLabel(flow.direction)}
        </span>
      </div>
      <div style={{ marginTop: 12, display: "grid", gap: 7, fontFamily: "Geist Mono, ui-monospace, monospace" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <span style={{ color: "#686e73", fontSize: 11 }}>IDR billion</span>
          <strong style={{ color: colour, fontSize: 18 }}>{formatSigned(flow.idr_billion)}</strong>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <span style={{ color: "#686e73", fontSize: 11 }}>USD million{flow.usd_approximate ? "~" : ""}</span>
          <strong style={{ color: colour, fontSize: 15 }}>{formatSigned(flow.usd_million)}</strong>
        </div>
      </div>
    </article>
  );
}
