// TaxonomyMapPage — Konglo and Themes taxonomy maps.
//
// The route path encodes the taxonomy: /maps/konglo or /maps/themes.

import { Link, useLocation, useNavigate } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import TaxonomyMap from "../components/TaxonomyMap";
import ResearchEvents from "../components/ResearchEvents";
import ForeignFlowSample from "../components/ForeignFlowSample";
import type { TaxonomyKind } from "../data/snapshot";
import { formatDateLabel, formatEnumLabel } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";

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
  const navigate = useNavigate();
  const taxonomyKind = TAXONOMY_BY_PATH[location.pathname] ?? "KONGLO";
  const snap = useSnapshot();
  const adapted = snap.data;

  if (snap.loading) {
    return (
      <main style={{ padding: 32, color: "var(--muted)" }}>
        Loading snapshot…
      </main>
    );
  }
  if (snap.error || !adapted) {
    return (
      <main style={{ padding: 32 }}>
        <h1 style={{ fontSize: 28 }}>Snapshot unavailable</h1>
        <p style={{ color: "var(--down)" }}>{snap.error ?? "No snapshot loaded."}</p>
        <Link to="/overview">Return to overview</Link>
      </main>
    );
  }

  const view = adapted.taxonomyViews[taxonomyKind.toLowerCase()];
  const asOf = formatDateLabel(adapted.payload.as_of);
  const providerMode = adapted.payload.manifest?.entries?.[0]?.provider_mode ?? "PUBLIC_PROTOTYPE";

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
          borderBottom: "1px solid var(--line)",
          paddingBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div className="eyebrow-muted">{KIND_LABEL[taxonomyKind]} taxonomy map</div>
            <EvidenceBadge kind="CLASSIFICATION" compact />
          </div>
          <h1 style={{ margin: "6px 0 4px", fontSize: 30, letterSpacing: "-.02em" }}>
            {view?.taxonomy_name ?? `${KIND_LABEL[taxonomyKind]} taxonomy`}
          </h1>
          <div
            style={{
              display: "flex",
              gap: 12,
              fontSize: 12,
              fontFamily: "Geist Mono, monospace",
              color: "var(--muted)",
              flexWrap: "wrap",
            }}
          >
            <span>Taxonomy version: {view?.taxonomy_version ?? "—"}</span>
            <span>·</span>
            <span>Source kind: {formatEnumLabel(view?.source_kind)}</span>
            <span>·</span>
            <span>As of {asOf}</span>
            <span>·</span>
            <span>Provider mode: {formatEnumLabel(providerMode)}</span>
            <span>·</span>
            <span>
              Static membership definition · aggregate metrics from current snapshot
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link
            to={taxonomyKind === "KONGLO" ? "/konglo" : "/themes"}
            style={{
              padding: "10px 14px",
              border: "1px solid var(--line)",
              color: "var(--ink)",
              textDecoration: "none",
              fontSize: 12,
            }}
          >
            {taxonomyKind === "KONGLO" ? "Konglo" : "Themes"} catalog
          </Link>
          <Link
            to={`/map?taxonomy=${taxonomyKind}&mode=groups`}
            style={{
              padding: "10px 14px",
              border: "1px solid var(--line)",
              color: "var(--ink)",
              textDecoration: "none",
              fontSize: 12,
            }}
          >
            Rotation
          </Link>
          <Link
            to={taxonomyKind === "KONGLO" ? "/maps/themes" : "/maps/konglo"}
            style={{
              padding: "10px 14px",
              border: "1px solid #202325",
              color: "var(--ink)",
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
              color: "var(--ink)",
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
            ? "Documented disclosed holdings and named listed parents. Overlapping portfolios are shown separately."
            : "Captured IDXIC subindustries. Multi-classification tickers count within each subindustry."
        }
        asOf={adapted.payload.as_of}
        onSelectGroup={(groupId) => {
          navigate(`/explorer?taxonomy=${taxonomyKind}&group=${encodeURIComponent(groupId)}`);
        }}
      />

      <ForeignFlowSample sample={adapted.foreignFlow} asOf={asOf} />

      <ResearchEvents events={adapted.researchEvents} limit={5} />
    </main>
  );
}
