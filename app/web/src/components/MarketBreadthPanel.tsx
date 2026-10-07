import { useMemo, useState } from "react";
import { Link } from "react-router";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDateLabel } from "../data/format";
import { useMarketBreadth } from "../data/marketWorkspace";
import { AssetLoadState } from "./AssetLoadState";

const HORIZONS = [
  ["5d", "5D"], ["20d", "20D"], ["60d", "60D"], ["52w", "52 weeks"],
] as const;
const DIRECTIONS = [
  ["advancing", "Advancing"], ["unchanged", "Unchanged"], ["declining", "Declining"],
] as const;

function compactIdr(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const absolute = Math.abs(value);
  const divisor = absolute >= 1e12 ? 1e12 : absolute >= 1e9 ? 1e9 : absolute >= 1e6 ? 1e6 : 1;
  const suffix = divisor === 1e12 ? "T" : divisor === 1e9 ? "B" : divisor === 1e6 ? "M" : "";
  return `${value < 0 ? "−" : ""}Rp${(absolute / divisor).toFixed(divisor === 1 ? 0 : 2)}${suffix}`;
}

function integer(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : Math.round(value).toLocaleString();
}

export default function MarketBreadthPanel() {
  const { data, loading, error } = useMarketBreadth();
  const [horizon, setHorizon] = useState<(typeof HORIZONS)[number][0]>("20d");
  const [side, setSide] = useState<"highs" | "lows">("highs");
  const [search, setSearch] = useState("");
  const [direction, setDirection] = useState<(typeof DIRECTIONS)[number][0] | null>(null);
  const [directionSearch, setDirectionSearch] = useState("");

  const chartRows = useMemo(() => data?.historical_price_breadth.sessions.filter(row => row.net_advances !== null) ?? [], [data]);
  const availableHorizons = HORIZONS.filter(([id]) => Boolean(data?.new_highs_lows.items[id]));
  const activeHorizon = data?.new_highs_lows.items[horizon] ? horizon : (availableHorizons[0]?.[0] ?? "20d");
  const selected = data?.new_highs_lows.items[activeHorizon];
  const list = selected ? selected[side === "highs" ? "new_highs" : "new_lows"] : [];
  const visibleRows = list.filter(row => !search.trim() || `${row.ticker} ${row.company_name}`.toLowerCase().includes(search.trim().toLowerCase()));
  const breadth = data?.official_daily.breadth;
  const values = data?.official_daily.traded_value;
  const activity = data?.official_daily.activity;
  const marketTotals = activity?.market_scope_totals;
  const flow = data?.official_daily.market_foreign_flow;
  const totalStocks = breadth?.traded_count ?? 0;
  const directionRows = direction && data ? data.official_daily.constituents_by_direction[direction] : [];
  const matchedDirectionRows = directionRows.filter(row => !directionSearch.trim() || `${row.ticker} ${row.company_name}`.toLowerCase().includes(directionSearch.trim().toLowerCase()));

  if (!data) return <section className="dash-card breadth-panel" aria-label="Market breadth"><h2>Market breadth</h2><AssetLoadState label="Market breadth" loading={loading} error={error} absentMessage="This release does not include a market breadth recording." /></section>;

  return (
    <section className="breadth-panel" aria-labelledby="breadth-title">
      <header className="breadth-heading">
        <div><div className="eyebrow-muted">Official daily statistics · {formatDateLabel(data.as_of)}</div><h2 id="breadth-title">Market breadth</h2></div>
        <span>{integer(totalStocks)} traded stocks</span>
      </header>

      <div className="breadth-glance" aria-label="At a glance">
        <article><span>Market turnover</span><strong>{compactIdr(marketTotals?.turnover_idr)}</strong><small>{marketTotals?.current_to_average_turnover_multiple?.toFixed(2) ?? "—"}× the preceding 20-session average</small></article>
        <article><span>Stock Summary activity</span><strong>{compactIdr(activity?.turnover_idr)}</strong><small>{integer(activity?.volume_shares)} shares · {integer(activity?.volume_lots)} lots · {integer(activity?.frequency_trades)} trades</small></article>
        <article><span>Advancing share</span><strong>{breadth?.advancing_pct_of_moving_stocks?.toFixed(1) ?? "—"}%</strong><small>{integer(breadth?.advancers)} up · {integer(breadth?.decliners)} down</small></article>
        <article><span>Foreign net flow</span><strong className={(flow?.daily_net_idr ?? 0) < 0 ? "breadth-negative" : "breadth-positive"}>{compactIdr(flow?.daily_net_idr)}</strong><small>{flow?.direction ?? "No direction"} · {integer(flow?.consecutive_sessions)} sessions</small><small>20-session mean absolute net {compactIdr(flow?.preceding_20_session_average_absolute_net_idr)}</small></article>
      </div>

      <div className="breadth-panel-grid">
        <article className="breadth-card">
          <div className="breadth-card-title"><h3>Advancing / unchanged / declining</h3><span>Net advances <b>{(breadth?.net_advances ?? 0) > 0 ? "+" : ""}{integer(breadth?.net_advances)}</b></span></div>
          <div className="breadth-stacked-bar" aria-label={`${integer(breadth?.advancers)} advancing, ${integer(breadth?.unchanged)} unchanged, ${integer(breadth?.decliners)} declining`}>
            <i className="breadth-up" style={{ width: `${totalStocks ? (breadth!.advancers / totalStocks) * 100 : 0}%` }} />
            <i className="breadth-flat" style={{ width: `${totalStocks ? (breadth!.unchanged / totalStocks) * 100 : 0}%` }} />
            <i className="breadth-down" style={{ width: `${totalStocks ? (breadth!.decliners / totalStocks) * 100 : 0}%` }} />
          </div>
          <div className="breadth-three-values">{DIRECTIONS.map(([key, label]) => <div key={key}><span>{label}</span><button type="button" aria-pressed={direction === key} onClick={() => { setDirection(direction === key ? null : key); setDirectionSearch(""); }}>{integer(breadth?.[key === "advancing" ? "advancers" : key === "unchanged" ? "unchanged" : "decliners"])}</button></div>)}</div>
          <p className="breadth-footnote">A/D ratio {breadth?.advancers_to_decliners_ratio?.toFixed(2) ?? "—"} · {breadth?.advancing_pct_of_moving_stocks?.toFixed(1) ?? "—"}% of moving stocks advanced.</p>
          {direction && <div className="breadth-constituent-browser">
            <div className="breadth-constituent-heading"><strong>{DIRECTIONS.find(([key]) => key === direction)?.[1]} stocks</strong><span>{integer(directionRows.length)} names</span></div>
            <label className="breadth-search"><span className="sr-only">Search directional constituents</span><input type="search" value={directionSearch} onChange={event => setDirectionSearch(event.target.value)} placeholder="Search ticker or company" /></label>
            <div className="breadth-stock-list" aria-live="polite">
              {matchedDirectionRows.length ? matchedDirectionRows.slice(0, 40).map(row => <div key={row.ticker}><Link to={`/ticker/${encodeURIComponent(row.ticker.replace(/\.JK$/i, ""))}`}>{row.ticker.replace(/\.JK$/i, "")}</Link><span>{row.company_name}</span><strong>{row.return_1d_pct > 0 ? "+" : ""}{row.return_1d_pct.toFixed(2)}%</strong></div>) : <p>No matching stocks in this direction.</p>}
            </div>
            <small>Showing up to 40 names; search the full selected group. Ticker links open stock details.</small>
          </div>}
        </article>

        <article className="breadth-card">
          <div className="breadth-card-title"><h3>Traded value by direction</h3><span>{compactIdr(values?.denominator_idr)}</span></div>
          <div className="breadth-stacked-bar" aria-label="Share of traded value by daily direction">
            <i className="breadth-up" style={{ width: `${values?.advancing_pct ?? 0}%` }} />
            <i className="breadth-flat" style={{ width: `${values?.unchanged_pct ?? 0}%` }} />
            <i className="breadth-down" style={{ width: `${values?.declining_pct ?? 0}%` }} />
          </div>
          <div className="breadth-three-values breadth-value-shares"><div><span>Advancing</span><strong>{values?.advancing_pct?.toFixed(1) ?? "—"}%</strong><small>{compactIdr(values?.advancing_idr)}</small></div><div><span>Unchanged</span><strong>{values?.unchanged_pct?.toFixed(1) ?? "—"}%</strong><small>{compactIdr(values?.unchanged_idr)}</small></div><div><span>Declining</span><strong>{values?.declining_pct?.toFixed(1) ?? "—"}%</strong><small>{compactIdr(values?.declining_idr)}</small></div></div>
          <p className="breadth-footnote">Denominator: {values?.denominator_idr ? compactIdr(values.denominator_idr) : "—"} across {integer(values?.coverage_count)} stocks with a comparable close and reported value.</p>
        </article>

        <article className="breadth-card breadth-history-card">
          <div className="breadth-card-title"><div><h3>Net advances through time</h3><p>Fixed cohort · {formatDateLabel(data.historical_price_breadth.start)}–{formatDateLabel(data.historical_price_breadth.end)}</p></div><span>{integer(data.historical_price_breadth.cohort_count)} stocks</span></div>
          <div className="breadth-chart" role="img" aria-label="Historical net advances calculated from a fixed adjusted-close cohort">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartRows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 4" vertical={false} />
                <XAxis dataKey="as_of" tickFormatter={value => formatDateLabel(String(value)).replace(/\s\d{4}$/, "")} minTickGap={38} tick={{ fontSize: 10 }} />
                <YAxis width={50} tick={{ fontSize: 10 }} />
                <ReferenceLine y={0} stroke="var(--muted)" />
                <Tooltip labelFormatter={value => formatDateLabel(String(value))} formatter={(value, name) => [integer(Number(value)), name === "net_advances" ? "Net advances" : String(name)]} />
                <Area type="monotone" dataKey="net_advances" stroke="#167f72" fill="#167f72" fillOpacity={0.12} strokeWidth={2} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <details><summary>Price cohort and calculation</summary><p>{data.historical_price_breadth.basis} Cohort hash: <code>{data.historical_price_breadth.cohort_sha256}</code>.</p></details>
        </article>

        <article className="breadth-card breadth-highlow-card">
          <div className="breadth-card-title"><div><h3>New highs / lows</h3><p>Strict break of the previous adjusted-close range</p></div><span>{integer(selected?.eligible_count)} eligible</span></div>
          <div className="breadth-horizon-tabs" role="tablist" aria-label="High and low lookback">
          {availableHorizons.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={activeHorizon === id} onClick={() => setHorizon(id)}>{label}</button>)}
          </div>
          <div className="breadth-hilo-summary"><button type="button" aria-pressed={side === "highs"} onClick={() => setSide("highs")}><span>New highs</span><strong>{integer(selected?.new_high_count)}</strong></button><button type="button" aria-pressed={side === "lows"} onClick={() => setSide("lows")}><span>New lows</span><strong>{integer(selected?.new_low_count)}</strong></button></div>
          <label className="breadth-search"><span className="sr-only">Search high and low stocks</span><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search ticker or company" /></label>
          <div className="breadth-stock-list">
            {visibleRows.length ? visibleRows.slice(0, 30).map(row => <div key={row.ticker}><Link to={`/ticker/${encodeURIComponent(row.ticker.replace(/\.JK$/i, ""))}`}>{row.ticker.replace(/\.JK$/i, "")}</Link><span>{row.company_name}</span><strong>{row.change_from_prior_close_pct > 0 ? "+" : ""}{row.change_from_prior_close_pct.toFixed(2)}%</strong></div>) : <p>No matching names in this selected-session list.</p>}
          </div>
          <details><summary>Eligibility and dates</summary><p>{selected?.eligible_scope}. Prior range: {selected?.start ? formatDateLabel(selected.start) : "—"} to {selected?.end ? formatDateLabel(selected.end) : "—"}. {selected?.tie_rule}</p><p>Showing at most 30 rows; use search to find other qualifying names.</p></details>
        </article>
      </div>

      <details className="breadth-methodology"><summary>Sources, units and coverage</summary>
        <p>Official Stock Summary values use {data.official_daily.scope.toLowerCase()}. The displayed value-share denominator is {compactIdr(values?.denominator_idr)}. Volume in shares, lots and frequency are summed from eligible Stock Summary rows.</p>
        <p>{marketTotals?.scope} Daily market turnover is {compactIdr(marketTotals?.turnover_idr)}; the preceding 20-session mean is {compactIdr(marketTotals?.preceding_20_session_average_turnover_idr)}. The published page reports turnover in whole IDR billions, volume in millions of shares, and frequency in thousands of trades.</p>
        <p>Official foreign flow: {flow?.provider}, {flow?.scope}. Daily net {compactIdr(flow?.daily_net_idr)}; preceding 20-session mean absolute net {compactIdr(flow?.preceding_20_session_average_absolute_net_idr)} from {integer(flow?.preceding_20_session_count)} sessions.</p>
        <ul>{data.methodology.map(line => <li key={line}>{line}</li>)}{data.coverage.limits.map(line => <li key={line}>{line}</li>)}</ul>
        <dl className="breadth-hashes">{Object.entries(data.sources).map(([key, value]) => <div key={key}><dt>{key.replace(/_/g, " ")}</dt><dd><code>{value}</code></dd></div>)}</dl>
      </details>
    </section>
  );
}
