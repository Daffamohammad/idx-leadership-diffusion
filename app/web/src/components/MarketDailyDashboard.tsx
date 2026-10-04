import { useState } from "react";
import { Link } from "react-router";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { useWorkspaceAsset, type MarketWorkspace } from "../data/marketWorkspace";
import { formatDateLabel, formatPercent } from "../data/format";

export default function MarketDailyDashboard() {
  const { data, error, loading } = useWorkspaceAsset<MarketWorkspace>("market");
  const [period, setPeriod] = useState(60);
  if (!data) return <section className="dash-card" aria-live="polite">{loading ? "Loading market history…" : error}</section>;
  const history = data.benchmark.slice(-period);
  const latest = data.benchmark.at(-1)!; const previous = data.benchmark.at(-2)!;
  const change = latest.close - previous.close;
  const contributions = [...data.index_movers.rows].sort((a, b) => b.points - a.points);
  const sorted = data.records.filter(r => r.traded && r.return_1d !== null).sort((a, b) => b.return_1d! - a.return_1d!);
  const movers = data.index_movers.status === "RECONCILED"
    ? { leaders: contributions.slice(0, 6), laggards: contributions.slice(-6).reverse() }
    : { leaders: sorted.slice(0, 6).map(r => ({ ...r, points: null })), laggards: sorted.slice(-6).reverse().map(r => ({ ...r, points: null })) };
  return <div className="market-grid">
    <section className="dash-card">
      <div className="eyebrow-muted">Official close · {formatDateLabel(data.as_of)}</div><h2>Market overview</h2>
      <div className="market-level">IHSG {latest.close.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
      <p className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(3)} pts · {formatPercent(change / previous.close * 100, 2)}</p>
      <div className="workspace-controls" role="group" aria-label="IHSG chart period">{[[20, "1M"], [60, "3M"], [120, "6M"], [188, "Available history"]].map(([n, label]) => <button className="btn btn-outline" key={n} aria-pressed={period === n} onClick={() => setPeriod(Number(n))}>{label}</button>)}</div>
      <div className="workspace-chart" role="img" aria-label={`IHSG end-of-day closes, ${formatDateLabel(history[0].date)} to ${formatDateLabel(latest.date)}, latest ${latest.close}`}>
        <ResponsiveContainer width="100%" height="100%"><LineChart data={history} margin={{ top: 12, right: 8, left: 0, bottom: 4 }}><CartesianGrid vertical={false} stroke="var(--line)"/><XAxis dataKey="date" tickFormatter={v => formatDateLabel(v).slice(0, 6)} minTickGap={45} tick={{ fontSize: 10 }}/><YAxis domain={["auto", "auto"]} width={54} tick={{ fontSize: 10 }}/><Tooltip labelFormatter={v => formatDateLabel(String(v))} formatter={v => [Number(v).toFixed(3), "IHSG close"]}/><Line type="linear" dataKey="close" stroke="var(--up)" dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer>
      </div>
      <div className="breadth-bar" aria-hidden="true"><span style={{ flex: data.breadth.advancers, background: "var(--up)" }}/><span style={{ flex: data.breadth.flat, background: "var(--muted)" }}/><span style={{ flex: data.breadth.decliners, background: "var(--down)" }}/></div>
      <p className="meta">{data.breadth.advancers} up · {data.breadth.flat} flat · {data.breadth.decliners} down. {data.breadth.traded_count} traded stocks; {data.breadth.not_traded_or_unavailable} not traded or outside the stock lane.</p>
      <Link to="/heatmap" className="btn btn-outline">Open stock heatmap →</Link>
    </section>
    <section className="dash-card"><div className="eyebrow-muted">Latest session</div><h2>{data.index_movers.status === "RECONCILED" ? "Index movers" : "Stock movers"}</h2>
      <div className="mover-columns">{(["leaders", "laggards"] as const).map(side => <div key={side}><h3>{side === "leaders" ? "Leaders" : "Laggards"}</h3>{movers[side].map(r => <Link className="mover-row" to={`/ticker/${r.ticker}`} key={r.ticker}><strong>{r.ticker.replace(".JK", "")}</strong><span className={side === "leaders" ? "positive" : "negative"}>{r.points !== null ? `${r.points > 0 ? "+" : ""}${r.points.toFixed(2)} pts` : formatPercent(r.return_1d, 2)}</span><small>{formatPercent(r.return_1d, 2)}</small></Link>)}</div>)}</div>
      <details className="meta"><summary>Calculation and coverage</summary>{data.index_movers.status === "RECONCILED" ? <p>{data.index_movers.method}. Summed contributions: {data.index_movers.calculated_change?.toFixed(6)} pts; official move: {data.index_movers.official_change?.toFixed(3)} pts; residual: {data.index_movers.residual?.toFixed(6)} pts. Calculated from the official workbook; applies to this session only. <a href={data.index_movers.source} target="_blank" rel="noreferrer">IDX index methodology</a>.</p> : <p>{data.index_movers.reason}. Percentage movers are shown instead.</p>}<p>{data.coverage.observed_histories} observed histories of {data.coverage.requested} requested stocks. {data.coverage.signal_eligible} eligible for the sector signal policy. End-of-day observations; chart values are index levels.</p></details>
    </section>
  </div>;
}
