// Empty-state card for snapshot sections that the prototype writer does not
// emit. Renders inline so the page keeps its structure but the user sees a
// clear, honest explanation of why the chart / table is blank.

import type { ReactNode } from "react";

export interface EmptyStateProps {
  label: string;
  title: string;
  body: ReactNode;
  height?: number;
}

export function EmptyState({ label, title, body, height = 160 }: EmptyStateProps) {
  return (
    <div
      style={{
        background: "var(--surface-subtle)",
        border: "1px dashed var(--line)",
        padding: "20px 22px",
        minHeight: height,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 6,
      }}
    >
      <div
        className="eyebrow-muted"
        style={{ color: "var(--accent-ink)" }}
      >
        {label}
      </div>
      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.55 }}>
        {body}
      </div>
    </div>
  );
}
