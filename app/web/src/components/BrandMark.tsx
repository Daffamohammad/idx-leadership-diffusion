interface BrandMarkProps { size?: number; }

export function BrandMark({ size = 32 }: BrandMarkProps) {
  return (
    <svg viewBox="0 0 36 36" width={size} height={size} role="img" aria-label="IDX Leadership Diffusion logo" style={{ display: "block", flexShrink: 0 }}>
      <title>IDX Leadership Diffusion</title>
      <path d="M5 29V20L14 11L19 16L30 5V29H5Z" fill="var(--accent, #d97956)" />
      <path d="M10 25V21.7L14 17.7L19 22.7L26 15.7V25H10Z" fill="var(--surface, #faf9f6)" />
    </svg>
  );
}

export function BrandLockup({ compact = false }: { compact?: boolean }) {
  return <div style={{ display: "flex", alignItems: "center", gap: 9, whiteSpace: "nowrap", padding: 2 }}>
    <BrandMark size={compact ? 25 : 31} />
    {!compact && <div style={{ lineHeight: 1 }}><div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-.025em", color: "var(--ink)" }}>IDX Leadership</div><div style={{ fontFamily: "Geist Mono, ui-monospace, monospace", fontSize: 9, letterSpacing: ".12em", color: "var(--muted)", marginTop: 5 }}>DIFFUSION</div></div>}
  </div>;
}
