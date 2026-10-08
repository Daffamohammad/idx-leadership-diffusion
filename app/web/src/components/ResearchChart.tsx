import { useMemo, useState } from "react";
import { LineChart, Line, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, Legend } from "recharts";
import { formatDateLabel } from "../data/format";

type Close = {date: string; close: number};
export function ResearchChart({histories, benchmark, members, date, title, actions = [], comparison}: {
  histories: Record<string, Close[]>; benchmark: Close[]; members: string[]; date: string; title: string; actions?: Array<{date: string; type: string}>; comparison?: {name: string; members: string[]};
}) {
  const [range, setRange] = useState("60");
  const [constituent, setConstituent] = useState("");
  const calculated = useMemo(() => {
    const available = benchmark.filter(row => row.date <= date && row.close > 0).sort((a,b) => a.date.localeCompare(b.date));
    const sessions = range === "all" ? available : available.slice(-(Number(range) + 1));
    if (sessions.length < 2) return {rows: [], names: [], excluded: members, comparisonCount: 0};
    const start = sessions[0].date;
    const individual = constituent || (members.length === 1 ? members[0] : "");
    const selected = individual ? [individual] : members;
    const lookups = Object.fromEntries(selected.map(ticker => [ticker, new Map((histories[ticker] ?? []).map(row => [row.date, row.close]))]));
    const names = selected.filter(ticker => (individual ? (lookups[ticker].get(start) ?? 0) > 0 : sessions.every(row => (lookups[ticker].get(row.date) ?? 0) > 0)) && (individual || !actions.some(action => start < action.date && action.date <= date && action.type.startsWith(`${ticker}:`))));
    const comparisonLookups = Object.fromEntries((comparison?.members ?? []).map(ticker => [ticker, new Map((histories[ticker] ?? []).map(row => [row.date,row.close]))]));
    const comparisonNames = (comparison?.members ?? []).filter(ticker => sessions.every(row => (comparisonLookups[ticker].get(row.date) ?? 0) > 0) && !actions.some(action => start < action.date && action.date <= date && action.type.startsWith(`${ticker}:`)));
    const baseBenchmark = sessions[0].close;
    return {names, comparisonCount: comparisonNames.length, excluded: selected.filter(ticker => !names.includes(ticker)), rows: sessions.map(row => ({date: row.date,
      basket: names.length && names.every(ticker => (lookups[ticker].get(row.date) ?? 0) > 0) ? names.reduce((sum,ticker) => sum + (lookups[ticker].get(row.date)! / lookups[ticker].get(start)! - 1) * 100, 0) / names.length : null,
      comparison: comparisonNames.length ? comparisonNames.reduce((sum,ticker) => sum + (comparisonLookups[ticker].get(row.date)! / comparisonLookups[ticker].get(start)! - 1) * 100, 0) / comparisonNames.length : null,
      ihsg: (row.close / baseBenchmark - 1) * 100}))};
  }, [histories, benchmark, members, date, range, constituent, actions, comparison]);
  return <section className="dash-card research-chart" aria-label={title}>
    <div className="section-title-row"><h2>{title}</h2><div className="workspace-controls">
      <label>Window <select aria-label={`${title} window`} value={range} onChange={event => setRange(event.target.value)}><option value="20">20 sessions</option><option value="60">60 sessions</option><option value="all">Available history</option></select></label>
      <label>Constituent <select aria-label={`${title} constituent`} value={constituent} onChange={event => setConstituent(event.target.value)}><option value="">Group basket</option>{members.map(ticker => <option key={ticker}>{ticker}</option>)}</select></label>
    </div></div>
    <p className="meta">{calculated.names.length} of {constituent ? 1 : members.length} contributors · prices rebased at the window’s starting close · through {formatDateLabel(date)}. IHSG uses the same dates. {members.length === 1 || constituent ? "Individual price path; corporate-action markers do not adjust the underlying closes." : calculated.names.length > 0 && calculated.names.length < 5 ? "Equal-weight descriptive basket; fewer than five contributors." : "Equal-weight basket with fixed constituents."}</p>
    {comparison && <p className="meta">Comparison: {comparison.name} · {calculated.comparisonCount} / {comparison.members.length} fixed contributors over the identical window.</p>}
    {calculated.names.length ? <div style={{height: 320, minWidth: 0}}><ResponsiveContainer width="100%" height="100%"><LineChart data={calculated.rows} margin={{top: 8, right: 20, bottom: 8, left: 2}}>
      <CartesianGrid stroke="var(--line)" strokeDasharray="3 3"/><XAxis dataKey="date" tickFormatter={value => formatDateLabel(value)} minTickGap={65}/><YAxis tickFormatter={value => `${value.toFixed(0)}%`} width={54}/><Tooltip labelFormatter={value => formatDateLabel(String(value))} formatter={value => `${Number(value).toFixed(2)}%`}/><Legend/><ReferenceLine y={0} stroke="var(--muted)"/>
      <Line type="linear" dataKey="basket" name={constituent || (members.length === 1 ? members[0] : "Equal-weight basket")} stroke="var(--up)" dot={false} connectNulls={false} isAnimationActive={false}/><Line type="linear" dataKey="ihsg" name="IHSG" stroke="var(--muted)" dot={false} strokeDasharray="5 3" connectNulls={false} isAnimationActive={false}/>
      {comparison && <Line type="linear" dataKey="comparison" name={comparison.name} stroke="var(--accent-ink)" dot={false} connectNulls={false} isAnimationActive={false}/>}
      {actions.filter(action => members.some(ticker => action.type.startsWith(`${ticker}:`)) && calculated.rows.some(row => row.date === action.date)).map(action => <ReferenceLine key={`${action.date}:${action.type}`} x={action.date} stroke="var(--accent-ink)" label={{value: action.type.split(":").at(-1), position: "insideTop"}}/>)}
    </LineChart></ResponsiveContainer></div> : <p role="status">No complete matched-session basket for this window. Choose a shorter window or inspect an individual stock.</p>}
    {calculated.excluded.length > 0 && <details><summary>{calculated.excluded.length} excluded from this curve</summary><p>{calculated.excluded.join(", ")} — missing a matching close or affected by a corporate action within this window. No value is filled.</p></details>}
  </section>;
}
