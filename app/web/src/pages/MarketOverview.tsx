// MarketOverview — landing page that surfaces the market heatmap,
// foreign-flow sample, and the latest research events.
//
// This replaces the public homepage's role for an interactive heatmap
// view; PublicHome keeps the marketing surface and links here for
// detailed analysis.

import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import MarketHeatmap from "../components/MarketHeatmap";
import ForeignFlowSample from "../components/ForeignFlowSample";
import IDXStatisticsRelease from "../components/IDXStatisticsRelease";
import IDXDailyStatistics from "../components/IDXDailyStatistics";
import ResearchEvents from "../components/ResearchEvents";
import type { TaxonomyKind } from "../data/snapshot";
import { formatDateLabel, formatEnumLabel, formatSnapshotId } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";

const KIND_LABELS: Record<TaxonomyKind, string> = {
  SECTOR: "Sector",
  KONGLO: "Konglo",
  THEMES: "Themes",
};

export default function MarketOverview() {
  const snap = useSnapshot();
  const navigate = useNavigate();
  const location = useLocation();
  const adapted = snap.data;

  useEffect(() => {
    const legacy = location.hash.match(/^#(sector|konglo|themes)=([^&]+)$/i);
    if (!legacy) return;
    const taxonomy = legacy[1].toUpperCase();
    const group = decodeURIComponent(legacy[2]);
    navigate(`/explorer?taxonomy=${taxonomy}&group=${encodeURIComponent(group)}`, {
      replace: true,
    });
  }, [location.hash, navigate]);

  if (snap.loading) {
    return (
      <main style={{ padding: 32, color: "#686e73" }}>
        Loading snapshot…
      </main>
    );
  }

  if (snap.error || !adapted) {
    return (
      <main style={{ padding: 32 }}>
        <h1 style={{ fontSize: 28 }}>Snapshot unavailable</h1>
        <p style={{ color: "#8f2424" }}>{snap.error ?? "No snapshot loaded."}</p>
        <Link to="/methodology">Review methodology</Link>
      </main>
    );
  }

  const asOf = formatDateLabel(adapted.payload.as_of);
  const providerMode = adapted.payload.manifest?.entries?.[0]?.provider_mode ?? "PUBLIC_PROTOTYPE";

  // Build taxonomyIds map for the heatmap.
  const taxonomyKindsById: Record<string, TaxonomyKind> = {};
  for (const [taxonomyId, view] of Object.entries(adapted.taxonomyViews)) {
    taxonomyKindsById[taxonomyId] = view.taxonomy_kind;
  }

  return (
    <main
      className="content-shell"
      style={{
        padding: "32px var(--page-gutter) 56px",
        display: "grid",
        gap: "var(--card-gap)",
        maxWidth: "var(--content-max)",
        margin: "0 auto",
      }}
    >
      <header
        style={{
          borderBottom: "1px solid #dfe2e1",
          paddingBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div className="eyebrow-muted">Market overview</div>
            <EvidenceBadge kind="SNAPSHOT" compact />
          </div>
          <h1 style={{ margin: "6px 0 4px", fontSize: 32, letterSpacing: "-.02em" }}>
            IDX leadership & diffusion
          </h1>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
              fontSize: 12,
              fontFamily: "Geist Mono, monospace",
              color: "#686e73",
            }}
          >
            <span>As of {asOf}</span>
            <span>·</span>
            <span>Provider mode: {formatEnumLabel(providerMode)}</span>
            <span>·</span>
            <span>Snapshot: {formatSnapshotId(adapted.payload.snapshot_id, adapted.payload.as_of)}</span>
          </div>
          <p style={{ margin: "10px 0 0", color: "#686e73", fontSize: 12, lineHeight: 1.5 }}>
            Real market snapshot first. Static research lenses and bounded samples are labeled in their sections.
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link
            to="/map"
            style={{
              padding: "10px 14px",
              border: "1px solid #202325",
              color: "#202325",
              textDecoration: "none",
              fontSize: 12,
            }}
          >
            Leadership map
          </Link>
          <Link
            to="/explorer"
            style={{
              padding: "10px 14px",
              border: "1px solid #202325",
              color: "#202325",
              textDecoration: "none",
              fontSize: 12,
            }}
          >
            Group explorer
          </Link>
        </div>
      </header>

      <MarketHeatmap
        taxonomyGroups={adapted.taxonomyGroups}
        taxonomyNames={KIND_LABELS}
        taxonomyKindsById={taxonomyKindsById}
        foreignFlow={adapted.foreignFlow}
        asOf={asOf}
        onSelectGroup={(kind, taxonomyId, groupId) => {
          void taxonomyId;
          navigate(`/explorer?taxonomy=${kind}&group=${encodeURIComponent(groupId)}`);
        }}
      />

      <IDXStatisticsRelease release={adapted.idxInvestorRelease} />

      <IDXDailyStatistics statistics={adapted.idxDailyStatistics} />

      <ForeignFlowSample sample={adapted.foreignFlow} asOf={asOf} />

      <ResearchEvents events={adapted.researchEvents} limit={5} />
    </main>
  );
}
