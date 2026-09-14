import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { useSnapshot } from "../data/SnapshotProvider";
import type {
  AdaptedSnapshot,
  ConstituentData,
  FlowState,
  SectorData,
  TaxonomyGroupData,
} from "../data/adapter";
import type { TaxonomyKind } from "../data/snapshot";
import { DataStatusChip, LeadershipChip, DiffusionChip } from "../components/StatusChips";
import { EmptyState } from "../components/EmptyState";
import {
  getTavilyCategory,
  getTavilyCategoryStatus,
  shortenEvidence,
  type ResearchContextCategory,
} from "../data/researchContext";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { leadershipColor } from "../components/StatusChips";
import PriceChart from "../components/PriceChart";
import { formatCountLabel, formatDateLabel, formatEnumLabel, formatPercent, formatSnapshotId } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";
import { WindowCapNotice } from "../components/SnapshotNotices";

const card: React.CSSProperties = {
  background: "#ffffff",
  borderRadius: 6,
  boxShadow: "rgba(0,0,0,0.08) 0px 0px 0px 1px, rgb(250,250,250) 0px 0px 0px 2px",
};

function displayMetric(val: number | null | undefined, suffix = "%"): string {
  if (suffix === "%") return formatPercent(val);
  if (val === null || val === undefined || !Number.isFinite(val)) return "—";
  return `${val > 0 ? "+" : ""}${val.toFixed(1)}${suffix}`;
}

function Num({ val, suffix = "%" }: { val: number | null | undefined; suffix?: string }) {
  const color =
    val === null || val === undefined || !Number.isFinite(val)
      ? "#8f8f8f"
      : val > 0
        ? "#1a6e62"
        : val < 0
          ? "#8f2424"
          : "#5a5a5a";
  return (
    <span
      style={{
        fontFamily: "Geist Mono, monospace",
        fontSize: 13,
        fontWeight: 500,
        color,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {displayMetric(val, suffix)}
    </span>
  );
}

function SectionHead({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "32px 0 14px" }}>
      <span className="eyebrow-muted">{label}</span>
      <div style={{ flex: 1, height: 1, background: "#ebebeb" }} />
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div style={{ ...card, flex: 1, padding: "16px 18px" }}>
      <div className="eyebrow-muted" style={{ marginBottom: 8 }}>{label}</div>
      <div
        style={{
          fontFamily: "Geist Mono, monospace",
          fontSize: 24,
          fontWeight: 500,
          color: color || "#171717",
          letterSpacing: "-0.02em",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: "#666666", marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

const flowCfg: Record<FlowState, { label: string; color: string }> = {
  CONFIRMING: { label: "Confirming", color: "#1a6e62" },
  NEUTRAL: { label: "Neutral", color: "#5a5a5a" },
  AGAINST: { label: "Against", color: "#8f2424" },
  DATA_GAP: { label: "Not available", color: "#7a5010" },
};

function ConstituentTable({ constituents }: { constituents: ConstituentData[] }) {
  return (
    <div className="table-scroll" style={{ ...card }}>
      <table style={{ width: "100%", minWidth: 1180, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #ebebeb" }}>
            {["Ticker", "Company", "YTD Ret", "YTD Exc", "20D Ret", "20D Exc", "60D Exc", "Part.", "Abs. Move", "Membership", "Foreign Flow"].map(
              (col) => (
                <th
                  key={col}
                style={{
                    padding: "9px 12px",
                    fontFamily: "Geist Mono, monospace",
                    fontSize: 10,
                    fontWeight: 400,
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    color: "#666666",
                    textAlign: col === "Ticker" || col === "Company" ? "left" : "right",
                    background: "#fafafa",
                    whiteSpace: "nowrap",
                  }}
                >
                  {col}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {constituents.map((c, i) => {
            const flow = flowCfg[c.foreignFlow];
            return (
              <tr
                key={c.ticker}
                style={{ borderBottom: i < constituents.length - 1 ? "1px solid #ebebeb" : "none" }}
              >
                <td style={{ padding: "9px 12px", fontFamily: "Geist Mono, monospace", fontSize: 12, fontWeight: 600, color: "#171717" }}>
                  <Link
                    to={`/ticker/${c.ticker}`}
                    style={{ color: "#171717", textDecoration: "underline" }}
                  >
                    {c.ticker}
                  </Link>
                </td>
                <td style={{ padding: "9px 12px", fontSize: 12, color: "#4d4d4d", maxWidth: 220 }}>
                  {c.name || "—"}
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right" }}>
                  <Num val={c.returnYtd} />
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right" }}>
                  <Num val={c.excessYtd} />
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right" }}>
                  <Num val={c.return20d} />
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right" }}>
                  <Num val={c.excess20d} />
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right" }}>
                  <Num val={c.excess60d} />
                </td>
                <td
                  style={{
                    padding: "9px 12px",
                    textAlign: "right",
                    fontFamily: "Geist Mono, monospace",
                    fontSize: 11,
                    color: c.participating === null ? "#8f8f8f" : c.participating ? "#1a6e62" : "#8f8f8f",
                  }}
                >
                  {c.participating === null ? "—" : c.participating ? "● Yes" : "○ No"}
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 12, color: "#171717" }}>
                  {c.contribution === null ? "—" : `${c.contribution}%`}
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right", fontSize: 11, color: "#666", whiteSpace: "nowrap" }}>
                  {formatEnumLabel(c.membershipType)}
                </td>
                <td
                  style={{
                    padding: "9px 12px",
                    textAlign: "right",
                    fontFamily: "Geist Mono, monospace",
                    fontSize: 11,
                    color: flow.color,
                    letterSpacing: "0.03em",
                  }}
                >
                  {flow.label}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ContribBars({ constituents }: { constituents: ConstituentData[] }) {
  if (constituents.every((c) => c.contribution === null)) {
    return (
      <EmptyState
        label="NO CONTRIBUTION DATA"
        title="Contribution percentages are unavailable"
        body="The snapshot does not contain enough constituent-level return data to calculate this breakdown."
        height={100}
      />
    );
  }
  const available = constituents
    .filter(
      (c): c is ConstituentData & { contribution: number } => c.contribution !== null,
    )
    .sort((a, b) => b.contribution - a.contribution);
  const top3 = available.slice(0, 3);
  const topTotal = top3.reduce((s, c) => s + c.contribution, 0);
  const other = Math.max(0, 100 - topTotal);
  const rows: Array<{ label: string; val: number; isOther: boolean }> = [
    ...top3.map((c) => ({ label: c.ticker, val: c.contribution, isOther: false })),
    { label: "Other", val: other, isOther: true },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {rows.map((r) => (
        <div key={r.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              width: 64,
              fontFamily: "Geist Mono, monospace",
              fontSize: 11,
              fontWeight: r.isOther ? 400 : 600,
              color: r.isOther ? "#8f8f8f" : "#171717",
            }}
          >
            {r.label}
          </span>
          <div style={{ flex: 1, height: 6, background: "#ebebeb", borderRadius: 1, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${r.val}%`,
                background: r.isOther ? "#c9c9c9" : "#171717",
                borderRadius: 1,
                transition: "width 0.3s",
              }}
            />
          </div>
          <span
            style={{
              width: 32,
              fontFamily: "Geist Mono, monospace",
              fontSize: 11,
              color: "#666666",
              textAlign: "right",
            }}
          >
            {r.val}%
          </span>
        </div>
      ))}
    </div>
  );
}

function findGroupFromLocation(
  state: unknown,
  fallbackId: string | undefined,
  sectors: SectorData[],
): string {
  const fromState = (state as { sectorId?: string } | null)?.sectorId;
  if (fromState && sectors.some((s) => s.id === fromState)) return fromState;
  if (fallbackId && sectors.some((s) => s.id === fallbackId)) return fallbackId;
  return sectors[0]?.id ?? "";
}

function normalizeTaxonomyKind(value: string | null): TaxonomyKind | null {
  const normalized = value?.toUpperCase();
  return normalized === "SECTOR" || normalized === "KONGLO" || normalized === "THEMES"
    ? normalized
    : null;
}

function TaxonomyGroupDetail({
  group,
  data,
}: {
  group: TaxonomyGroupData;
  data: AdaptedSnapshot;
}) {
  const backPath = group.taxonomyKind === "KONGLO" ? "/maps/konglo" : "/maps/themes";
  const members = group.memberships;
  const quantitativeMembers = members.filter((member) => member.membership_type !== "EXCLUDED");
  const groupKey = `${group.taxonomyId}::${group.id}`;
  const constituents = data.constituentsByTaxonomyGroup[groupKey] ?? [];
  const pricePoints = data.taxonomyGroupPriceHistory[groupKey] ?? [];
  const manifestEntry = data.payload.manifest.entries[0];
  const metric = (value: number | null | undefined, suffix = "%") => {
    if (value == null || !Number.isFinite(value)) return "—";
    return `${value >= 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
  };
  const ytdCoverage = group.constituents > 0
    ? `${group.ytdEligible}/${group.constituents}`
    : "—";

  return (
    <div className="taxonomy-detail-page content-shell" style={{ padding: "36px var(--page-gutter)", maxWidth: "var(--content-max)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20, marginBottom: 24, flexWrap: "wrap" }}>
        <div>
          <Link to={backPath} style={{ color: "#686e73", fontSize: 12, textDecoration: "none" }}>
            ← Back to {group.taxonomyKind === "KONGLO" ? "Konglo" : "Themes"} map
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 16, marginBottom: 8 }}>
            <div className="eyebrow-muted">
              {group.taxonomyName} · group detail
            </div>
            <EvidenceBadge kind="PROTOTYPE" compact />
          </div>
          <h1 style={{ margin: 0, fontSize: 30, fontWeight: 400, letterSpacing: "-1.5px" }}>
            {group.name}
          </h1>
          <p style={{ margin: "8px 0 0", color: "#686e73", fontSize: 13, lineHeight: 1.5 }}>
            Aggregate metrics use the current snapshot. Membership is an analyst-defined research lens and is not an official IDX classification.
          </p>
        </div>
        <Link to="/overview" style={{ padding: "9px 13px", border: "1px solid #202325", color: "#202325", textDecoration: "none", fontSize: 12 }}>
          Overview
        </Link>
      </div>

      <div style={{ ...card, padding: "18px 22px", marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <LeadershipChip state={group.leadership as Parameters<typeof LeadershipChip>[0]["state"]} />
          <DiffusionChip state={group.diffusion as Parameters<typeof DiffusionChip>[0]["state"]} />
          <span style={{ fontFamily: "Geist Mono, monospace", fontSize: 11, color: "#666", border: "1px solid #ebebeb", padding: "2px 8px", borderRadius: 4 }}>
            {formatEnumLabel(group.dataQuality)}
          </span>
          <span style={{ fontFamily: "Geist Mono, monospace", fontSize: 11, color: "#666" }}>
            {formatCountLabel(group.constituents, "ticker")} · {group.eligible} with 20D history
          </span>
        </div>
        <div className="explorer-metrics" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginTop: 16 }}>
          <MetricCard label="YTD excess" value={metric(group.excessYtd)} sub={group.ytdStartDate ? `from ${formatDateLabel(group.ytdStartDate)} vs IHSG` : "baseline unavailable"} />          <MetricCard label="YTD group return" value={metric(group.returnYtd)} sub={`${ytdCoverage} with YTD history`} />
          <MetricCard label="IHSG YTD" value={metric(group.benchmarkYtd)} sub="same dates and price basis" />
          <MetricCard label="20D excess" value={metric(group.excess20d)} sub="diagnostic vs IHSG" />
          <MetricCard label="Breadth" value={metric(group.breadth, "%")} sub={group.breadthDelta === null ? "change unavailable" : `${metric(group.breadthDelta)} vs prior`} />
          <MetricCard label="Concentration" value={metric(group.concentration, "%")} sub="Top-3 contribution" />
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <WindowCapNotice data={data} compact />
      </div>

      <SectionHead label="Performance and membership" />
      <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "#171717" }}>Constituent performance</div>
          <span className="eyebrow-muted">YTD is primary · 20D and 60D are diagnostics</span>
        </div>
        {constituents.length > 0 ? (
          <ConstituentTable constituents={constituents} />
        ) : (
          <div style={{ color: "#686e73", fontSize: 12, padding: "12px 0" }}>
            Constituent rows unavailable in this snapshot. Membership definitions are preserved below.
          </div>
        )}
      </div>

      <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "#171717" }}>Contribution and price context</div>
          <span className="eyebrow-muted">Persisted price history only</span>
        </div>
        {constituents.length > 0 && <ContribBars constituents={constituents} />}
        {pricePoints.length > 0 ? (
          <div style={{ marginTop: 16 }}>
            <PriceChart
              groupName={group.name}
              points={pricePoints.map((point) => ({ date: point.date, value: point.value }))}
              benchmarkPoints={pricePoints.filter((point) => point.benchmark !== null).map((point) => ({ date: point.date, value: point.benchmark }))}
              groupPoints={pricePoints}
              asOf={data.payload.as_of}
              source="Persisted snapshot prices"
              metricLabel="Equal-weight group index · rebased to 100"
              referenceValue={100}
              providerMode={manifestEntry?.provider_mode}
              priceBasis={manifestEntry?.price_basis}
              dataStatus={data.payload.quality?.status}
              height={260}
            />
          </div>
        ) : (
          <div style={{ marginTop: 12, color: "#686e73", fontSize: 12 }}>
            No persisted group price history is available. No synthetic history is shown.
          </div>
        )}
      </div>

      <SectionHead label="Membership evidence" />
      <div style={{ ...card, overflowX: "auto" }}>
        {members.length > 0 ? (
          <table style={{ width: "100%", minWidth: 720, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #ebebeb" }}>
                {["Ticker", "Membership", "Confidence", "Source", "Source date"].map((label) => (
                  <th key={label} style={{ padding: "10px 12px", textAlign: label === "Ticker" || label === "Source" ? "left" : "right", fontFamily: "Geist Mono, monospace", fontSize: 10, fontWeight: 400, color: "#666", textTransform: "uppercase", whiteSpace: "nowrap" }}>{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {members.map((member, index) => (
                <tr key={`${member.ticker}-${member.membership_type}`} style={{ borderBottom: index < members.length - 1 ? "1px solid #ebebeb" : "none", opacity: member.membership_type === "EXCLUDED" ? 0.6 : 1 }}>
                  <td style={{ padding: "10px 12px", fontFamily: "Geist Mono, monospace", fontSize: 12, fontWeight: 600 }}>
                    <Link to={`/ticker/${encodeURIComponent(member.ticker)}`} style={{ color: "#171717" }}>{member.ticker}</Link>
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "right", fontSize: 12 }}>{formatEnumLabel(member.membership_type)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 12 }}>{Math.round(member.confidence * 100)}%</td>
                  <td style={{ padding: "10px 12px", fontSize: 12, maxWidth: 360 }}>
                    {member.source?.startsWith("http") ? <a href={member.source} target="_blank" rel="noreferrer">Official source</a> : member.source || "—"}
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 11, color: "#666", whiteSpace: "nowrap" }}>{formatDateLabel(member.source_as_of)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ padding: 22, color: "#686e73", fontSize: 13 }}>
            Membership list unavailable in this snapshot. The aggregate is preserved without inventing constituent records.
          </div>
        )}
      </div>

      <div style={{ marginTop: 12, color: "#686e73", fontSize: 11, lineHeight: 1.5 }}>
        Snapshot: {formatSnapshotId(data.payload.snapshot_id, data.payload.as_of)} · As of {formatDateLabel(data.payload.as_of)} · {quantitativeMembers.length} membership records enter quantitative rows; excluded memberships remain visible for audit.
      </div>
    </div>
  );
}

function ResearchEvidencePanel({
  label,
  category,
  payload,
  groupName,
}: {
  label: string;
  category: ResearchContextCategory;
  payload: Parameters<typeof getTavilyCategory>[0];
  groupName: string;
}) {
  const context = getTavilyCategory(payload, category);
  const status = getTavilyCategoryStatus(payload, category);
  const hasContext = context.records.length > 0;
  const verdict = hasContext ? "CONTEXT_ONLY" : status === "FAILED" ? "FAILED" : "DATA_GAP";
  const verdictColor = hasContext ? "#7a5010" : status === "FAILED" ? "#8f2424" : "#7a5010";
  return (
    <div style={{ ...card, padding: "16px 18px", minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 10 }}>
        <div className="eyebrow-muted">{label}</div>
        <DataStatusChip status={status} />
      </div>
      <p style={{ margin: "0 0 12px", fontSize: 12, color: "#666666", lineHeight: 1.5 }}>
        {context.note || (hasContext
          ? "Qualitative web context only; it does not change the confirmation metric."
          : "No source-backed context is attached to this snapshot.")}
      </p>
      {hasContext ? (
        <>
          <div style={{ fontSize: 11, color: "#7a5010", marginBottom: 8 }}>
            Market-level sources; not attributed to {groupName}.
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {context.records.slice(0, 3).map((record) => (
              <div key={`${record.request_id ?? record.url}-${record.url}`} style={{ borderTop: "1px solid #ebebeb", paddingTop: 9 }}>
                <a
                  href={record.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: "#245b76", fontSize: 12, fontWeight: 500, lineHeight: 1.35, textDecoration: "none" }}
                >
                  {record.title}
                </a>
                <div style={{ marginTop: 4, fontSize: 11, color: "#777777", lineHeight: 1.45 }}>
                  {shortenEvidence(record.content, 150)}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div style={{ fontSize: 12, color: "#8f8f8f" }}>No eligible source was attached.</div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14 }}>
        <span style={{ fontSize: 11, color: "#666666" }}>Overall</span>
        <span
          style={{
            fontFamily: "Geist Mono, monospace",
            fontSize: 10,
            letterSpacing: "0.071em",
            textTransform: "uppercase",
            color: verdictColor,
            boxShadow: "rgb(235,235,235) 0 0 0 1px",
            background: "#ffffff",
            padding: "2px 8px",
            borderRadius: 4,
          }}
        >
          {formatEnumLabel(verdict)}
        </span>
      </div>
    </div>
  );
}

export default function GroupExplorer() {
  const { data } = useSnapshot();
  const location = useLocation();
  const [selected, setSelected] = useState<string>("");
  const sectors = data?.sectors ?? [];
  const constituentsByGroup = data?.constituentsByGroup ?? {};
  const groupPriceHistory = data?.groupPriceHistory ?? {};
  const dataSources = data?.dataSources ?? { breadthHistory: false, constituents: false, fundamentals: false, foreignFlow: false, trajectory: false };
  const queryGroup = new URLSearchParams(location.search).get("group") ?? undefined;
  const queryTaxonomy = normalizeTaxonomyKind(new URLSearchParams(location.search).get("taxonomy"));
  useEffect(() => {
    if (sectors.length > 0) {
      setSelected(findGroupFromLocation(location.state, queryGroup, sectors));
    }
  }, [sectors, location.state, queryGroup]);

  if (!data) return null;
  if (queryTaxonomy && queryTaxonomy !== "SECTOR") {
    const taxonomyGroup = Object.values(data.taxonomyGroups).find(
      (group) => group.taxonomyKind === queryTaxonomy && (!queryGroup || group.id === queryGroup),
    ) ?? Object.values(data.taxonomyGroups).find((group) => group.taxonomyKind === queryTaxonomy);
    if (!taxonomyGroup) {
      return (
        <div style={{ padding: "36px 40px", maxWidth: 1280, margin: "0 auto" }}>
          <EmptyState label="GROUP NOT FOUND" title="Taxonomy group is unavailable" body="The selected taxonomy group is not present in the current snapshot." height={220} />
        </div>
      );
    }
    return <TaxonomyGroupDetail group={taxonomyGroup} data={data} />;
  }
  if (sectors.length === 0) {
    return (
      <div style={{ padding: "36px 40px", maxWidth: 1280, margin: "0 auto" }}>
        <EmptyState
          label="NO GROUPS"
          title="Snapshot contains no group data"
          body="Export a readable snapshot with `.venv/bin/python -m scripts.export_snapshot_json --latest`, then refresh the app."
          height={240}
        />
      </div>
    );
  }

  const sector = sectors.find((s) => s.id === selected) ?? sectors[0];
  const constituents = constituentsByGroup[sector.id] ?? [];
  const groupBreadthHistory = data.breadthHistory.filter(
    (point) => point.group_id === sector.id,
  );
  const groupPricePoints = groupPriceHistory[sector.id] ?? [];
  const manifestEntry = data.payload.manifest.entries[0];
  const chartSource = manifestEntry?.provider
    ? `${manifestEntry.provider} snapshot`
    : "Snapshot data";
  const delta =
    sector.prevBreadth !== undefined && sector.breadth !== null
      ? sector.breadth - sector.prevBreadth
      : undefined;

  return (
    <div className="content-shell" style={{ padding: "36px var(--page-gutter)", maxWidth: "var(--content-max)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <div className="eyebrow-muted" style={{ marginBottom: 8 }}>
            IDX → Group → {sector.name}
          </div>
          <h1
            style={{
              fontSize: 30,
              fontWeight: 400,
              color: "#171717",
              letterSpacing: "-1.5px",
              lineHeight: 1.1,
              marginBottom: 0,
            }}
          >
            {sector.name}
          </h1>
        </div>
        <select
          aria-label="Select group"
          value={sector.id}
          onChange={(e) => setSelected(e.target.value)}
          style={{
            padding: "8px 14px",
            fontSize: 13,
            borderRadius: 6,
            border: "none",
            boxShadow: "rgb(235,235,235) 0 0 0 1px",
            background: "#ffffff",
            color: "#171717",
            fontFamily: "Geist, sans-serif",
            cursor: "pointer",
          }}
        >
          {sectors.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div style={{ ...card, padding: "18px 22px", marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
          <LeadershipChip state={sector.leadership} />
          <DiffusionChip state={sector.diffusion} />
          <span
            style={{
              fontFamily: "Geist Mono, monospace",
              fontSize: 11,
              letterSpacing: "0.065em",
              textTransform: "uppercase",
              color: "#666666",
              boxShadow: "rgb(235,235,235) 0 0 0 1px",
              background: "#ffffff",
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            {sector.eligibleConstituents} eligible / {sector.constituents} total
          </span>
          <span style={{ fontFamily: "Geist Mono", fontSize: 11, color: "#666666" }}>
            Leadership state persisted for {sector.persistence} observation{sector.persistence !== 1 ? "s" : ""}
          </span>
          {sector.prevLeadership && (
            <span style={{ fontFamily: "Geist Mono", fontSize: 10, color: "#7a5010", border: "1px solid #ebebeb", padding: "2px 6px", borderRadius: 4 }}>
              {formatEnumLabel(sector.prevLeadership)} → {formatEnumLabel(sector.leadership)}
            </span>
          )}
        </div>
        <p style={{ fontSize: 13, color: "#4d4d4d", lineHeight: 1.6, maxWidth: 720 }}>
          {sector.interpretation}
        </p>
        <div style={{ marginTop: 10, display: "flex", gap: 16, flexWrap: "wrap", fontSize: 11, color: "#666666", fontFamily: "Geist Mono" }}>
          <span>YTD Excess <b style={{ color: sector.excessYtd !== null && sector.excessYtd >= 0 ? "#1a6e62" : "#8f2424" }}>{displayMetric(sector.excessYtd)}</b></span>
          <span>20D Excess <b style={{ color: sector.excess20d !== null && sector.excess20d >= 0 ? "#1a6e62" : "#8f2424" }}>{displayMetric(sector.excess20d)}</b></span>
          <span>Breadth <b>{displayMetric(sector.breadth)}</b> {delta !== undefined ? <span style={{ color: delta !== null && delta > 0 ? "#1a6e62" : delta !== null && delta < 0 ? "#8f2424" : "#666" }}>({delta === null ? "Δ unavailable" : `${formatPercent(delta)} vs prior observation`})</span> : ""}</span>
          <span>Top-3 <b>{displayMetric(sector.concentration)}</b></span>
          {sector.missingConstituents > 0 && (
            <span style={{ color: "#7a5010" }}>{sector.missingConstituents} constituent{sector.missingConstituents !== 1 ? "s" : ""} missing from the 20D metric</span>
          )}
        </div>
        <div style={{ marginTop: 8, fontSize: 10, color: "#8f8f8f" }}>
          {sector.diffusion === "UNCONFIRMED" ? "No comparable prior snapshot is available. Current breadth can be shown, but diffusion change cannot yet be classified." : `Diffusion: ${formatEnumLabel(sector.diffusion)}${sector.prevDiffusion ? ` (previous ${formatEnumLabel(sector.prevDiffusion)})` : ""}${sector.diffusionV2 ? ` · v2 detail ${formatEnumLabel(sector.diffusionV2)}` : ""}`}
        </div>
      </div>

      <WindowCapNotice data={data} />

      <div className="explorer-metrics" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 24 }}>
        <MetricCard
          label="YTD excess"
          value={displayMetric(sector.excessYtd)}
          sub={sector.ytdStartDate ? `from ${formatDateLabel(sector.ytdStartDate)} vs IHSG` : "baseline unavailable"}
          color={
            sector.excessYtd === null
              ? "#8f8f8f"
              : sector.excessYtd >= 0
                ? "#1a6e62"
                : "#8f2424"
          }
        />
        <MetricCard
          label="YTD group return"
          value={displayMetric(sector.returnYtd)}
          sub={`${sector.ytdEligible}/${sector.constituents} with YTD history`}
        />
        <MetricCard
          label="IHSG YTD"
          value={displayMetric(sector.benchmarkYtd)}
          sub="same dates and price basis"
        />
        <MetricCard
          label="Breadth"
          value={displayMetric(sector.breadth)}
          sub={delta != null ? `${formatPercent(delta)} vs prior` : "change unavailable"}
          color={sector.breadth === null ? "#8f8f8f" : "#1a6e62"}
        />
        <MetricCard
          label="Concentration"
          value={displayMetric(sector.concentration)}
          sub="Top-3 contribution"
          color={
            sector.concentration === null
              ? "#8f8f8f"
              : sector.concentration > 60
                ? "#8f2424"
                : sector.concentration > 45
                  ? "#7a5010"
                  : "#1a6e62"
          }
        />
        <MetricCard
          label="Constituents"
          value={String(sector.constituents)}
          sub={`${sector.eligibleConstituents} eligible / ${sector.constituents} total`}
        />
      </div>

      <SectionHead label="Time series" />
      {dataSources.breadthHistory && groupBreadthHistory.length > 0 ? (
        <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "#171717", marginBottom: 8 }}>
            {sector.name} — breadth history
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={groupBreadthHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ebebeb" />
              <XAxis dataKey="as_of" tickFormatter={(v) => String(v).slice(0, 10)} fontSize={10} />
              <YAxis domain={[0, 100]} fontSize={10} />
              <Tooltip />
              <Area type="monotone" dataKey="breadth" stroke={leadershipColor(sector.leadership)} fill={leadershipColor(sector.leadership)} fillOpacity={0.15} name="Breadth %" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
          <EmptyState
            label="NO HISTORY"
            title="Per-group breadth history not emitted"
            body="Export a snapshot that includes breadth history to see the time series."
            height={140}
          />
        </div>
      )}

      <SectionHead label="Price context" />
      {groupPricePoints.length > 0 ? (
        <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
          <PriceChart
            groupName={sector.name}
            points={groupPricePoints.map((point) => ({
              date: point.date,
              value: point.value,
            }))}
            benchmarkPoints={groupPricePoints
              .filter((point) => point.benchmark !== null)
              .map((point) => ({
                date: point.date,
                value: point.benchmark,
              }))}
            groupPoints={groupPricePoints}
            asOf={data.payload.as_of}
            source={chartSource}
            metricLabel="Equal-weight group index · rebased to 100"
            referenceValue={100}
            providerMode={manifestEntry?.provider_mode}
            priceBasis={manifestEntry?.price_basis}
            dataStatus={data.payload.quality?.status}
            height={300}
          />
          <div style={{ marginTop: 10, fontSize: 11, color: "#777777", lineHeight: 1.45 }}>
            Descriptive equal-weight group performance versus IHSG. This chart is
            presentation-only and does not change leadership or diffusion signals.
          </div>
        </div>
      ) : (
        <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
          <EmptyState
            label="NO PRICE SERIES"
            title="Group price history is unavailable"
            body="The selected snapshot does not emit a safe chart series for this group. No demonstration values are shown."
            height={140}
          />
        </div>
      )}

      <SectionHead label="Constituents — driver decomposition" />
      {dataSources.constituents && constituents.length > 0 ? (
        <>
          <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: "#171717" }}>Absolute 20D move contribution</span>
              <span className="eyebrow-muted">Top-3 absolute move: {displayMetric(sector.concentration)} · top-1 capped at 100% · equal-weight convention</span>
            </div>
            <p style={{ fontSize: 11, color: "#666", lineHeight: 1.5, margin: "0 0 12px" }}>
              {(() => {
                const part = constituents.filter((c) => c.participating === true).length;
                const total = constituents.filter((c) => c.excess20d !== null).length;
                const conc = sector.concentration ?? 0;
                if (conc > 60) return `Performance is carried by a few names (${conc}% top-3) — narrow and fragile.`;
                if (conc > 45) return `Performance is moderately concentrated (${conc}% top-3) — check breadth for confirmation.`;
                if (part / Math.max(1, total) > 0.6) return `Broad participation: ${part}/${total} outperforming — move is supported by multiple names.`;
                return `Mixed participation: ${part}/${total} outperforming — internally diverging.`;
              })()}
            </p>
            <ContribBars constituents={constituents} />
            <div style={{ marginTop: 12, display: "flex", gap: 16, fontSize: 11, color: "#666", fontFamily: "Geist Mono", flexWrap: "wrap" }}>
              <span>Positive contributors: {constituents.filter((c) => c.excess20d !== null && c.excess20d > 0).length}</span>
              <span>Negative contributors: {constituents.filter((c) => c.excess20d !== null && c.excess20d <= 0).length}</span>
              <span>Participating: {constituents.filter((c) => c.participating).length}/{constituents.filter((c) => c.excess20d !== null).length}</span>
            </div>
          </div>
          <ConstituentTable constituents={constituents} />
          <div style={{ marginTop: 8, fontSize: 10, color: "#8f8f8f", lineHeight: 1.4 }}>
            Methodology: absolute 20D return sorted descending; top-N shares use the sum of absolute constituent returns. Signed attribution (buy/sell) is separate and undefined when net is unstable.
            Equal-weight convention; no market-cap weighting.
          </div>
        </>
      ) : (
        <EmptyState
          label="NO CONSTITUENTS"
          title={`No constituents on file for ${sector.name}`}
          body="No feature rows matched this group in the exported security master, so constituent-level participation cannot be shown."
          height={140}
        />
      )}

      <SectionHead label="Confirmation" />
      <div className="explorer-confirmation-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <ResearchEvidencePanel
          label="Fundamentals"
          category="fundamentals"
          payload={data.payload}
          groupName={sector.name}
        />
        <ResearchEvidencePanel
          label="Foreign flow"
          category="foreign_flow"
          payload={data.payload}
          groupName={sector.name}
        />
        <ResearchEvidencePanel
          label="Events / catalyst"
          category="events"
          payload={data.payload}
          groupName={sector.name}
        />
      </div>

      <SectionHead label="What could contradict this signal?" />
      {sector.contradictions.length ? (
        <ol style={{ margin: "0 0 12px", paddingLeft: 18, fontSize: 13, lineHeight: 1.6 }}>
          {sector.contradictions.map((c) => (
            <li key={c.metric}>
              <strong>{c.severity === "CRITICAL" ? "CRITICAL" : "Warning"}</strong>
              {` — ${c.label}`}
              {c.evidence ? <span style={{ color: "#686e73" }}>{` — ${c.evidence}`}</span> : null}
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState
          label="NO CONTRADICTION RECORDS"
          title="Per-group contradiction evidence is not in the web snapshot"
          body="The current payload does not emit contradiction records, so no generic warning is shown for this group."
          height={108}
        />
      )}

      <div
        style={{
          borderRadius: 6,
          border: "1px solid #ebebeb",
          background: "#fafafa",
          padding: "16px 18px",
          margin: "12px 0 40px",
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 500, color: "#171717", marginBottom: 8 }}>Screen invalidation</div>
        {sector.invalidation.length ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#333333", lineHeight: 1.6 }}>
            {sector.invalidation.map((row, i) => (
              <li key={i}>
                {row.condition}
                {row.threshold ? <span style={{ color: "#686e73" }}>{` (${row.threshold})`}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ fontSize: 12, color: "#666666", margin: 0 }}>
            Per-group invalidation conditions are not emitted by the current web snapshot.
            Review the versioned methodology and the next comparable snapshot before treating
            a state as changed.
          </p>
        )}
        <p
          style={{
            fontSize: 10,
            color: "#8f8f8f",
            marginTop: 10,
            fontFamily: "Geist Mono, monospace",
            letterSpacing: "0.04em",
          }}
        >
          Screen-state invalidation, not an investment recommendation.
        </p>
      </div>
    </div>
  );
}
