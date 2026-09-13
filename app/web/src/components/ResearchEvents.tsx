// ResearchEvents — timeline of normalized, source-backed events.
//
// Events are explicitly context only. They are NEVER scored or turned
// into quantitative confirmation.

import type { ResearchEventView } from "../data/adapter";
import { formatDateLabel, formatEnumLabel } from "../data/format";
import { EvidenceBadge } from "./EvidenceModel";

interface ResearchEventsProps {
  events: ResearchEventView[];
  limit?: number;
  emptyMessage?: string;
}

const CATEGORY_LABEL: Record<string, string> = {
  earnings: "Earnings",
  dividend: "Dividend",
  rights_issue: "Rights issue",
  stock_split: "Stock split",
  suspension: "Suspension",
  index_inclusion: "Index inclusion",
  corporate_action: "Corporate action",
  major_filing: "Major filing",
  other_sourced_event: "Other sourced event",
};

export default function ResearchEvents({
  events,
  limit,
  emptyMessage = "No research events in the current snapshot.",
}: ResearchEventsProps) {
  if (!events.length) {
    return (
      <section
        id="research-events"
        aria-label="Research events"
        style={{
          border: "1px dashed #dfe2e1",
          padding: 22,
          background: "#faf9f6",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div className="eyebrow-muted">Research events</div>
          <EvidenceBadge kind="CONTEXT" compact />
        </div>
        <p style={{ margin: "8px 0 0", fontSize: 13, color: "#686e73" }}>
          {emptyMessage}
        </p>
      </section>
    );
  }
  const sorted = [...events].sort((a, b) => b.eventDate.localeCompare(a.eventDate));
  const sliced = typeof limit === "number" ? sorted.slice(0, limit) : sorted;

  return (
    <section
      id="research-events"
      aria-label="Research events"
      style={{
        border: "1px solid #dfe2e1",
        padding: 22,
        background: "#faf9f6",
      }}
    >
      <header style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div className="eyebrow-muted">Research events</div>
          <EvidenceBadge kind="CONTEXT" compact />
        </div>
        <h2 style={{ margin: "6px 0 4px", fontSize: 20 }}>
          {sliced.length} dated event{sliced.length === 1 ? "" : "s"} · context only
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: 11,
            color: "#686e73",
            fontFamily: "Geist Mono, monospace",
          }}
        >
          Events are persisted source-backed observations; they remain descriptive context and never become signals.
        </p>
      </header>
      <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
        {sliced.map((event) => (
          <li
            key={event.eventId}
            style={{
              borderLeft: "3px solid #c69f4a",
              paddingLeft: 12,
              display: "grid",
              gap: 4,
            }}
          >
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                alignItems: "center",
                fontSize: 11,
                color: "#686e73",
                fontFamily: "Geist Mono, monospace",
              }}
            >
              <span>{formatDateLabel(event.eventDate)}</span>
              <span>·</span>
              <span>{CATEGORY_LABEL[event.category] ?? formatEnumLabel(event.category)}</span>
              <span>·</span>
              <span>{event.ticker}</span>
              {event.provider && (
                <>
                  <span>·</span>
                  <span>{formatEnumLabel(event.provider)}</span>
                </>
              )}
            </div>
            <div style={{ fontWeight: 600 }}>{event.title}</div>
            <div style={{ fontSize: 13, color: "#202325" }}>{event.summary}</div>
            <div style={{ fontSize: 11, color: "#686e73" }}>
              {event.sourceUrl.startsWith("http://") ||
              event.sourceUrl.startsWith("https://") ? (
                <a href={event.sourceUrl} target="_blank" rel="noopener noreferrer">
                  {event.sourceName}
                </a>
              ) : (
                <span>{event.sourceName}</span>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
