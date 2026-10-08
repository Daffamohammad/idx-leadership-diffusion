import type { OfficialMarketContextAdapted } from "../data/adapter";
import { formatDateLabel, formatEnumLabel, formatPercent } from "../data/format";
import { EvidenceBadge } from "./EvidenceModel";

interface OfficialMarketContextProps {
  context: OfficialMarketContextAdapted | null;
}

function formatTrillion(value: number): string {
  const sign = value < 0 ? "−" : value > 0 ? "+" : "";
  return `${sign}${Math.abs(value).toFixed(2)}T Rp`;
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={{ border: "1px solid var(--line)", padding: "12px 14px", background: "var(--surface)" }}>
      <div style={{ color: "var(--muted)", fontSize: 10, textTransform: "uppercase", letterSpacing: ".08em" }}>{label}</div>
      <div style={{ marginTop: 6, color: "var(--ink)", fontSize: 20, fontFamily: "Geist Mono, ui-monospace, monospace" }}>{value}</div>
      <div style={{ marginTop: 4, color: "var(--muted)", fontSize: 11 }}>{detail}</div>
    </div>
  );
}

export default function OfficialMarketContext({ context }: OfficialMarketContextProps) {
  if (!context) return null;
  const { metrics, source } = context;
  const pages = source.parsed_pages?.length ? `pages ${source.parsed_pages.join(", ")}` : "bounded pages";
  return (
    <section
      aria-labelledby="official-market-context-title"
      style={{
        border: "1px solid var(--line)",
        padding: 22,
        background: "var(--tint-note)",
        display: "grid",
        gap: 16,
      }}
    >
      <header style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div className="eyebrow-muted">Official market context</div>
          <EvidenceBadge kind="OFFICIAL_RELEASE" compact />
          <span style={{ color: "var(--muted)", fontSize: 11, fontFamily: "Geist Mono, ui-monospace, monospace" }}>
            {formatEnumLabel(context.status)}
          </span>
        </div>
        <h2 id="official-market-context-title" style={{ margin: 0, fontSize: 22, letterSpacing: "-.02em" }}>
          OJK market observations · {formatDateLabel(context.periodEnd)}
        </h2>
        <p style={{ margin: 0, color: "var(--up)", fontSize: 12, lineHeight: 1.5 }}>
          Market-level figures parsed from an official OJK publication. They are descriptive context only and are not assigned to a ticker, sector, or group.
        </p>
      </header>

      <div className="official-market-context-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 10 }}>
        <Metric label="IHSG close" value={metrics.ihsg_close.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} detail={`YTD ${formatPercent(metrics.ihsg_ytd_pct)}`} />
        <Metric label="Foreign equity flow" value={formatTrillion(metrics.equity_net_foreign_idr_trillion)} detail={formatEnumLabel(metrics.equity_net_foreign_direction)} />
        <Metric label="Equity RNTH" value={formatTrillion(metrics.equity_rnth_idr_trillion)} detail="monthly average daily turnover" />
        <Metric label="Local ownership" value={`${metrics.local_ownership_pct.toFixed(2)}%`} detail={`${metrics.market_cap_idr_trillion.toLocaleString("en-US")}T Rp market cap`} />
      </div>

      <footer style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", color: "var(--muted)", fontSize: 10, fontFamily: "Geist Mono, ui-monospace, monospace" }}>
        <span>Source: {source.publisher}</span>
        <span>·</span>
        <span>Parsed by {source.parser_agent ?? "LlamaCloud"} · {pages}</span>
        <span>·</span>
        {source.url.startsWith("https://") ? (
          <a href={source.url} target="_blank" rel="noopener noreferrer">Open official data</a>
        ) : (
          <span>Official source link unavailable</span>
        )}
      </footer>
    </section>
  );
}
