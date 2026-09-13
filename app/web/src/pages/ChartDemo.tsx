import { useEffect, useState } from "react";
import { Link } from "react-router";

import PriceChart from "../components/PriceChart";
import { EmptyState } from "../components/EmptyState";
import { useSnapshot } from "../data/SnapshotProvider";
import { formatSnapshotId } from "../data/format";

/**
 * A snapshot-backed chart route used to validate the chart component without
 * introducing a second data source. It intentionally renders no simulated
 * or hard-coded market observations.
 */
export default function ChartDemo() {
  const { data, loading, error } = useSnapshot();
  const [selected, setSelected] = useState("");

  useEffect(() => {
    if (!selected && data?.sectors.length) {
      setSelected(data.sectors[0].id);
    }
  }, [data, selected]);

  if (loading) {
    return (
      <main style={{ maxWidth: 1100, margin: "auto", padding: 40 }}>
        <EmptyState
          label="LOADING SNAPSHOT"
          title="Loading chart data"
          body="The chart will appear when the persisted snapshot is available."
          height={220}
        />
      </main>
    );
  }

  if (!data) {
    return (
      <main style={{ maxWidth: 1100, margin: "auto", padding: 40 }}>
        <EmptyState
          label="CHART UNAVAILABLE"
          title="The snapshot could not be loaded"
          body={error ?? "No chart data is available for this run."}
          height={220}
        />
      </main>
    );
  }

  const group = data.sectors.find((sector) => sector.id === selected) ?? data.sectors[0];
  const points = group ? data.groupPriceHistory[group.id] ?? [] : [];
  const entry = data.payload.manifest.entries[0];
  const source = entry?.provider ? `${entry.provider} snapshot` : "Snapshot data";

  return (
    <main style={{ maxWidth: 1100, margin: "auto", padding: 40 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 20, alignItems: "flex-start", flexWrap: "wrap", marginBottom: 24 }}>
        <div>
          <div className="eyebrow-muted" style={{ marginBottom: 8 }}>Snapshot-backed chart</div>
          <h1 style={{ fontSize: 26, letterSpacing: "-.03em", margin: "0 0 6px" }}>
            Interactive price context
          </h1>
          <p style={{ color: "#747a7d", margin: 0, lineHeight: 1.5 }}>
            Equal-weight group performance versus IHSG from persisted snapshot data.
          </p>
        </div>
        {data.sectors.length > 0 && (
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, color: "#686e73" }}>
            Group
            <select
              aria-label="Select chart group"
              value={group?.id ?? ""}
              onChange={(event) => setSelected(event.target.value)}
              style={{ minWidth: 190, padding: "8px 10px", border: "1px solid #dfe2e1", background: "#fff", color: "#202325" }}
            >
              {data.sectors.map((sector) => (
                <option key={sector.id} value={sector.id}>{sector.name}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      {group && points.length > 0 ? (
        <PriceChart
          groupName={group.name}
          points={points.map((point) => ({ date: point.date, value: point.value }))}
          benchmarkPoints={points
            .filter((point) => point.benchmark !== null)
            .map((point) => ({ date: point.date, value: point.benchmark }))}
          groupPoints={points}
          asOf={data.payload.as_of}
          source={source}
          metricLabel="Equal-weight group index · rebased to 100"
          referenceValue={100}
          providerMode={entry?.provider_mode}
          priceBasis={entry?.price_basis}
          dataStatus={data.payload.quality?.status}
          height={380}
        />
      ) : (
        <EmptyState
          label="NO PRICE SERIES"
          title="No persisted chart series is available"
          body="This snapshot does not emit a safe group price series. No simulated values are shown."
          height={240}
        />
      )}

      <div style={{ marginTop: 16, display: "flex", gap: 16, flexWrap: "wrap", fontSize: 11, color: "#747a7d", fontFamily: "Geist Mono, monospace" }}>
        <span>Snapshot: {formatSnapshotId(data.payload.snapshot_id, data.payload.as_of)}</span>
        <span>Source: {source}</span>
        <span>As of: {data.payload.as_of}</span>
        <Link to="/explorer" style={{ color: "#245b76" }}>Open group explorer →</Link>
      </div>
    </main>
  );
}
