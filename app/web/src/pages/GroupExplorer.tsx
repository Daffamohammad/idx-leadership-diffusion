import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { useSnapshot } from "../data/SnapshotProvider";
import type {
  AdaptedSnapshot,
  ConstituentData,
  FlowState,
  SectorData,
  TaxonomyGroupData,
} from "../data/adapter";
import type { TaxonomyKind, TaxonomyMembershipData } from "../data/snapshot";
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
import PriceChart, { CHART_PERIODS, type ChartRange } from "../components/PriceChart";
import { formatCountLabel, formatDateLabel, formatEnumLabel, formatPercent, formatSnapshotId } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";
import { WindowCapNotice } from "../components/SnapshotNotices";
import { catalogHref, rememberCatalogFocus } from "../data/catalogFocus";
import { useHistoricalComparison } from "../data/marketWorkspace";

const card: React.CSSProperties = {
  background: "var(--surface)",
  borderRadius: 6,
  boxShadow: "rgba(0,0,0,0.08) 0px 0px 0px 1px, rgb(250,250,250) 0px 0px 0px 2px",
};

function displayMetric(val: number | null | undefined, suffix = "%"): string {
  if (suffix === "%") return formatPercent(val);
  if (val === null || val === undefined || !Number.isFinite(val)) return "—";
  return `${val > 0 ? "+" : ""}${val.toFixed(1)}${suffix}`;
}

function submissionInvalidationLabel(row: { condition: string; threshold: string | null }): string {
  if (/diffusion shifts to narrowing or unconfirmed/i.test(row.condition)) {
    return "Participation narrows or no longer meets the diffusion evidence floor";
  }
  if (/breadth falls below/i.test(row.condition)) {
    const cutoff = row.threshold?.match(/<\s*([\d.]+)%/)?.[1];
    return cutoff ? `Breadth falls below ${cutoff}%` : "Breadth falls below its configured threshold";
  }
  return row.condition;
}

function replayTransitionLabel(value: string | null | undefined): string {
  if (!value) return "No phase change";
  return value.split(/\s*(?:->|→)\s*/)
    .map(part => part.toUpperCase() === "UNCONFIRMED" ? "Baseline" : formatEnumLabel(part))
    .join(" → ");
}

function Num({ val, suffix = "%" }: { val: number | null | undefined; suffix?: string }) {
  const color =
    val === null || val === undefined || !Number.isFinite(val)
      ? "var(--muted)"
      : val > 0
        ? "var(--up)"
        : val < 0
          ? "var(--down)"
          : "var(--muted)";
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
      <div style={{ flex: 1, height: 1, background: "var(--line)" }} />
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
          color: color || "var(--ink)",
          letterSpacing: "-0.02em",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

const flowCfg: Record<FlowState, { label: string; color: string }> = {
  CONFIRMING: { label: "Confirming", color: "var(--up)" },
  NEUTRAL: { label: "Neutral", color: "var(--muted)" },
  AGAINST: { label: "Against", color: "var(--down)" },
  DATA_GAP: { label: "—", color: "var(--accent-ink)" },
};

function ConstituentTable({ constituents }: { constituents: ConstituentData[] }) {
  return (
    <div className="table-scroll" style={{ ...card }}>
      <table style={{ width: "100%", minWidth: 1180, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--line)" }}>
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
                    color: "var(--muted)",
                    textAlign: col === "Ticker" || col === "Company" ? "left" : "right",
                    background: "var(--surface-subtle)",
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
                <td style={{ padding: "9px 12px", fontFamily: "Geist Mono, monospace", fontSize: 12, fontWeight: 600, color: "var(--ink)" }}>
                  <Link
                    to={`/ticker/${c.ticker}`}
                    style={{ color: "var(--ink)", textDecoration: "underline" }}
                  >
                    {c.ticker}
                  </Link>
                </td>
                <td style={{ padding: "9px 12px", fontSize: 12, color: "var(--muted)", maxWidth: 220 }}>
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
                    color: c.participating === null ? "var(--muted)" : c.participating ? "var(--up)" : "var(--muted)",
                  }}
                >
                  {c.participating === null ? "—" : c.participating ? "● Yes" : "○ No"}
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right", fontFamily: "Geist Mono, monospace", fontSize: 12, color: "var(--ink)" }}>
                  {c.contribution === null ? "—" : `${c.contribution}%`}
                </td>
                <td style={{ padding: "9px 12px", textAlign: "right", fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap" }}>
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
        title="Contribution share —"
        body="Driver shares are shown when this release contains enough constituent-level return observations."
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
              color: r.isOther ? "var(--muted)" : "var(--ink)",
            }}
          >
            {r.label}
          </span>
          <div style={{ flex: 1, height: 6, background: "var(--line)", borderRadius: 1, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${r.val}%`,
                background: r.isOther ? "var(--line)" : "var(--ink)",
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
              color: "var(--muted)",
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

function CatalogBackLink({ taxonomyKind, groupId, label }: {
  taxonomyKind: TaxonomyKind;
  groupId: string;
  label: string;
}) {
  return (
    <Link
      to={catalogHref(taxonomyKind)}
      onClick={() => rememberCatalogFocus(groupId)}
      style={{ color: "var(--muted)", fontSize: 12, textDecoration: "none" }}
    >
      ← Back to {label}
    </Link>
  );
}

type MemberSortKey = "ticker" | "membership" | "confidence" | "sourceDate";

// A relationship subtype is only shown when the snapshot stored one.
function relationshipLabel(member: TaxonomyMembershipData): string {
  return member.relationship?.trim() ? formatEnumLabel(member.relationship) : "—";
}

const th: React.CSSProperties = {
  padding: "10px 12px",
  fontFamily: "Geist Mono, monospace",
  fontSize: 10,
  fontWeight: 400,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: "var(--muted)",
  textAlign: "left",
  background: "var(--surface-subtle)",
  whiteSpace: "nowrap",
};

const thRight: React.CSSProperties = { ...th, textAlign: "right" };

const td: React.CSSProperties = { padding: "10px 12px", fontSize: 12, color: "var(--ink)" };
const tdMono: React.CSSProperties = { ...td, fontFamily: "Geist Mono, monospace", fontVariantNumeric: "tabular-nums" };
const tdRight: React.CSSProperties = { ...tdMono, textAlign: "right" };

const sortButtonStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  padding: 0,
  font: "inherit",
  letterSpacing: "inherit",
  textTransform: "inherit",
  color: "inherit",
  cursor: "pointer",
};

function MembershipTable({ members, compact }: { members: TaxonomyMembershipData[]; compact?: boolean }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<MemberSortKey>("ticker");
  const [asc, setAsc] = useState(true);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = needle
      ? members.filter((m) =>
          m.ticker.toLowerCase().includes(needle) ||
          m.taxonomy_group_name.toLowerCase().includes(needle) ||
          relationshipLabel(m).toLowerCase().includes(needle),
        )
      : members;
    const direction = asc ? 1 : -1;
    return [...filtered].sort((a, b) => {
      switch (sort) {
        case "membership":
          return direction * (a.membership_type.localeCompare(b.membership_type) || a.ticker.localeCompare(b.ticker));
        case "confidence":
          return direction * (a.confidence - b.confidence) || a.ticker.localeCompare(b.ticker);
        case "sourceDate":
          return direction * String(a.source_as_of ?? "").localeCompare(String(b.source_as_of ?? "")) || a.ticker.localeCompare(b.ticker);
        default:
          return direction * a.ticker.localeCompare(b.ticker);
      }
    });
  }, [members, query, sort, asc]);

  const toggleSort = (key: MemberSortKey) => {
    if (sort === key) setAsc((v) => !v);
    else {
      setSort(key);
      setAsc(true);
    }
  };

  const arrow = (key: MemberSortKey) => (sort === key ? (asc ? " ↑" : " ↓") : "");

  if (members.length === 0) {
    return (
      <EmptyState
        label="NO MEMBERSHIPS"
        title="Membership count"
        body="The documented aggregate count is preserved; constituent rows follow the selected release evidence."
        height={140}
      />
    );
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search ticker, group or relationship…"
          aria-label="Search memberships by ticker, group or relationship"
          style={{
            padding: "7px 10px",
            border: "1px solid var(--line)",
            borderRadius: 4,
            fontFamily: "Geist Mono, monospace",
            fontSize: 12,
            background: "var(--surface)",
            minWidth: 220,
            boxSizing: "border-box",
          }}
        />
        <span className="eyebrow-muted" aria-live="polite">
          {rows.length} of {members.length} memberships
        </span>
      </div>

      <div className="table-scroll" style={card}>
        <table style={{ width: "100%", minWidth: compact ? 720 : 860, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--line)" }}>
              <th style={th}>
                <button type="button" style={sortButtonStyle} onClick={() => toggleSort("ticker")}>
                  Ticker{arrow("ticker")}
                </button>
              </th>
              <th style={thRight}>
                <button type="button" style={sortButtonStyle} onClick={() => toggleSort("membership")}>
                  Membership{arrow("membership")}
                </button>
              </th>
              <th style={thRight}>Relationship</th>
              <th style={thRight}>
                <button type="button" style={sortButtonStyle} onClick={() => toggleSort("confidence")}>
                  Confidence{arrow("confidence")}
                </button>
              </th>
              <th style={th}>Source</th>
              <th style={thRight}>
                <button type="button" style={sortButtonStyle} onClick={() => toggleSort("sourceDate")}>
                  Source date{arrow("sourceDate")}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((member, index) => (
              <tr
                key={`${member.ticker}-${member.membership_type}-${member.taxonomy_group_id}`}
                style={{
                  borderBottom: index < rows.length - 1 ? "1px solid #ebebeb" : "none",
                  opacity: member.membership_type === "EXCLUDED" ? 0.6 : 1,
                }}
              >
                <td style={{ ...tdMono, fontWeight: 600, color: "var(--ink)" }}>
                  <Link
                    to={`/ticker/${encodeURIComponent(member.ticker)}`}
                    style={{ color: "var(--ink)", textDecoration: "underline" }}
                  >
                    {member.ticker}
                  </Link>
                </td>
                <td style={{ ...td, textAlign: "right" }}>{formatEnumLabel(member.membership_type)}</td>
                <td style={{ ...td, textAlign: "right", color: member.relationship ? "var(--ink)" : "var(--muted)" }}>
                  {relationshipLabel(member)}
                </td>
                <td style={tdRight}>{Math.round(member.confidence * 100)}%</td>
                <td style={{ ...td, maxWidth: 360 }}>
                  {member.source?.startsWith("http") ? (
                    <a href={member.source} target="_blank" rel="noreferrer" style={{ color: "var(--link)" }}>
                      Official source
                    </a>
                  ) : (
                    member.source || "—"
                  )}
                </td>
                <td style={{ ...tdRight, color: "var(--muted)" }}>{formatDateLabel(member.source_as_of)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Leaders and laggards use the primary period where it exists (YTD excess)
// and fall back to the 20D diagnostic only when every YTD value is missing.
function LeadersLaggards({ constituents }: { constituents: ConstituentData[] }) {
  const useYtd = constituents.length > 0 && constituents.some((c) => c.excessYtd !== null);
  const scored = constituents
    .map((c) => ({ c, score: useYtd ? c.excessYtd : c.excess20d }))
    .filter((row): row is { c: ConstituentData; score: number } => row.score !== null && Number.isFinite(row.score))
    .sort((a, b) => b.score - a.score);

  if (scored.length === 0) {
    return (
      <EmptyState
        label="NO PERIOD DATA"
        title="Leaders and laggards cannot be ranked"
        body="Neither YTD nor 20D excess is available for enough members on this snapshot."
        height={120}
      />
    );
  }

  const leaders = scored.slice(0, 5);
  const laggards = scored.slice(-5).reverse();
  const periodLabel = useYtd ? "YTD excess vs IHSG" : "20D excess vs IHSG";

  const column = (title: string, rows: typeof leaders, tone: "up" | "down") => (
    <div style={{ flex: 1, minWidth: 240 }}>
      <div className="eyebrow-muted" style={{ marginBottom: 8 }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {rows.map(({ c, score }) => (
          <div
            key={c.ticker}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: "7px 10px",
              borderRadius: 4,
              background: "var(--surface-subtle)",
              border: "1px solid #efefef",
            }}
          >
            <span style={{ minWidth: 0 }}>
              <Link
                to={`/ticker/${encodeURIComponent(c.ticker)}`}
                style={{ fontFamily: "Geist Mono, monospace", fontSize: 12, fontWeight: 600, color: "var(--ink)" }}
              >
                {c.ticker}
              </Link>
              <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: 8 }}>
                {c.name || "—"}
              </span>
            </span>
            <span
              style={{
                fontFamily: "Geist Mono, monospace",
                fontSize: 12,
                fontVariantNumeric: "tabular-nums",
                color: tone === "up" ? "var(--up)" : "var(--down)",
              }}
            >
              {score >= 0 ? "+" : ""}{score.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div>
      <div className="eyebrow-muted" style={{ marginBottom: 10 }}>
        Ranked on {periodLabel} · {scored.length} of {constituents.length} members with a value
      </div>
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        {column("Leaders", leaders, "up")}
        {column("Laggards", laggards, "down")}
      </div>
    </div>
  );
}

// One comparison model for both detail paths (sector and taxonomy groups) so
// the selector, labels and cell formatting cannot drift between views.
interface ComparableGroup {
  id: string;
  name: string;
  leadership: string;
  diffusion: string;
  dataQuality: string;
  excessYtd: number | null;
  returnYtd: number | null;
  excess20d: number | null;
  excess60d: number | null;
  breadth: number | null;
  breadthDelta: number | null;
  concentration: number | null;
  eligible: number;
  constituents: number;
  ytdEligible: number;
}

function fromSector(sector: SectorData): ComparableGroup {
  return {
    id: sector.id,
    name: sector.name,
    leadership: sector.leadership,
    diffusion: sector.diffusion,
    dataQuality: sector.dataQuality ?? "DATA_GAP",
    excessYtd: sector.excessYtd,
    returnYtd: sector.returnYtd,
    excess20d: sector.excess20d,
    excess60d: sector.excess60d,
    breadth: sector.breadth,
    breadthDelta:
      sector.breadth !== null && sector.prevBreadth !== undefined
        ? sector.breadth - sector.prevBreadth
        : null,
    concentration: sector.concentration,
    eligible: sector.eligibleConstituents,
    constituents: sector.constituents,
    ytdEligible: sector.ytdEligible,
  };
}

function fromTaxonomy(group: TaxonomyGroupData): ComparableGroup {
  return {
    id: group.id,
    name: group.name,
    leadership: group.leadership,
    diffusion: group.diffusion,
    dataQuality: group.dataQuality,
    excessYtd: group.excessYtd,
    returnYtd: group.returnYtd,
    excess20d: group.excess20d,
    excess60d: group.excess60d,
    breadth: group.breadth,
    breadthDelta: group.breadthDelta,
    concentration: group.concentration,
    eligible: group.eligible,
    constituents: group.constituents,
    ytdEligible: group.ytdEligible,
  };
}

function compareValue(value: number | null | undefined, suffix = "%"): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (suffix === "%") return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
}

function peerCoverage(group: ComparableGroup): string {
  return group.constituents > 0 ? `${group.ytdEligible}/${group.constituents}` : "—";
}

function ComparisonPanel({ current, peers }: {
  current: ComparableGroup;
  peers: ComparableGroup[];
}) {
  const [params, setParams] = useSearchParams();
  const compareId = params.get("compare");
  const peer = compareId ? peers.find((candidate) => candidate.id === compareId) : undefined;

  const updateCompare = (value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set("compare", value);
    else next.delete("compare");
    setParams(next, { replace: true });
  };

  const rows: Array<{ label: string; left: string; right: string }> = [
    { label: "YTD excess", left: compareValue(current.excessYtd), right: peer ? compareValue(peer.excessYtd) : "—" },
    { label: "YTD group return", left: compareValue(current.returnYtd), right: peer ? compareValue(peer.returnYtd) : "—" },
    { label: "20D excess", left: compareValue(current.excess20d), right: peer ? compareValue(peer.excess20d) : "—" },
    { label: "60D excess", left: compareValue(current.excess60d), right: peer ? compareValue(peer.excess60d) : "—" },
    { label: "Breadth", left: compareValue(current.breadth), right: peer ? compareValue(peer.breadth) : "—" },
    { label: "Δ Breadth", left: compareValue(current.breadthDelta), right: peer ? compareValue(peer.breadthDelta) : "—" },
    { label: "Top-3 concentration", left: compareValue(current.concentration), right: peer ? compareValue(peer.concentration) : "—" },
    { label: "Eligible / total (20D)", left: `${current.eligible}/${current.constituents}`, right: peer ? `${peer.eligible}/${peer.constituents}` : "—" },
    { label: "YTD eligible / total", left: peerCoverage(current), right: peer ? peerCoverage(peer) : "—" },
    { label: "Leadership", left: formatEnumLabel(current.leadership), right: peer ? formatEnumLabel(peer.leadership) : "—" },
    { label: "Diffusion", left: formatEnumLabel(current.diffusion), right: peer ? formatEnumLabel(peer.diffusion) : "—" },
    { label: "Data quality", left: formatEnumLabel(current.dataQuality), right: peer ? formatEnumLabel(peer.dataQuality) : "—" },
  ];

  return (
    <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <label htmlFor="compare-group" style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>
          Compare with
        </label>
        <select
          id="compare-group"
          aria-label="Comparison group"
          value={peer?.id ?? ""}
          onChange={(e) => updateCompare(e.target.value)}
          style={{
            padding: "7px 11px",
            fontSize: 12,
            borderRadius: 4,
            border: "1px solid var(--line)",
            background: "var(--surface)",
            color: "var(--ink)",
            fontFamily: "Geist, sans-serif",
            cursor: "pointer",
            maxWidth: 320,
          }}
        >
          <option value="">No peer — this group only</option>
          {peers.map((candidate) => (
            <option key={candidate.id} value={candidate.id}>
              {candidate.name}
            </option>
          ))}
        </select>
        <span className="eyebrow-muted">{peers.length} peer groups available</span>
      </div>

      {peer ? (
        <div className="table-scroll">
          <table style={{ width: "100%", minWidth: 460, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--line)" }}>
                <th style={th}>Metric</th>
                <th style={thRight}>{current.name}</th>
                <th style={thRight}>{peer.name}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.label} style={{ borderBottom: index < rows.length - 1 ? "1px solid #ebebeb" : "none" }}>
                  <td style={td}>{row.label}</td>
                  <td style={{ ...tdRight, color: "var(--ink)" }}>{row.left}</td>
                  <td style={{ ...tdRight, color: "var(--muted)" }}>{row.right}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p style={{ margin: 0, fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
          Pick a peer group to place its stored aggregates beside this one. Values are shown
          exactly as the snapshot records them — no difference or percentage change is derived
          between two groups, because they do not share a documented weighting history. IHSG
          appears as the shared benchmark on each chart instead of as a third column.
        </p>
      )}
    </div>
  );
}

function TaxonomyGroupDetail({
  group,
  data,
}: {
  group: TaxonomyGroupData;
  data: AdaptedSnapshot;
}) {
  const [params, setParams] = useSearchParams();
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

  // Shareable URL state: ?period=1M|3M|6M|1Y|ALL. The comparison selector keeps
  // its own ?compare=<groupId> in ComparisonPanel.
  const peers = useMemo(
    () =>
      Object.values(data.taxonomyGroups)
        .filter((candidate) => candidate.taxonomyKind === group.taxonomyKind && candidate.id !== group.id)
        .sort((a, b) => a.name.localeCompare(b.name)),
    [data.taxonomyGroups, group.taxonomyKind, group.id],
  );
  const periodParam = (params.get("period") ?? "").toUpperCase();
  const period: ChartRange = (CHART_PERIODS as string[]).includes(periodParam)
    ? (periodParam as ChartRange)
    : "ALL";

  const updateParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const catalogLabel =
    group.taxonomyKind === "KONGLO" ? "Konglo catalog" : group.taxonomyKind === "THEMES" ? "IDXIC subindustries" : "All Groups catalog";

  const coverageNotes = [
    group.constituents > 0
      ? `${group.eligible} of ${group.constituents} members have the 20D history required for the diagnostic metric (${group.coveragePct.toFixed(0)}% coverage).`
      : "No member counts are recorded for this group in the current snapshot.",
    `${ytdCoverage} members carry YTD history${group.ytdStartDate ? `, measured from ${formatDateLabel(group.ytdStartDate)} against IHSG on the same dates` : "; no YTD baseline is included in this release"}.`,
    group.offScale
      ? "This group is off-scale — its value sits outside the standard map axis."
      : null,
    constituents.length === 0
      ? "Constituent rows are not present in this snapshot; membership definitions are preserved and no synthetic rows are shown."
      : null,
    pricePoints.length === 0
      ? "No persisted equal-weight price history for this group, so the benchmark chart stays hidden rather than backfilled."
      : null,
    "Membership is an analyst-defined research lens, not an official IDX classification, and groups overlap so their members are never summed into a market share.",
  ].filter((note): note is string => note !== null);

  return (
    <div className="taxonomy-detail-page content-shell" style={{ padding: "36px var(--page-gutter)", maxWidth: "var(--content-max)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20, marginBottom: 24, flexWrap: "wrap" }}>
        <div>
          <CatalogBackLink taxonomyKind={group.taxonomyKind} groupId={group.id} label={catalogLabel} />
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 16, marginBottom: 8 }}>
            <div className="eyebrow-muted">
              {group.taxonomyName} · group detail
            </div>
            <EvidenceBadge kind="CLASSIFICATION" compact />
          </div>
          <h1 style={{ margin: 0, fontSize: 30, fontWeight: 400, letterSpacing: "-1.5px" }}>
            {group.name}
          </h1>
          <div
            style={{
              marginTop: 8,
              fontFamily: "Geist Mono, monospace",
              fontSize: 11,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: "var(--muted)",
            }}
          >
            {formatEnumLabel(group.taxonomyKind)} · {formatSnapshotId(data.payload.snapshot_id, data.payload.as_of)}
          </div>
          <p style={{ margin: "8px 0 0", color: "var(--muted)", fontSize: 13, lineHeight: 1.5, maxWidth: 640 }}>
            Aggregate metrics use the selected release. Membership follows dated ownership evidence
            or captured IDXIC subindustry classifications.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <Link
            to={`/map?taxonomy=${group.taxonomyKind}&mode=groups`}
            style={{ padding: "9px 13px", border: "1px solid var(--line)", color: "var(--ink)", textDecoration: "none", fontSize: 12, borderRadius: 4 }}
          >
            Rotation →
          </Link>
          <Link
            to={`/groups?taxonomy=${group.taxonomyKind}&view=table`}
            style={{ padding: "9px 13px", border: "1px solid var(--line)", color: "var(--ink)", textDecoration: "none", fontSize: 12, borderRadius: 4 }}
          >
            Table →
          </Link>
          <Link to="/overview" style={{ padding: "9px 13px", border: "1px solid #202325", color: "var(--ink)", textDecoration: "none", fontSize: 12 }}>
            Overview
          </Link>
        </div>
      </div>

      <div style={{ ...card, padding: "18px 22px", marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <LeadershipChip state={group.leadership as Parameters<typeof LeadershipChip>[0]["state"]} />
          <DiffusionChip state={group.diffusion as Parameters<typeof DiffusionChip>[0]["state"]} />
          <span style={{ fontFamily: "Geist Mono, monospace", fontSize: 11, color: "var(--muted)" }}>
            {formatCountLabel(group.constituents, "ticker")} · {group.eligible} with 20D history
          </span>
        </div>
        <div className="explorer-metrics" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginTop: 16 }}>
          <MetricCard label="YTD excess" value={metric(group.excessYtd)} sub={group.ytdStartDate ? `from ${formatDateLabel(group.ytdStartDate)} vs IHSG` : "selected release dates"} />
          <MetricCard label="YTD group return" value={metric(group.returnYtd)} sub={`${ytdCoverage} with YTD history`} />
          <MetricCard label="IHSG YTD" value={metric(group.benchmarkYtd)} sub="same dates and price basis" />
          <MetricCard label="20D excess" value={metric(group.excess20d)} sub="diagnostic vs IHSG" />
          <MetricCard label="Breadth" value={metric(group.breadth, "%")} sub={group.breadthDelta === null ? "current level" : `${metric(group.breadthDelta)} vs prior`} />
          <MetricCard label="Concentration" value={metric(group.concentration, "%")} sub="Top-3 contribution" />
        </div>
      </div>

      <details className="source-details">
        <summary>Sources and coverage</summary>
        <div style={{ ...card, padding: "16px 18px", marginTop: 10 }}>
          <WindowCapNotice data={data} compact />
          <ul style={{ margin: "12px 0 0", paddingLeft: 18, fontSize: 12, color: "var(--muted)", lineHeight: 1.7 }}>
            {coverageNotes.map((note) => <li key={note}>{note}</li>)}
          </ul>
        </div>
      </details>

      <SectionHead label="Performance and membership" />
      <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>Constituent performance</div>
          <span className="eyebrow-muted">YTD is primary · 20D and 60D are diagnostics</span>
        </div>
        {constituents.length > 0 ? (
          <ConstituentTable constituents={constituents} />
        ) : (
          <div style={{ color: "var(--muted)", fontSize: 12, padding: "12px 0" }}>
            Membership definitions and constituent counts are shown below.
          </div>
        )}
      </div>

      <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>Leaders and laggards</div>
        </div>
        <LeadersLaggards constituents={constituents} />
      </div>

      <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>Contribution and price context</div>
          <span className="eyebrow-muted">Persisted price history only</span>
        </div>
        {constituents.length > 0 && <ContribBars constituents={constituents} />}
        {pricePoints.length > 0 ? (
          <div style={{ marginTop: 16 }}>
            <div className="eyebrow-muted" style={{ marginBottom: 6 }}>
              Period tabs live on the chart; the selected period is kept in the URL.
            </div>
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
              initialRange={period}
              onRangeChange={(next) => updateParam("period", next === "ALL" ? null : next)}
              height={260}
            />
          </div>
        ) : (
          <div style={{ marginTop: 12, color: "var(--muted)", fontSize: 12 }}>
            Price history is not part of this group release.
          </div>
        )}
      </div>

      <SectionHead label="Comparison" />
      <ComparisonPanel current={fromTaxonomy(group)} peers={peers.map(fromTaxonomy)} />

      <SectionHead label="Membership evidence" />
      <div style={{ ...card, padding: "16px 18px" }}>
        <MembershipTable members={members} />
        <div style={{ marginTop: 12, fontSize: 11, color: "var(--muted)", lineHeight: 1.55 }}>
          Relationship subtype (control / subsidiary / affiliate / cross-shareholding /
          founder-director / ecosystem) is shown only where a source-backed value is stored.
          Confidence and source date are reproduced exactly as recorded and are never upgraded
          to fit a narrative.
        </div>
      </div>

      <div style={{ marginTop: 12, color: "var(--muted)", fontSize: 11, lineHeight: 1.5 }}>
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
  if (!hasContext) return null;
  const verdict = hasContext ? "CONTEXT_ONLY" : status === "FAILED" ? "FAILED" : "DATA_GAP";
  const verdictColor = hasContext ? "var(--accent-ink)" : status === "FAILED" ? "var(--down)" : "var(--accent-ink)";
  return (
    <div style={{ ...card, padding: "16px 18px", minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 10 }}>
        <div className="eyebrow-muted">{label}</div>
        <DataStatusChip status={status} />
      </div>
      <p style={{ margin: "0 0 12px", fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>
        {context.note || (hasContext
          ? "Qualitative web context only; it does not change the confirmation metric."
          : "No source-backed context is attached to this snapshot.")}
      </p>
      {hasContext ? (
        <>
          <div style={{ fontSize: 11, color: "var(--accent-ink)", marginBottom: 8 }}>
            Market-level sources; not attributed to {groupName}.
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {context.records.slice(0, 3).map((record) => (
              <div key={`${record.request_id ?? record.url}-${record.url}`} style={{ borderTop: "1px solid var(--line)", paddingTop: 9 }}>
                <a
                  href={record.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: "var(--link)", fontSize: 12, fontWeight: 500, lineHeight: 1.35, textDecoration: "none" }}
                >
                  {record.title}
                </a>
                <div style={{ marginTop: 4, fontSize: 11, color: "var(--muted)", lineHeight: 1.45 }}>
                  {shortenEvidence(record.content, 150)}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div style={{ fontSize: 12, color: "var(--muted)" }}>No eligible source was attached.</div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14 }}>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>Overall</span>
        <span
          style={{
            fontFamily: "Geist Mono, monospace",
            fontSize: 10,
            letterSpacing: "0.071em",
            textTransform: "uppercase",
            color: verdictColor,
            boxShadow: "0 0 0 1px var(--line)",
            background: "var(--surface)",
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
  const historyState = useHistoricalComparison();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selected, setSelected] = useState<string>("");
  const sectors = data?.sectors ?? [];
  const constituentsByGroup = data?.constituentsByGroup ?? {};
  const groupPriceHistory = data?.groupPriceHistory ?? {};
  const dataSources = data?.dataSources ?? { breadthHistory: false, constituents: false, fundamentals: false, foreignFlow: false, trajectory: false };
  const queryGroup = new URLSearchParams(location.search).get("group") ?? undefined;
  const queryTaxonomy = normalizeTaxonomyKind(new URLSearchParams(location.search).get("taxonomy"));
  // Shareable chart period for the sector detail path. ?period=1M|3M|6M|1Y|ALL
  // is read on load and written back when a period tab is chosen, so the view
  // can be linked and so the sector path behaves like the taxonomy path.
  const periodParam = (searchParams.get("period") ?? "").toUpperCase();
  const sectorPeriod: ChartRange = (CHART_PERIODS as string[]).includes(periodParam)
    ? (periodParam as ChartRange)
    : "ALL";
  const setSectorPeriod = (next: ChartRange) => {
    const params = new URLSearchParams(searchParams);
    if (next === "ALL") params.delete("period");
    else params.set("period", next);
    setSearchParams(params, { replace: true });
  };
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
          <EmptyState label="GROUP DETAILS" title="This group is outside the selected release" body="Choose a group from the current catalog to view its supported members and metrics." height={220} />
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
  const matchedReplay = historyState.data?.weekly.flatMap((week) => {
    const group = week.groups.find((candidate) => candidate.group_id === sector.id || candidate.name === sector.name);
    return group ? [{ as_of: week.as_of, ...group }] : [];
  }) ?? [];
  const groupPricePoints = groupPriceHistory[sector.id] ?? [];
  const manifestEntry = data.payload.manifest.entries[0];
  const hasResearchContext = (["fundamentals", "foreign_flow", "events"] as ResearchContextCategory[])
    .some(category => getTavilyCategory(data.payload, category).records.length > 0);
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
          <CatalogBackLink taxonomyKind="SECTOR" groupId={sector.id} label="All Groups catalog" />
          <div className="eyebrow-muted" style={{ marginBottom: 8, marginTop: 12 }}>
            IDX → Group → {sector.name} · {sector.eligibleConstituents}/{sector.constituents} eligible
          </div>
          <h1
            style={{
              fontSize: 30,
              fontWeight: 400,
              color: "var(--ink)",
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
          onChange={(e) => {
            setSelected(e.target.value);
            const next = new URLSearchParams(searchParams);
            next.set("taxonomy", "SECTOR");
            next.set("group", e.target.value);
            setSearchParams(next, { replace: true });
          }}
          style={{
            padding: "8px 14px",
            fontSize: 13,
            borderRadius: 6,
            border: "none",
            boxShadow: "0 0 0 1px var(--line)",
            background: "var(--surface)",
            color: "var(--ink)",
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
              color: "var(--muted)",
              boxShadow: "0 0 0 1px var(--line)",
              background: "var(--surface)",
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            {sector.eligibleConstituents} eligible / {sector.constituents} total
          </span>
          <span style={{ fontFamily: "Geist Mono", fontSize: 11, color: "var(--muted)" }}>
            Leadership state persisted for {sector.persistence} observation{sector.persistence !== 1 ? "s" : ""}
          </span>
          {sector.prevLeadership && (
            <span style={{ fontFamily: "Geist Mono", fontSize: 10, color: "var(--accent-ink)", border: "1px solid var(--line)", padding: "2px 6px", borderRadius: 4 }}>
              {formatEnumLabel(sector.prevLeadership)} → {formatEnumLabel(sector.leadership)}
            </span>
          )}
        </div>
        <p style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.6, maxWidth: 720 }}>
          {sector.interpretation}
        </p>
        <div style={{ marginTop: 10, display: "flex", gap: 16, flexWrap: "wrap", fontSize: 11, color: "var(--muted)", fontFamily: "Geist Mono" }}>
          <span>YTD Excess <b style={{ color: sector.excessYtd !== null && sector.excessYtd >= 0 ? "var(--up)" : "var(--down)" }}>{displayMetric(sector.excessYtd)}</b></span>
          <span>20D Excess <b style={{ color: sector.excess20d !== null && sector.excess20d >= 0 ? "var(--up)" : "var(--down)" }}>{displayMetric(sector.excess20d)}</b></span>
          <span>Breadth <b>{displayMetric(sector.breadth)}</b> {delta !== undefined && delta !== null ? <span style={{ color: delta > 0 ? "var(--up)" : delta < 0 ? "var(--down)" : "var(--muted)" }}>({formatPercent(delta)} vs prior observation)</span> : ""}</span>
          <span>Top-3 <b>{displayMetric(sector.concentration)}</b></span>
          {sector.missingConstituents > 0 && (
            <span style={{ color: "var(--accent-ink)" }}>{sector.missingConstituents} constituent{sector.missingConstituents !== 1 ? "s" : ""} missing from the 20D metric</span>
          )}
        </div>
        <div style={{ marginTop: 8, fontSize: 10, color: "var(--muted)" }}>
          {sector.diffusion === "UNCONFIRMED" ? "Diffusion —" : `Diffusion: ${formatEnumLabel(sector.diffusion)}${sector.prevDiffusion ? ` (previous ${formatEnumLabel(sector.prevDiffusion)})` : ""}${sector.diffusionV2 ? ` · v2 detail ${formatEnumLabel(sector.diffusionV2)}` : ""}`}
        </div>
      </div>

      <div className="explorer-metrics" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 24 }}>
        <MetricCard
          label="YTD excess"
          value={displayMetric(sector.excessYtd)}
          sub={sector.ytdStartDate ? `from ${formatDateLabel(sector.ytdStartDate)} vs IHSG` : "selected release dates"}
          color={
            sector.excessYtd === null
              ? "var(--muted)"
              : sector.excessYtd >= 0
                ? "var(--up)"
                : "var(--down)"
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
          sub={delta != null ? `${formatPercent(delta)} vs prior` : "current level"}
          color={sector.breadth === null ? "var(--muted)" : "var(--up)"}
        />
        <MetricCard
          label="Concentration"
          value={displayMetric(sector.concentration)}
          sub="Top-3 contribution"
          color={
            sector.concentration === null
              ? "var(--muted)"
              : sector.concentration > 60
                ? "var(--down)"
                : sector.concentration > 45
                  ? "var(--accent-ink)"
                  : "var(--up)"
          }
        />
        <MetricCard
          label="Constituents"
          value={String(sector.constituents)}
          sub={`${sector.eligibleConstituents} eligible / ${sector.constituents} total`}
        />
      </div>

      <SectionHead label="Time series" />
      {matchedReplay.length > 0 ? (
        <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", marginBottom: 6 }}>
            {sector.name} · historical price replay using current membership
          </div>
          <p style={{ margin: "0 0 12px", color: "var(--muted)", fontSize: 11, lineHeight: 1.5 }}>
            {matchedReplay[0].cohort_count} fixed contributors · membership reference {formatDateLabel(historyState.data!.membership_as_of)} · leadership, breadth, and diffusion are replay measures; current release readings above remain separate.
          </p>
          <div className="table-scroll">
            <table className="matched-replay-table"><thead><tr><th>As of</th><th>20D excess</th><th>60D excess</th><th>Breadth</th><th>Weekly breadth</th><th>Diffusion</th><th>Phase change</th></tr></thead>
              <tbody>{matchedReplay.map((point) => <tr key={point.as_of}>
                <td>{formatDateLabel(point.as_of)}</td><td>{formatPercent(point.excess_return_20d)}</td><td>{formatPercent(point.excess_return_60d)}</td>
                <td>{point.breadth_pct === null ? "—" : `${point.breadth_pct.toFixed(1)}%`}</td><td>{point.breadth_change_pp === null ? "Baseline" : `${point.breadth_change_pp > 0 ? "+" : ""}${point.breadth_change_pp.toFixed(1)} pp`}</td>
                <td>{point.diffusion === "UNCONFIRMED" ? "Baseline observation" : formatEnumLabel(point.diffusion)}</td>
                <td>{replayTransitionLabel(point.leadership_transition ?? point.diffusion_transition)}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </div>
      ) : dataSources.breadthHistory && groupBreadthHistory.length > 0 ? (
        <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", marginBottom: 8 }}>
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
          <div style={{ padding: 16, color: "var(--muted)", fontSize: 12 }}>
            <Link to={`/map?taxonomy=SECTOR&mode=groups&q=${encodeURIComponent(sector.name)}`}>Open the dated group readings →</Link>
          </div>
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
            initialRange={sectorPeriod}
            onRangeChange={setSectorPeriod}
            height={300}
          />
          <div style={{ marginTop: 10, fontSize: 11, color: "var(--muted)", lineHeight: 1.45 }}>
            Descriptive equal-weight group performance versus IHSG. This chart is
            presentation-only and does not change leadership or diffusion signals.
          </div>
        </div>
      ) : (
        <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
          <EmptyState
            label="NO PRICE SERIES"
            title="Group price history"
            body="The selected release does not include this group's daily price series."
            height={140}
          />
        </div>
      )}

      <SectionHead label="Constituents — driver decomposition" />
      {dataSources.constituents && constituents.length > 0 ? (
        <>
          <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>Absolute 20D move contribution</span>
              <span className="eyebrow-muted">Top-3 absolute move: {displayMetric(sector.concentration)} · top-1 capped at 100% · equal-weight convention</span>
            </div>
            <p style={{ fontSize: 11, color: "var(--muted)", lineHeight: 1.5, margin: "0 0 12px" }}>
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
            <div style={{ marginTop: 12, display: "flex", gap: 16, fontSize: 11, color: "var(--muted)", fontFamily: "Geist Mono", flexWrap: "wrap" }}>
              <span>Positive contributors: {constituents.filter((c) => c.excess20d !== null && c.excess20d > 0).length}</span>
              <span>Negative contributors: {constituents.filter((c) => c.excess20d !== null && c.excess20d <= 0).length}</span>
              <span>Participating: {constituents.filter((c) => c.participating).length}/{constituents.filter((c) => c.excess20d !== null).length}</span>
            </div>
          </div>
          <ConstituentTable constituents={constituents} />
          <div style={{ marginTop: 8, fontSize: 10, color: "var(--muted)", lineHeight: 1.4 }}>
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

      <details className="source-details" style={{ marginBottom: 16 }}>
        <summary>Sources and coverage</summary>
        <div style={{ ...card, padding: "16px 18px", marginTop: 10 }}>
        <WindowCapNotice data={data} compact />
        <ul style={{ margin: "12px 0 0", paddingLeft: 18, fontSize: 12, color: "var(--muted)", lineHeight: 1.7 }}>
          <li>
            {sector.eligibleConstituents} of {sector.constituents} members carry the 20D history
            required for the diagnostic metric.
          </li>
          <li>
            {sector.ytdEligible} of {sector.constituents} members carry YTD history
            {sector.ytdStartDate
              ? `, measured from ${formatDateLabel(sector.ytdStartDate)} against IHSG on the same dates`
              : "; no YTD baseline is included in this release"}
            .
          </li>
          {sector.missingConstituents > 0 && (
            <li style={{ color: "var(--accent-ink)" }}>
              {sector.missingConstituents} member{sector.missingConstituents !== 1 ? "s are" : " is"} missing from the 20D metric.
            </li>
          )}
          <li>
            Sectors are mutually exclusive in this snapshot, so their member counts can be summed;
            Theme and Konglo groups overlap and must not be.
          </li>
        </ul>
        </div>
      </details>

      <SectionHead label="Leaders and laggards" />
      <div style={{ ...card, padding: "16px 18px", marginBottom: 12 }}>
        <LeadersLaggards constituents={constituents} />
      </div>

      <SectionHead label="Comparison" />
      <ComparisonPanel
        current={fromSector(sector)}
        peers={sectors.filter((candidate) => candidate.id !== sector.id).map(fromSector)}
      />

      {hasResearchContext && <>
        <SectionHead label="Research context" />
        <div className="explorer-confirmation-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
          <ResearchEvidencePanel label="Fundamentals" category="fundamentals" payload={data.payload} groupName={sector.name} />
          <ResearchEvidencePanel label="Foreign flow" category="foreign_flow" payload={data.payload} groupName={sector.name} />
          <ResearchEvidencePanel label="Events / catalyst" category="events" payload={data.payload} groupName={sector.name} />
        </div>
      </>}

      <SectionHead label="What could contradict this signal?" />
      {sector.contradictions.length ? (
        <ol style={{ margin: "0 0 12px", paddingLeft: 18, fontSize: 13, lineHeight: 1.6 }}>
          {sector.contradictions.map((c) => (
            <li key={c.metric}>
              <strong>{c.severity === "CRITICAL" ? "CRITICAL" : "Warning"}</strong>
              {` — ${c.label}`}
              {c.evidence ? <span style={{ color: "var(--muted)" }}>{` — ${c.evidence}`}</span> : null}
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
          border: "1px solid var(--line)",
          background: "var(--surface-subtle)",
          padding: "16px 18px",
          margin: "12px 0 40px",
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", marginBottom: 8 }}>Screen invalidation</div>
        {sector.invalidation.length ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--ink)", lineHeight: 1.6 }}>
            {sector.invalidation.map((row, i) => (
              <li key={i}>{submissionInvalidationLabel(row)}</li>
            ))}
          </ul>
        ) : (
          <p style={{ fontSize: 12, color: "var(--muted)", margin: 0 }}>
            Per-group invalidation conditions are not emitted by the current web snapshot.
            Review the versioned methodology and the next comparable snapshot before treating
            a state as changed.
          </p>
        )}
        <p
          style={{
            fontSize: 10,
            color: "var(--muted)",
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
