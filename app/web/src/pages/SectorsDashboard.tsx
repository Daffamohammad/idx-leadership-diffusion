import { useMemo, useState } from "react";
import { Link } from "react-router";
import {
  CartesianGrid,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { WorkspaceTable } from "../components/WorkspaceTable";
import { formatDateLabel, formatEnumLabel, formatPercent } from "../data/format";
import { useRecordedSectorsSample, useSectorsSignalAnalysis } from "../data/marketWorkspace";
import { useSnapshot } from "../data/SnapshotProvider";

type ReplayMode = "daily" | "weekly";

function actionSummary(reason: string | null) {
  if (!reason) return "Eligible";
  if (reason.startsWith("MECHANICAL_ACTION_")) return reason.replace("MECHANICAL_ACTION_", "Action: ").replace(/_/g, " ");
  return reason.replace(/_/g, " ").toLowerCase();
}

export default function SectorsDashboard() {
  const snapshot = useSnapshot();
  const sampleState = useRecordedSectorsSample();
  const analysisState = useSectorsSignalAnalysis();
  const [mode, setMode] = useState<ReplayMode>("daily");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const analysis = analysisState.data;
  const sample = sampleState.data;
  const replayRows = mode === "daily" ? analysis?.daily ?? [] : analysis?.weekly ?? [];
  const replay = replayRows.find(row => row.date === selectedDate) ?? replayRows.at(-1) ?? null;
  const groups = replay?.groups ?? [];
  const ranked = useMemo(() => [...groups].sort((left, right) => {
    const leftValue = left.returns["20d"].excess_return_pct;
    const rightValue = right.returns["20d"].excess_return_pct;
    if (leftValue === null && rightValue === null) return left.sector.localeCompare(right.sector);
    if (leftValue === null) return 1;
    if (rightValue === null) return -1;
    return rightValue - leftValue || left.sector.localeCompare(right.sector);
  }), [groups]);
  const sectors = groups.map(row => row.sector);
  const activeSector = sectors.includes(selectedSector ?? "") ? selectedSector : ranked[0]?.sector ?? null;
  const inspected = groups.find(row => row.sector === activeSector) ?? null;
  const ytdGroups = analysis?.ytd.groups ?? [];
  const ytdEligibleCount = ytdGroups.reduce((total, group) => total + group.eligible_contributors, 0);
  const ytdConfirmedCount = ytdGroups.filter(group => group.status === "PASS").length;
  const inspectedYtd = ytdGroups.find(group => group.sector === activeSector);
  const ytdByTicker = new Map((inspectedYtd?.contributors ?? []).map(row => [row.ticker, row]));
  const mapRows = groups.flatMap(group => group.map ? [{
    sector: group.sector,
    x: group.map.x_60d_excess_pct,
    y: group.map.y_relative_momentum_pct,
    state: group.leadership_state,
  }] : []);

  if (snapshot.error || sampleState.error || analysisState.error) {
    return <main className="workspace-page">
      <div className="eyebrow-muted">Sectors · primary workflow</div>
      <h1>Sectors analysis could not be verified</h1>
      <p role="alert" className="sectors-error">{analysisState.error ?? sampleState.error ?? snapshot.error}</p>
      <p className="meta">The dashboard is held until its recorded sample, frozen selection source, and analysis asset validate together.</p>
    </main>;
  }
  if (snapshot.loading || sampleState.loading || analysisState.loading) {
    return <main className="workspace-page"><p className="meta" role="status">Loading and verifying the selected Sectors release.</p></main>;
  }
  if (!sample) {
    return <main className="workspace-page">
      <div className="eyebrow-muted">Sectors · primary workflow</div>
      <h1>Recorded Sectors sample is absent</h1>
      <p className="meta">This immutable release does not include the 66-stock Sectors sample required for the primary workflow.</p>
    </main>;
  }
  if (!analysis) {
    return <main className="workspace-page">
      <div className="eyebrow-muted">Sectors · primary workflow</div>
      <h1>Sectors analysis is absent</h1>
      <p role="alert" className="meta">This release includes the recorded sample but does not include its verified Sectors analysis asset.</p>
    </main>;
  }

  return <main className="workspace-page sectors-dashboard">
    <header className="sectors-heading">
      <div>
        <div className="eyebrow-muted">Sectors API · Market Intelligence</div>
        <h1>Leadership beneath the index</h1>
        <p>Replay a frozen sample of 66 Indonesian stocks against native IHSG closes. The selected names are retained as one fixed membership set across the replay.</p>
      </div>
      <div className="sectors-asof">
        <span>Recorded through</span>
        <strong>{formatDateLabel(analysis.as_of)}</strong>
        <small>11 IDX sectors · 6 selected stocks each</small>
      </div>
    </header>

    <section className="sectors-disclosure" aria-label="Sample and calculation disclosures">
      <strong>Sample boundary</strong>
      <p>The 66 names were selected by market capitalization on {formatDateLabel(analysis.selection.selected_market_cap_date)} and are applied retrospectively. This is not a point-in-time market universe. Returns use raw Sectors closes and native Sectors IHSG closes; prices are not adjusted.</p>
      <p>Mechanical corporate-action windows and missing matched observations are excluded. Sector signals require at least five contributors. No missing value is filled.</p>
    </section>

    <section className="sectors-ytd" aria-label="Year-to-date coverage">
      {analysis.ytd.status === "PASS" ? <>
        <div><div className="eyebrow-muted">YTD raw-price coverage</div><strong>Baseline · {formatDateLabel(analysis.ytd.baseline_date)}</strong></div>
        <p>Through {formatDateLabel(analysis.ytd.end_date ?? analysis.as_of)}: native IHSG return {formatPercent(analysis.ytd.benchmark_return_pct ?? null, 2)}. {ytdEligibleCount} of 66 stocks have a matching baseline and action-free window; {ytdConfirmedCount} of 11 sector aggregates meet the five-contributor floor. Mechanical-action and missing-baseline windows remain excluded.</p>
      </> : <>
        <div><div className="eyebrow-muted">YTD coverage</div><strong>Baseline unavailable</strong></div>
        <p>{analysis.ytd.reason ?? "YTD remains unavailable until stock closes and native IHSG share an observed prior-year baseline."}</p>
      </>}
    </section>
    {analysis.ytd.status === "PASS" && <section className="sectors-section" aria-label="Year-to-date sector readings">
      <div className="sectors-section-heading">
        <div><div className="eyebrow-muted">Same-date baseline · raw unadjusted closes</div><h2>YTD sector readings</h2></div>
        <span className="sectors-meta">Only sectors with at least five eligible constituents receive an aggregate.</span>
      </div>
      <WorkspaceTable rows={ytdGroups} rowKey={row => row.sector} columns={[
        { label: "Sector", cell: row => row.sector },
        { label: "Eligible", cell: row => `${row.eligible_contributors} / ${row.requested_constituents}` },
        { label: "Stock return", cell: row => formatPercent(row.stock_return_pct, 2) },
        { label: "IHSG", cell: row => formatPercent(row.benchmark_return_pct, 2) },
        { label: "Excess return", cell: row => formatPercent(row.excess_return_pct, 2) },
        { label: "Status", cell: row => row.status === "PASS" ? "Confirmed" : "Unconfirmed · below five" },
      ]} />
    </section>}

    <section className="sectors-section" aria-labelledby="sector-ranking-heading">
      <div className="sectors-section-heading">
        <div><div className="eyebrow-muted">Current replay · {formatDateLabel(replay?.date)}</div><h2 id="sector-ranking-heading">Sector ranking by 20D excess return</h2></div>
        <span className="sectors-meta">Equal-weighted raw-price returns · benchmark: Sectors IHSG</span>
      </div>
      <WorkspaceTable rows={ranked} rowKey={row => row.sector} columns={[
        { label: "Rank", cell: row => ranked.findIndex(item => item.sector === row.sector) + 1 },
        { label: "Sector", cell: row => <button className="sector-name-button" type="button" onClick={() => setSelectedSector(row.sector)} aria-pressed={activeSector === row.sector}>{row.sector}</button> },
        { label: "20D excess", cell: row => <strong>{formatPercent(row.returns["20d"].excess_return_pct, 2)}</strong> },
        { label: "Stock return", cell: row => formatPercent(row.returns["20d"].stock_return_pct, 2) },
        { label: "IHSG", cell: row => formatPercent(row.returns["20d"].benchmark_return_pct, 2) },
        { label: "20D contributors", cell: row => `${row.contributor_counts["20d"]} / 6` },
        { label: "Leadership", cell: row => formatEnumLabel(row.leadership_state) },
        { label: "Diffusion", cell: row => `${formatEnumLabel(row.diffusion.state)}${row.diffusion.change_count === null ? "" : ` · ${row.diffusion.change_count > 0 ? "+" : ""}${row.diffusion.change_count}`}` },
      ]} />
    </section>

    <section className="sectors-section" aria-labelledby="sectors-map-heading">
      <div className="sectors-section-heading">
        <div><div className="eyebrow-muted">Leadership map · selected replay date</div><h2 id="sectors-map-heading">60D excess return and relative momentum</h2></div>
        <span className="sectors-meta">X: 60D excess · Y: 20D excess minus 60D excess</span>
      </div>
      <div className="sectors-map-chart">
        {mapRows.length ? <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 24, right: 24, bottom: 16, left: 8 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
            <XAxis type="number" dataKey="x" name="60D excess" unit="%" tick={{ fill: "var(--muted)", fontSize: 11 }} />
            <YAxis type="number" dataKey="y" name="Relative momentum" unit="%" tick={{ fill: "var(--muted)", fontSize: 11 }} />
            <ReferenceLine x={0} stroke="var(--muted)" strokeDasharray="4 4" />
            <ReferenceLine y={0} stroke="var(--muted)" strokeDasharray="4 4" />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={value => formatPercent(Number(value), 2)} labelFormatter={(_, payload) => payload?.[0]?.payload?.sector ?? ""} />
            <Scatter name="Sector" data={mapRows} fill="#2c776d">
              <LabelList dataKey="sector" position="top" fill="var(--ink)" fontSize={10} />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer> : <p className="meta">Fewer than five names have matched 20D and 60D readings for this map date.</p>}
      </div>
      <p className="sectors-meta">A blank sector is unconfirmed because its matched 20D/60D cohort is below five contributors.</p>
    </section>

    <section className="sectors-section" aria-labelledby="sectors-replay-heading">
      <div className="sectors-section-heading">
        <div><div className="eyebrow-muted">Daily and weekly replay</div><h2 id="sectors-replay-heading">Replay the recorded market</h2></div>
      </div>
      <div className="sectors-replay-controls">
        <div role="group" aria-label="Replay frequency" className="workspace-controls">
          <button className="btn btn-outline" aria-pressed={mode === "daily"} onClick={() => { setMode("daily"); setSelectedDate(null); }}>Daily</button>
          <button className="btn btn-outline" aria-pressed={mode === "weekly"} onClick={() => { setMode("weekly"); setSelectedDate(null); }}>Weekly</button>
        </div>
        <label className="sectors-date-select">Replay date
          <select value={replay?.date ?? ""} onChange={event => setSelectedDate(event.target.value)}>
            {replayRows.map(row => <option key={row.date} value={row.date}>{formatDateLabel(row.date)}</option>)}
          </select>
        </label>
      </div>
      <p className="sectors-meta">Diffusion compares the selected date with {formatDateLabel(replay?.previous_date)} using the same names at both dates. Its denominator may change between comparisons when a close is missing or an action affects a window.</p>
    </section>

    <section className="sectors-section" aria-labelledby="constituent-heading">
      <div className="sectors-section-heading">
        <div><div className="eyebrow-muted">Constituent inspector · {activeSector}</div><h2 id="constituent-heading">Selected-stock readings</h2></div>
        <label className="sectors-date-select">Sector
          <select value={activeSector ?? ""} onChange={event => setSelectedSector(event.target.value)}>
            {ranked.map(row => <option key={row.sector} value={row.sector}>{row.sector}</option>)}
          </select>
        </label>
      </div>
      {inspected && <>
        <div className="sectors-inspector-summary">
          <span>{inspected.contributor_counts["20d"]} of 6 contribute to 20D ranking</span>
          <span>Leadership cohort: {inspected.comparison_cohorts.leadership_tickers.length}</span>
          <span>Diffusion cohort: {inspected.diffusion.eligible_count}</span>
          <span>20D concentration: {formatEnumLabel(inspected.concentration_v2?.status)}</span>
          <span>YTD contributors: {inspectedYtd?.eligible_contributors ?? 0} of 6</span>
        </div>
        <WorkspaceTable rows={inspected.contributors} rowKey={row => row.ticker} columns={[
          { label: "Ticker", cell: row => row.ticker.replace(".JK", "") },
          { label: "Company", cell: row => row.company_name ?? "—" },
          { label: "5D raw / excess", cell: row => `${formatPercent(row.returns["5d"].return_pct, 2)} / ${formatPercent(row.returns["5d"].excess_return_pct, 2)}` },
          { label: "20D raw / excess", cell: row => `${formatPercent(row.returns["20d"].return_pct, 2)} / ${formatPercent(row.returns["20d"].excess_return_pct, 2)}` },
          { label: "60D raw / excess", cell: row => `${formatPercent(row.returns["60d"].return_pct, 2)} / ${formatPercent(row.returns["60d"].excess_return_pct, 2)}` },
          { label: "YTD raw / excess", cell: row => {
            const reading = ytdByTicker.get(row.ticker);
            return `${formatPercent(reading?.return_pct ?? null, 2)} / ${formatPercent(reading?.excess_return_pct ?? null, 2)}`;
          } },
          { label: "20D eligibility", cell: row => row.contributes_20d ? "Eligible" : actionSummary(row.returns["20d"].exclusion_reason) },
          { label: "60D eligibility", cell: row => actionSummary(row.returns["60d"].exclusion_reason) },
          { label: "YTD eligibility", cell: row => actionSummary(ytdByTicker.get(row.ticker)?.exclusion_reason ?? null) },
        ]} />
      </>}
    </section>

    <details className="sectors-details">
      <summary>Methods, corporate actions, and limitations</summary>
      <ul>{analysis.methodology.map((item, index) => <li key={index}>{item}</li>)}</ul>
      <p>Action-affected windows keep the stock in the 66-name roster but exclude it from that reading. See <Link to="/recorded-sample">the acquisition record and source receipts</Link>.</p>
      <p>Broader market, ownership, foreign-flow, and theme pages are context from the IDX research release, not the Sectors sample analysis.</p>
    </details>
  </main>;
}
