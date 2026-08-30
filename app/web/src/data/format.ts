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
