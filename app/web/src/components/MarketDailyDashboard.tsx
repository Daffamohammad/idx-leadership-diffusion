import { useState } from "react";
import { Link } from "react-router";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { useWorkspaceAsset, type MarketWorkspace } from "../data/marketWorkspace";
import { formatDateLabel, formatPercent } from "../data/format";
import type { TaxonomyKind } from "../data/snapshot";
import TradingViewTechnicalAnalysis from "./TradingViewTechnicalAnalysis";
import TradingViewWidget from "./TradingViewWidget";

export interface OverviewRanking {
  id: string;
  name: string;
  kind: TaxonomyKind;
  excess20d: number | null;
  eligible: number;
}

interface Props {
  rankKind: TaxonomyKind;
  onRankKindChange: (kind: TaxonomyKind) => void;
  rankings: OverviewRanking[];
  rankingCounts: Record<TaxonomyKind, number>;
  asOf: string;
}

const RANK_LABELS: Record<TaxonomyKind, string> = {
  SECTOR: "Sectors",
  KONGLO: "Konglo",
  THEMES: "Subindustries",
};

function catalogPath(kind: TaxonomyKind): string {
  if (kind === "SECTOR") return "/map?taxonomy=SECTOR&mode=groups";
  if (kind === "KONGLO") return "/konglo";
  return "/themes";
}

export default function MarketDailyDashboard({ rankKind, onRankKindChange, rankings, rankingCounts, asOf }: Props) {
  const { data, error, loading } = useWorkspaceAsset<MarketWorkspace>("market");
  const [period, setPeriod] = useState(60);
  const latest = data?.benchmark.at(-1);
  const previous = data?.benchmark.at(-2);
  const change = latest && previous ? latest.close - previous.close : null;
  const history = data?.benchmark.slice(-period) ?? [];
  const contributions = [...(data?.index_movers.rows ?? [])].sort((a, b) => b.points - a.points);
  const sorted = (data?.records ?? []).filter(r => r.traded && r.return_1d !== null).sort((a, b) => b.return_1d! - a.return_1d!);
  const movers = data?.index_movers.status === "RECONCILED"
    ? { leaders: contributions.slice(0, 6), laggards: contributions.slice(-6).reverse() }
    : { leaders: sorted.slice(0, 6).map(r => ({ ...r, points: null })), laggards: sorted.slice(-6).reverse().map(r => ({ ...r, points: null })) };
  const maxAbsReturn = Math.max(0.01, ...rankings.map((row) => Math.abs(row.excess20d ?? 0)));

  return <>
    <div className="overview-dashboard-grid">
      <section className="dash-card overview-market-card" aria-labelledby="market-overview-title">
        <div className="eyebrow-muted">Official close · {formatDateLabel(data?.as_of ?? null)}</div>
        <h2 id="market-overview-title">Jakarta Composite Index</h2>
        {latest && previous && change !== null ? <>
          <div className="market-level">IHSG {latest.close.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          <p className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(3)} pts · {formatPercent(change / previous.close * 100, 2)}</p>
          <div className="market-overview-prior">Previous close <strong>{previous.close.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></div>
        </> : <p className="market-overview-prior" aria-live="polite">{loading ? "Loading the selected release…" : error ?? "No close is available for this release."}</p>}
        <TradingViewTechnicalAnalysis />
        <details className="official-history-details">
          <summary>Selected-release daily history</summary>
          {data && latest && history.length > 0 ? <>
            <div className="workspace-controls" role="group" aria-label="IHSG history period">{[[20, "1M"], [60, "3M"], [120, "6M"], [188, "Available history"]].map(([n, label]) => <button className="btn btn-outline" key={n} aria-pressed={period === n} onClick={() => setPeriod(Number(n))}>{label}</button>)}</div>
            <div className="workspace-chart" role="img" aria-label={`IHSG end-of-day closes, ${formatDateLabel(history[0].date)} to ${formatDateLabel(latest.date)}, latest ${latest.close}`}>
              <ResponsiveContainer width="100%" height="100%"><LineChart data={history} margin={{ top: 12, right: 8, left: 0, bottom: 4 }}><CartesianGrid vertical={false} stroke="var(--line)"/><XAxis dataKey="date" tickFormatter={v => formatDateLabel(v).slice(0, 6)} minTickGap={45} tick={{ fontSize: 10 }}/><YAxis domain={["auto", "auto"]} width={54} tick={{ fontSize: 10 }}/><Tooltip labelFormatter={v => formatDateLabel(String(v))} formatter={v => [Number(v).toFixed(3), "IHSG close"]}/><Line type="linear" dataKey="close" stroke="var(--up)" dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer>
            </div>
            <div className="breadth-bar" aria-hidden="true"><span style={{ flex: data.breadth.advancers, background: "var(--up)" }}/><span style={{ flex: data.breadth.flat, background: "var(--muted)" }}/><span style={{ flex: data.breadth.decliners, background: "var(--down)" }}/></div>
            <p className="meta">{data.breadth.advancers} up · {data.breadth.flat} flat · {data.breadth.decliners} down. {data.breadth.traded_count} traded stocks; {data.breadth.not_traded_or_unavailable} not traded or outside the stock lane.</p>
            <Link to="/heatmap" className="btn btn-outline">Open stock heatmap →</Link>
          </> : <p className="meta">Dated closing observations are not available in this release.</p>}
        </details>
      </section>

      <TradingViewWidget ticker="IHSG" symbolOverride="IDX:COMPOSITE" title="IDX Composite · IHSG" containerId="market-overview-ihsg-chart" />

      <section className="dash-card overview-groups-card" aria-labelledby="overview-groups-title">
        <div className="eyebrow-muted">Snapshot {asOf} · 20D excess vs IHSG</div>
        <h2 id="overview-groups-title">Sectors &amp; groups</h2>
        <div className="overview-group-tabs" role="group" aria-label="Sectors and group categories">
          {(["SECTOR", "KONGLO", "THEMES"] as TaxonomyKind[]).map((kind) => <button key={kind} type="button" aria-pressed={rankKind === kind} onClick={() => onRankKindChange(kind)}>{RANK_LABELS[kind]}</button>)}
        </div>
        <div className="overview-group-count">{rankKind === "SECTOR" ? `${rankingCounts[rankKind]} sectors` : `Top ${rankings.length} of ${rankingCounts[rankKind]} documented groups`}</div>
        <div className="overview-group-list">
          {rankings.map((row) => {
            const value = row.excess20d;
            const width = value === null ? 0 : Math.max(2, Math.min(100, Math.abs(value) / maxAbsReturn * 100));
            const groupPath = `/explorer?taxonomy=${row.kind}&group=${encodeURIComponent(row.id)}`;
            return <Link className="overview-group-row" to={groupPath} key={row.id}>
              <span className="overview-group-name">{row.name}</span>
              <span className="overview-group-value" style={{ color: value === null ? "var(--muted)" : value >= 0 ? "var(--up)" : "var(--down)" }}>{formatPercent(value)}</span>
              <span className="overview-group-track" aria-hidden="true"><i style={{ width: `${width}%`, marginLeft: value !== null && value < 0 ? "auto" : 0, background: value !== null && value >= 0 ? "var(--up)" : "var(--down)" }}/></span>
            </Link>;
          })}
          {!rankings.length && <p className="meta">No documented groups are included in this release.</p>}
        </div>
        <Link className="overview-catalog-link" to={catalogPath(rankKind)}>{rankKind === "SECTOR" ? "Open sector rotation" : `Browse all ${rankingCounts[rankKind]} ${rankKind === "KONGLO" ? "Konglo portfolios" : "IDXIC subindustries"}`} →</Link>
      </section>
    </div>

    <section className="dash-card overview-movers-card" aria-labelledby="overview-movers-title">
      <div className="eyebrow-muted">Latest session · {formatDateLabel(data?.as_of ?? null)}</div>
      <h2 id="overview-movers-title">{data?.index_movers.status === "RECONCILED" ? "Index movers" : "Stock movers"}</h2>
      {!data && <p className="meta" aria-live="polite">{loading ? "Loading market movers…" : error ?? "Market data is unavailable."}</p>}
      {data && <>
        <div className="mover-columns">{(["leaders", "laggards"] as const).map(side => <div key={side}><h3>{side === "leaders" ? "Leaders" : "Laggards"}</h3>{movers[side].map(r => <Link className="mover-row" to={`/ticker/${r.ticker}`} key={r.ticker}><strong>{r.ticker.replace(".JK", "")}</strong><span className={side === "leaders" ? "positive" : "negative"}>{r.points !== null ? `${r.points > 0 ? "+" : ""}${r.points.toFixed(2)} pts` : formatPercent(r.return_1d, 2)}</span><small>{formatPercent(r.return_1d, 2)}</small></Link>)}</div>)}</div>
        <details className="meta overview-calculation-notes"><summary>Calculation and coverage</summary>{data.index_movers.status === "RECONCILED" ? <p>{data.index_movers.method}. Summed contributions: {data.index_movers.calculated_change?.toFixed(6)} pts; official move: {data.index_movers.official_change?.toFixed(3)} pts; residual: {data.index_movers.residual?.toFixed(6)} pts. Calculated from the official workbook; applies to this session only. <a href={data.index_movers.source} target="_blank" rel="noreferrer">IDX index methodology</a>.</p> : <p>{data.index_movers.reason}. Percentage movers are shown instead.</p>}<p>{data.coverage.observed_histories} observed histories of {data.coverage.requested} requested stocks. {data.coverage.signal_eligible} eligible for the sector signal policy. End-of-day observations; chart values are index levels.</p></details>
      </>}
    </section>
  </>;
}
