import ListingRegistryPanel from "../components/ListingRegistryPanel";
import { useSnapshot } from "../data/SnapshotProvider";

export default function TickerExplorer() {
  const { data, loading } = useSnapshot();
  return (
    <section style={{ padding: "28px var(--page-gutter) 56px", minWidth: 0 }}>
      <div className="eyebrow-muted">Listed companies</div>
      <h1 style={{ margin: "8px 0 12px" }}>Ticker Explorer</h1>
      <p style={{ color: "#686e73", marginBottom: 24, lineHeight: 1.6 }}>
        Search the listing registry and open a company’s detail page. Price history and analysis coverage vary by ticker.
      </p>
      {loading ? <p role="status">Loading listings…</p> : data?.listingRegistry
        ? <ListingRegistryPanel registry={data.listingRegistry} />
        : <p>No listing registry is available in this snapshot.</p>}
    </section>
  );
}
