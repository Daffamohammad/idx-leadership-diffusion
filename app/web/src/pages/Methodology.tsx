import { useState } from 'react';
import { useSnapshot } from "../data/SnapshotProvider";
import { DataStatusChip } from "../components/StatusChips";
import { normalizeDataStatus, type DataStatus, type SnapshotPayload } from "../data/snapshot";
import type { AdaptedSnapshot } from "../data/adapter";
import { buildDiffusionReadiness } from "../data/readiness";
import { formatCountLabel, formatDateLabel, formatEnumLabel } from "../data/format";
import {
  getTavilyCategory,
  getTavilyCategoryStatus,
  getTavilyCrawl,
  normalizeTavilyContext,
  getYouCategory,
  getYouCategoryStatus,
  normalizeYouContext,
  shortenEvidence,
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
      return `${label}: ${formatCountLabel(symbols.length, "security")} (full list remains in snapshot diagnostics)`;
    }
    return issue;
  });
  return `Data-quality flags: ${readable.join("; ")}`;
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
    const parts: string[] = [];
    if (tavilyCount > 0) parts.push(formatCountLabel(tavilyCount, "Tavily source"));
    if (youCount > 0) parts.push(formatCountLabel(youCount, "You.com source"));
    return `${parts.join(" + ")} attached; qualitative context only, not normalized into a confirmation metric.`;
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

function buildDataRows(payload: SnapshotPayload | null): DataRow[] {
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
        ? `Sectors structured taxonomy; ${taxonomyCoverage ?? "—"}% coverage in the persisted report.`
        : `Prototype taxonomy coverage: ${taxonomyCoverage ?? "—"}%; mapping is provider-specific and not authoritative.`,
    },
    { label: "Benchmark (IHSG)", status: benchmarkStatus, asOf, note: q?.benchmark_latest_date ? `Latest benchmark: ${formatDateLabel(q.benchmark_latest_date)}` : "Benchmark date not present in the snapshot." },
    { label: "Diffusion Comparison", status: diffusionReadiness.status, asOf, note: diffusionReadiness.note },
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
    detail: "Tavily can attach first-party research context, but web sources are not a normalized per-ticker metric. Confirmation remains a data gap unless the snapshot emits structured, comparable fundamental and flow observations.",
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
  const coverage = adapted?.coverageHonest;
  const ev = adapted?.researchEvents ?? [];
  const taxonomy = adapted?.taxonomyViews ?? {};

  const layerStatus = (kind: string) => {
    if (kind === "prices") return providerMode;
    if (kind === "benchmark") return "READY";
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
      limitation: "No structured per-ticker parser; data gap",
    },
    {
      name: "Events",
      status: layerStatus("events"),
      source: ev.length > 0 ? "Tavily + You.com bounded discovery" : "—",
      asOf: ev[0]?.publishedAt ?? "—",
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
  const dataRows = buildDataRows(data?.payload ?? null);
  const manifestEntries = data?.payload.manifest?.entries?.[0];
  const quality = data?.payload.quality;
  const coverage = data?.payload.coverage;
  const providerMode = manifestEntries?.provider_mode;
  const isLiveSectors = providerMode === "SECTORS_LIVE";
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
  const discoveredCount = coverage?.discovered_count;
  const usedCount = coverage?.used_count ?? coverage?.security_master_total;
  const coverageItems = [
    {
      label: "IDX Master Securities",
      value: isPrefixSample && discoveredCount
        ? `${usedCount} of ${discoveredCount} discovered`
        : (coverage?.security_master_total?.toString() ?? requested?.toString() ?? "—"),
    },
    { label: "Eligible Securities", value: coverage?.eligible_securities?.toString() ?? usable?.toString() ?? "—" },
    { label: "History Coverage", value: coverage?.price_history_coverage_pct !== undefined ? `${coverage.price_history_coverage_pct}%` : "—" },
    { label: "Taxonomy Coverage", value: coverage?.taxonomy_coverage_pct !== undefined ? `${coverage.taxonomy_coverage_pct}%` : "—" },
  ];
  const exclusionRows = Object.entries(coverage?.exclusion_reasons ?? {}).map(([reason, count]) => ({ reason, count }));
  return (
    <div className="content-shell" style={{ padding: '36px var(--page-gutter)', maxWidth: 'var(--content-max)' }}>
      <div style={{ marginBottom: 36 }}>
        <h1 style={{ fontSize: 30, fontWeight: 400, color: '#171717', letterSpacing: '-1.5px', lineHeight: 1.1, marginBottom: 8 }}>
          Methodology &amp; Data Quality
        </h1>
        <p style={{ fontSize: 14, color: '#4d4d4d', lineHeight: 1.5 }}>
          Transparent documentation of analytical definitions, data sources, and coverage gaps.
        </p>
      </div>

      {/* Prefix Sample Warning */}
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
          <strong>Partial universe sample.</strong>{" "}
          This snapshot uses {usedCount} of {discoveredCount} discovered securities
          (alphabetical prefix). It is NOT full IDX coverage. The Sectors
          client discovered {discoveredCount} rows; max-symbols capped the run.
        </div>
      )}

      {/* Data Status */}
      <SectionHead label="Data Status" />
      <div className="table-scroll" style={{ ...card }}>
        <table style={{ width: '100%', minWidth: 760, borderCollapse: 'collapse' }}>
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
                <td style={{ padding: '10px 16px', fontFamily: 'Geist Mono, monospace', fontSize: 11, color: '#666666' }}>{row.asOf}</td>
                <td style={{ padding: '10px 16px', fontSize: 12, color: '#666666', fontStyle: row.note ? 'italic' : 'normal' }}>{row.note || '—'}</td>
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
          Leadership uses the current return and acceleration inputs independently; a diffusion data gap does not invalidate a valid leadership state.
        </p>
      </div>

      {/* Data Gaps */}
      <SectionHead label="Known Data Gaps" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {[
          attachedResearchSources + attachedYouSources > 0
            ? `Tavily provides ${formatCountLabel(attachedResearchSources, "source")} and You.com provides ${formatCountLabel(attachedYouSources, "source")} as qualitative context; the numeric confirmation layer remains a data gap because no per-ticker or per-group fundamentals, flow, or event metrics are emitted.`
            : isLiveSectors
              ? 'Fundamentals, foreign-flow, and event layers are not emitted by the current live snapshot; confirmation is therefore a data gap.'
              : 'Fundamentals, foreign-flow, and event layers are not emitted by the current snapshot; confirmation is therefore a data gap.',
          ...(isLiveSectors
            ? ['Sectors did not expose an explicit instrument-type field in the sampled company response; unresolved rows remain unknown and require verification.']
            : []),
          ...(hasBreadthHistory
            ? []
            : ['Per-group rolling breadth and performance history is not emitted; current breadth describes the latest eligible cross-section only.']),
        ].map((msg, i) => (
          <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 14px', borderRadius: 6, border: '1px solid #ebebeb', background: '#fafafa' }}>
            <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10, fontWeight: 500, letterSpacing: '0.04em', color: '#7a5010', flexShrink: 0, paddingTop: 1 }}>Data gap</span>
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
                {context.research_answer && (
                  <div style={{ margin: '0 0 12px', padding: '10px 12px', background: '#fafafa', borderLeft: '2px solid #7a5010', fontSize: 11, color: '#4d4d4d', lineHeight: 1.5 }}>
                    <div className="eyebrow-muted" style={{ marginBottom: 4 }}>Research synthesis (unsourced)</div>
                    {shortenEvidence(context.research_answer, 360)}
                  </div>
                )}
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
      <div className="method-coverage-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
        {coverageItems.map(item => (
          <div key={item.label} style={{ ...card, padding: '14px 16px' }}>
            <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 24, fontWeight: 500, color: '#171717', letterSpacing: '-0.02em', marginBottom: 4 }}>{item.value}</div>
            <div style={{ fontSize: 11, color: '#666666' }}>{item.label}</div>
          </div>
        ))}
      </div>

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
            <span style={{ flex: 1, fontSize: 13, color: '#4d4d4d' }}>{ex.reason}</span>
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
        ].map(([label, val], i, arr) => (
          <div key={String(label)} style={{ display: 'flex', padding: '10px 16px', borderBottom: i < arr.length - 1 ? '1px solid #ebebeb' : 'none' }}>
            <span style={{ width: 200, fontSize: 12, color: '#666666' }}>{label}</span>
            <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 12, color: '#171717' }}>{val}</span>
          </div>
        ))}
        <div style={{ padding: '12px 16px', borderTop: '1px solid #ebebeb' }}>
          <div className="eyebrow-muted">Full method reference: docs/METHODOLOGY.md</div>
        </div>
      </div>
      <EvidenceMatrix adapted={data ?? null} manifestEntries={manifestEntries} />
    </div>
  );
}
