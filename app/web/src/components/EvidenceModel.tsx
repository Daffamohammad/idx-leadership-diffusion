import type { ReactNode } from "react";
import { Link } from "react-router";

export type EvidenceKind =
  | "SNAPSHOT"
  | "OFFICIAL_RELEASE"
  | "SAMPLE"
  | "CLASSIFICATION"
  | "CONTEXT";

const EVIDENCE_CONFIG: Record<
  EvidenceKind,
  { label: string; color: string; background: string; border: string; description: string }
> = {
  SNAPSHOT: {
    label: "Market observations",
    color: "var(--up)",
    background: "var(--tint-ok)",
    border: "#b9ded6",
    description: "Persisted market observations used for quantitative signals.",
  },
  OFFICIAL_RELEASE: {
    label: "Official IDX data",
    color: "var(--up)",
    background: "var(--tint-ok)",
    border: "#a9d9ce",
    description: "First-party IDX publication parsed from its published table.",
  },
  SAMPLE: {
    label: "Source coverage",
    color: "var(--accent-ink)",
    background: "var(--tint-flag)",
    border: "#ead39b",
    description: "Real observations with bounded coverage; not a full-universe feed.",
  },
  CLASSIFICATION: {
    label: "Documented classification",
    color: "var(--link)",
    background: "var(--tint-note)",
    border: "#bed7e6",
    description: "Dated membership evidence from official classification or disclosed holdings.",
  },
  CONTEXT: {
    label: "Research context",
    color: "var(--muted)",
    background: "var(--surface-subtle)",
    border: "var(--line)",
    description: "Persisted descriptive context; it does not create a quantitative signal.",
  },
};

export function EvidenceBadge({
  kind,
  compact = false,
}: {
  kind: EvidenceKind;
  compact?: boolean;
}) {
  const config = EVIDENCE_CONFIG[kind];
  return (
    <span
      title={config.description}
      aria-label={`Evidence type: ${config.label}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        width: "fit-content",
        padding: compact ? "3px 8px" : "4px 9px",
        border: `1px solid ${config.border}`,
        borderRadius: 999,
        background: config.background,
        color: config.color,
        fontFamily: "Geist Mono, ui-monospace, monospace",
        fontSize: compact ? 10 : 11,
        letterSpacing: "0.02em",
        whiteSpace: "nowrap",
      }}
    >
      {config.label}
    </span>
  );
}

export interface EvidenceLane {
  kind: EvidenceKind;
  title: string;
  detail: string;
  meta: string;
  to?: string;
  actionLabel?: string;
}

export function EvidenceModel({
  lanes,
  intro = "This product intentionally separates real market evidence from coverage limits and research context.",
}: {
  lanes: EvidenceLane[];
  intro?: ReactNode;
}) {
  return (
    <section
      className="evidence-model"
      aria-labelledby="evidence-model-title"
      style={{
        border: "1px solid var(--line)",
        background: "var(--surface-subtle)",
        padding: 18,
        display: "grid",
        gap: 14,
      }}
    >
      <header style={{ display: "grid", gap: 6 }}>
        <div className="eyebrow-muted">Product delivery model</div>
        <h2 id="evidence-model-title" style={{ margin: 0, fontSize: 20, letterSpacing: "-.02em" }}>
          Hybrid research workspace
        </h2>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: 12, lineHeight: 1.55 }}>
          {intro}
        </p>
      </header>
      <div
        className="evidence-model-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
          gap: 10,
        }}
      >
        {lanes.map((lane) => (
          <article
            key={`${lane.kind}-${lane.title}`}
            style={{
              minWidth: 0,
              background: "var(--surface)",
              border: "1px solid var(--line)",
              padding: "13px 14px",
              display: "grid",
              alignContent: "start",
              gap: 8,
            }}
          >
            <EvidenceBadge kind={lane.kind} compact />
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>{lane.title}</h3>
            <p style={{ margin: 0, color: "var(--muted)", fontSize: 12, lineHeight: 1.5 }}>
              {lane.detail}
            </p>
            <div style={{ color: "var(--muted)", fontFamily: "Geist Mono, ui-monospace, monospace", fontSize: 10, lineHeight: 1.45 }}>
              {lane.meta}
            </div>
            {lane.to && (
              <Link
                to={lane.to}
                style={{ color: "var(--link)", fontSize: 11, textDecoration: "none", marginTop: 2 }}
              >
                {lane.actionLabel ?? "Open section"} →
              </Link>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
