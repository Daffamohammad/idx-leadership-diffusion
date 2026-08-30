// TaxonomyMapPage — Konglo and Themes taxonomy maps.
//
// The route path encodes the taxonomy: /maps/konglo or /maps/themes.

import { Link, useLocation } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import TaxonomyMap from "../components/TaxonomyMap";
import ResearchEvents from "../components/ResearchEvents";
import ForeignFlowSample from "../components/ForeignFlowSample";
import type { TaxonomyKind } from "../data/snapshot";

const TAXONOMY_BY_PATH: Record<string, TaxonomyKind> = {
  "/maps/konglo": "KONGLO",
  "/maps/themes": "THEMES",
};

const KIND_LABEL: Record<TaxonomyKind, string> = {
  SECTOR: "Sector",
  KONGLO: "Konglo",
  THEMES: "Themes",
};

export default function TaxonomyMapPage() {
  const location = useLocation();
  const taxonomyKind = TAXONOMY_BY_PATH[location.pathname] ?? "KONGLO";
  const snap = useSnapshot();
  const adapted = snap.data;

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
        <Link to="/overview">Return to overview</Link>
      </main>
    );
  }

  const view = adapted.taxonomyViews[taxonomyKind.toLowerCase()];
  const asOf = adapted.payload.as_of;
  const providerMode = adapted.payload.manifest?.entries?.[0]?.provider_mode ?? "PUBLIC_PROTOTYPE";

  return (
    <main
      style={{
        padding: "32px 36px 56px",
        display: "grid",
        gap: 24,
        maxWidth: 1280,
        margin: "0 auto",
      }}
    >
      <header
        style={{
          borderBottom: "1px solid #dfe2e1",
          paddingBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div>
          <div className="eyebrow-muted">{KIND_LABEL[taxonomyKind]} taxonomy map</div>
          <h1 style={{ margin: "6px 0 4px", fontSize: 30, letterSpacing: "-.02em" }}>
            {view?.taxonomy_name ?? `${KIND_LABEL[taxonomyKind]} taxonomy`}
          </h1>
          <div
            style={{
              display: "flex",
              gap: 12,
              fontSize: 12,
              fontFamily: "Geist Mono, monospace",
              color: "#686e73",
              flexWrap: "wrap",
            }}
          >
            <span>Taxonomy version: {view?.taxonomy_version ?? "—"}</span>
            <span>·</span>
            <span>Source kind: {view?.source_kind ?? "—"}</span>
            <span>·</span>
            <span>As of {asOf}</span>
            <span>·</span>
            <span>Provider mode: {providerMode}</span>
            <span>·</span>
            <span>
              {taxonomyKind === "KONGLO" ? "ANALYST_DEFINED_PROTOTYPE" : "ANALYST-DEFINED PROTOTYPE TAXONOMY"}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <Link
            to={taxonomyKind === "KONGLO" ? "/maps/themes" : "/maps/konglo"}
            style={{
              padding: "10px 14px",
              border: "1px solid #202325",
              color: "#202325",
              textDecoration: "none",
              fontSize: 12,
            }}
          >
            Switch to {taxonomyKind === "KONGLO" ? "Themes" : "Konglo"}
          </Link>
          <Link
            to="/overview"
            style={{
              padding: "10px 14px",
              border: "1px solid #202325",
              color: "#202325",
              textDecoration: "none",
              fontSize: 12,
            }}
          >
            ← Overview
          </Link>
        </div>
      </header>

      <TaxonomyMap
        taxonomyGroups={adapted.taxonomyGroups}
        foreignFlow={adapted.foreignFlow}
        taxonomyKind={taxonomyKind}
        title={view?.taxonomy_name ?? `${KIND_LABEL[taxonomyKind]} taxonomy`}
        subtitle={
          taxonomyKind === "KONGLO"
            ? "Analyst-defined conglomerate archetype. Lower confidence rows are excluded from signal eligibility."
            : "Analyst-defined prototype themes. Multi-theme tickers counted per-theme, never aggregated cross-theme."
        }
      />

      <ForeignFlowSample sample={adapted.foreignFlow} asOf={asOf} />

      <ResearchEvents events={adapted.researchEvents} limit={5} />
    </main>
  );
}