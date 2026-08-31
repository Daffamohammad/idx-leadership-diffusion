import type { IDXInvestorReleaseAdapted } from "../data/adapter";
import { formatDateLabel, formatEnumLabel, formatIdrCompact } from "../data/format";
import { EvidenceBadge } from "./EvidenceModel";

interface IDXStatisticsReleaseProps {
  release: IDXInvestorReleaseAdapted | null;
}

function directionColour(direction: string): string {
  if (direction === "NET_BUY") return "#178477";
  if (direction === "NET_SELL") return "#8f2424";
  return "#686e73";
}

function shortDate(value: string): string {
  return formatDateLabel(value).replace(/ \d{4}$/, "");
}

export default function IDXStatisticsRelease({ release }: IDXStatisticsReleaseProps) {
  if (!release) {
    return (
      <section
        aria-labelledby="idx-release-title"
        style={{
          border: "1px dashed #dfe2e1",
          padding: 22,
          background: "#faf9f6",
        }}
      >
        <div className="eyebrow-muted" id="idx-release-title">Official IDX release</div>
        <h2 style={{ margin: "6px 0 8px", fontSize: 22 }}>Investor trading statistics unavailable</h2>
        <p style={{ margin: 0, color: "#686e73", fontSize: 13, lineHeight: 1.5 }}>
          No validated IDX Digital Statistic release is attached to this snapshot.
        </p>
      </section>
    );
  }

  const latest = release.daily[release.daily.length - 1];
  const positiveDays = release.quality.positive_day_count ?? 0;
  const negativeDays = release.quality.negative_day_count ?? 0;
  const releaseReady = release.status === "READY" && release.quality.full_month_release;
  const maxAbs = Math.max(...release.daily.map((row) => Math.abs(row.netForeignIdr)), 1);

  return (
    <section
      aria-labelledby="idx-release-title"
      style={{
        border: "1px solid #b9ded6",
        padding: 22,
        background: "#f8fcfb",
        display: "grid",
        gap: 18,
      }}
    >
      <header style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div className="eyebrow-muted" id="idx-release-title">Official IDX release</div>
          <EvidenceBadge kind="OFFICIAL_RELEASE" compact />
          {!releaseReady && <EvidenceBadge kind="SAMPLE" compact />}
        </div>
        <h2 style={{ margin: 0, fontSize: 22, letterSpacing: "-.02em" }}>
          Daily trading by type of investor
        </h2>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            color: "#686e73",
            fontFamily: "Geist Mono, ui-monospace, monospace",
            fontSize: 11,
          }}
        >
          <span>{release.periodLabel}</span>
          <span>·</span>
          <span>{release.tradingDayCount} trading days</span>
          <span>·</span>
          <span>Published source: Indonesia Stock Exchange</span>
        </div>
        <p style={{ margin: 0, color: "#315d57", fontSize: 12, lineHeight: 1.5 }}>
          Real market-level release. It does not contain per-ticker ownership flow and is not used to confirm group leadership.
        </p>
      </header>

      <div
        className="idx-release-metrics"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 10,
        }}
      >
        <MetricCard
          label={`Latest day · ${formatDateLabel(latest.asOf)}`}
          value={formatIdrCompact(latest.netForeignIdr)}
          sublabel={formatEnumLabel(latest.direction)}
          colour={directionColour(latest.direction)}
        />
        <MetricCard
          label="Monthly net foreign"
          value={formatIdrCompact(release.totals.netForeignIdr)}
          sublabel={formatEnumLabel(release.totals.direction)}
          colour={directionColour(release.totals.direction)}
        />
        <MetricCard
          label="Observed direction days"
          value={`${positiveDays} buy · ${negativeDays} sell`}
          sublabel="From the published daily rows"
          colour="#202325"
          compactValue
        />
      </div>

      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Daily net foreign (IDR)</h3>
        <div
          role="img"
          aria-label={`Daily net foreign flow for ${release.periodLabel}`}
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${release.daily.length}, minmax(12px, 1fr))`,
            alignItems: "end",
            gap: 5,
            minHeight: 138,
            padding: "8px 4px 0",
            borderTop: "1px solid #dfe2e1",
            borderBottom: "1px solid #dfe2e1",
          }}
        >
          {release.daily.map((row) => {
            const height = Math.max(5, Math.round((Math.abs(row.netForeignIdr) / maxAbs) * 86));
            return (
              <div
                key={row.asOf}
                title={`${formatDateLabel(row.asOf)} · ${formatIdrCompact(row.netForeignIdr)}`}
                style={{
                  minWidth: 0,
                  display: "grid",
                  gridTemplateRows: "18px 86px 24px",
                  alignItems: "end",
                  justifyItems: "center",
                  gap: 3,
                  color: "#686e73",
                  fontFamily: "Geist Mono, ui-monospace, monospace",
                  fontSize: 9,
                }}
              >
                <span style={{ whiteSpace: "nowrap", transform: "rotate(-45deg)", transformOrigin: "center" }}>
                  {shortDate(row.asOf)}
                </span>
                <span
                  aria-hidden="true"
                  style={{
                    width: "min(18px, 100%)",
                    height,
                    background: directionColour(row.direction),
                    opacity: 0.9,
                  }}
                />
                <span style={{ color: directionColour(row.direction), whiteSpace: "nowrap" }}>
                  {row.netForeignIdr === 0 ? "0" : row.netForeignIdr > 0 ? "+" : "−"}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <details>
        <summary style={{ cursor: "pointer", fontSize: 12, color: "#315d57" }}>
          Show source composition and parser checks
        </summary>
        <div
          className="idx-release-detail-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 12,
            marginTop: 12,
          }}
        >
          <dl style={{ margin: 0, fontSize: 12 }}>
            <DetailRow label="Foreign sells to domestic" value={formatIdrCompact(release.totals.foreignToDomesticIdr)} />
            <DetailRow label="Domestic sells to foreign" value={formatIdrCompact(release.totals.domesticToForeignIdr)} />
            <DetailRow label="Net foreign formula" value="Domestic sells to foreign − foreign sells to domestic" />
          </dl>
          <dl style={{ margin: 0, fontSize: 12 }}>
            <DetailRow label="Table checks" value={releaseReady ? "Passed" : "Review"} />
            <DetailRow label="Retrieved" value={formatDateLabel(release.source.retrieved_at)} />
            <DetailRow label="Parser" value="Parsed official IDX tables" />
          </dl>
        </div>
      </details>

      <footer
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          alignItems: "center",
          color: "#686e73",
          fontFamily: "Geist Mono, ui-monospace, monospace",
          fontSize: 10,
        }}
      >
        <span>Source: Indonesia Stock Exchange</span>
        <span>·</span>
        <a href={release.source.url} target="_blank" rel="noreferrer">Open official release</a>
        <span>·</span>
        <span>{releaseReady ? "Table totals reconcile" : "Table reconciliation needs review"}</span>
      </footer>
    </section>
  );
}

function MetricCard({
  label,
  value,
  sublabel,
  colour,
  compactValue = false,
}: {
  label: string;
  value: string;
  sublabel: string;
  colour: string;
  compactValue?: boolean;
}) {
  return (
    <article style={{ background: "#fff", border: "1px solid #dfe2e1", padding: 14, minWidth: 0 }}>
      <div className="eyebrow-muted">{label}</div>
      <div
        style={{
          marginTop: 6,
          color: colour,
          fontFamily: "Geist Mono, ui-monospace, monospace",
          fontSize: compactValue ? 16 : 22,
          lineHeight: 1.2,
          overflowWrap: "anywhere",
        }}
      >
        {value}
      </div>
      <div style={{ marginTop: 5, color: "#686e73", fontSize: 11 }}>{sublabel}</div>
    </article>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.3fr)", gap: 8, borderBottom: "1px solid #dfe2e1", padding: "7px 0" }}>
      <dt style={{ color: "#686e73" }}>{label}</dt>
      <dd style={{ margin: 0, color: "#202325", overflowWrap: "anywhere" }}>{value}</dd>
    </div>
  );
}
