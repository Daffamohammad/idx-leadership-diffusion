import { useMemo } from "react";
import { Link, useSearchParams } from "react-router";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { useWorkspaceAsset, type ForeignHistory, type MarketWorkspace } from "../data/marketWorkspace";
import { formatDateLabel, formatIdrCompact } from "../data/format";
import { WorkspaceTable } from "../components/WorkspaceTable";

type Period = "1M" | "3M" | "QUARTER" | "YTD";

function previousCompleteQuarter(asOf: string) {
  const current = new Date(`${asOf}T00:00:00Z`);
  const currentQuarterMonth = Math.floor(current.getUTCMonth() / 3) * 3;
  const start = new Date(Date.UTC(current.getUTCFullYear(), currentQuarterMonth - 3, 1));
  const end = new Date(Date.UTC(current.getUTCFullYear(), currentQuarterMonth, 0));
  const iso = (date: Date) => date.toISOString().slice(0, 10);
  const quarter = Math.floor(start.getUTCMonth() / 3) + 1;
  return {
    start: iso(start),
    end: iso(end),
    label: `Q${quarter} ${start.getUTCFullYear()}`,
  };
}

function relativeStart(asOf: string, months: number) {
  const date = new Date(`${asOf}T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() - months);
  return date.toISOString().slice(0, 10);
}

export default function ForeignFlow() {
  const history = useWorkspaceAsset<ForeignHistory>("foreign");
  const market = useWorkspaceAsset<MarketWorkspace>("market");
  const [params, setParams] = useSearchParams();
  const data = history.data;
  const quarter = useMemo(
    () => (data ? previousCompleteQuarter(data.as_of) : null),
    [data?.as_of],
  );
  const ytdAvailable = Boolean(
    data?.validation.ytd_continuity
      && data.daily.some((row) => Number.isFinite(row.ytd_net_foreign_value_idr)),
  );
  const quarterRows = data && quarter
    ? data.daily.filter((row) => row.as_of >= quarter.start && row.as_of <= quarter.end)
    : [];
  const quarterAvailable = Boolean(data && quarter && data.validation.session_continuity
    && data.start <= quarter.start && data.as_of >= quarter.end
    && quarterRows.length >= 40
    && new Date(`${quarterRows[0]?.as_of}T00:00:00Z`).getTime() - new Date(`${quarter.start}T00:00:00Z`).getTime() <= 7 * 86400000
    && new Date(`${quarter.end}T00:00:00Z`).getTime() - new Date(`${quarterRows.at(-1)?.as_of}T00:00:00Z`).getTime() <= 7 * 86400000);
  const requestedPeriod = params.get("period");
  const period: Period = requestedPeriod === "YTD" && ytdAvailable
    ? "YTD"
    : requestedPeriod === "QUARTER" && quarterAvailable
      ? "QUARTER"
      : requestedPeriod === "1M"
        ? "1M"
        : "3M";
  const search = (params.get("search") ?? "").toLowerCase();

  const rangeStart = useMemo(() => {
    if (!data) return "";
    if (period === "YTD") return data.start;
    if (period === "QUARTER") return quarter?.start ?? data.start;
    return relativeStart(data.as_of, period === "1M" ? 1 : 3);
  }, [data, period, quarter]);
  const selected = useMemo(() => {
    if (!data) return [];
    if (period === "QUARTER") return quarterRows;
    return data.daily.filter((row) => row.as_of >= rangeStart);
  }, [data, period, quarterRows, rangeStart]);
  const total = period === "YTD"
    ? selected.at(-1)?.ytd_net_foreign_value_idr ?? null
    : selected.reduce((sum, row) => sum + row.net_foreign_value_idr, 0);
  const chart = useMemo(() => {
    let cumulative = 0;
    return selected.map((row) => {
      cumulative += row.net_foreign_value_idr;
      return {
        ...row,
        net: row.net_foreign_value_idr / 1e12,
        cumulative: (period === "YTD" ? row.ytd_net_foreign_value_idr : cumulative) / 1e12,
      };
    });
  }, [selected, period]);
  const buySessions = selected.filter((row) => row.net_foreign_value_idr > 0).length;
  const sellSessions = selected.filter((row) => row.net_foreign_value_idr < 0).length;
  const strongestBuy = selected.reduce<typeof selected[number] | null>(
    (best, row) => !best || row.net_foreign_value_idr > best.net_foreign_value_idr ? row : best,
    null,
  );
  const strongestSell = selected.reduce<typeof selected[number] | null>(
    (best, row) => !best || row.net_foreign_value_idr < best.net_foreign_value_idr ? row : best,
    null,
  );
  const stocks = (market.data?.records ?? [])
    .filter((row) => row.analysis_requested && row.foreign_net_shares !== null
      && (!search || `${row.ticker} ${row.company_name}`.toLowerCase().includes(search)))
    .sort((a, b) => b.foreign_net_shares! - a.foreign_net_shares!);
  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    setParams(next, { replace: true });
  };

  const periodLabel = period === "QUARTER" ? quarter?.label ?? "Previous quarter" : period;
  const periodStart = selected[0]?.as_of;
  const totalLabel = total === null ? "—" : formatIdrCompact(total);

  return (
    <main className="workspace-page foreign-flow-page">
      <header>
        <h1>Foreign flow</h1>
        <p className="meta">IDX-reported net foreign transaction value · all stock trading markets · {data ? formatDateLabel(data.as_of) : "Loading dated release"}</p>
      </header>

      <section className="dash-card foreign-flow-card">
        <div className="foreign-flow-card-heading">
          <div>
            <div className="eyebrow-muted">Market foreign flow</div>
            <h2>Net foreign buying and selling</h2>
          </div>
          <div className="workspace-controls foreign-flow-periods" role="group" aria-label="Foreign-flow period">
            {(["1M", "3M", "QUARTER", "YTD"] as const).map((item) => (
              <button
                key={item}
                type="button"
                className="btn btn-outline"
                aria-pressed={period === item}
                disabled={(item === "YTD" && !ytdAvailable) || (item === "QUARTER" && !quarterAvailable)}
                onClick={() => setParam("period", item)}
              >
                {item === "QUARTER" ? quarter?.label ?? "Last full quarter" : item}
              </button>
            ))}
          </div>
        </div>

        {!data ? (
          <p aria-live="polite">{history.loading ? "Loading verified daily flow…" : history.error}</p>
        ) : (
          <>
            <div className="foreign-flow-total" aria-live="polite">
              <div className="market-level">{totalLabel}</div>
              <div className="eyebrow-muted">{periodLabel} net</div>
            </div>
            <p className="meta foreign-flow-date-range">
              {period === "YTD"
                ? `Official YTD running total through ${formatDateLabel(data.as_of)}. Daily bars shown from ${formatDateLabel(data.start)}; the line carries IDX’s reported YTD balance, including earlier sessions.`
                : `Complete verified sessions · ${formatDateLabel(periodStart)} → ${formatDateLabel(selected.at(-1)?.as_of)} · positive is net foreign buying; negative is net foreign selling.`}
            </p>
            <div className="foreign-flow-readout" aria-label={`${periodLabel} activity summary`}>
              <div><span>Net-buy sessions</span><strong>{buySessions}</strong></div>
              <div><span>Net-sell sessions</span><strong>{sellSessions}</strong></div>
              <div><span>Largest buy day</span><strong>{strongestBuy ? `${formatIdrCompact(strongestBuy.net_foreign_value_idr)} · ${formatDateLabel(strongestBuy.as_of)}` : "—"}</strong></div>
              <div><span>Largest sell day</span><strong>{strongestSell ? `${formatIdrCompact(strongestSell.net_foreign_value_idr)} · ${formatDateLabel(strongestSell.as_of)}` : "—"}</strong></div>
            </div>
            {period === "YTD" && (
              <p className="foreign-flow-window-note">
                Session counts and daily bars above cover the displayed {selected.length}-session window from {formatDateLabel(data.start)}. The headline and line use IDX’s validated YTD cumulative values.
              </p>
            )}
            <div className="workspace-chart foreign-flow-chart" role="img" aria-label={`Daily net foreign flow and ${periodLabel} cumulative net, ${totalLabel}`}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chart} margin={{ top: 14, right: 20, left: 4, bottom: 8 }}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="as_of" tickFormatter={(value) => formatDateLabel(value).slice(0, 6)} minTickGap={45} tick={{ fontSize: 10 }} />
                  <YAxis yAxisId="net" orientation="right" tickFormatter={(value) => `${value}T`} width={48} tick={{ fontSize: 10 }} />
                  <YAxis yAxisId="cumulative" tickFormatter={(value) => `${value}T`} width={58} tick={{ fontSize: 10 }} />
                  <Tooltip
                    labelFormatter={(value) => formatDateLabel(String(value))}
                    formatter={(value, name) => [formatIdrCompact(Number(value) * 1e12), name === "net" ? "Daily net" : period === "YTD" ? "IDX YTD balance" : "Period cumulative net"]}
                  />
                  <ReferenceLine yAxisId="net" y={0} stroke="var(--muted)" />
                  <Bar yAxisId="net" dataKey="net" isAnimationActive={false}>
                    {chart.map((row) => <Cell key={row.as_of} fill={row.net >= 0 ? "var(--up)" : "var(--down)"} />)}
                  </Bar>
                  <Line yAxisId="cumulative" dataKey="cumulative" stroke="var(--ink)" dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <p className="meta foreign-flow-chart-note">
              Bars: daily net (right axis). Line: {period === "YTD" ? "IDX’s official running YTD net balance" : "cumulative net within the selected period"} (left axis). IDX daily PDFs report values rounded to IDR 0.01 billion; period sums retain that rounding.
            </p>
            <details className="foreign-flow-sources">
              <summary>Daily values and official IDX sources</summary>
              <WorkspaceTable rows={selected} rowKey={(row) => row.as_of} columns={[
                { label: "Session", cell: (row) => formatDateLabel(row.as_of) },
                { label: "Daily net · IDR", cell: (row) => formatIdrCompact(row.net_foreign_value_idr) },
                { label: "YTD net · IDR", cell: (row) => formatIdrCompact(row.ytd_net_foreign_value_idr) },
                { label: "Official source", cell: (row) => <a href={row.source.url} target="_blank" rel="noreferrer">IDX Daily Statistics</a> },
              ]} />
            </details>
          </>
        )}
      </section>

      <section>
        <h2>Stock foreign activity · shares</h2>
        <p className="meta">{market.data ? formatDateLabel(market.data.as_of) : ""} · latest official Stock Summary. These are share quantities, separate from the rupiah market-flow chart; no share quantity is converted to rupiah at a closing price.</p>
        <input className="workspace-search" aria-label="Search foreign-activity ticker" placeholder="Search ticker…" value={params.get("search") ?? ""} onChange={(event) => setParam("search", event.target.value)} />
        <WorkspaceTable rows={stocks} rowKey={(row) => row.ticker} columns={[
          { label: "Stock", cell: (row) => <Link to={`/ticker/${row.ticker}`}>{row.ticker.replace(".JK", "")}</Link> },
          { label: "Company", cell: (row) => row.company_name },
          { label: "Foreign buy · shares", cell: (row) => row.foreign_buy_shares?.toLocaleString() ?? "—" },
          { label: "Foreign sell · shares", cell: (row) => row.foreign_sell_shares?.toLocaleString() ?? "—" },
          { label: "Net · shares", cell: (row) => <span className={(row.foreign_net_shares ?? 0) < 0 ? "negative" : "positive"}>{row.foreign_net_shares?.toLocaleString() ?? "—"}</span> },
        ]} />
      </section>
    </main>
  );
}
