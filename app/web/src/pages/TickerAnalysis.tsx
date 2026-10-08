import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { useResearch, groupHref } from "../data/research";
import { ResearchChart } from "../components/ResearchChart";
import { AssetLoadState } from "../components/AssetLoadState";
import { formatDateLabel, formatPercent } from "../data/format";

export default function TickerAnalysis() {
  const {ticker: rawTicker} = useParams<{ticker: string}>();
  const code = (rawTicker ?? "").toUpperCase();
  const ticker = code.endsWith(".JK") ? code : `${code}.JK`;
  const state = useResearch();
  const [playing, setPlaying] = useState(false);
  const index = state.dates.indexOf(state.date);
  useEffect(() => {
    if (!playing || !state.dates.length) return;
    const timer = window.setTimeout(() => {
      if (index >= state.dates.length - 1) setPlaying(false);
      else state.set("date", state.dates[index + 1]);
    }, 850);
    return () => window.clearTimeout(timer);
  }, [playing, index, state]);
  const series = (state.histories[ticker] ?? []).filter(row => row.date <= state.date);
  const stock = state.source?.stocks.find(row => row.ticker === ticker);
  const memberships = state.allGroups.filter(group => group.members.some(member => member.ticker === ticker));
  const member = memberships.flatMap(group => group.members).find(row => row.ticker === ticker);
  const native = state.native?.[state.cadence].find(row => row.date === state.date)?.groups.flatMap(group => group.contributors).find(row => row.ticker === ticker);
  const actions = (state.native?.action_events?.[ticker] ?? []).map(event => ({date:event.date,type:`${ticker}:${event.type}`}));
  if (state.loading || state.error) return <main className="workspace-page"><h1>{ticker}</h1><AssetLoadState label="Stock history" loading={state.loading} error={state.error} absentMessage="Stock history is unavailable."/></main>;
  return <main className="workspace-page research-workspace">
    <header className="submission-page-heading"><div><div className="eyebrow-muted">{ticker} · {state.scope === "sectors" ? "Raw Sectors closes" : "Yahoo Finance adjusted closes"}</div><h1>{stock?.company_name ?? member?.name ?? ticker}</h1><p>Through {formatDateLabel(state.date)} · {series.length} observed closes. {state.scope === "sectors" ? "Corporate-action windows are excluded from signal readings; the price curve retains the observed closes." : "Broader IDX research context."}</p></div><Link to={state.scope === "sectors" ? "/sectors" : "/groups"}>Group research</Link></header>
    <div className="replay-controls">
      <label>Cadence <select aria-label="Stock replay cadence" value={state.cadence} onChange={event => {setPlaying(false);state.set("cadence",event.target.value);}}><option value="daily">Daily</option><option value="weekly">Weekly</option></select></label>
      <label>As of <select aria-label="Stock replay date" value={state.date} onChange={event => {setPlaying(false);state.set("date",event.target.value);}}>{state.dates.map(day => <option key={day} value={day}>{formatDateLabel(day)}</option>)}</select></label>
      <button className="btn btn-outline" disabled={index <= 0} onClick={() => {setPlaying(false);state.set("date",state.dates[index-1]);}}>Previous</button>
      <button className="btn btn-outline" disabled={index >= state.dates.length-1} onClick={() => {setPlaying(false);state.set("date",state.dates[index+1]);}}>Next</button>
      <button className="btn btn-primary" onClick={() => {if(index >= state.dates.length-1) state.set("date",state.dates[0]);setPlaying(!playing);}}>{playing ? "Pause" : "Play"}</button>
    </div>
    <div className="workspace-stats"><div className="workspace-stat"><span className="meta">Latest observed close</span><strong>{series.at(-1)?.close.toLocaleString("en-US",{maximumFractionDigits:2}) ?? "Unavailable"} IDR</strong><small>{formatDateLabel(series.at(-1)?.date)}</small></div>
      {state.scope === "sectors" && (["5d","20d","60d"] as const).map(horizon => <div className="workspace-stat" key={horizon}><span className="meta">{horizon.toUpperCase()} excess vs IHSG</span><strong>{formatPercent(native?.returns[horizon].excess_return_pct,2)}</strong><small>{native?.returns[horizon].exclusion_reason?.replace(/_/g," ") ?? "Matched start and end dates"}</small></div>)}
    </div>
    {series.length ? <ResearchChart histories={state.histories} benchmark={state.benchmark} members={[ticker]} date={state.date} title={`${ticker} price performance`} actions={state.scope === "sectors" ? actions : []}/> : <AssetLoadState label={`${ticker} price history`} loading={false} error={null} absentMessage="No verified price history for this stock in the selected universe. Its catalogue membership remains visible."/>}
    {actions.length > 0 && <section className="dash-card"><h2>Corporate actions</h2><ul>{actions.map(action => <li key={`${action.date}:${action.type}`}>{formatDateLabel(action.date)} · {action.type.split(":").at(-1)?.replace(/_/g," ")}</li>)}</ul></section>}
    <section><h2>Groups and ownership</h2><div className="workspace-controls">{memberships.map(group => <Link key={`${group.taxonomy}:${group.id}`} className="btn btn-outline" to={groupHref(group,state.date,state.cadence,state.horizon)}>{group.name}</Link>)}<Link className="btn btn-outline" to={`/ownership?view=stocks&search=${ticker.replace(/\.JK$/,"")}`}>Disclosed shareholders</Link></div></section>
  </main>;
}
