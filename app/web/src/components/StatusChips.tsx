import type { LeadershipState, DiffusionState, DataStatus } from "../data/snapshot";
import { formatEnumLabel } from "../data/format";

/* Vercel-style chips: hairline ring, mono text, color only on text */

const leadershipCfg: Record<LeadershipState, { color: string; dot: string }> = {
  LEADING:     { color: '#54718b', dot: '#54718b' },
  IMPROVING:   { color: '#438b82', dot: '#438b82' },
  WEAKENING:   { color: '#ad6765', dot: '#ad6765' },
  LAGGING:     { color: '#7c858c', dot: '#7c858c' },
  UNCONFIRMED: { color: '#7c858c', dot: '#7c858c' },
};

const diffusionCfg: Record<DiffusionState, { color: string; symbol: string }> = {
  BROADENING:  { color: '#438b82', symbol: '↑' },
  STABLE:      { color: '#7c858c', symbol: '→' },
  NARROWING:   { color: '#ad6765', symbol: '↓' },
  UNCONFIRMED: { color: '#7c858c', symbol: '?' },
};

const dataCfg: Record<DataStatus, { color: string; dotColor: string }> = {
  READY: { color: "#297a3a", dotColor: "#297a3a" },
  READY_WITH_GAPS: { color: "#7a5010", dotColor: "#7a5010" },
  PARTIAL: { color: "#7a5010", dotColor: "#7a5010" },
  STALE: { color: "#5a5a5a", dotColor: "#8f8f8f" },
  FAILED: { color: "#8f2424", dotColor: "#8f2424" },
  DATA_GAP: { color: "#7a5010", dotColor: "#7a5010" },
  UNAVAILABLE: { color: "#7c858c", dotColor: "#8f8f8f" },
};

const chipBase: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  fontFamily: 'Geist Mono, ui-monospace, monospace',
  fontWeight: 400,
  letterSpacing: '0.02em',
  textTransform: 'none' as const,
  padding: '2px 7px',
  borderRadius: 4,
  whiteSpace: 'nowrap' as const,
  boxShadow: '#dfe2e1 0px 0px 0px 1px',
  background: '#ffffff',
};

export function LeadershipChip({ state, small }: { state: LeadershipState; small?: boolean }) {
  const cfg = leadershipCfg[state];
  return (
    <span style={{ ...chipBase, fontSize: small ? 10 : 11, color: cfg.color }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: cfg.dot, display: 'inline-block', flexShrink: 0 }} />
      {formatEnumLabel(state)}
    </span>
  );
}

export function DiffusionChip({ state, small }: { state: DiffusionState; small?: boolean }) {
  const cfg = diffusionCfg[state];
  return (
    <span style={{ ...chipBase, fontSize: small ? 10 : 11, color: cfg.color }}>
      <span style={{ lineHeight: 1, fontSize: small ? 9 : 10 }}>{cfg.symbol}</span>
      {formatEnumLabel(state)}
    </span>
  );
}

export function DataStatusChip({ status }: { status: DataStatus }) {
  const cfg = dataCfg[status];
  return (
    <span style={{ ...chipBase, fontSize: 11, color: cfg.color }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: cfg.dotColor, display: 'inline-block', flexShrink: 0 }} />
      {formatEnumLabel(status)}
    </span>
  );
}

export function leadershipColor(state: LeadershipState): string {
  return leadershipCfg[state].color;
}
