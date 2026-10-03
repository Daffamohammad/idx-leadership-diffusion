import { useState } from 'react';
import { useSnapshot } from "../data/SnapshotProvider";
import { DataStatusChip } from "../components/StatusChips";
import { normalizeDataStatus, type DataStatus, type SnapshotPayload } from "../data/snapshot";
import type { AdaptedSnapshot, IDXInvestorReleaseAdapted } from "../data/adapter";
import { buildDiffusionReadiness } from "../data/readiness";
import { formatCountLabel, formatDateLabel, formatEnumLabel } from "../data/format";
import { EvidenceModel, EvidenceBadge } from "../components/EvidenceModel";
import ListingRegistryPanel from "../components/ListingRegistryPanel";
import {
  getTavilyCategory,
  getTavilyCategoryStatus,
  getTavilyCrawl,
  normalizeTavilyContext,
  getYouCategory,
  getYouCategoryStatus,
  normalizeYouContext,
  shortenEvidence,
  truncateResearchAnswer,
  RESEARCH_ANSWER_MAX_CHARS,
  type ResearchContextCategory,
} from "../data/researchContext";

const card: React.CSSProperties = {
  background: '#ffffff',
  borderRadius: 6,
  boxShadow: 'rgba(0,0,0,0.08) 0px 0px 0px 1px, rgb(250,250,250) 0px 0px 0px 2px',
};

interface DataRow { label: string; status: DataStatus; asOf: string; note?: string; }

function formatQualityIssues(issues: string[] | undefined): string | undefined {
  if (!issues?.length) return undefined;
  const readable = issues.map((issue) => {
    const listIssue = issue.match(/^(failed_securities|insufficient_history)=\[(.*)\]$/);
    if (listIssue) {
      const symbols = listIssue[2].split(/,\s*/).filter(Boolean);
      const label = listIssue[1] === "failed_securities" ? "failed history requests" : "insufficient history";
      return `${formatCountLabel(symbols.length, "security", "securities")} with ${label}`;
    }
    return issue.replace(/\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b/g, (token) =>
      token.split("_").join(" "),
    );
  });
  return readable.join("; ");
}

function formatCoreDataNote(quality: SnapshotPayload["quality"] | undefined): string | undefined {
  if (!quality) return undefined;
  const coverage =
    Number.isFinite(quality.coverage_pct) && quality.requested_securities > 0
      ? `${quality.usable_securities}/${quality.requested_securities} usable histories (${quality.coverage_pct}%)`
      : undefined;
  const issues = formatQualityIssues(quality.issues);
  return [coverage, issues].filter(Boolean).join("; ") || undefined;
}

const researchCategoryLabels: Record<ResearchContextCategory, string> = {
  fundamentals: "Fundamentals",
  foreign_flow: "Foreign Flow",
  events: "Events / Catalyst",
};

function researchCategoryNote(
  payload: SnapshotPayload | null,
  category: ResearchContextCategory,
): string {
  const tavily = getTavilyCategory(payload, category);
  const you = getYouCategory(payload, category);
  const tavilyCount = tavily.records.length;
  const youCount = you.records.length;
  const total = tavilyCount + youCount;
  if (total > 0) {
    return `${formatCountLabel(total, "research source")} available for context. Quantitative confirmation is not assessed.`;
  }
  const tavilyFailed = getTavilyCategoryStatus(payload, category) === "FAILED";
  const youFailed = getYouCategoryStatus(payload, category) === "FAILED";
  if (tavilyFailed || youFailed) {
    return "Web-context request failed; no confirmation conclusion is drawn.";
  }
  return "No source-backed context attached; quantitative confirmation is not evaluated.";
}

function combinedCategoryStatus(
  payload: SnapshotPayload | null,
  category: ResearchContextCategory,
): DataStatus {
  const tavily = getTavilyCategoryStatus(payload, category);
  const you = getYouCategoryStatus(payload, category);
  // READY_WITH_GAPS wins over FAILED wins over DATA_GAP.
  if (tavily === "READY_WITH_GAPS" || you === "READY_WITH_GAPS") return "READY_WITH_GAPS";
  if (tavily === "FAILED" || you === "FAILED") return "FAILED";
  return "DATA_GAP";
}

function buildDataRows(
  payload: SnapshotPayload | null,
  idxRelease: IDXInvestorReleaseAdapted | null,
): DataRow[] {
  const asOf = formatDateLabel(payload?.as_of);
  const q = payload?.quality;
  const status: DataStatus = normalizeDataStatus(q?.status) ?? "PARTIAL";
  const qualityNote = formatCoreDataNote(q);
  const mode = payload?.manifest?.entries?.[0]?.provider_mode;
  const liveSectors = mode === "SECTORS_LIVE";
  const taxonomyCoverage = payload?.coverage?.taxonomy_coverage_pct;
  const taxonomyStatus: DataStatus =
    taxonomyCoverage === undefined
      ? status
      : taxonomyCoverage >= 100
        ? "READY"
        : "READY_WITH_GAPS";
  const benchmarkStatus: DataStatus = q?.benchmark_latest_date ? "READY" : status;
  const officialContext = payload?.official_market_context;
  const diffusionReadiness = buildDiffusionReadiness(payload);
  const researchRows = (Object.keys(researchCategoryLabels) as ResearchContextCategory[]).map(
    (category) => ({
      label: researchCategoryLabels[category],
      status: combinedCategoryStatus(payload, category),
      asOf,
      note: researchCategoryNote(payload, category),
    }),
  );
  return [
    { label: "Core Market Data", status, asOf, note: qualityNote },
    {
      label: "Taxonomy",
      status: taxonomyStatus,
      asOf,
      note: liveSectors
        ? `Sectors classification covers ${taxonomyCoverage ?? "—"}% of the recorded universe.`
        : `Research classification covers ${taxonomyCoverage ?? "—"}%. It is not an official taxonomy.`,
    },
    { label: "Benchmark (IHSG)", status: benchmarkStatus, asOf, note: q?.benchmark_latest_date ? `Latest benchmark: ${formatDateLabel(q.benchmark_latest_date)}` : "Benchmark date not present in the snapshot." },
    {
      label: "IDX Investor Release",
      status: normalizeDataStatus(idxRelease?.status) ?? "DATA_GAP",
      asOf: formatDateLabel(idxRelease?.asOfMax ?? payload?.as_of),
      note: idxRelease
        ? `${formatCountLabel(idxRelease.tradingDayCount, "trading day")} of market-level investor trading; not a per-ticker or group confirmation metric.`
        : "No validated official IDX release is attached to this snapshot.",
    },
    {
      label: "OJK Market Context",
      status: normalizeDataStatus(officialContext?.status) ?? "UNAVAILABLE",
      asOf: formatDateLabel(officialContext?.period_end ?? payload?.as_of),
      note: officialContext
        ? "Official OJK release. Market context only; not company or group evidence."
        : "No validated official OJK market context is attached to this snapshot.",
    },
    { label: "Diffusion Comparison", status: diffusionReadiness.status, asOf, note: payload?.comparability?.status === "COMPATIBLE" ? diffusionReadiness.note : "No comparable earlier observation is available. Changes in participation cannot yet be confirmed." },
    ...researchRows,
  ];
}

const methodCards = [
  {
    title: "Leadership",
    def: "Relative performance versus IHSG using 20D excess return and acceleration.",
    formula: "Acceleration = 5D Excess Return − 60D Excess Return",
    detail: "LEADING: 20D excess return is positive and acceleration clears the configured threshold. IMPROVING: 20D excess return is non-positive while acceleration clears the threshold. LAGGING and WEAKENING are the corresponding non-accelerating states.",
  },
  {
    title: "Breadth",
    def: "Share of eligible constituents outperforming the benchmark.",
    formula: "Breadth = Outperforming Constituents / Eligible Constituents",
    detail: "The current engine reports an equal-weight constituent ratio. Missing or misaligned observations remain outside the eligible denominator rather than being treated as underperformance.",
  },
  {
    title: "Diffusion",
    def: "Change in participation breadth between observations, with a group-size-aware floor.",
    formula: "Breadth Change = Breadth(t) − Breadth(t−1)",
    detail: "The configured diffusion classifier applies broadening and narrowing thresholds plus minimum constituent requirements. Unconfirmed means either the data does not contain a comparable prior breadth observation, or the group fails the configured evidence floor; it is never silently treated as Stable.",
  },
  {
    title: "Concentration",
    def: "Degree to which a group’s absolute price move is dominated by a small number of constituents.",
    formula: "Top-N Concentration = Top-N Absolute Move / Total Absolute Group Move",
    detail: "The configured v2 calculation reports absolute-move Top-1, Top-3, Top-5, signed attribution, and HHI diagnostics. Missing Top-3 data is shown as unavailable rather than inferred from HHI.",
  },
  {
    title: "Confirmation",
    def: "Independent fundamental and flow evidence aligned with the leadership signal.",
    formula: "— qualitative composite",
    detail: "Tavily can attach first-party research context, but web sources are not a normalized per-ticker metric. Confirmation is not available unless the snapshot emits structured, comparable fundamental and flow observations.",
  },
];

function SectionHead({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '36px 0 14px' }}>
      <span className="eyebrow-muted">{label}</span>
      <div style={{ flex: 1, height: 1, background: '#ebebeb' }} />
    </div>
  );
}

/**
 * Acquisition + pagination + window-cap diagnostics, read from persisted
 * backend metadata only. Empty backend state renders an explicit
 * "not reported" line — never a fabricated zero presented as measured.
 */
function AcquisitionDiagnostics({
  coverage,
  diagnostics,
  paginationIncomplete,
  windowCapped90d,
  windowCapNote,
  bundleComplete,
}: {
  coverage: SnapshotPayload["coverage"];
  diagnostics: AdaptedSnapshot["acquisitionDiagnostics"] | null;
  paginationIncomplete: boolean;
  windowCapped90d: boolean;
  windowCapNote: string | null;
  bundleComplete: boolean | null;
}) {
  const failedCount = coverage?.acquisition_failed_constituents;
  const emptyCount = coverage?.acquisition_empty_constituents;
  const failedTickers = diagnostics?.failed ?? [];
  const emptyTickers = diagnostics?.empty ?? [];
  const hasHistoryDiag =
    diagnostics !== null &&
    (failedTickers.length > 0 ||
      emptyTickers.length > 0 ||
      diagnostics.requestedSymbols !== null ||
      diagnostics.returnedSymbols !== null);
  const showTickerList = (tickers: string[], label: string) => {
    if (tickers.length === 0) return null;
    const preview = tickers.slice(0, 12).join(", ");
    return (
      <details style={{ marginTop: 4 }}>
        <summary
          style={{
            cursor: "pointer",
            fontSize: 11,
            color: "#245b76",
            fontFamily: "Geist Mono, monospace",
          }}
        >
          {label}: {tickers.length} ticker{tickers.length === 1 ? "" : "s"} ({preview}
          {tickers.length > 12 ? ` +${tickers.length - 12} more` : ""})
        </summary>
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            fontFamily: "Geist Mono, monospace",
            color: "#4d4d4d",
            lineHeight: 1.6,
            wordBreak: "break-word",
          }}
        >
          {tickers.join(", ")}
        </div>
      </details>
    );
  };
  return (
    <div style={{ ...card, padding: "12px 16px", marginBottom: 16 }} aria-label="Acquisition diagnostics">
      <div className="eyebrow-muted" style={{ marginBottom: 8 }}>Acquisition diagnostics</div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#4d4d4d", lineHeight: 1.7 }}>
        <li>
          Failed acquisitions:{" "}
          {failedCount !== undefined ? <strong>{failedCount}</strong> : "not reported by this export"}
          {diagnostics?.requestedSymbols !== null && diagnostics?.requestedSymbols !== undefined
            ? ` · ${diagnostics.returnedSymbols ?? "—"}/${diagnostics.requestedSymbols} symbols returned`
            : null}
          {showTickerList(failedTickers, "Failed")}
        </li>
        <li>
          Empty histories:{" "}
          {emptyCount !== undefined ? <strong>{emptyCount}</strong> : "not reported by this export"}
          {showTickerList(emptyTickers, "Empty")}
        </li>
        {!hasHistoryDiag && failedCount === undefined && emptyCount === undefined && (
          <li>Per-ticker failed/empty sets are not present in this snapshot export.</li>
        )}
        <li>
          Pagination:{" "}
          {paginationIncomplete ? (
            <strong style={{ color: "#7a5900" }}>
              incomplete — universe coverage may be understated; denominators reflect observed rows only.
            </strong>
          ) : (
            "no incomplete-pagination flag in this export."
          )}
        </li>
        <li>
          History window:{" "}
          {windowCapped90d ? (
            <strong>
              capped to the latest 90 calendar days.{" "}
              {windowCapNote ?? "YTD baselines may be unavailable."}
            </strong>
          ) : (
            "no 90-day cap flag in this export."
          )}
        </li>
        <li>
          Bundle completeness:{" "}
          {bundleComplete === false ? (
            <strong style={{ color: "#8f2424" }}>
              partial — written before the atomic-completeness sentinel; treat levels as provisional.
            </strong>
          ) : bundleComplete === true ? (
            "complete — atomic bundle verified."
          ) : (
            "not reported by this export (predates completeness forwarding)."
          )}
        </li>
        <li>
          Suspension screening:{" "}
          {coverage?.suspension_check === "checked" ? (
            "ran against the provider suspension feed."
          ) : coverage?.suspension_check === "failed" ? (
            <strong style={{ color: "#7a5900" }}>
              feed failed — suspended names may remain eligible; treat halts as unfiltered.
            </strong>
          ) : coverage?.suspension_check === "not_supported" ? (
            "provider has no suspension feed; halts are not screened."
          ) : (
            "not reported by this export."
          )}
        </li>
        <li>
          Session timing:{" "}
          {coverage?.intraday_build === true ? (
            <strong style={{ color: "#7a5900" }}>
              built mid-session — latest bars may be partial, not final closes.
            </strong>
          ) : coverage?.intraday_build === false ? (
            "built outside trading hours or from an explicit as-of date."
          ) : (
            "not reported by this export."
          )}
        </li>
        <li>
          Observation alignment:{" "}
          {coverage?.max_observation_lag_days === undefined ||
          coverage?.max_observation_lag_days === null ? (
            "per-ticker end-date dispersion not reported by this export."
          ) : (
            <>
              max end-date lag vs benchmark:{" "}
              <strong>{coverage.max_observation_lag_days}d</strong>
              {coverage?.tickers_lagging_gt2d
                ? ` · ${coverage.tickers_lagging_gt2d} ticker(s) lagging over 2 sessions (mixed windows)`
                : " · all constituents within 2 sessions"}
            </>
          )}
        </li>
      </ul>
    </div>
  );
}

function EvidenceMatrix({
  adapted,
  manifestEntries,
}: {
  adapted: AdaptedSnapshot | null;
  manifestEntries: SnapshotPayload["manifest"]["entries"][number] | undefined;
}) {
  const asOf = formatDateLabel(manifestEntries?.as_of);
  const providerMode = manifestEntries?.provider_mode ?? "PUBLIC_PROTOTYPE";
  const fk = adapted?.foreignFlow;
  const idxRelease = adapted?.idxInvestorRelease;
  const marketContext = adapted?.officialMarketContext;
  const coverage = adapted?.coverageHonest;
  const ev = adapted?.researchEvents ?? [];
  const taxonomy = adapted?.taxonomyViews ?? {};

  const layerStatus = (kind: string) => {
    if (kind === "prices") return providerMode;
    if (kind === "benchmark") return "READY";
    if (kind === "idx_release") {
      return idxRelease
        ? normalizeDataStatus(idxRelease.status) ?? "UNAVAILABLE"
        : "DATA_GAP";
    }
    if (kind === "market_context") {
      return marketContext
        ? normalizeDataStatus(marketContext.status) ?? "UNAVAILABLE"
        : "UNAVAILABLE";
    }
    if (kind === "sectors") return providerMode === "SECTORS_LIVE" ? "READY" : "PROTOTYPE_CONFIG";
    if (kind === "konglo") {
      const v = taxonomy.konglo;
      return v ? "ANALYST_DEFINED" : "DATA_GAP";
    }
    if (kind === "themes") {
      const v = taxonomy.themes;
      return v ? "ANALYST_DEFINED" : "DATA_GAP";
    }
    if (kind === "foreign_flow") {
      return fk ? (fk.signalEligible ? "READY_WITH_GAPS" : "SAMPLE_ONLY") : "DATA_GAP";
    }
    if (kind === "fundamentals") return "DATA_GAP";
    if (kind === "events") return ev.length > 0 ? "CONTEXT_ONLY" : "UNAVAILABLE";
    if (kind === "tradingview") return "CONTEXT_ONLY";
    return "—";
  };

  const layers: Array<{
    name: string;
    status: string;
    source: string;
    asOf: string;
    coverage: string;
    quant: string;
    signalEligible: boolean;
    limitation: string;
  }> = [
    {
      name: "Prices",
      status: layerStatus("prices"),
      source: providerMode === "SECTORS_LIVE" ? "Sectors API (read-only)" : "yfinance (cached)",
      asOf,
      coverage: coverage?.coverage_pct ? `${coverage.coverage_pct.toFixed(1)}%` : "—",
      quant: "quantitative",
      signalEligible: true,
      limitation: providerMode === "PUBLIC_PROTOTYPE" ? "Adj-close vs close basis explicit" : "—",
    },
    {
      name: "Benchmark",
      status: layerStatus("benchmark"),
      source: "^JKSE / IHSG",
      asOf,
      coverage: "n/a",
      quant: "quantitative",
      signalEligible: true,
      limitation: "IHSG only — no cross-country index",
    },
    {
      name: "IDX investor release",
      status: layerStatus("idx_release"),
      source: idxRelease ? "Indonesia Stock Exchange · Digital Statistics" : "—",
      asOf: formatDateLabel(idxRelease?.asOfMax),
      coverage: idxRelease ? formatCountLabel(idxRelease.tradingDayCount, "trading day") : "—",
      quant: "quantitative (market)",
      signalEligible: false,
      limitation: "Market-level investor flow; no per-ticker or group confirmation",
    },
    {
      name: "OJK market context",
      status: layerStatus("market_context"),
      source: marketContext ? "OJK official release · LlamaCloud parse" : "—",
      asOf: formatDateLabel(marketContext?.periodEnd),
      coverage: marketContext ? "market-level" : "—",
      quant: "quantitative (market)",
      signalEligible: false,
      limitation: "Descriptive context; not assigned to a ticker, sector, or group",
    },
    {
      name: "Sectors",
      status: layerStatus("sectors"),
      source: providerMode === "SECTORS_LIVE" ? "Sectors API taxonomy" : "Prototype universe.yaml",
      asOf,
      coverage: coverage?.taxonomy_coverage_pct ? `${coverage.taxonomy_coverage_pct}%` : "—",
      quant: "quantitative",
      signalEligible: true,
      limitation: "Coarse prototype labels",
    },
    {
      name: "Konglo",
      status: layerStatus("konglo"),
      source: taxonomy.konglo?.taxonomy_id ? `config/konglo.yaml (${taxonomy.konglo.taxonomy_version})` : "—",
      asOf,
      coverage: fk?.mappedCompanyObservationPct ? `${fk.mappedCompanyObservationPct.toFixed(1)}% mapped` : "—",
      quant: "context",
      signalEligible: false,
      limitation: "Analyst-defined prototype",
    },
    {
      name: "Themes",
      status: layerStatus("themes"),
      source: taxonomy.themes?.taxonomy_id ? `config/themes.yaml (${taxonomy.themes.taxonomy_version})` : "—",
      asOf,
      coverage: "—",
      quant: "context",
      signalEligible: false,
      limitation: "Analyst-defined prototype; multi-theme not aggregated cross-theme",
    },
    {
      name: "Foreign flow",
      status: layerStatus("foreign_flow"),
      source: "IDNFinancials secondary articles (top-buy / top-sell lists)",
      asOf: formatDateLabel(fk?.asOfMax),
      coverage: fk ? `${formatCountLabel(fk.marketDayCount, "market date")} · ${formatCountLabel(fk.companyObservationCount, "observation")}` : "—",
      quant: "quantitative (sample)",
      signalEligible: fk?.signalEligible ?? false,
      limitation: "Top-list sample, not full market. Net-only for company rows.",
    },
    {
      name: "Fundamentals",
      status: layerStatus("fundamentals"),
      source: "—",
      asOf: "—",
      coverage: "0%",
      quant: "n/a",
      signalEligible: false,
      limitation: "No structured per-ticker parser; confirmation not available",
    },
    {
      name: "Events",
      status: layerStatus("events"),
      source: ev.length > 0 ? "Tavily + You.com bounded discovery" : "—",
      asOf: formatDateLabel(ev[0]?.publishedAt),
      coverage: `${ev.length} events`,
      quant: "context",
      signalEligible: false,
      limitation: "Context only — never signals",
    },
    {
      name: "TradingView",
      status: layerStatus("tradingview"),
      source: "TradingView embed (CDN)",
      asOf: "live",
      coverage: "—",
      quant: "context",
      signalEligible: false,
      limitation: "Widget unavailable when CDN blocked",
    },
  ];

  return (
    <div className="table-scroll" style={{ ...card, marginBottom: 40 }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid #ebebeb' }}>
        <div className="eyebrow-muted">Evidence matrix</div>
        <h2 style={{ fontSize: 18, margin: '4px 0 0', color: '#171717' }}>
          Layer · status · source · coverage
        </h2>
        <p style={{ margin: '6px 0 0', fontSize: 11, fontFamily: 'Geist Mono, monospace', color: '#666666' }}>
          One row per evidence layer. Status and source coverage are reported separately.
        </p>
      </div>
      <table style={{ width: '100%', minWidth: 980, borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {["Layer", "Status", "Source", "As of", "Coverage", "Quantitative?", "Signal eligible?", "Limitation"].map((label) => (
              <th
                key={label}
                align="left"
                style={{
                  borderBottom: '1px solid #ebebeb',
                  padding: '10px 14px',
                  fontSize: 11,
                  fontFamily: 'Geist Mono, monospace',
                  color: '#666666',
                  textTransform: 'uppercase',
                }}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {layers.map((row, index) => (
            <tr key={row.name} style={{ borderBottom: index < layers.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
              <td style={{ padding: '10px 14px', fontWeight: 600 }}>{row.name}</td>
              <td style={{ padding: '10px 14px', fontFamily: 'Geist Mono, monospace' }}>{formatEnumLabel(row.status)}</td>
              <td style={{ padding: '10px 14px', color: '#4d4d4d' }}>{row.source}</td>
              <td style={{ padding: '10px 14px', fontFamily: 'Geist Mono, monospace', whiteSpace: 'nowrap' }}>{row.asOf}</td>
              <td style={{ padding: '10px 14px', fontFamily: 'Geist Mono, monospace' }}>{row.coverage}</td>
              <td style={{ padding: '10px 14px' }}>{row.quant}</td>
              <td style={{ padding: '10px 14px' }}>{row.signalEligible ? "Yes" : "No"}</td>
              <td style={{ padding: '10px 14px', color: '#666666' }}>{row.limitation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Methodology() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data } = useSnapshot();
  const dataRows = buildDataRows(data?.payload ?? null, data?.idxInvestorRelease ?? null);
  const manifestEntries = data?.payload.manifest?.entries?.[0];
  const quality = data?.payload.quality;
  const coverage = data?.payload.coverage;
  const providerMode = manifestEntries?.provider_mode;
  const isLiveSectors = providerMode === "SECTORS_LIVE";
  const listingRegistry = data?.listingRegistry;
  const diffusionReadiness = buildDiffusionReadiness(data?.payload ?? null);
  const hasBreadthHistory = Array.isArray(data?.payload.breadth_history)
    && data.payload.breadth_history.length > 0;
  const tavilyContext = normalizeTavilyContext(data?.payload.tavily_context);
  const crawl = getTavilyCrawl(data?.payload ?? null);
  const researchCategories = (Object.keys(researchCategoryLabels) as ResearchContextCategory[]).map(
    (category) => ({
      category,
      label: researchCategoryLabels[category],
      context: getTavilyCategory(data?.payload ?? null, category),
      status: getTavilyCategoryStatus(data?.payload ?? null, category),
    }),
  );
  const youContext = normalizeYouContext(data?.payload.you_context);
  const youResearchCategories = (Object.keys(researchCategoryLabels) as ResearchContextCategory[]).map(
    (category) => ({
      category,
      label: researchCategoryLabels[category],
      context: getYouCategory(data?.payload ?? null, category),
      status: getYouCategoryStatus(data?.payload ?? null, category),
    }),
  );
  const attachedResearchSources = researchCategories.reduce(
    (count, item) => count + item.context.records.length,
    0,
  );
  const attachedYouSources = youResearchCategories.reduce(
    (count, item) => count + item.context.records.length,
    0,
  );
  const requested = quality?.requested_securities;
  const usable = quality?.usable_securities;
  const excludedCount =
    requested !== undefined && usable !== undefined
      ? Math.max(0, requested - usable)
      : null;
  const isPrefixSample = coverage?.is_prefix_sample === true;
  const discoveredCount = listingRegistry?.discoveredCount ?? coverage?.discovered_count;
  const usedCount = coverage?.analysis_universe_count
    ?? coverage?.used_count
    ?? listingRegistry?.analysisRequestedCount
    ?? coverage?.security_master_total;
  const fullAccessibleListing = listingRegistry?.fullAccessibleUniverseListed
    ?? coverage?.full_accessible_universe_listed === true;
  const coverageItems = [
    {
      label: "Listed Securities",
      value: listingRegistry?.listedCount?.toString() ?? coverage?.security_master_total?.toString() ?? discoveredCount?.toString() ?? "—",
    },
    {
      label: "Analysis Sample",
      value: isPrefixSample && discoveredCount
        ? `${usedCount} of ${discoveredCount} discovered`
        : (usedCount?.toString() ?? requested?.toString() ?? "—"),
    },
    { label: "Eligible in Sample", value: coverage?.eligible_securities?.toString() ?? usable?.toString() ?? "—" },
    { label: "History Coverage", value: coverage?.price_history_coverage_pct !== undefined ? `${coverage.price_history_coverage_pct}%` : "—" },
    { label: "Taxonomy Coverage", value: listingRegistry?.taxonomyCoveragePct !== undefined ? `${listingRegistry.taxonomyCoveragePct}%` : coverage?.taxonomy_coverage_pct !== undefined ? `${coverage.taxonomy_coverage_pct}%` : "—" },
  ];
  const exclusionRows = Object.entries(coverage?.exclusion_reasons ?? {}).map(([reason, count]) => ({ reason, count }));
  const taxonomyViews = data?.taxonomyViews ?? {};
  const snapshotCoverage = isPrefixSample && discoveredCount && usedCount
    ? fullAccessibleListing
      ? `${usedCount} analyzed · ${discoveredCount} listed`
      : `${usedCount} analyzed · ${discoveredCount} discovered`
    : `${formatCountLabel(data?.sectors.length ?? 0, "sector group")}`;
  const evidenceLanes = [
    {
      kind: "SNAPSHOT" as const,
      title: "Market signal",
      detail: `Real persisted ${formatEnumLabel(providerMode ?? "market")} observations power returns, breadth, leadership, and constituent metrics.`,
      meta: `${snapshotCoverage} · ${formatDateLabel(data?.payload.as_of)}`,
      to: "/overview",
      actionLabel: "Open real snapshot",
    },
    {
      kind: "OFFICIAL_RELEASE" as const,
      title: "IDX investor release",
      detail: data?.idxInvestorRelease
        ? "The official daily investor-type table is integrated as a real market-level release. It does not establish per-ticker or group ownership flow."
        : "The official IDX release lane is not attached to this snapshot yet; no market-level investor-flow claim is made.",
      meta: data?.idxInvestorRelease
        ? `${formatCountLabel(data.idxInvestorRelease.tradingDayCount, "trading day")} · ${formatDateLabel(data.idxInvestorRelease.asOfMax)}`
        : "Release unavailable",
      to: "/overview#idx-release-title",
      actionLabel: "Open official release",
    },
    {
      kind: "SAMPLE" as const,
      title: "Foreign flow",
      detail: "Source-backed top-list observations are useful context, but they are not a full-universe live feed or confirmation signal.",
      meta: data?.foreignFlow
        ? `${formatCountLabel(data.foreignFlow.marketDayCount, "market date")} · ${formatCountLabel(data.foreignFlow.companyObservationCount, "company observation")}`
        : "No sample attached",
      to: "/overview#foreign-flow-sample",
      actionLabel: "Open sample",
    },
    {
      kind: "PROTOTYPE" as const,
      title: "Konglo and Themes",
      detail: "Membership definitions are static analyst research lenses. Their aggregate metrics reuse the current snapshot but are not official IDX classifications.",
      meta: `${formatCountLabel(taxonomyViews.konglo?.groups.length ?? 0, "Konglo group")} · ${formatCountLabel(taxonomyViews.themes?.groups.length ?? 0, "theme")}`,
      to: "/maps/konglo",
      actionLabel: "Open prototype lens",
    },
    {
      kind: "CONTEXT" as const,
      title: "Research context",
      detail: "Events and web research are frozen with the snapshot as descriptive context. They do not create or alter quantitative signals.",
      meta: `${formatCountLabel(data?.researchEvents.length ?? 0, "dated event")} · descriptive only`,
      to: "/overview#research-events",
      actionLabel: "Open context",
    },
  ];
  return (
    <div className="content-shell" style={{ padding: '36px var(--page-gutter)', maxWidth: 'var(--content-max)' }}>
      <div style={{ marginBottom: 36 }}>
        <h1 style={{ fontSize: 30, fontWeight: 400, color: '#171717', letterSpacing: '-1.5px', lineHeight: 1.1, marginBottom: 8 }}>
          Methodology &amp; Data Quality
        </h1>
        <p style={{ fontSize: 14, color: '#4d4d4d', lineHeight: 1.5 }}>
          Transparent documentation of analytical definitions, data sources, and coverage boundaries.
        </p>
      </div>

      <EvidenceModel
        lanes={evidenceLanes}
        intro="Market analysis uses recorded observations. Research themes, published samples and market context are identified separately so you can assess their coverage."
      />

      {/* Bounded Analysis Notice */}
      {isPrefixSample && discoveredCount && (
        <div
          style={{
            background: "#fff8e1",
            border: "1px solid #ffe082",
            borderRadius: 8,
            padding: "12px 16px",
            marginBottom: 18,
            color: "#7a5900",
            fontSize: 13,
          }}
          role="alert"
        >
          <strong>Bounded demo analysis.</strong>{" "}
          {fullAccessibleListing
            ? `The full accessible listing contains ${listingRegistry?.listedCount ?? coverage?.security_master_total ?? discoveredCount} securities.`
            : `The persisted listing contains ${listingRegistry?.persistedCount ?? coverage?.security_master_total ?? usedCount} of ${discoveredCount} discovered securities.`}{" "}
          Daily history and group metrics cover {usedCount} selected securities
          within the available history sample.
        </div>
      )}

      {/* Data Status */}
      <SectionHead label="Data Status" />
      <div className="table-scroll methodology-status-table" style={{ ...card }}>
        <table style={{ width: '100%', minWidth: 940, borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: 170 }} />
            <col style={{ width: 225 }} />
            <col style={{ width: 130 }} />
            <col />
          </colgroup>
          <thead>
            <tr style={{ borderBottom: '1px solid #ebebeb' }}>
              {['Data Layer', 'Status', 'As of', 'Notes'].map(col => (
                <th key={col} style={{ padding: '9px 16px', fontFamily: 'Geist Mono, monospace', fontSize: 10, fontWeight: 400, letterSpacing: '0.07em', textTransform: 'uppercase', color: '#666666', textAlign: 'left', background: '#fafafa' }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, i) => (
              <tr key={row.label} style={{ borderBottom: i < dataRows.length - 1 ? '1px solid #ebebeb' : 'none' }}>
                <td style={{ padding: '10px 16px', fontSize: 13, fontWeight: 500, color: '#171717' }}>{row.label}</td>
                <td style={{ padding: '10px 16px' }}><DataStatusChip status={row.status} /></td>
                <td style={{ padding: '10px 16px', fontFamily: 'Geist Mono, monospace', fontSize: 11, color: '#666666', whiteSpace: 'nowrap' }}>{row.asOf}</td>
                <td style={{ padding: '12px 16px', fontSize: 12, color: '#666666', lineHeight: 1.6, overflowWrap: 'anywhere' }}>{row.note || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Classification readiness */}
      <SectionHead label="Classification Readiness" />
      <div
        role="status"
        style={{
          ...card,
          padding: "16px 18px",
          borderLeft: `3px solid ${diffusionReadiness.status === "READY" ? "#297a3a" : "#7a5010"}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <div className="eyebrow-muted" style={{ marginBottom: 6 }}>Diffusion evidence</div>
            <div style={{ fontFamily: "Geist Mono, monospace", fontSize: 22, color: "#171717" }}>
              {diffusionReadiness.confirmedGroups}/{diffusionReadiness.totalGroups} groups classified
            </div>
          </div>
          <DataStatusChip status={diffusionReadiness.status} />
        </div>
        <p style={{ margin: "12px 0 0", fontSize: 13, color: "#4d4d4d", lineHeight: 1.55 }}>
          {diffusionReadiness.note}
        </p>
        <p style={{ margin: "8px 0 0", fontSize: 12, color: "#666666", lineHeight: 1.55 }}>
          Leadership uses the current return and acceleration inputs independently; missing diffusion data does not invalidate a valid leadership state.
        </p>
      </div>

      {/* Coverage notes */}
      <SectionHead label="Coverage notes" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {[
          attachedResearchSources + attachedYouSources > 0
            ? `Tavily provides ${formatCountLabel(attachedResearchSources, "source")} and You.com provides ${formatCountLabel(attachedYouSources, "source")} as qualitative context. The official IDX investor release is market-level; per-ticker or per-group quantitative confirmation is not yet available.`
            : isLiveSectors
              ? 'The official IDX investor release is a separate market-level lane. Fundamentals, per-ticker or group foreign-flow, and event metrics are not emitted by the current live snapshot; confirmation is therefore not yet available.'
              : 'The official IDX investor release is a separate market-level lane. Fundamentals, per-ticker or group foreign-flow, and event metrics are not emitted by the current snapshot; confirmation is therefore not yet available.',
          ...(isLiveSectors
            ? ['Sectors did not expose an explicit instrument-type field in the sampled company response; unresolved rows remain unknown and require verification.']
            : []),
          ...(hasBreadthHistory
            ? []
            : ['Per-group rolling breadth and performance history is not emitted; current breadth describes the latest eligible cross-section only.']),
        ].map((msg, i) => (
          <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 14px', borderRadius: 6, border: '1px solid #ebebeb', background: '#fafafa' }}>
            <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10, fontWeight: 500, letterSpacing: '0.04em', color: '#7a5010', flexShrink: 0, paddingTop: 1 }}>Not available</span>
            <span style={{ fontSize: 13, color: '#4d4d4d', lineHeight: 1.55 }}>{msg}</span>
          </div>
        ))}
      </div>

      {/* Optional qualitative web context */}
      <SectionHead label="Tavily Research Context" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }} className="method-research-grid">
        {researchCategories.map(({ category, label, context, status }) => (
          <div key={category} style={{ ...card, padding: '16px 18px', minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
              <div className="eyebrow-muted">{label}</div>
              <DataStatusChip status={status} />
            </div>
            <p style={{ margin: '0 0 12px', fontSize: 12, color: '#666666', lineHeight: 1.5 }}>
              {context.note || researchCategoryNote(data?.payload ?? null, category)}
            </p>
            {context.records.length === 0 ? (
              <div style={{ fontSize: 12, color: '#8f8f8f' }}>No eligible first-party source was attached.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {context.records.slice(0, 3).map((record) => (
                  <div key={`${record.request_id ?? record.url}-${record.url}`} style={{ borderTop: '1px solid #ebebeb', paddingTop: 9 }}>
                    <a
                      href={record.url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: '#245b76', fontSize: 12, fontWeight: 500, lineHeight: 1.35, textDecoration: 'none' }}
                    >
                      {record.title}
                    </a>
                    <div style={{ marginTop: 4, fontSize: 11, color: '#777777', lineHeight: 1.45 }}>
                      {shortenEvidence(record.content, 170)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {(crawl.records.length > 0 || tavilyContext) && (
        <div style={{ ...card, padding: '12px 16px', marginTop: 12, marginBottom: 6, background: '#fafafa' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span className="eyebrow-muted">Evidence boundary</span>
            <span style={{ fontSize: 12, color: '#4d4d4d' }}>
              {tavilyContext?.status === 'REQUESTED' ? 'Tavily requested' : 'Tavily not requested'}
              {crawl.records.length > 0 ? ` · ${crawl.records.length} bounded IDX crawl source(s)` : ''}
              {' · context only; metrics are unchanged'}
            </span>
          </div>
        </div>
      )}
      {youContext && (
        <>
          <SectionHead label="You.com Research Context" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }} className="method-research-grid">
            {youResearchCategories.map(({ category, label, context, status }) => (
              <div key={category} style={{ ...card, padding: '16px 18px', minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
                  <div className="eyebrow-muted">{label}</div>
                  <DataStatusChip status={status} />
                </div>
                <p style={{ margin: '0 0 12px', fontSize: 12, color: '#666666', lineHeight: 1.5 }}>
                  {context.note || (context.records.length > 0
                    ? `${formatCountLabel(context.records.length, "You.com source")} attached; qualitative context only, not normalized into a confirmation metric.`
                    : 'No source-backed context attached; quantitative confirmation is not evaluated.')}
                </p>
                {context.research_answer && (() => {
                  const capped = truncateResearchAnswer(context.research_answer);
                  return (
                    <div style={{ margin: '0 0 12px', padding: '10px 12px', background: '#fafafa', borderLeft: '2px solid #7a5010', fontSize: 11, color: '#4d4d4d', lineHeight: 1.5 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
                        <div className="eyebrow-muted">Research synthesis (unsourced)</div>
                        <EvidenceBadge kind="CONTEXT" compact />
                      </div>
                      {capped.text}
                      <div style={{ marginTop: 6, fontSize: 10, color: "#8f8f8f", fontFamily: "Geist Mono, monospace" }}>
                        {capped.truncated
                          ? `Truncated to the ${RESEARCH_ANSWER_MAX_CHARS}-char display cap (${capped.originalLength} chars persisted); full text remains in the snapshot sidecar. Context only — never a signal.`
                          : `Shown within the ${RESEARCH_ANSWER_MAX_CHARS}-char display cap. Context only — never a signal.`}
                      </div>
                    </div>
                  );
                })()}
                {context.records.length === 0 ? (
                  <div style={{ fontSize: 12, color: '#8f8f8f' }}>No eligible first-party source was attached.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {context.records.slice(0, 3).map((record) => (
                      <div key={`${record.request_id ?? record.url}-${record.url}`} style={{ borderTop: '1px solid #ebebeb', paddingTop: 9 }}>
                        <a
                          href={record.url}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: '#245b76', fontSize: 12, fontWeight: 500, lineHeight: 1.35, textDecoration: 'none' }}
                        >
                          {record.title}
                        </a>
                        <div style={{ marginTop: 4, fontSize: 11, color: '#777777', lineHeight: 1.45 }}>
                          {shortenEvidence(record.content, 170)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div style={{ ...card, padding: '12px 16px', marginTop: 12, marginBottom: 6, background: '#fafafa' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span className="eyebrow-muted">Evidence boundary</span>
              <span style={{ fontSize: 12, color: '#4d4d4d' }}>
                {youContext.status === 'REQUESTED' ? 'You.com requested' : 'You.com not requested'}
                {attachedYouSources > 0 ? ` · ${formatCountLabel(attachedYouSources, "source")} attached` : ''}
                {' · context only; metrics are unchanged'}
              </span>
            </div>
          </div>
        </>
      )}

      {/* Coverage */}
      <SectionHead label="Universe Coverage" />
      <ListingRegistryPanel registry={data?.listingRegistry ?? null} />
      <div className="method-coverage-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
        {coverageItems.map(item => (
          <div key={item.label} style={{ ...card, padding: '14px 16px' }}>
            <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 24, fontWeight: 500, color: '#171717', letterSpacing: '-0.02em', marginBottom: 4 }}>{item.value}</div>
            <div style={{ fontSize: 11, color: '#666666' }}>{item.label}</div>
          </div>
        ))}
      </div>

      <AcquisitionDiagnostics
        coverage={coverage}
        diagnostics={data?.acquisitionDiagnostics ?? null}
        paginationIncomplete={data?.paginationIncomplete ?? false}
        windowCapped90d={data?.windowCapped90d ?? false}
        windowCapNote={data?.windowCapNote ?? null}
        bundleComplete={data?.bundleComplete ?? null}
      />

      <div style={{ ...card, overflow: 'hidden', marginBottom: 6 }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid #ebebeb', fontFamily: 'Geist Mono, monospace', fontSize: 10, letterSpacing: '0.07em', textTransform: 'uppercase', color: '#666666', background: '#fafafa' }}>
          {coverage?.excluded_securities !== undefined
            ? `Exclusions · ${coverage.excluded_securities} securities`
            : excludedCount === null
              ? "Exclusions"
              : `Exclusions · ${excludedCount} securities`}
        </div>
        {exclusionRows.length === 0 ? (
          <div style={{ padding: "12px 14px", fontSize: 12, color: "#666666" }}>
            Exclusion counts are not present in this snapshot.
          </div>
        ) : exclusionRows.map((ex, i) => (
          <div key={ex.reason} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '9px 14px', borderBottom: i < exclusionRows.length - 1 ? '1px solid #ebebeb' : 'none' }}>
            <span style={{ flex: 1, fontSize: 13, color: '#4d4d4d' }}>{formatEnumLabel(ex.reason)}</span>
            <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 12, color: '#171717', fontWeight: 500, width: 28, textAlign: 'right' }}>{ex.count}</span>
            <div style={{ width: 100, height: 3, background: '#ebebeb', borderRadius: 1, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: '100%', background: '#4d4d4d', borderRadius: 1 }} />
            </div>
          </div>
        ))}
      </div>
      <p style={{ fontSize: 10, color: '#8f8f8f', fontFamily: 'Geist Mono, monospace', letterSpacing: '0.04em', fontStyle: 'italic' }}>
        Counts are read from the current snapshot coverage and quality metadata.
      </p>

      <SectionHead label="Live Warnings" />
      <div style={{ ...card, padding: '12px 16px', marginBottom: 6 }}>
        {(data?.payload.data_warnings?.warnings ?? []).length === 0 ? (
          <div style={{ fontSize: 12, color: '#666666' }}>No persisted data warnings.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18, color: '#4d4d4d', fontSize: 12, lineHeight: 1.6 }}>
            {(data?.payload.data_warnings?.warnings ?? []).map((warning) => <li key={warning}>{formatQualityIssues([warning])}</li>)}
          </ul>
        )}
      </div>

      {/* Method cards */}
      <SectionHead label="Analytical Definitions" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, borderRadius: 6, overflow: 'hidden', boxShadow: 'rgba(0,0,0,0.08) 0px 0px 0px 1px, rgb(250,250,250) 0px 0px 0px 2px' }}>
        {methodCards.map((m, i) => (
          <div key={m.title} style={{ background: '#ffffff', borderBottom: i < methodCards.length - 1 ? '1px solid #ebebeb' : 'none' }}>
            <button
              type="button"
              aria-expanded={expanded === m.title}
              aria-controls={`method-${m.title.toLowerCase()}`}
              onClick={() => setExpanded(expanded === m.title ? null : m.title)}
              style={{
                width: '100%', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                gap: 16, padding: '14px 18px', background: 'none', border: 'none', cursor: 'pointer',
                textAlign: 'left', fontFamily: 'Geist, sans-serif',
              }}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: '#171717', marginBottom: 2 }}>{m.title}</div>
                <div style={{ fontSize: 12, color: '#666666', lineHeight: 1.5 }}>{m.def}</div>
              </div>
              <span style={{ fontSize: 14, color: '#8f8f8f', flexShrink: 0, lineHeight: 1, marginTop: 2 }}>{expanded === m.title ? '−' : '+'}</span>
            </button>
            {expanded === m.title && (
              <div id={`method-${m.title.toLowerCase()}`} style={{ padding: '0 18px 16px', borderTop: '1px solid #ebebeb' }}>
                <div style={{ paddingTop: 14 }}>
                  <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 12, color: '#171717', background: '#fafafa', padding: '8px 12px', borderRadius: 4, border: '1px solid #ebebeb', marginBottom: 10 }}>
                    {m.formula}
                  </div>
                  <p style={{ fontSize: 13, color: '#4d4d4d', lineHeight: 1.6 }}>{m.detail}</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Provenance */}
      <SectionHead label="Provenance" />
      <div style={{ ...card, overflow: 'hidden', marginBottom: 40 }}>
        {[
          ["Core Data Source", formatEnumLabel(manifestEntries?.provider)],
          ["Execution Mode", formatEnumLabel(manifestEntries?.provider_mode)],
          ["Benchmark", "IHSG"],
          ["Method Version", manifestEntries?.method_version ?? "—"],
          ["Diffusion Version", manifestEntries?.diffusion_version ?? "—"],
          ["Snapshot Date", formatDateLabel(manifestEntries?.as_of)],
          ["Benchmark Latest Date", formatDateLabel(quality?.benchmark_latest_date)],
          ["Latest Common Date", formatDateLabel(quality?.latest_common_date)],
        ].map(([label, val], i, arr) => (
          <div key={String(label)} style={{ display: 'flex', padding: '10px 16px', borderBottom: i < arr.length - 1 ? '1px solid #ebebeb' : 'none' }}>
            <span style={{ width: 200, fontSize: 12, color: '#666666' }}>{label}</span>
            <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 12, color: '#171717' }}>{val}</span>
          </div>
        ))}
        <div style={{ padding: '12px 16px', borderTop: '1px solid #ebebeb' }}>
          <div className="eyebrow-muted">Full method reference: docs/METHODOLOGY.md</div>
          <p style={{ margin: '8px 0 0', fontSize: 12, color: '#686e73' }}>
            STALE means the snapshot as-of date lags the latest available benchmark or common trading date shown above; coverage and transitions remain as persisted and are not refreshed in the browser.
          </p>
        </div>
      </div>
      <EvidenceMatrix adapted={data ?? null} manifestEntries={manifestEntries} />
    </div>
  );
}
