import { useMemo } from "react";
import { Link, useSearchParams } from "react-router";
import { useWorkspaceAsset, type MarketStock } from "../data/marketWorkspace";
import { formatDateLabel } from "../data/format";

const CATEGORIES = [
  { id: "gainers", label: "Top gainers", field: "return_1d", direction: "desc", unit: "percent" },
  { id: "losers", label: "Top losers", field: "return_1d", direction: "asc", unit: "percent" },
  { id: "value", label: "Top value", field: "value_idr", direction: "desc", unit: "idr" },
  { id: "volume", label: "Top volume", field: "volume_shares", direction: "desc", unit: "shares" },
  { id: "frequency", label: "Top frequency", field: "frequency_trades", direction: "desc", unit: "trades" },
  { id: "foreign-buy", label: "Foreign net-buy shares", field: "foreign_net_shares", direction: "desc", unit: "shares" },
  { id: "foreign-sell", label: "Foreign net-sell shares", field: "foreign_net_shares", direction: "asc", unit: "shares" },
] as const;

type CategoryId = typeof CATEGORIES[number]["id"];
type Metric = number | null;

const integer = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("id-ID", { signDisplay: "always", minimumFractionDigits: 2, maximumFractionDigits: 2 });

function metric(row: MarketStock, category: CategoryId): Metric {
  if (category === "gainers" || category === "losers") return row.return_1d;
  if (category === "value") return row.value_idr;
  if (category === "volume") return row.volume_shares;
  if (category === "frequency") return row.frequency_trades;
  return row.foreign_net_shares;
}

function displayMetric(value: Metric, category: CategoryId): string {
  if (value === null || !Number.isFinite(value)) return "—";
  if (category === "gainers" || category === "losers") return `${percent.format(value)}%`;
  if (category === "value") return `Rp ${integer.format(value)}`;
  return integer.format(value);
}

function rowsForCategory(rows: MarketStock[], category: CategoryId, query = "", board = "all"): MarketStock[] {
  const spec = CATEGORIES.find(row => row.id === category)!;
  const eligible = rows.filter(row => row.traded && row.close !== null && metric(row, category) !== null &&
    (category === "gainers" || category === "losers" ? row.return_1d !== null : true) &&
    (!query || `${row.ticker} ${row.company_name}`.toLowerCase().includes(query)) &&
    (board === "all" || row.listing_board === board));
  const directional = category === "gainers" ? eligible.filter(row => row.return_1d! > 0)
    : category === "losers" ? eligible.filter(row => row.return_1d! < 0)
      : category === "foreign-buy" ? eligible.filter(row => row.foreign_net_shares! > 0)
        : category === "foreign-sell" ? eligible.filter(row => row.foreign_net_shares! < 0)
          : eligible;
  return [...directional].sort((a, b) => {
    const difference = metric(a, category)! - metric(b, category)!;
    return (spec.direction === "desc" ? -difference : difference) || a.ticker.localeCompare(b.ticker);
  }).slice(0, 25);
}

export default function MarketMovers() {
  const market = useWorkspaceAsset<import("../data/marketWorkspace").MarketWorkspace>("market");
  const [params, setParams] = useSearchParams();
  const category = CATEGORIES.some(row => row.id === params.get("rank")) ? params.get("rank") as CategoryId : "gainers";
  const query = (params.get("q") ?? "").trim().toLowerCase();
  const board = params.get("board") ?? "all";
  const boards = useMemo(() => [...new Set((market.data?.records ?? []).map(row => row.listing_board).filter((value): value is string => Boolean(value)))].sort(), [market.data]);
  const rows = useMemo(() => rowsForCategory(market.data?.records ?? [], category, query, board), [market.data, category, query, board]);
  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };
  const active = CATEGORIES.find(row => row.id === category)!;

  return (
    <main className="workspace-page movers-page">
      <header className="submission-page-heading"><div><div className="eyebrow-muted">Research · Official IDX Stock Summary</div><h1>Market movers</h1><p>Daily rankings from the selected release. Foreign activity is shown in shares; turnover value is shown in rupiah.</p></div><div className="movers-asof">Release date<strong>{market.data ? formatDateLabel(market.data.as_of) : "Loading"}</strong></div></header>
      <nav className="movers-tabs" aria-label="Market mover ranking">
        {CATEGORIES.map(item => <button key={item.id} type="button" aria-pressed={category === item.id} onClick={() => setParam("rank", item.id)}>{item.label}</button>)}
      </nav>
      <section className="dash-card movers-table-card">
        <div className="movers-toolbar"><div><div className="eyebrow-muted">Top 25 · {active.label}</div><h2>{active.label}</h2></div><div className="movers-filters"><input type="search" aria-label="Search ticker or company" placeholder="Search ticker or company…" value={params.get("q") ?? ""} onChange={event => setParam("q", event.target.value)} /><label><span>Board</span><select aria-label="Filter listing board" value={board} onChange={event => setParam("board", event.target.value)}><option value="all">All boards</option>{boards.map(value => <option key={value} value={value}>{value}</option>)}</select></label></div></div>
        {market.loading && <p role="status">Loading the selected release…</p>}
        {market.error && <p role="alert">This ranking could not be loaded: {market.error}</p>}
        {market.data && <>
          <div className="movers-result-count">Top {rows.length} of the filtered ranking · securities must have traded volume and a same-session official close</div>
          <div className="table-scroll"><table><thead><tr><th>#</th><th>Stock</th><th>Company</th><th>Board</th><th>Close</th><th>Daily change</th><th>Value · IDR</th><th>Volume · shares</th><th>Frequency</th><th>Foreign net · shares</th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.ticker}>
            <td>{index + 1}</td><td><Link to={`/ticker/${encodeURIComponent(row.ticker)}`}>{row.ticker.replace(/\.JK$/, "")}</Link></td><td>{row.company_name}</td><td>{row.listing_board ?? "—"}</td><td>{row.close === null ? "—" : `Rp ${integer.format(row.close)}`}</td><td className={(row.return_1d ?? 0) > 0 ? "positive" : "negative"}>{displayMetric(row.return_1d, "gainers")}</td><td>{row.value_idr === null ? "—" : integer.format(row.value_idr)}</td><td>{row.volume_shares === null ? "—" : integer.format(row.volume_shares)}</td><td>{row.frequency_trades === null ? "—" : integer.format(row.frequency_trades)}</td><td className={(row.foreign_net_shares ?? 0) >= 0 ? "positive" : "negative"}>{row.foreign_net_shares === null ? "—" : integer.format(row.foreign_net_shares)}</td>
          </tr>)}</tbody></table></div>
          {rows.length === 0 && <p className="movers-empty">No traded securities match this search and board.</p>}
          <details className="submission-source-details"><summary>Ranking definition and source</summary><p>Ranking fields come from IDX’s official Stock Summary for {market.data.as_of}. Same-session non-traded observations are excluded. Equal metric values use ticker order as the tie-breaker. A missing source field remains blank and is not ranked.</p><p>Daily change is close versus previous close. Value is IDR, volume and foreign buy/sell net are shares, and frequency is trade count.</p><p>Source record: {JSON.stringify(market.data.sources.stock_summary ?? market.data.sources)}</p></details>
        </>}
      </section>
    </main>
  );
}
