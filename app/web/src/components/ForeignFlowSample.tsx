// ForeignFlowSample — surface the bounded foreign-flow sample.
//
// Renders:
//   * Coverage card (market days, observation count, signal eligibility)
//   * Daily market totals (chart of net flow per market date)
//   * Sample NET_BUY / NET_SELL leaders
//   * Sample-vs-market divergence
//   * Provenance with source URLs
//
// The values are read from the Python-calculated
// `foreign_flow_sample` envelope. The component never recomputes.

import type { ForeignFlowAdapted } from "../data/adapter";
import { formatCountLabel, formatDateLabel, formatEnumLabel, formatIdrCompact } from "../data/format";

interface ForeignFlowSampleProps {
  sample: ForeignFlowAdapted | null;
  asOf: string | null;
}

function formatPercent(numerator: number, denominator: number): string {
  if (denominator === 0) return "—";
  return `${Math.round((numerator / denominator) * 100)}%`;
}

export default function ForeignFlowSample({ sample, asOf }: ForeignFlowSampleProps) {
  if (!sample) {
    return (
      <section
        aria-label="Foreign flow sample"
        style={{
          border: "1px dashed #dfe2e1",
          padding: 22,
          background: "#faf9f6",
        }}
      >
        <div className="eyebrow-muted">Foreign-flow sample</div>
        <p style={{ margin: "8px 0 0", color: "#686e73", fontSize: 13 }}>
          The exporter did not emit a foreign-flow sample for this snapshot.
        </p>
      </section>
    );
  }

  const breadthRows = [
    ["Sample positive days", sample.breadth.samplePositiveDayCount],
    ["Sample negative days", sample.breadth.sampleNegativeDayCount],
    ["Market positive days", sample.breadth.marketPositiveDayCount],
    ["Market negative days", sample.breadth.marketNegativeDayCount],
  ] as const;

  const signalThreshold = [
    ["Market days ≥ 5", sample.coverageGateMet ? "Met" : "Review"],
    [`${formatPercent(sample.mappedCompanyObservationPct, 100)} mapped coverage`, sample.coverageGateMet ? "Met" : "Review"],
    ["Regime diversity", sample.regimeDiversity ? "Yes" : "No"],
  ];

  return (
    <section
      aria-label="Foreign flow sample"
      style={{
        border: "1px solid #dfe2e1",
        padding: 22,
        background: "#faf9f6",
        display: "grid",
        gap: 18,
      }}
    >
      <header>
        <div className="eyebrow-muted">Foreign-flow sample</div>
        <h2 style={{ margin: "6px 0 4px", fontSize: 22, letterSpacing: "-.02em" }}>
          Multi-date foreign flow · source-backed top-list
        </h2>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            fontSize: 11,
            fontFamily: "Geist Mono, monospace",
            color: "#686e73",
          }}
        >
          <span>Sample only · bounded top-list</span>
          <span>·</span>
          <span>As of {formatDateLabel(sample.asOfMax || asOf) || "n/a"}</span>
          <span>·</span>
          <span>{formatCountLabel(sample.marketDayCount, "market date")}</span>
          <span>·</span>
          <span>{formatCountLabel(sample.companyObservationCount, "company observation")}</span>
          <span>·</span>
          <span>
            signal eligibility: {sample.signalEligible ? "Eligible" : "Review"}
          </span>
        </div>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
        }}
      >
        <article
          style={{
            background: "#fff",
            padding: 14,
            border: "1px solid #dfe2e1",
          }}
        >
          <div className="eyebrow-muted">Latest market net</div>
          <div
            style={{
              fontSize: 24,
              fontFamily: "Geist Mono, monospace",
              marginTop: 4,
              color:
                sample.lastMarketDirection === "NET_BUY"
                  ? "#178477"
                  : sample.lastMarketDirection === "NET_SELL"
                    ? "#8f2424"
                    : "#7c858c",
            }}
          >
            {formatEnumLabel(sample.lastMarketDirection)}
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 12, color: "#686e73" }}>
            Reported market total (one observation per market date).
          </p>
        </article>
        <article
          style={{
            background: "#fff",
            padding: 14,
            border: "1px solid #dfe2e1",
          }}
        >
          <div className="eyebrow-muted">Latest sample net</div>
          <div
            style={{
              fontSize: 24,
              fontFamily: "Geist Mono, monospace",
              marginTop: 4,
              color:
                sample.lastSampleDirection === "NET_BUY"
                  ? "#178477"
                  : sample.lastSampleDirection === "NET_SELL"
                    ? "#8f2424"
                    : "#7c858c",
            }}
          >
            {formatEnumLabel(sample.lastSampleDirection)}
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 12, color: "#686e73" }}>
            Top-list company rows. Distinct from market totals by design.
          </p>
        </article>
        <article
          style={{
            background: "#fff",
            padding: 14,
            border: "1px solid #dfe2e1",
          }}
        >
          <div className="eyebrow-muted">Market ↔ sample alignment</div>
          <div
            style={{
              fontSize: 24,
              fontFamily: "Geist Mono, monospace",
              marginTop: 4,
            }}
          >
            {sample.marketSampleAligned ? "Aligned" : "Divergent"}
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 12, color: "#686e73" }}>
            Sample is not a market-wide observation; divergence is expected.
          </p>
        </article>
      </div>

      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Observed breadth</h3>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontFamily: "Geist Mono, monospace",
            fontSize: 12,
          }}
        >
          <tbody>
            {breadthRows.map(([label, value]) => (
              <tr key={label}>
                <td style={{ borderBottom: "1px solid #dfe2e1", padding: "6px 4px" }}>{label}</td>
                <td
                  align="right"
                  style={{ borderBottom: "1px solid #dfe2e1", padding: "6px 4px" }}
                >
                  {value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Daily market net (IDR)</h3>
        <DailyBars marketDaily={sample.marketDaily} />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
        }}
      >
        <TopList
          title="Latest top-buys (sample)"
          rows={sample.topBuys}
          accent="#178477"
        />
        <TopList
          title="Latest top-sells (sample)"
          rows={sample.topSells}
          accent="#8f2424"
        />
      </div>

      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Signal-eligibility gate</h3>
        <ul
          style={{
            margin: 0,
            padding: 0,
            listStyle: "none",
            display: "grid",
            gap: 4,
            fontSize: 12,
            fontFamily: "Geist Mono, monospace",
          }}
        >
          {signalThreshold.map(([label, status]) => (
            <li
              key={label}
              style={{
                display: "flex",
                justifyContent: "space-between",
                borderBottom: "1px solid #dfe2e1",
                paddingBottom: 4,
              }}
            >
              <span>{label}</span>
              <span>{status}</span>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Source provenance</h3>
        <ul
          style={{
            margin: 0,
            padding: 0,
            listStyle: "none",
            display: "grid",
            gap: 6,
            fontSize: 12,
          }}
        >
          {sample.provenance.map((row) => (
            <li
              key={row.sourceUrl}
              style={{
                borderBottom: "1px solid #dfe2e1",
                paddingBottom: 6,
              }}
            >
              <a href={row.sourceUrl} target="_blank" rel="noreferrer">
                {row.sourceName}
              </a>
              <span
                style={{
                  color: "#686e73",
                  marginLeft: 6,
                  fontFamily: "Geist Mono, monospace",
                  fontSize: 11,
                }}
              >
                · {formatCountLabel(row.observedRows, "observation")}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Methodology limitations</h3>
        <ul style={{ margin: 0, padding: "0 0 0 18px", fontSize: 12, color: "#686e73" }}>
          {sample.limitations.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function DailyBars({
  marketDaily,
}: {
  marketDaily: Array<{
    asOf: string;
    netValueIdr: number;
    direction: string;
  }>;
}) {
  if (marketDaily.length === 0) {
    return (
      <p style={{ margin: 0, color: "#686e73", fontSize: 12 }}>
        No market-level observations.
      </p>
    );
  }
  const max = Math.max(...marketDaily.map((row) => Math.abs(row.netValueIdr)));
  return (
    <div
      role="img"
      aria-label="Daily market net flow"
      style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 120 }}
    >
      {marketDaily.map((row) => {
        const ratio = max === 0 ? 0 : Math.abs(row.netValueIdr) / max;
        const height = Math.max(4, Math.round(ratio * 96));
        const colour =
          row.direction === "NET_BUY"
            ? "#178477"
            : row.direction === "NET_SELL"
              ? "#8f2424"
              : "#7c858c";
        return (
          <div
            key={row.asOf}
            style={{
              flex: 1,
              display: "grid",
              gap: 4,
              textAlign: "center",
              fontFamily: "Geist Mono, monospace",
              fontSize: 10,
              color: "#202325",
            }}
            title={`${row.asOf} · ${formatIdrCompact(row.netValueIdr)}`}
          >
            <div style={{ color: "#686e73" }}>{formatDateLabel(row.asOf).replace(/ \d{4}$/, "")}</div>
            <div
              style={{
                background: colour,
                height,
                margin: "0 auto",
                width: 24,
              }}
            />
            <div>{formatIdrCompact(row.netValueIdr, 1)}</div>
          </div>
        );
      })}
    </div>
  );
}

function TopList({
  title,
  rows,
  accent,
}: {
  title: string;
  rows: Array<{
    asOf: string;
    ticker: string;
    netValueIdr: number;
    direction: string;
    sourceName: string;
    sourceUrl: string;
  }>;
  accent: string;
}) {
  return (
    <article
      style={{
        background: "#fff",
        border: "1px solid #dfe2e1",
        padding: 14,
      }}
    >
      <div className="eyebrow-muted" style={{ color: accent }}>
        {title}
      </div>
      {rows.length === 0 ? (
        <p style={{ margin: "8px 0 0", fontSize: 12, color: "#686e73" }}>
          No sample rows.
        </p>
      ) : (
        <ul style={{ margin: "8px 0 0", padding: 0, listStyle: "none", fontSize: 12 }}>
          {rows.map((row, index) => (
            <li
              key={`${row.ticker}-${row.asOf}-${index}`}
              style={{
                display: "flex",
                justifyContent: "space-between",
                borderBottom: "1px solid #dfe2e1",
                paddingBottom: 4,
              }}
            >
              <span>
                <strong>{row.ticker}</strong>
                <span
                  style={{
                    fontFamily: "Geist Mono, monospace",
                    color: "#686e73",
                    marginLeft: 6,
                  }}
                >
                  {formatDateLabel(row.asOf)}
                </span>
              </span>
              <span style={{ color: accent, fontFamily: "Geist Mono, monospace" }}>
                {formatIdrCompact(row.netValueIdr, 2)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
