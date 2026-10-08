import { Link } from "react-router";
import { publicCopy } from "../data/publicCopy";
import { useMemo } from "react";
import { formatDateLabel, formatIdrCompact } from "../data/format";
import { useRecordedSectorsSample, useSectorsSignalAnalysis } from "../data/marketWorkspace";
import { useSnapshot } from "../data/SnapshotProvider";
import { AssetLoadState } from "../components/AssetLoadState";
import { WorkspaceTable } from "../components/WorkspaceTable";

export default function RecordedSample() {
  const { loading: snapshotLoading, error: snapshotError } = useSnapshot();
  const sampleState = useRecordedSectorsSample();
  const analysisState = useSectorsSignalAnalysis();
  const sample = sampleState.data;
  const rows = useMemo(() => (sample?.stocks ?? []).map(stock => ({
    ...stock,
    last_close: [...stock.prices].sort((a, b) => a.date.localeCompare(b.date)).at(-1)?.close ?? null,
  })).sort((a, b) => a.sector.localeCompare(b.sector) || a.ticker.localeCompare(b.ticker)), [sample]);

  if (snapshotError || sampleState.error) return <main className="workspace-page"><h1>Coverage &amp; sources</h1><AssetLoadState label="Sectors source evidence" loading={false} error={sampleState.error ?? snapshotError} absentMessage="" /></main>;
  if (!sample && (snapshotLoading || sampleState.loading)) return <main className="workspace-page"><p className="meta" role="status">Loading coverage and sources…</p></main>;
  if (!sample) return <main className="workspace-page"><h1>Coverage &amp; sources</h1><p className="meta">Sectors source evidence is unavailable.</p></main>;

  const quarter = sample.foreign_reconciliation.complete_quarter;
  const ytd = sample.foreign_reconciliation.sectors_ytd;
  const q3Sessions = sample.foreign_flow.complete_quarter.session_check.observed_sessions;
  const stockCount = sample.selection.stock_count;
  const stocksPerSector = sample.selection.stocks_per_sector;
  const priceCoverage = sample.coverage?.price_history;
  const ytdCoverage = sample.coverage?.ytd;
  const companyFlowCoverage = sample.coverage?.company_flow ?? {
    stock_count: stockCount,
    start_date: sample.foreign_flow.stock_recent_start,
    end_date: sample.as_of,
  };
  const ytdStocks = analysisState.data?.ytd.groups?.flatMap(group => group.contributors.filter(row => row.eligible)) ?? [];
  const ytdStockCount = ytdCoverage?.stock_count ?? stockCount;

  return <main className="content-shell-wide recorded-sample-page">
    <header className="submission-page-heading">
      <div><div className="eyebrow-muted">IDX prices · Source: Sectors API</div><h1>Coverage &amp; sources</h1><p>{stockCount} stocks across 11 IDX sectors, {stocksPerSector} per sector by market-cap ranking. Data through {formatDateLabel(sample.as_of)}. This set defines the project’s research coverage; it does not represent every listed company.</p></div>
      <div className="recorded-session"><span>Data through</span><strong>{formatDateLabel(sample.as_of)}</strong><span>Market-cap ranking: {formatDateLabel(sample.selection.selected_market_cap_date)} · membership reference: {formatDateLabel(sample.selection.membership_as_of)}</span></div>
    </header>
    <section className="recorded-summary-grid" aria-label="Coverage summary">
      <article><span>Stocks across sectors</span><strong>{sample.stocks.length}</strong><small>{stocksPerSector} per sector · ranked by market capitalization on {formatDateLabel(sample.selection.selected_market_cap_date)}</small></article>
      <article><span>Replay price history</span><strong>{formatDateLabel(priceCoverage?.first_required_price_date ?? sample.price_history.start)} → {formatDateLabel(priceCoverage?.end_date ?? sample.price_history.end)}</strong><small>Raw Sectors closes · {priceCoverage?.daily_dates.length ?? "—"} daily and {priceCoverage?.weekly_dates.length ?? "—"} weekly dates · affected windows are excluded</small></article>
      <article><span>Official IDX foreign flow</span><strong>{formatIdrCompact(sample.foreign_reconciliation.official_ytd.total_idr)}</strong><small>YTD through {formatDateLabel(sample.foreign_reconciliation.official_ytd.as_of)} · IDR net flow</small></article>
      <article><span>IDX Q3 market flow</span><strong>{formatIdrCompact(quarter.sectors_sum_idr)}</strong><small>{formatDateLabel(quarter.start)} → {formatDateLabel(quarter.end)} · {q3Sessions} verified sessions · Source: Sectors API</small></article>
    </section>
    <section className="recorded-section" aria-label="Data sources">
      <div className="section-title-row"><div><div className="eyebrow-muted">Data sources</div><h2>Which source supports each view?</h2></div></div>
      <div className="flow-reconciliation-grid">
        <article><h3>Sectors API</h3><p>Raw stock closes, native IHSG closes, and corporate-action information for the sector dashboard. Company-level flow is also from Sectors API.</p></article>
        <article><h3>Official IDX publications</h3><p>The daily Stock Summary and Daily Statistics provide market movers and market-level foreign-flow figures. Dated ownership registers use IDX and KSEI disclosures.</p></article>
        <article><h3>Yahoo Finance · yfinance Python client</h3><p>Adjusted Yahoo Finance prices support the broader market and group comparisons. These readings use a different price basis and coverage from the Sectors dashboard.</p></article>
      </div>
    </section>
    <section className="recorded-section">
      <div className="section-title-row"><div><div className="eyebrow-muted">Stock closes</div><h2>Stocks in this set and their latest closes</h2></div><span className="eyebrow-muted">{rows.length} stocks</span></div>
      <p className="meta">Latest raw closes are shown with their dates. Return calculations and corporate-action exclusions are available in the dashboard. The ranking is applied retrospectively; it does not represent the full market.</p>
      <WorkspaceTable rows={rows} rowKey={row => row.ticker} countLabel="stocks" columns={[
        { label: "Sector", cell: row => <Link to={`/explorer?scope=sectors&taxonomy=SECTOR&group=${encodeURIComponent(row.sector)}&date=${sample.as_of}&cadence=daily&horizon=60d`}>{row.sector}</Link> },
        { label: "Ticker", cell: row => <Link to={`/ticker/${row.ticker}?scope=sectors&date=${sample.as_of}&cadence=daily&horizon=60d`}>{row.ticker.replace(".JK", "")}</Link> },
        { label: "Company", cell: row => row.company_name ?? "—" },
        { label: "Latest close · IDR", cell: row => row.last_close?.toLocaleString("en-US") ?? "—" },
        { label: "Price date", cell: row => formatDateLabel([...row.prices].sort((a, b) => a.date.localeCompare(b.date)).at(-1)?.date) },
      ]} />
    </section>
    <section className="recorded-section">
      <div className="section-title-row"><div><div className="eyebrow-muted">Separate market-level providers</div><h2>Foreign-flow reconciliation</h2></div><span className="eyebrow-muted">IDR · positive = net foreign buying</span></div>
      <p className="meta">Company-level Sectors flow covers {companyFlowCoverage.stock_count} stocks, from {formatDateLabel(companyFlowCoverage.start_date)} through {formatDateLabel(companyFlowCoverage.end_date)}. {stockCount > companyFlowCoverage.stock_count ? `Price history adds ${stockCount - companyFlowCoverage.stock_count} more stocks; company-level flow is unavailable for them.` : "Price and company-flow coverage include the same stocks."}</p>
      <div className="flow-reconciliation-grid">
        <article><h3>Official IDX · Q3</h3><strong>{formatIdrCompact(quarter.official_sum_idr)}</strong><p>Daily IDX values summed over {formatDateLabel(quarter.start)} → {formatDateLabel(quarter.end)} · {quarter.session_count} sessions</p></article>
        <article><h3>IDX · IHSG · Q3 · Sectors API</h3><strong>{formatIdrCompact(quarter.sectors_sum_idr)}</strong><p>Daily Sectors values over the same {quarter.session_count} sessions</p></article>
      </div>
      <div className="recorded-reconciliation">
        <p>Matched Q3 comparison: {formatDateLabel(quarter.start)} → {formatDateLabel(quarter.end)} · {quarter.session_count} shared sessions · difference {formatIdrCompact(quarter.difference_idr)} · {quarter.status === "MATCHED" ? "same total" : "source difference retained"}.</p>
        <details><summary>Sources, method and remaining difference</summary><ul>
          <li>Official IDX is the published series and remains the default foreign-flow view.</li>
          <li>Sectors values come from its IHSG market-flow endpoint. The Q3 comparison uses identical native IHSG session dates and daily IDR net flow.</li>
          <li>Official IDX YTD is {formatIdrCompact(sample.foreign_reconciliation.official_ytd.total_idr)} through {formatDateLabel(sample.foreign_reconciliation.official_ytd.as_of)}.</li>
          <li>The Sectors YTD response contains {ytd.observed_sessions} of {ytd.expected_sessions} expected sessions; its known-value sum ({formatIdrCompact(ytd.known_value_sum_idr)}) is not compared with the complete official YTD total.</li>
          <li>Sessions absent from the Sectors YTD response after a targeted check: {ytd.missing_dates.map(formatDateLabel).join(", ")}.</li>
          <li>Matched Q3 difference: {formatIdrCompact(quarter.difference_idr)}. The providers remain separate; no offset, scaling, zero-fill, or imputation is applied.</li>
          <li>Source links, date ranges, and the checks used for this comparison are listed with the release information.</li>
          {sample.foreign_reconciliation.limitations.map(item => <li key={item}>{publicCopy(item)}</li>)}
          {sample.limitations.map(item => <li key={item}>{publicCopy(item)}</li>)}
        </ul></details>
      </div>
    </section>
    <section className="recorded-section">
      <div className="section-title-row"><div><div className="eyebrow-muted">Narrower history</div><h2>YTD coverage</h2></div><span className="eyebrow-muted">Through {formatDateLabel(ytdCoverage?.end_date ?? sample.as_of)}</span></div>
      <p className="meta">YTD uses the original {ytdStockCount} stocks. {analysisState.loading ? "Eligible readings are loading." : analysisState.error ? "YTD readings are unavailable because their source data did not load." : `${ytdStocks.length} have an action-free return from ${formatDateLabel(ytdCoverage?.baseline_date ?? analysisState.data?.ytd.baseline_date)} through ${formatDateLabel(ytdCoverage?.end_date ?? sample.as_of)}.`} Missing baselines and action-affected windows remain excluded.</p>
    </section>
    <section className="recorded-section">
      <div className="section-title-row"><div><div className="eyebrow-muted">Membership reference</div><h2>{stocksPerSector} stocks in each IDX sector</h2></div><span className="eyebrow-muted">As of {formatDateLabel(sample.selection.membership_as_of)}</span></div>
      <div className="sector-sample-grid">{Object.entries(sample.selection.sector_counts).map(([sector, count]) => <div key={sector}><Link to={`/explorer?scope=sectors&taxonomy=SECTOR&group=${encodeURIComponent(sector)}&date=${sample.as_of}&cadence=daily&horizon=60d`}>{sector}</Link><strong>{count}</strong></div>)}</div>
    </section>
  </main>;
}
