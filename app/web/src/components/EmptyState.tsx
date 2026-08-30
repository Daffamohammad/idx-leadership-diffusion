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
        background: "#fafafa",
        border: "1px dashed #dfe2e1",
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
        style={{ color: "#7a5010" }}
      >
        {label}
      </div>
      <div style={{ fontSize: 13, fontWeight: 500, color: "#16191c" }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: "#4d4d4d", lineHeight: 1.55 }}>
        {body}
      </div>
    </div>
  );
}
