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
  DATA_GAP: "Data gap",
  READY_WITH_GAPS: "Ready with gaps",
  SAMPLE_ONLY: "Sample only",
  CONTEXT_ONLY: "Context only",
  DIRECT_SOURCE_REVIEW: "Direct source review",
  ANALYST_DEFINED: "Analyst-defined",
  ANALYST_DEFINED_PROTOTYPE: "Analyst-defined prototype",
  PROTOTYPE_CONFIG: "Prototype config",
  PRIMARY_INDEX: "Primary index",
  PUBLIC_PROTOTYPE: "Public prototype",
  SECTORS_LIVE: "Live Sectors",
  SECTORS_FIXTURE: "Sectors fixture",
  DEMO_FIXTURE: "Demo fixture",
  NET_BUY: "Net buy",
  NET_SELL: "Net sell",
  UNCONFIRMED: "Unconfirmed",
  NO_COMPARABLE_PRIOR: "No comparable prior",
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

export function formatCountLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
