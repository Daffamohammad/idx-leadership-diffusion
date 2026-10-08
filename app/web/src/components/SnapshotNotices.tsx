// SnapshotNotices — fail-closed banners for new backend bundle states.
//
// Every notice renders ONLY from an explicitly persisted backend signal:
//   - `complete === false` → stale partial bundle warning (pre-sentinel write)
//   - `pagination_incomplete === true` → incomplete pagination warning
//   - 90-day window cap → YTD limitation notice (render near YTD figures)
// Absent/unknown backend state renders nothing authoritative: no banner is
// better than a fabricated one. All copy keeps the quantitative_use=false
// display boundary (descriptive, never a signal).

import type { AdaptedSnapshot } from "../data/adapter";
import { EvidenceBadge } from "./EvidenceModel";
import { formatDateLabel } from "../data/format";

const bannerBase: React.CSSProperties = {
  borderRadius: 6,
  padding: "10px 14px",
  fontSize: 12,
  lineHeight: 1.55,
};

export function BundleNotices({ data }: { data: AdaptedSnapshot | null }) {
  if (!data) return null;
  const items: React.ReactNode[] = [];
  if (data.bundleComplete === false) {
    items.push(
      <div
        key="complete"
        role="alert"
        style={{
          ...bannerBase,
          background: "var(--tint-alert)",
          border: "1px solid var(--alert-line)",
          color: "var(--alert-ink)",
        }}
      >
        <strong>Data needs verification.</strong> Data as of {formatDateLabel(data.payload.as_of)}.
        {" "}Bundle completeness has not been verified. Treat these results as provisional.
      </div>,
    );
  }
  if (data.paginationIncomplete) {
    items.push(
      <div
        key="pagination"
        role="alert"
        style={{
          ...bannerBase,
          background: "var(--tint-warn)",
          border: "1px solid #ffe082",
          color: "var(--accent-ink)",
        }}
      >
        <strong>Incomplete pagination.</strong> The provider reported a partial
        page window for this data package, so universe coverage may be understated.
        Coverage denominators on this page already reflect only observed rows.
      </div>,
    );
  }
  const coverage = data.payload.coverage;
  const boundedAnalysis =
    coverage?.analysis_scope === "BOUNDED_DEMO" ||
    (coverage?.analysis_scope === undefined && coverage?.is_prefix_sample === true);
  if (boundedAnalysis) {
    const listed = data.listingRegistry?.listedCount ?? coverage?.security_master_total ?? coverage?.discovered_count;
    const analyzed = coverage?.analysis_universe_count ?? coverage?.used_count;
    const fullListing = data.listingRegistry?.fullAccessibleUniverseListed ?? (coverage?.full_accessible_universe_listed === true);
    items.push(
      <div
        key="analysis-scope"
        role="note"
        style={{
          ...bannerBase,
          background: "var(--surface-subtle)",
          border: "1px solid var(--line)",
          color: "var(--muted)",
        }}
      >
        <strong>Price-history coverage.</strong>{" "}
        {fullListing
          ? `The full accessible listing${listed !== undefined ? ` (${listed} securities)` : ""} is retained;`
          : `This data package retains a bounded listing${listed !== undefined ? ` (${listed} securities)` : ""};`}{" "}
        daily history and group metrics use
        {analyzed !== undefined ? ` ${analyzed} selected securities` : " selected securities"}
        {" "}within the available price history.
      </div>,
    );
  }
  if (items.length === 0) return null;
  return (
    <div
      className="content-shell"
      style={{ paddingTop: 16, paddingBottom: 0, display: "grid", gap: 8 }}
    >
      {items}
    </div>
  );
}

/**
 * 90-day history-window limitation notice. Render wherever YTD figures are
 * shown (Group Explorer, Groups Table, Methodology coverage): a capped
 * window means YTD baselines may be unavailable, never silently short.
 */
export function WindowCapNotice({
  data,
  compact = false,
}: {
  data: AdaptedSnapshot | null;
  compact?: boolean;
}) {
  if (!data?.windowCapped90d) return null;
  return (
    <div
      role="note"
      aria-label="90-day history limitation"
      style={{
        ...bannerBase,
        background: "var(--surface-subtle)",
        border: "1px solid var(--line)",
        color: "var(--muted)",
        fontSize: compact ? 11 : 12,
      }}
    >
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <EvidenceBadge kind="CONTEXT" compact />
        <span>
          <strong>90-day history window.</strong>{" "}
          {data.windowCapNote ??
            "Price/benchmark history is truncated to the latest 90 calendar days; YTD baselines may be unavailable."}{" "}
          YTD figures below cover only the persisted window.
        </span>
      </span>
    </div>
  );
}
