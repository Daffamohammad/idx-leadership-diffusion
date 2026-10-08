import { useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ResponsiveContainer, Treemap, type TreemapNode } from "recharts";
import { useSnapshot } from "../data/SnapshotProvider";
import { useWorkspaceAsset, type MarketWorkspace, type MarketStock } from "../data/marketWorkspace";
import { formatDateLabel, formatPercent } from "../data/format";
import { WorkspaceTable } from "../components/WorkspaceTable";
import TradingViewStockHeatmap from "../components/TradingViewStockHeatmap";

function tileColor(value: number | null) {
  if (value === null) return "#646b72";
  if (value === 0) return "#454d56";
  const magnitude = Math.min(1, Math.abs(value) / 8);
  return value > 0 ? `rgb(${Math.round(42 - magnitude * 20)},${Math.round(88 + magnitude * 42)},${Math.round(70 + magnitude * 23)})` : `rgb(${Math.round(97 + magnitude * 62)},${Math.round(45 - magnitude * 10)},${Math.round(57 - magnitude * 12)})`;
}
export default function StockHeatmap() {
  const [params, setParams] = useSearchParams();
  const view = params.get("view") === "tradingview" ? "tradingview" : "snapshot";
  const tvColor = params.get("tv-color") === "YTD" ? "ytd" : "daily";
  const setPageParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    setParams(next, { replace: true });
  };

  return (
    <main className="workspace-page">
      <header>
        <h1>Stock heatmap</h1>
        <p className="meta">Compare TradingView’s Indonesia market view with the app’s dated IDX observations.</p>
      </header>
      <div className="heatmap-view-switch" role="group" aria-label="Heatmap source">
        <button type="button" className="btn btn-outline" aria-pressed={view === "tradingview"} onClick={() => setPageParam("view", "tradingview")}>TradingView</button>
        <button type="button" className="btn btn-outline" aria-pressed={view === "snapshot"} onClick={() => setPageParam("view", "snapshot")}>IDX stocks</button>
      </div>
      {view === "tradingview" ? (
        <>
          <div className="heatmap-view-switch" role="group" aria-label="TradingView heatmap color period">
            <button type="button" className="btn btn-outline" aria-pressed={tvColor === "daily"} onClick={() => setPageParam("tv-color", "daily")}>Daily change</button>
            <button type="button" className="btn btn-outline" aria-pressed={tvColor === "ytd"} onClick={() => setPageParam("tv-color", "YTD")}>YTD performance</button>
          </div>
          <TradingViewStockHeatmap color={tvColor} />
        </>
      ) : <SnapshotStockHeatmap />}
    </main>
  );
}

function SnapshotStockHeatmap() {
  const snapshot = useSnapshot(); const { data, error, loading } = useWorkspaceAsset<MarketWorkspace>("market");
  const [params, setParams] = useSearchParams(); const navigate = useNavigate();
  const kind = params.get("taxonomy") === "KONGLO" ? "KONGLO" : params.get("taxonomy") === "THEMES" ? "THEMES" : "MARKET";
  const weekly = params.get("period") === "weekly"; const query = (params.get("search") ?? "").toLowerCase(); const group = params.get("group") ?? "";
  const setParam = (key: string, value: string) => { const next = new URLSearchParams(params); value ? next.set(key, value) : next.delete(key); if (key === "taxonomy") next.delete("group"); setParams(next, { replace: true }); };
  const groups = useMemo(() => {
    const result = new Map<string, { name: string; rows: MarketStock[] }>();
    if (!data) return result;
    const stocks = new Map(data.records.filter(r => r.analysis_requested).map(r => [r.ticker, r]));
    if (kind === "MARKET") for (const row of stocks.values()) { const name = row.taxonomy.sector || "Unclassified"; const entry = result.get(name) ?? { name, rows: [] }; entry.rows.push(row); result.set(name, entry); }
    else for (const membership of snapshot.data?.taxonomyViews[kind.toLowerCase()]?.memberships ?? []) {
      const row = stocks.get(membership.ticker); if (!row) continue;
      const entry = result.get(membership.taxonomy_group_id) ?? { name: membership.taxonomy_group_name, rows: [] };
      if (!entry.rows.some(r => r.ticker === row.ticker)) entry.rows.push(row);
      result.set(membership.taxonomy_group_id, entry);
    }
    return result;
  }, [data, kind, snapshot.data]);
  const selected = [...groups.entries()].filter(([id]) => !group || id === group).map(([id, g]) => ({ id, name: g.name, rows: g.rows.filter(r => !query || `${r.ticker} ${r.company_name}`.toLowerCase().includes(query)) }));
  const rows = [...new Map(selected.flatMap(g => g.rows).map(r => [r.ticker, r])).values()].sort((a,b)=>(b.market_cap ?? 0)-(a.market_cap ?? 0));
  const value = (r: MarketStock) => weekly ? r.return_1w : r.return_1d;
  const tiles = selected.map(g => ({ name: g.name, groupId: g.id, children: g.rows.filter(r => r.market_cap !== null && r.market_cap > 0).map(r => ({ name: r.ticker.replace(".JK", ""), ticker: r.ticker, size: r.market_cap!, change: value(r), company: r.company_name, price: r.close })) })).filter(g=>g.children.length);
  const content = (node: TreemapNode) => {
    if (node.depth === 0) return <g/>;
    const leaf = typeof node.ticker === "string"; const change = typeof node.change === "number" ? node.change : null;
    const activate = () => leaf ? navigate(`/ticker/${node.ticker}`) : setParam("group", String(node.groupId));
    return <g role="button" tabIndex={node.width > 20 && node.height > 20 ? 0 : -1} aria-label={leaf ? `${node.name}, ${formatPercent(change, 2)}, open ticker` : `${node.name}, open group`} onClick={activate} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(); } }} style={{ cursor: "pointer" }}>
      <title>{leaf ? `${node.name} · ${node.company} · ${formatPercent(change,2)} · IDR ${node.price}` : node.name}</title>
      <rect x={node.x} y={node.y} width={node.width} height={node.height} fill={leaf ? tileColor(change) : "var(--surface-subtle)"} stroke="var(--surface)"/>
      {leaf && node.width > 48 && node.height > 32 && <text x={node.x+node.width/2} y={node.y+node.height/2} textAnchor="middle" fill="white" fontSize={node.width>110?15:11} fontWeight={600}>{node.name}</text>}
      {leaf && node.width > 58 && node.height > 55 && <text x={node.x+node.width/2} y={node.y+node.height/2+17} textAnchor="middle" fill="white" fontSize={11}>{formatPercent(change,2)}</text>}
      {!leaf && node.width > 80 && <text x={node.x+8} y={node.y+15} fill="var(--ink)" fontSize={11}>{node.name.length > node.width/7 ? `${node.name.slice(0,Math.floor(node.width/7)-1)}…` : node.name}</text>}
    </g>;
  };
  return <><p className="meta">{data ? `As of ${formatDateLabel(data.as_of)} · end-of-day` : "Dated IDX market data"}. Tile size uses listed-share market cap; color uses stock price returns.</p>
    <div className="workspace-controls" role="group" aria-label="Heatmap taxonomy">{(["MARKET","KONGLO","THEMES"] as const).map(k=><button key={k} className="btn btn-outline" aria-pressed={kind===k} onClick={()=>setParam("taxonomy",k)}>{k==="MARKET"?"Market":k==="KONGLO"?"Konglo":"Themes"}</button>)}</div>
    <div className="workspace-controls"><div role="group" aria-label="Heatmap return period"><button className="btn btn-outline" aria-pressed={!weekly} onClick={()=>setParam("period","daily")}>Daily</button><button className="btn btn-outline" aria-pressed={weekly} onClick={()=>setParam("period","weekly")}>Weekly</button></div><label>Group <select className="workspace-search" value={group} onChange={e=>setParam("group",e.target.value)}><option value="">All groups</option>{[...groups].sort((a,b)=>a[1].name.localeCompare(b[1].name)).map(([id,g])=><option key={id} value={id}>{g.name} · {g.rows.length}</option>)}</select></label><input className="workspace-search" aria-label="Search heatmap ticker or company" placeholder="Search ticker or company…" value={params.get("search")??""} onChange={e=>setParam("search",e.target.value)}/></div>
    {!data ? <p aria-live="polite">{loading?"Loading stock observations…":error}</p> : <>
      <p className="meta">{rows.length} matching stocks · {rows.filter(r=>value(r)!==null).length} with a plotted return. {weekly?`Five-session adjusted-price return from ${formatDateLabel(data.weekly_start)}.`:"Daily official close versus previous close, including unchanged untraded quotes."} Konglo portfolios can overlap. IDXIC subindustries are dated 27 Aug 2026.</p>
      <section className="dash-card" aria-label="Hierarchical stock heatmap"><div style={{height:620,minWidth:0}}>{tiles.length?<ResponsiveContainer width="100%" height="100%"><Treemap data={tiles} dataKey="size" nameKey="name" nodeInset={20} nodeGap={1} content={content} isAnimationActive={false}/></ResponsiveContainer>:<p>No sized stocks match these filters.</p>}</div><div className="workspace-controls" aria-label="Heatmap legend">{[-8,-4,0,4,8,null].map(v=><span key={String(v)} style={{padding:"6px 12px",background:tileColor(v),color:"white",fontSize:11}}>{v===null?"—":`${v>0?"+":""}${v}%`}</span>)}</div></section>
      <section><h2>All matching stocks</h2><p className="meta">The table includes small tiles and rows without a calculated return.</p><WorkspaceTable rows={rows} rowKey={r=>r.ticker} columns={[{label:"Stock",cell:r=><Link to={`/ticker/${r.ticker}`}>{r.ticker.replace(".JK","")}</Link>},{label:"Company",cell:r=>r.company_name},{label:weekly?"Weekly":"Daily",cell:r=><span className={(value(r)??0)<0?"negative":"positive"}>{formatPercent(value(r),2)}</span>},{label:"Market cap · IDR",cell:r=>r.market_cap?.toLocaleString()??"—"},{label:"History",cell:r=>r.history_status},{label:"Signal policy",cell:r=>r.signal_eligible?"Eligible":"Excluded"}]}/></section>
    </>}
  </>;
}
