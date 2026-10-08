import { useMemo, useState } from "react";
import { LineChart, Line, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, Legend } from "recharts";
import { formatDateLabel } from "../data/format";

type Close = {date: string; close: number};
type ChartInputs = {
  histories: Record<string, Close[]>; benchmark: Close[]; members: string[]; date: string;
  actions?: Array<{date: string; type: string}>; cohorts?: Record<string, string[]>;
  comparison?: {name: string; members: string[]; cohorts?: Record<string, string[]>};
};

/** Keep the analytical horizon cohort fixed; break paths at missing intermediate observations. */
export function buildResearchCurve({histories, benchmark, members, date, actions = [], cohorts, comparison}: ChartInputs, range: string, constituent = "") {
  const available = benchmark.filter(row => row.date <= date && row.close > 0).sort((a,b) => a.date.localeCompare(b.date));
  const sessions = range === "all" ? available : available.slice(-(Number(range) + 1));
  if (sessions.length < 2) return {rows: [], names: [], excluded: members, comparisonCount: 0};
  const start = sessions[0].date, end = sessions.at(-1)!.date;
  const individual = constituent || (members.length === 1 ? members[0] : "");
  const selected = individual ? [individual] : members;
  const lookups = Object.fromEntries([...selected, ...(comparison?.members ?? [])].map(ticker => [ticker, new Map((histories[ticker] ?? []).map(row => [row.date, row.close]))]));
  const eligible = (ticker: string, allowed?: string[]) => (!allowed || allowed.includes(ticker)) &&
    (lookups[ticker].get(start) ?? 0) > 0 && (lookups[ticker].get(end) ?? 0) > 0 &&
    !actions.some(action => start < action.date && action.date <= date && action.type.startsWith(`${ticker}:`));
  const names = selected.filter(ticker => individual ? (lookups[ticker].get(start) ?? 0) > 0 : eligible(ticker, cohorts?.[`${range}d`]));
  const comparisonNames = (comparison?.members ?? []).filter(ticker => eligible(ticker, comparison?.cohorts?.[`${range}d`]));
  const basket = (names: string[], day: string) => names.length && names.every(ticker => (lookups[ticker].get(day) ?? 0) > 0)
    ? names.reduce((sum,ticker) => sum + (lookups[ticker].get(day)! / lookups[ticker].get(start)! - 1) * 100, 0) / names.length : null;
  return {names, comparisonCount: comparisonNames.length, excluded: selected.filter(ticker => !names.includes(ticker)),
    rows: sessions.map(row => ({date: row.date, basket: basket(names,row.date), comparison: basket(comparisonNames,row.date), ihsg: (row.close / sessions[0].close - 1) * 100}))};
}

export function ResearchChart({histories, benchmark, members, date, title, actions = [], cohorts, comparison}: ChartInputs & {title: string}) {
  const [range, setRange] = useState("60");
  const [constituent, setConstituent] = useState("");
  const activeConstituent = members.includes(constituent) ? constituent : "";
  const calculated = useMemo(() => buildResearchCurve({histories,benchmark,members,date,actions,cohorts,comparison},range,activeConstituent),
    [histories,benchmark,members,date,actions,cohorts,comparison,range,activeConstituent]);
  return <section className="dash-card research-chart" aria-label={title}>
    <div className="section-title-row"><h2>{title}</h2><div className="workspace-controls">
      <label>Window <select aria-label={`${title} window`} value={range} onChange={event => setRange(event.target.value)}><option value="20">20 sessions</option><option value="60">60 sessions</option><option value="all">Available history</option></select></label>
      <label>Constituent <select aria-label={`${title} constituent`} value={activeConstituent} onChange={event => setConstituent(event.target.value)}><option value="">Group basket</option>{members.map(ticker => <option key={ticker}>{ticker}</option>)}</select></label>
    </div></div>
    <p className="meta">{calculated.names.length} of {activeConstituent ? 1 : members.length} contributors · prices rebased at the window’s starting close · through {formatDateLabel(date)}. IHSG uses the same dates. {members.length === 1 || activeConstituent ? "Individual price path; corporate-action markers do not adjust the underlying closes." : calculated.names.length > 0 && calculated.names.length < 5 ? "Equal-weight descriptive basket; fewer than five contributors." : "Equal-weight basket with fixed constituents."}</p>
    {comparison && <p className="meta">Comparison: {comparison.name} · {calculated.comparisonCount} / {comparison.members.length} fixed contributors over the identical window.</p>}
    {calculated.names.length ? <div style={{height: 320, minWidth: 0}}><ResponsiveContainer width="100%" height="100%"><LineChart data={calculated.rows} margin={{top: 8, right: 20, bottom: 8, left: 2}}>
      <CartesianGrid stroke="var(--line)" strokeDasharray="3 3"/><XAxis dataKey="date" tickFormatter={value => formatDateLabel(value)} minTickGap={65}/><YAxis tickFormatter={value => `${value.toFixed(0)}%`} width={54}/><Tooltip labelFormatter={value => formatDateLabel(String(value))} formatter={value => `${Number(value).toFixed(2)}%`}/><Legend/><ReferenceLine y={0} stroke="var(--muted)"/>
      <Line type="linear" dataKey="basket" name={activeConstituent || (members.length === 1 ? members[0] : "Equal-weight basket")} stroke="var(--up)" dot={false} connectNulls={false} isAnimationActive={false}/><Line type="linear" dataKey="ihsg" name="IHSG" stroke="var(--muted)" dot={false} strokeDasharray="5 3" connectNulls={false} isAnimationActive={false}/>
      {comparison && <Line type="linear" dataKey="comparison" name={comparison.name} stroke="var(--accent-ink)" dot={false} connectNulls={false} isAnimationActive={false}/>}
      {actions.filter(action => members.some(ticker => action.type.startsWith(`${ticker}:`)) && calculated.rows.some(row => row.date === action.date)).map(action => <ReferenceLine key={`${action.date}:${action.type}`} x={action.date} stroke="var(--accent-ink)" label={{value: action.type.split(":").at(-1), position: "insideTop"}}/>)}
    </LineChart></ResponsiveContainer></div> : <p role="status">No complete matched-session basket for this window. Choose a shorter window or inspect an individual stock.</p>}
    {calculated.excluded.length > 0 && <details><summary>{calculated.excluded.length} excluded from this curve</summary><p>{calculated.excluded.join(", ")} — outside the eligible horizon cohort, missing a matching baseline or endpoint, or affected by a corporate action within this window. Paths break across missing intermediate closes. No value is filled.</p></details>}
  </section>;
}
