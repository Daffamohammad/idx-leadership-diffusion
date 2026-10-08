import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
import { LineChart, Line, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine } from "recharts";
import { useResearch, groupHref, rotationPhase, type ResearchGroup } from "../data/research";
import { rotationPlotRanges, rotationTrailSegments, validRotationPoint } from "../data/mapGeometry";
import { formatDateLabel, formatEnumLabel, formatPercent } from "../data/format";
import { AssetLoadState } from "./AssetLoadState";
import { WorkspaceTable } from "./WorkspaceTable";
import { ResearchChart } from "./ResearchChart";

const kinds = [{id:"SECTOR", label:"Sectors"},{id:"KONGLO",label:"Konglo"},{id:"IDXIC",label:"IDXIC"},{id:"CURATED_THEMES",label:"Themes"}];
const colors = ["#167f72","#4278bd","#d1713d","#7865b3","#bd547f","#219caa","#b58a21","#d64b4b","#637c9a","#3eaa66","#728d38"];
export default function ResearchWorkspace({view}: {view: "dashboard" | "map" | "catalog" | "detail"}) {
  const location = useLocation();
  const state = useResearch(view === "dashboard" ? "sectors" : "market");
  const [playing, setPlaying] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const {date, dates, cadence, horizon, scope, reading} = state;
  const kind = location.pathname === "/konglo" ? "KONGLO" : location.pathname === "/themes" && !state.params.get("taxonomy") ? "CURATED_THEMES" : state.taxonomy;
  const groups = state.allGroups.filter(group => group.taxonomy === kind);
  const search = state.params.get("q")?.toLowerCase() ?? "";
  const listed = groups.filter(group => `${group.name} ${group.members.map(member => member.ticker).join(" ")}`.toLowerCase().includes(search));
  const ranked = [...listed].sort((a,b) => (reading(b)?.excess_return_20d ?? -Infinity) - (reading(a)?.excess_return_20d ?? -Infinity) || a.name.localeCompare(b.name));
  const selected = listed.find(group => group.id === state.params.get("group")) ?? ranked[0];
  const active = selected ? reading(selected) : undefined;
  const coordinates = (point: ReturnType<typeof reading>) => ({x: horizon === "ytd" ? point?.map_x_ytd !== undefined ? point.map_x_ytd : point?.excess_return_ytd ?? null : point?.map_x_60d !== undefined ? point.map_x_60d : point?.excess_return_60d ?? null,
    y: horizon === "ytd" && point?.map_y_ytd !== undefined ? point.map_y_ytd : point?.relative_momentum ?? null});
  const plotted = listed.flatMap((group,index) => {
    const point = reading(group); const xy = coordinates(point);
    return validRotationPoint(xy) ? [{group, point, ...xy, color: colors[index % colors.length], count: horizon === "ytd" ? point?.ytd_map_contributors ?? point?.breadth_denominator ?? 0 : point?.map_contributors ?? point?.breadth_denominator ?? 0}] : [];
  });
  const ranges = rotationPlotRanges(plotted.map(item => ({...item, history: item.group[cadence].map(point => ({...coordinates(point)}))})));
  const px = (value: number) => 64 + (value-ranges.x[0])/(ranges.x[1]-ranges.x[0])*690;
  const py = (value: number) => 425 - (value-ranges.y[0])/(ranges.y[1]-ranges.y[0])*385;
  const index = dates.indexOf(date);
  const setDate = (next: number) => state.set("date", dates[Math.max(0,Math.min(next,dates.length-1))]);
  useEffect(() => {
    if (!playing) return;
    if (index >= dates.length-1) {setPlaying(false); return;}
    const timer = window.setTimeout(() => state.set("date", dates[index+1]), 850);
    return () => window.clearTimeout(timer);
  }, [playing,index,dates,state]);
  const choose = (id: string) => state.set("group", id);
  const href = (group: ResearchGroup) => groupHref(group,date,cadence,horizon);
  const count = active?.contributor_counts?.["20d"] ?? active?.breadth_denominator ?? 0;
  const ytd = state.native?.ytd;
  const ytdStocks = ytd?.groups?.flatMap(group => group.contributors.filter(row => row.eligible).map(row => ({...row,sector:group.sector}))) ?? [];
  const sectorStockCount = state.source?.selection.stock_count ?? 66;
  const stocksPerSector = state.source?.selection.stocks_per_sector ?? 6;
  const ytdStockCount = state.source?.coverage?.ytd.stock_count ?? state.source?.selection.stock_count ?? 66;
  const coreGroup = state.native?.[cadence].find(day => day.date === date)?.groups.find(group => group.sector === selected?.name);
  const actions = Object.entries(state.native?.action_events ?? {}).flatMap(([ticker,events]) => events.map(event => ({date:event.date,type:`${ticker}:${event.type}`})));
  const comparison = groups.find(group => group.id === state.params.get("compare") && group.id !== selected?.id);
  const rawContributors = coreGroup?.contributors.filter(row => row.contributes_20d) ?? [];
  const gross = rawContributors.reduce((sum,row) => sum + Math.abs(row.returns["20d"].return_pct ?? 0),0);
  const attribution = scope === "sectors" ? rawContributors.map(row => ({ticker: row.ticker, return_pct: row.returns["20d"].return_pct!, absolute_share_pct: gross > 0 ? Math.abs(row.returns["20d"].return_pct!) / gross * 100 : null})).sort((a,b) => (b.absolute_share_pct ?? 0)-(a.absolute_share_pct ?? 0)) : active?.concentration_detail ?? [];
  if (state.loading || state.error || !state.allGroups.length) return <main className="workspace-page"><h1>{view === "dashboard" ? "Dashboard" : "Group research"}</h1><AssetLoadState label={scope === "sectors" ? "Sectors analysis" : "Group analysis"} loading={state.loading} error={state.error} absentMessage="Group evidence is unavailable for this universe."/></main>;
  return <main className="workspace-page research-workspace">
    <header className="submission-page-heading"><div><div className="eyebrow-muted">{scope === "sectors" ? `${sectorStockCount} stocks · 11 IDX sectors · Source: Sectors API` : "IDX research · broader market coverage"}</div><h1>{view === "dashboard" ? "Leadership beneath the index" : view === "catalog" ? kind === "KONGLO" ? "Konglo catalogue" : "Group catalogue" : view === "detail" ? selected?.name ?? "Group research" : "Leadership map"}</h1><p>Data through {formatDateLabel(scope === "sectors" ? state.native?.as_of : state.context?.as_of)} · {scope === "sectors" ? `${stocksPerSector} stocks per sector by market-cap ranking.` : "Dated memberships with horizon-specific, fixed comparison cohorts."}</p></div><Link to="/sources">Coverage &amp; sources</Link></header>
    {scope === "market" && <nav className="submission-tabs" aria-label="Research taxonomy">{kinds.map(item => <Link key={item.id} aria-current={kind === item.id ? "page" : undefined} to={`${view === "map" ? "/map" : "/groups"}?taxonomy=${item.id}&scope=market&date=${date}&cadence=${cadence}&horizon=${horizon}`}>{item.label} <small>{state.allGroups.filter(group => group.taxonomy === item.id).length}</small></Link>)}</nav>}
    <div className="replay-controls" aria-label="Historical replay controls">
      <div role="group" aria-label="Replay cadence">{["daily","weekly"].map(mode => <button key={mode} className="btn btn-outline" aria-pressed={cadence === mode} onClick={() => {setPlaying(false); state.set("cadence",mode);}}>{formatEnumLabel(mode)}</button>)}</div>
      <button className="btn btn-outline" disabled={index <= 0} onClick={() => {setPlaying(false);setDate(index-1);}}>Previous</button><button className="btn btn-outline" disabled={index >= dates.length-1} onClick={() => {setPlaying(false);setDate(index+1);}}>Next</button>
      <button className="btn btn-primary" onClick={() => {if (index >= dates.length-1) setDate(0);setPlaying(!playing);}}>{playing ? "Pause" : "Play"}</button>
      <label>As of <select aria-label="Replay date" value={date} onChange={event => {setPlaying(false);state.set("date",event.target.value);}}>{dates.map(day => <option key={day} value={day}>{formatDateLabel(day)}</option>)}</select></label>
      <label>Map axis <select aria-label="Map horizon" value={horizon} onChange={event => state.set("horizon",event.target.value)}><option value="60d">60D excess vs IHSG</option><option value="ytd">YTD excess vs IHSG</option></select></label>
      <input className="workspace-search" aria-label="Search groups" placeholder="Search groups or tickers…" value={state.params.get("q") ?? ""} onChange={event => state.set("q",event.target.value)}/>
    </div>
    {view !== "detail" && view !== "catalog" && <section className="research-map-layout">
      <div className="dash-card"><h2>{horizon.toUpperCase()} leadership map</h2><p className="meta">Up = 20D excess − 60D excess. {plotted.length} points · {listed.length} groups. Hollow marks have fewer than five contributors.</p>
        {plotted.length ? <svg className="research-map" viewBox="0 0 790 490" role="img" aria-label={`${kind} rotation plot: ${horizon.toUpperCase()} excess return versus IHSG against 20D minus 60D excess momentum`}>
          <rect x={64} y={40} width={px(0)-64} height={py(0)-40} fill="var(--tint-note)"/><rect x={px(0)} y={40} width={754-px(0)} height={py(0)-40} fill="var(--tint-ok)"/><rect x={64} y={py(0)} width={px(0)-64} height={425-py(0)} fill="var(--tint-flag)"/><rect x={px(0)} y={py(0)} width={754-px(0)} height={425-py(0)} fill="var(--surface-subtle)"/>
          <line x1={px(0)} x2={px(0)} y1={40} y2={425} stroke="var(--muted)"/><line x1={64} x2={754} y1={py(0)} y2={py(0)} stroke="var(--muted)"/>
          {[ranges.x[0],0,ranges.x[1]].map(value => <text key={`x${value}`} x={px(value)} y={450} textAnchor="middle">{value.toFixed(0)}%</text>)}{[ranges.y[0],0,ranges.y[1]].map(value => <text key={`y${value}`} x={58} y={py(value)} textAnchor="end">{value.toFixed(0)}%</text>)}
          <text x={75} y={57}>Improving</text><text x={744} y={57} textAnchor="end">Leading</text><text x={75} y={414}>Lagging</text><text x={744} y={414} textAnchor="end">Weakening</text>
          {plotted.map(item => rotationTrailSegments(item.group[cadence].filter(point => point.as_of <= date).slice(-5).map(point => ({...coordinates(point)}))).filter(segment => segment.length > 1).map((segment,i) => <polyline key={`${item.group.id}-${i}`} points={segment.map(point => `${px(point.x)},${py(point.y)}`).join(" ")} fill="none" stroke={item.color} opacity={selected?.id === item.group.id ? .9 : .25} strokeWidth={selected?.id === item.group.id ? 2.5 : 1.2}/>))}
          {plotted.map(item => <g key={item.group.id} role="button" tabIndex={0} aria-label={`${item.group.name}: ${formatPercent(item.x)} ${horizon} excess, ${formatPercent(item.y)} momentum, ${item.count} contributors`} onMouseEnter={() => setHovered(item.group.id)} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(item.group.id)} onBlur={() => setHovered(null)} onClick={() => choose(item.group.id)} onKeyDown={event => {if (event.key === "Enter" || event.key === " ") {event.preventDefault();choose(item.group.id);}}}>
            <circle cx={px(item.x)} cy={py(item.y)} r={selected?.id === item.group.id ? 8 : 5.5} fill={item.count < 5 ? "var(--surface)" : item.color} stroke={item.color} strokeWidth={selected?.id === item.group.id ? 3 : 2} strokeDasharray={item.count < 5 ? "3 2" : undefined}/><title>{item.group.name} · {formatPercent(item.x)} excess · {formatPercent(item.y)} momentum · {item.count} contributors</title>
          </g>)}
          {plotted.filter(item => item.group.id === (hovered ?? selected?.id)).map(item => <text key={item.group.id} x={Math.min(600,px(item.x)+10)} y={Math.max(70,py(item.y)-12)} className="selected-point-label">{item.group.name}</text>)}
          <text x={410} y={482} textAnchor="middle">{horizon.toUpperCase()} excess return vs IHSG (%)</text>
        </svg> : <p role="status">No supported coordinates for this horizon and date. The table retains every group and its available readings.</p>}
        <p className="meta">{["LEADING","IMPROVING","LAGGING","WEAKENING"].map(phase => `${formatEnumLabel(phase)} ${plotted.filter(item => rotationPhase(item.x,item.y) === phase).length}`).join(" · ")}. Empty quadrants reflect the data.</p>
      </div>
      <div className="dash-card research-rankings"><h2>20D rankings</h2><ol>{ranked.map(group => <li key={group.id}><Link to={href(group)}>{group.name}</Link><strong>{formatPercent(reading(group)?.excess_return_20d)}</strong><button className="btn btn-ghost" aria-label={`Inspect ${group.name}`} onClick={() => choose(group.id)}>Inspect</button></li>)}</ol></div>
    </section>}
    {(view === "catalog" || view === "map") && <section><h2>Group readings · {formatDateLabel(date)}</h2><WorkspaceTable rows={ranked} rowKey={group => group.id} columns={[
      {label:"Group",cell:group => <Link to={href(group)}>{group.name}</Link>},{label:"Leadership",cell:group => formatEnumLabel(reading(group)?.leadership)},
      {label:"Rotation phase",cell:group => {const xy=coordinates(reading(group)); return formatEnumLabel(rotationPhase(xy.x,xy.y));}},
      {label:"20D excess",cell:group => formatPercent(reading(group)?.excess_return_20d)},{label:"60D excess",cell:group => formatPercent(reading(group)?.excess_return_60d)},
      {label:"YTD excess",cell:group => formatPercent(reading(group)?.excess_return_ytd)},{label:"Breadth",cell:group => formatPercent(reading(group)?.breadth_pct)},
      {label:"20D contributors / members",cell:group => `${reading(group)?.contributor_counts?.["20d"] ?? reading(group)?.breadth_denominator ?? 0} / ${group.members.length}`},
      {label:"Coverage",cell:group => !reading(group)?.breadth_denominator ? "No matched price cohort" : (reading(group)?.breadth_denominator ?? 0)<5 ? "Descriptive · signal below five" : "Signal eligible"},
    ]}/></section>}
    {selected && <section className="research-detail">
      <div className="section-title-row"><h2><Link to={href(selected)}>{selected.name}</Link> · {formatDateLabel(date)}</h2><label>Inspect group <select aria-label="Inspect group" value={selected.id} onChange={event => choose(event.target.value)}>{ranked.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label></div>
      {selected.definition && <p>{selected.definition}</p>}
      <div className="workspace-stats">{[["20D excess",formatPercent(active?.excess_return_20d)],["60D excess",formatPercent(active?.excess_return_60d)],["Leadership",formatEnumLabel(active?.leadership)],["Rotation phase",formatEnumLabel(rotationPhase(coordinates(active).x,coordinates(active).y))],["Diffusion",formatEnumLabel(active?.diffusion_v2)],["Top-three concentration",formatPercent(active?.concentration_top3_pct)]].map(([label,value]) => <div className="workspace-stat" key={label}><span className="meta">{label}</span><strong>{value}</strong></div>)}</div>
      <p className="meta">{count} / {selected.members.length} contribute to 20D returns. Rotation uses its shared 20D/60D cohort. Leadership uses 20D excess and 5D−60D acceleration with a 1 pp threshold; it requires five contributors. Rotation phase uses the signs of the displayed coordinates.</p>
      <p className="meta">Horizon contributors: {Object.entries(active?.contributor_counts ?? {}).filter(([key]) => ["5d","20d","60d","ytd"].includes(key)).map(([key,n]) => `${key.toUpperCase()} ${n}/${selected.members.length}`).join(" · ")}. Participation comparison: {active?.breadth_denominator ?? 0} paired names; denominator changes remain visible in the replay table.</p>
      <label>Compare group <select aria-label="Compare group" value={comparison?.id ?? ""} onChange={event => state.set("compare",event.target.value)}><option value="">IHSG only</option>{groups.filter(group => group.id !== selected.id).map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
      <ResearchChart histories={state.histories} benchmark={state.benchmark} members={selected.members.map(member => member.ticker)} cohorts={scope === "market" ? selected.cohorts : undefined} date={date} title="Price performance vs IHSG" actions={scope === "sectors" ? actions : []} comparison={comparison ? {name: comparison.name, members: comparison.members.map(member => member.ticker), cohorts: scope === "market" ? comparison.cohorts : undefined} : undefined}/>
      <details className="dash-card"><summary>20D concentration · {attribution.length} contributors</summary><p className="meta">Each name’s absolute price move divided by the sum of absolute moves in the actual 20D return cohort. This measures concentration of price moves, rather than index weights. A zero gross move leaves shares unavailable.</p><WorkspaceTable rows={attribution} rowKey={row => row.ticker} columns={[{label:"Stock",cell:row => <Link to={`/ticker/${row.ticker}?scope=${scope}&date=${date}&cadence=${cadence}&horizon=${horizon}`}>{row.ticker}</Link>},{label:"20D stock return",cell:row => formatPercent(row.return_pct,2)},{label:"Share of absolute moves",cell:row => formatPercent(row.absolute_share_pct,2)}]}/></details>
      <section className="dash-card"><h2>Participation beneath the price</h2><p className="meta">Integer counts, with identical names at both ends of each comparison. A missing first comparison remains unavailable.</p><div style={{height:240}}><ResponsiveContainer width="100%" height="100%"><LineChart data={selected[cadence].filter(point => point.as_of <= date)}><CartesianGrid stroke="var(--line)"/><XAxis dataKey="as_of" tickFormatter={formatDateLabel} minTickGap={45}/><YAxis domain={[0,100]} tickFormatter={value => `${value}%`}/><Tooltip labelFormatter={value => formatDateLabel(String(value))} formatter={value => `${Number(value).toFixed(1)}%`}/><ReferenceLine y={50}/><Line dataKey="breadth_pct" name="Outperforming IHSG" stroke="var(--up)" connectNulls={false} isAnimationActive={false} dot/></LineChart></ResponsiveContainer></div></section>
      <div className="table-scroll"><table className="matched-replay-table"><thead><tr>{["As of","20D excess","60D excess","Breadth","Count / cohort","Breadth change","Leadership","Diffusion"].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{selected[cadence].filter(point => point.as_of <= date).map(point => <tr key={point.as_of}><td>{formatDateLabel(point.as_of)}</td><td>{formatPercent(point.excess_return_20d)}</td><td>{formatPercent(point.excess_return_60d)}</td><td>{formatPercent(point.breadth_pct)}</td><td>{point.breadth_count ?? "—"} / {point.breadth_denominator}</td><td>{point.breadth_change_pp == null ? "Comparison unavailable" : `${point.breadth_change_pp.toFixed(1)} pp`}</td><td>{formatEnumLabel(point.leadership)}</td><td>{formatEnumLabel(point.diffusion_v2)}</td></tr>)}</tbody></table></div>
      <h2>Constituents · {selected.members.length}</h2><WorkspaceTable rows={selected.members} rowKey={member => member.ticker} columns={[
        {label:"Stock",cell:member => <Link to={`/ticker/${member.ticker}?scope=${scope}&date=${date}&cadence=${cadence}&horizon=${horizon}`}>{member.ticker.replace(/\.JK$/," ").trim()}</Link>},{label:"Company",cell:member => member.name},
        {label:"20D contribution",cell:member => {const nativeRow=coreGroup?.contributors.find(row => row.ticker === member.ticker); return nativeRow ? formatPercent(nativeRow.returns["20d"].excess_return_pct) : selected.cohorts["20d"]?.includes(member.ticker) ? "Included" : "Excluded";}},
        {label:"60D contribution",cell:member => {const nativeRow=coreGroup?.contributors.find(row => row.ticker === member.ticker); return nativeRow ? formatPercent(nativeRow.returns["60d"].excess_return_pct) : selected.cohorts["60d"]?.includes(member.ticker) ? "Included" : "Excluded";}},
        {label:"Coverage / evidence",cell:member => {const row=coreGroup?.contributors.find(row => row.ticker === member.ticker); const exclusions=row ? (["5d","20d","60d"] as const).flatMap(h => row.returns[h].exclusion_reason ? [`${h.toUpperCase()}: ${row.returns[h].exclusion_reason!.replace(/_/g," ")}`] : []).join("; ") : selected.coverageReasons[member.ticker];return <>{exclusions || "Matched observations"}{member.evidence?.map((evidence,i) => <div key={i}>{evidence.relationship} {evidence.source?.startsWith("https://") && <a href={evidence.source} target="_blank" rel="noreferrer noopener">Source · {formatDateLabel(evidence.source_as_of)}</a>}</div>)}</>;}}
      ]}/>
    </section>}
    {scope === "sectors" && <section className="dash-card"><h2>YTD coverage · through {formatDateLabel(ytd?.end_date ?? state.native?.as_of)}</h2><p>{ytdStocks.length} of {ytdStockCount} stocks in the original set have a matching prior-year baseline and an action-free window. {ytd?.groups?.filter(group => group.eligible_contributors >= 5).length ?? 0} of 11 sectors meet the five-contributor YTD floor. Baseline: {formatDateLabel(ytd?.baseline_date)}. These readings keep their own end date during replay.</p><WorkspaceTable rows={ytdStocks} rowKey={row => row.ticker} columns={[{label:"Stock",cell:row => <Link to={`/ticker/${row.ticker}?scope=sectors&date=${date}&cadence=${cadence}&horizon=ytd`}>{row.ticker}</Link>},{label:"Sector",cell:row => <Link to={`/explorer?scope=sectors&taxonomy=SECTOR&group=${encodeURIComponent(row.sector)}&date=${date}&cadence=${cadence}&horizon=ytd`}>{row.sector}</Link>},{label:"Raw-price return",cell:row => formatPercent(row.return_pct,2)},{label:"Excess vs IHSG",cell:row => formatPercent(row.excess_return_pct,2)}]}/></section>}
    <details className="dash-card"><summary>Coverage and calculation methods</summary><p>{scope === "sectors" ? `${sectorStockCount} stocks across 11 IDX sectors, ${stocksPerSector} per sector by market-cap ranking on 2 October 2026. The ranking is applied retrospectively. Prices are raw Sectors closes; affected corporate-action windows are excluded from signals. Native Sectors IHSG observations supply the benchmark. YTD and company-level Sectors flow remain limited to the original ${ytdStockCount} stocks.` : "Broader IDX context uses the validated Yahoo Finance adjusted-price panel and dated classifications or disclosed relationships. Current memberships are applied retrospectively; group baskets are not official IDX sector indices."}</p><p>Each horizon has its own eligible cohort. Confirmed leadership and diffusion require five contributors. Descriptive map points retain smaller groups. No missing coordinate or price is replaced with zero.</p><p>Ownership, affiliation, and legal control are distinct relationships, with separately dated evidence. Source documentation is available under <Link to="/sources">Coverage &amp; sources</Link>.</p></details>
  </main>;
}
