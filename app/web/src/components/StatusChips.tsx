import type { LeadershipState, DiffusionState, DataStatus } from "../data/snapshot";
import { formatEnumLabel } from "../data/format";

/* Vercel-style chips: hairline ring, mono text, color only on text */

const leadershipCfg: Record<LeadershipState, { color: string; dot: string }> = {
  LEADING:     { color: 'var(--color-leading)', dot: 'var(--color-leading)' },
  IMPROVING:   { color: 'var(--color-improving)', dot: 'var(--color-improving)' },
  WEAKENING:   { color: 'var(--color-weakening)', dot: 'var(--color-weakening)' },
  LAGGING:     { color: 'var(--muted)', dot: 'var(--muted)' },
  UNCONFIRMED: { color: 'var(--muted)', dot: 'var(--muted)' },
};

const diffusionCfg: Record<DiffusionState, { color: string; symbol: string }> = {
  BROADENING:  { color: 'var(--color-improving)', symbol: '↑' },
  STABLE:      { color: 'var(--muted)', symbol: '→' },
  NARROWING:   { color: 'var(--color-weakening)', symbol: '↓' },
  UNCONFIRMED: { color: 'var(--muted)', symbol: '?' },
};

const dataCfg: Record<DataStatus, { color: string; dotColor: string }> = {
  READY: { color: "var(--up)", dotColor: "var(--up)" },
  READY_WITH_GAPS: { color: "var(--accent-ink)", dotColor: "var(--accent-ink)" },
  PARTIAL: { color: "var(--accent-ink)", dotColor: "var(--accent-ink)" },
  STALE: { color: "var(--muted)", dotColor: "var(--muted)" },
  FAILED: { color: "var(--down)", dotColor: "var(--down)" },
  DATA_GAP: { color: "var(--accent-ink)", dotColor: "var(--accent-ink)" },
  UNAVAILABLE: { color: "var(--muted)", dotColor: "var(--muted)" },
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
  background: 'var(--surface)',
};

export function LeadershipChip({ state, small }: { state: LeadershipState; small?: boolean }) {
  if (state === "UNCONFIRMED") return <span aria-label="No classified leadership state">—</span>;
  const cfg = leadershipCfg[state];
  return (
    <span style={{ ...chipBase, fontSize: small ? 10 : 11, color: cfg.color }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: cfg.dot, display: 'inline-block', flexShrink: 0 }} />
      {formatEnumLabel(state)}
    </span>
  );
}

export function DiffusionChip({ state, small }: { state: DiffusionState; small?: boolean }) {
  if (state === "UNCONFIRMED") return <span aria-label="No comparable diffusion reading">—</span>;
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
  const label = status === "READY" ? "Ready" : "—";
  return (
    <span aria-label={label} style={{ ...chipBase, fontSize: 11, color: cfg.color }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: cfg.dotColor, display: 'inline-block', flexShrink: 0 }} />
      {label}
    </span>
  );
}

export function leadershipColor(state: LeadershipState): string {
  return leadershipCfg[state].color;
}
