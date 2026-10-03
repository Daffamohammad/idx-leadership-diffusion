import { useMemo, useState } from "react";
import { Link } from "react-router";
import type { ListingRegistryAdapted } from "../data/adapter";
import type { ListingRegistryRecord } from "../data/snapshot";
import { formatCountLabel, formatEnumLabel } from "../data/format";

interface ListingRegistryPanelProps {
  registry: ListingRegistryAdapted | null;
}

const card: React.CSSProperties = {
  background: "#ffffff",
  borderRadius: 6,
  boxShadow: "rgba(0,0,0,0.08) 0px 0px 0px 1px, rgb(250,250,250) 0px 0px 0px 2px",
};

function membershipNames(rows: Array<Record<string, unknown>>): string {
  const names = rows
    .map((row) => typeof row.taxonomy_group_name === "string" ? row.taxonomy_group_name : row.taxonomy_group_id)
    .filter((name): name is string => typeof name === "string" && name.length > 0);
  return names.length ? names.join(", ") : "—";
}

function clean(value: string | null | undefined): string {
  return value && value.trim() ? value : "—";
}

export default function ListingRegistryPanel({ registry }: ListingRegistryPanelProps) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toUpperCase();
  const sourceRecords = registry?.records ?? [];
  const records = useMemo(() => {
    if (!normalizedQuery) return sourceRecords;
    return sourceRecords.filter((record) =>
      [record.ticker, record.company_name, record.taxonomy.sector ?? "", record.taxonomy.subsector ?? ""]
        .join(" ")
        .toUpperCase()
        .includes(normalizedQuery),
    );
  }, [normalizedQuery, sourceRecords]);
  if (!registry) return null;
  const completeness = registry.fullAccessibleUniverseListed
    ? `All ${registry.listedCount} accessible listings are persisted.`
    : `${registry.persistedCount} of ${registry.discoveredCount} discovered listings are persisted in this bundle.`;

  return (
    <section aria-labelledby="listing-registry-title" style={{ ...card, marginBottom: 18, overflow: "hidden" }}>
      <div style={{ padding: "16px 18px", borderBottom: "1px solid #ebebeb" }}>
        <div className="eyebrow-muted">Universe registry</div>
        <h2 id="listing-registry-title" style={{ margin: "5px 0 6px", fontSize: 20, color: "#171717" }}>
          Listed securities and taxonomy mapping
        </h2>
        <p style={{ margin: 0, color: "#666666", fontSize: 12, lineHeight: 1.5 }}>{completeness}</p>
      </div>
      <div className="method-coverage-grid" style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", gap: 10, padding: "12px 18px" }}>
        {[
          ["Listed", registry.listedCount.toLocaleString("en-US")],
          ["Analysis sample", registry.analysisRequestedCount.toLocaleString("en-US")],
          ["Taxonomy mapped", `${registry.taxonomyCoveragePct.toFixed(1)}%`],
          ["Konglo listings mapped", registry.kongloMappedCount.toLocaleString("en-US")],
          ["Theme listings mapped", registry.themeMappedCount.toLocaleString("en-US")],
        ].map(([label, value]) => (
          <div key={label} style={{ border: "1px solid #ebebeb", padding: "10px 12px", background: "#fafafa" }}>
            <div style={{ fontFamily: "Geist Mono, monospace", fontSize: 18, color: "#171717" }}>{value}</div>
            <div style={{ marginTop: 3, fontSize: 10, color: "#666666" }}>{label}</div>
          </div>
        ))}
      </div>
      <div style={{ padding: "0 18px 14px", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input
          aria-label="Filter listed securities"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter ticker, company, sector…"
          style={{ flex: "1 1 260px", minWidth: 220, border: "1px solid #dfe2e1", padding: "9px 10px", fontSize: 12, color: "#202325" }}
        />
        <span style={{ color: "#686e73", fontSize: 11, fontFamily: "Geist Mono, ui-monospace, monospace" }}>
          {formatCountLabel(records.length, "row")} shown
        </span>
      </div>
      <div className="table-scroll">
        <table style={{ width: "100%", minWidth: 980, borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ borderTop: "1px solid #ebebeb", borderBottom: "1px solid #ebebeb", background: "#fafafa" }}>
              {["Ticker", "Company", "Sector / subsector", "Industry", "Konglo", "Themes", "Taxonomy", "Analysis"].map((label) => (
                <th key={label} style={{ padding: "9px 12px", textAlign: "left", color: "#666666", fontFamily: "Geist Mono, monospace", fontSize: 10, fontWeight: 400 }}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((record: ListingRegistryRecord) => (
              <tr key={record.ticker} style={{ borderBottom: "1px solid #f0f0f0" }}>
                <td style={{ padding: "8px 12px", fontFamily: "Geist Mono, monospace", fontWeight: 600 }}><Link to={`/ticker/${encodeURIComponent(record.ticker)}`} style={{ color: "#202325", textUnderlineOffset: 3 }}>{record.ticker}</Link></td>
                <td style={{ padding: "8px 12px", maxWidth: 240 }}>{record.company_name}</td>
                <td style={{ padding: "8px 12px" }}>{clean(record.taxonomy.sector)} · {clean(record.taxonomy.subsector)}</td>
                <td style={{ padding: "8px 12px" }}>{clean(record.taxonomy.industry)}</td>
                <td style={{ padding: "8px 12px" }}>{membershipNames(record.konglo_memberships)}</td>
                <td style={{ padding: "8px 12px" }}>{membershipNames(record.theme_memberships)}</td>
                <td style={{ padding: "8px 12px" }}>{formatEnumLabel(record.taxonomy_status)}</td>
                <td style={{ padding: "8px 12px" }}>{formatEnumLabel(record.analysis_status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ padding: "12px 18px", color: "#686e73", fontSize: 11, lineHeight: 1.5 }}>
        Sector membership comes from the provider security master. Konglo and theme memberships come only from the explicit configuration files; an unmapped row is not assigned by inference.
      </div>
    </section>
  );
}
