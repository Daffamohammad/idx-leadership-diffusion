export function formatIdrCompact(value: number, fractionDigits = 2): string {
  if (!Number.isFinite(value)) return "—";
  const absolute = Math.abs(value);
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  if (absolute >= 1_000_000_000_000) {
    return `${sign}${(absolute / 1_000_000_000_000).toFixed(fractionDigits)}T IDR`;
  }
  if (absolute >= 1_000_000_000) {
    return `${sign}${(absolute / 1_000_000_000).toFixed(fractionDigits)}B IDR`;
  }
  if (absolute >= 1_000_000) {
    return `${sign}${(absolute / 1_000_000).toFixed(fractionDigits)}M IDR`;
  }
  return `${sign}${absolute.toLocaleString("en-US", {
    maximumFractionDigits: fractionDigits,
  })} IDR`;
}

const LABEL_OVERRIDES: Record<string, string> = {
  DATA_GAP: "—",
  READY_WITH_GAPS: "Partial coverage",
  SAMPLE_ONLY: "Context only",
  CONTEXT_ONLY: "Context only",
  DIRECT_SOURCE_REVIEW: "Direct source review",
  ANALYST_DEFINED: "Analyst-defined",
  ANALYST_DEFINED_PROTOTYPE: "Research grouping",
  PROTOTYPE_CONFIG: "Configured grouping",
  PRIMARY_INDEX: "Primary index",
  PUBLIC_PROTOTYPE: "IDX research release",
  THIRD_PARTY: "Captured classification source",
  SECTORS_LIVE: "Live Sectors",
  SECTORS_FIXTURE: "Sectors fixture",
  DEMO_FIXTURE: "Demo fixture",
  NET_BUY: "Net buy",
  NET_SELL: "Net sell",
  UNCONFIRMED: "—",
  NO_COMPARABLE_PRIOR: "—",
  COMPATIBLE: "Comparable",
  INCOMPARABLE: "Not comparable",
};

export function formatEnumLabel(value: string | null | undefined): string {
  if (!value) return "—";
  const normalized = value.trim().toUpperCase();
  if (LABEL_OVERRIDES[normalized]) return LABEL_OVERRIDES[normalized];
  return normalized
    .split("_")
    .filter(Boolean)
    .map((part) => {
      if (part === "IDX" || part === "IHSG" || part === "IDR") return part;
      if (/^\d+D$/.test(part)) return part;
      return part.charAt(0) + part.slice(1).toLowerCase();
    })
    .join(" ");
}

export function formatDateLabel(value: string | null | undefined): string {
  if (!value) return "—";
  const match = value.slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return value;
  const [, year, month, day] = match;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${Number(day)} ${months[Number(month) - 1] ?? month} ${year}`;
}

/** Keep internal snapshot identifiers out of visible copy. */
export function formatSnapshotId(
  snapshotId: string | null | undefined,
  asOf?: string | null,
): string {
  const sourceDate = asOf || String(snapshotId ?? "").match(/(\d{4}-\d{2}-\d{2})/)?.[1];
  return sourceDate ? formatDateLabel(sourceDate) : formatEnumLabel(snapshotId);
}

export function formatCountLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

/** Display-only percentage formatter shared by maps, cards, and tables. */
export function formatPercent(value: number | null | undefined, fractionDigits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(fractionDigits)}%`;
}

export function formatDeltaPercent(value: number | null | undefined, fractionDigits = 1): string {
  return formatPercent(value, fractionDigits);
}

export function formatStatusLabel(value: string | null | undefined): string {
  return formatEnumLabel(value);
}

export function formatProviderMode(value: string | null | undefined): string {
  return formatEnumLabel(value);
}

export function formatSourceKind(value: string | null | undefined): string {
  return formatEnumLabel(value);
}

export function formatFlowDirection(value: string | null | undefined): string {
  return formatEnumLabel(value);
}
