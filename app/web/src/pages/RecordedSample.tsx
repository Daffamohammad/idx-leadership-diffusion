import { useMemo } from "react";
import { formatDateLabel, formatIdrCompact, formatPercent } from "../data/format";
import { useRecordedSectorsSample } from "../data/marketWorkspace";
import { useSnapshot } from "../data/SnapshotProvider";
import { WorkspaceTable } from "../components/WorkspaceTable";

const q3Start = "2026-07-01";

function returnSinceQ3(rows: Array<{ date: string; close: number }>) {
  const base = [...rows].filter(row => row.date <= q3Start).at(-1)
    ?? rows.find(row => row.date > q3Start && row.date <= "2026-07-08");
  const latest = [...rows].sort((a, b) => a.date.localeCompare(b.date)).at(-1);
  if (!base || !latest || base.close <= 0) return null;
  return (latest.close / base.close - 1) * 100;
}

export default function RecordedSample() {
  const { loading: snapshotLoading, error: snapshotError } = useSnapshot();
  const sampleState = useRecordedSectorsSample();
  const sample = sampleState.data;
  const rows = useMemo(() => (sample?.stocks ?? []).map(stock => ({
    ...stock,
    q3_return: returnSinceQ3(stock.prices),
    last_close: [...stock.prices].sort((a, b) => a.date.localeCompare(b.date)).at(-1)?.close ?? null,
  })).sort((a, b) => a.sector.localeCompare(b.sector) || a.ticker.localeCompare(b.ticker)), [sample]);

  if (snapshotError || sampleState.error) return <main className="workspace-page"><h1>Recorded Sectors sample</h1><p role="alert" className="meta">The selected release could not be verified: {sampleState.error ?? snapshotError}</p></main>;
  if (!sample && (snapshotLoading || sampleState.loading)) return <main className="workspace-page"><p className="meta" role="status">Loading the selected release.</p></main>;
  if (!sample) return <main className="workspace-page"><h1>Recorded Sectors sample</h1><p className="meta">The selected immutable release does not include a recorded Sectors sample.</p></main>;

  const quarter = sample.foreign_reconciliation.complete_quarter;
  const ytd = sample.foreign_reconciliation.sectors_ytd;
  const q3Sessions = sample.foreign_flow.complete_quarter.session_check.observed_sessions;
  const sectorReturns = rows.map(row => row.q3_return).filter((value): value is number => value !== null);

  return <main className="content-shell-wide recorded-sample-page">
    <header className="submission-page-heading">
      <div><div className="eyebrow-muted">Sectors API · recorded acquisition</div><h1>{sample.label}</h1><p>{sample.scope}</p></div>
      <div className="recorded-session"><span>Observed completed session</span><strong>{formatDateLabel(sample.as_of)}</strong><span>Selection frozen {formatDateLabel(sample.selection.membership_release_session)} · membership reference {formatDateLabel(sample.selection.membership_as_of)}</span></div>
    </header>
    <section className="recorded-summary-grid" aria-label="Recording summary">
      <article><span>Selected stocks</span><strong>{sample.stocks.length}</strong><small>6 per sector · market-cap order pinned to {formatDateLabel(sample.selection.selected_market_cap_date)}</small></article>
      <article><span>Price observations</span><strong>{formatDateLabel(sample.price_history.start)} → {formatDateLabel(sample.price_history.end)}</strong><small>Raw Sectors close · corporate actions are disclosed below</small></article>
      <article><span>Official IDX foreign flow</span><strong>{formatIdrCompact(sample.foreign_reconciliation.official_ytd.total_idr)}</strong><small>YTD through {formatDateLabel(sample.foreign_reconciliation.official_ytd.as_of)} · IDR net flow</small></article>
      <article><span>Sectors Q3 market flow</span><strong>{formatIdrCompact(quarter.sectors_sum_idr)}</strong><small>{formatDateLabel(quarter.start)} → {formatDateLabel(quarter.end)} · {q3Sessions} verified sessions</small></article>
    </section>
    <section className="recorded-section">
      <div className="section-title-row"><div><div className="eyebrow-muted">Computed sample</div><h2>Selected-stock Q3 price readings</h2></div><span className="eyebrow-muted">{sectorReturns.length} of {rows.length} stocks with a Q3 base close</span></div>
      <p className="meta">Returns compare each selected stock’s last close on or before 1 July 2026 with its latest recorded close. Equal samples describe these 66 names; they are not market-cap weighted. Raw close data are not adjusted for corporate actions.</p>
      <WorkspaceTable rows={rows} rowKey={row => row.ticker} columns={[
        { label: "Sector", cell: row => row.sector },
        { label: "Ticker", cell: row => row.ticker.replace(".JK", "") },
        { label: "Company", cell: row => row.company_name ?? "—" },
        { label: "Latest close · IDR", cell: row => row.last_close?.toLocaleString("en-US") ?? "—" },
        { label: "Q3-to-session return", cell: row => row.q3_return === null ? "—" : formatPercent(row.q3_return, 2) },
      ]} />
    </section>
    <section className="recorded-section">
      <div className="section-title-row"><div><div className="eyebrow-muted">Separate market-level providers</div><h2>Foreign-flow reconciliation</h2></div><span className="eyebrow-muted">IDR · positive = net foreign buying</span></div>
      <div className="flow-reconciliation-grid">
        <article><h3>Official IDX · Q3</h3><strong>{formatIdrCompact(quarter.official_sum_idr)}</strong><p>Daily IDX values summed over {formatDateLabel(quarter.start)} → {formatDateLabel(quarter.end)} · {quarter.session_count} sessions</p></article>
        <article><h3>Sectors · IHSG · Q3</h3><strong>{formatIdrCompact(quarter.sectors_sum_idr)}</strong><p>Daily Sectors values over the same {quarter.session_count} sessions</p></article>
      </div>
      <div className="recorded-reconciliation">
        <p>Matched Q3 comparison: {formatDateLabel(quarter.start)} → {formatDateLabel(quarter.end)} · {quarter.session_count} shared sessions · difference {formatIdrCompact(quarter.difference_idr)} · {quarter.status === "MATCHED" ? "same total" : "source difference retained"}.</p>
        <details><summary>Sources, method and remaining difference</summary><ul>
          <li>Official IDX is the public release series and remains the default foreign-flow view.</li>
          <li>Sectors values come from its IHSG market-flow endpoint. The Q3 comparison uses identical native IHSG session dates and daily IDR net flow.</li>
          <li>Official IDX YTD is {formatIdrCompact(sample.foreign_reconciliation.official_ytd.total_idr)} through {formatDateLabel(sample.foreign_reconciliation.official_ytd.as_of)}.</li>
          <li>The Sectors YTD response contains {ytd.observed_sessions} of {ytd.expected_sessions} expected sessions; its known-value sum ({formatIdrCompact(ytd.known_value_sum_idr)}) is not compared with the complete official YTD total.</li>
          <li>Sessions absent from the Sectors YTD response after a targeted check: {ytd.missing_dates.map(formatDateLabel).join(", ")}.</li>
          <li>Matched Q3 difference: {formatIdrCompact(quarter.difference_idr)}. The providers remain separate; no offset, scaling, zero-fill, or imputation is applied.</li>
          <li>Raw-response hashes, request windows, session continuity, and the persistent request receipt are included in the recorded acquisition archive.</li>
          {sample.foreign_reconciliation.limitations.map(item => <li key={item}>{item}</li>)}
          {sample.limitations.map(item => <li key={item}>{item}</li>)}
        </ul></details>
      </div>
    </section>
    <section className="recorded-section">
      <div className="section-title-row"><div><div className="eyebrow-muted">Membership reference</div><h2>Six stocks in each IDX sector</h2></div><span className="eyebrow-muted">As of {formatDateLabel(sample.selection.membership_as_of)}</span></div>
      <div className="sector-sample-grid">{Object.entries(sample.selection.sector_counts).map(([sector, count]) => <div key={sector}><span>{sector}</span><strong>{count}</strong></div>)}</div>
    </section>
  </main>;
}
