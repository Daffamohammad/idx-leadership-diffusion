// MarketOverview — three-card dashboard + tabbed detail.
// Cards: market snapshot (~44%), movers (~28%), rankings (~28%).
// Below: Overview / Market / Flow / Structure tabs with actual content.
// Research/events stay separate and context-only.

import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import MarketDailyDashboard from "../components/MarketDailyDashboard";
import MarketBreadthPanel from "../components/MarketBreadthPanel";
import MarketHeatmap from "../components/MarketHeatmap";
import ForeignFlowSample from "../components/ForeignFlowSample";
import IDXStatisticsRelease from "../components/IDXStatisticsRelease";
import IDXDailyStatistics from "../components/IDXDailyStatistics";
import OfficialMarketContext from "../components/OfficialMarketContext";
import ResearchEvents from "../components/ResearchEvents";
import type { TaxonomyKind } from "../data/snapshot";
import { formatCountLabel, formatDateLabel, formatEnumLabel, formatSnapshotId } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";

const KIND_LABELS: Record<TaxonomyKind, string> = {
  SECTOR: "Sector",
  KONGLO: "Konglo",
  THEMES: "IDXIC subindustries",
};

type DetailTab = "overview" | "market" | "flow" | "structure";

export default function MarketOverview() {
  const snap = useSnapshot();
  const navigate = useNavigate();
  const location = useLocation();
  const adapted = snap.data;
  const [rankKind, setRankKind] = useState<TaxonomyKind>("SECTOR");
  const [tab, setTab] = useState<DetailTab>("overview");

  useEffect(() => {
    const legacy = location.hash.match(/^#(sector|konglo|themes)=([^&]+)$/i);
    if (!legacy) return;
    const taxonomy = legacy[1].toUpperCase();
    const group = decodeURIComponent(legacy[2]);
    navigate(`/explorer?taxonomy=${taxonomy}&group=${encodeURIComponent(group)}`, {
      replace: true,
    });
  }, [location.hash, navigate]);

  const rankings = useMemo(() => {
    if (!adapted) return [];
    if (rankKind === "SECTOR") {
      return [...adapted.sectors]
        .map((s) => ({ id: s.id, name: s.name, kind: "SECTOR" as TaxonomyKind, excess20d: s.excess20d, members: s.constituents, eligible: s.eligibleConstituents }))
        .sort((a, b) => (b.excess20d ?? Number.NEGATIVE_INFINITY) - (a.excess20d ?? Number.NEGATIVE_INFINITY))
        .slice(0, 11);
    }
    return Object.values(adapted.taxonomyGroups)
      .filter((g) => g.taxonomyKind === rankKind)
      .map((g) => ({ id: g.id, name: g.name, kind: g.taxonomyKind, excess20d: g.excess20d, members: g.constituents, eligible: g.eligible }))
      .sort((a, b) => (b.excess20d ?? Number.NEGATIVE_INFINITY) - (a.excess20d ?? Number.NEGATIVE_INFINITY))
      .slice(0, 6);
  }, [adapted, rankKind]);

  const rankingCounts = useMemo(() => {
    if (!adapted) return { SECTOR: 0, KONGLO: 0, THEMES: 0 };
    return {
      SECTOR: adapted.sectors.length,
      KONGLO: Object.values(adapted.taxonomyGroups).filter((g) => g.taxonomyKind === "KONGLO").length,
      THEMES: Object.values(adapted.taxonomyGroups).filter((g) => g.taxonomyKind === "THEMES").length,
    };
  }, [adapted]);

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
        <Link to="/methodology">Review methodology</Link>
      </main>
    );
  }

  const asOf = formatDateLabel(adapted.payload.as_of);
  const providerMode = adapted.payload.manifest?.entries?.[0]?.provider_mode ?? "PUBLIC_PROTOTYPE";
  const taxonomyKindsById: Record<string, TaxonomyKind> = {};
  for (const [taxonomyId, view] of Object.entries(adapted.taxonomyViews)) {
    taxonomyKindsById[taxonomyId] = view.taxonomy_kind;
  }
  const registryTotal = adapted.listingRegistry?.listedCount ?? adapted.listingRegistry?.persistedCount ?? null;
  const sectorCount = adapted.sectors.length;
  const kongloCount = Object.values(adapted.taxonomyGroups).filter((g) => g.taxonomyKind === "KONGLO").length;
  const themeCount = Object.values(adapted.taxonomyGroups).filter((g) => g.taxonomyKind === "THEMES").length;

  return (
    <main
      className="content-shell"
      style={{
        padding: "32px var(--page-gutter) 56px",
        display: "grid",
        gap: "var(--card-gap)",
        gridTemplateColumns: "minmax(0, 1fr)",
        maxWidth: "var(--content-max)",
        width: "100%",
        boxSizing: "border-box",
        margin: "0 auto",
        minWidth: 0,
      }}
    >
      <header
        style={{
          borderBottom: "1px solid var(--line)",
          paddingBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 16,
          minWidth: 0,
          maxWidth: "100%",
        }}
      >
        <div style={{ minWidth: 0, maxWidth: "100%", overflowWrap: "anywhere" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div className="eyebrow-muted">Market overview</div>
            <EvidenceBadge kind="SNAPSHOT" compact />
          </div>
          <h1 style={{ margin: "6px 0 4px", fontSize: 32, letterSpacing: "-.02em" }}>
            IDX leadership &amp; diffusion
          </h1>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
              fontSize: 12,
              fontFamily: "Geist Mono, monospace",
              color: "var(--muted)",
            }}
          >
            <span>Snapshot overview · Data as of {asOf}</span>
            <span>·</span>
            <span>{formatEnumLabel(providerMode)}</span>
            <span>·</span>
            <span>Snapshot {formatSnapshotId(adapted.payload.snapshot_id, adapted.payload.as_of)}</span>
          </div>
          <details style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
            <summary style={{ cursor: "pointer" }}>Provenance and coverage</summary>
            <div style={{ marginTop: 6, lineHeight: 1.6 }}>
              {sectorCount} sectors · {kongloCount} konglo groups · {themeCount} themes ·{" "}
              {registryTotal !== null ? `${registryTotal} listed records` : "—"} ·{" "}
              {adapted.sectors.reduce((sum, sector) => sum + (sector.eligibleConstituents ?? 0), 0).toLocaleString()} eligible sector constituents ·{" "}
              Source observations, analysis eligibility, and their dates are preserved in this selected release.
            </div>
          </details>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link to="/map" className="btn btn-outline">Leadership map</Link>
          <Link to="/explorer" className="btn btn-primary">Group explorer</Link>
        </div>
      </header>

      <MarketDailyDashboard
        rankKind={rankKind}
        onRankKindChange={setRankKind}
        rankings={rankings}
        rankingCounts={rankingCounts}
        asOf={asOf}
      />

      <MarketBreadthPanel />

      <div className="tabs" role="tablist" aria-label="Overview detail">
        {(["overview", "market", "flow", "structure"] as DetailTab[]).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className="tab" onClick={() => setTab(t)}>
            {t === "overview" ? "Overview" : t === "market" ? "Market" : t === "flow" ? "Flow" : "Structure"}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <MarketHeatmap
          taxonomyGroups={adapted.taxonomyGroups}
          taxonomyNames={KIND_LABELS}
          taxonomyKindsById={taxonomyKindsById}
          asOf={asOf}
          onSelectGroup={(kind, taxonomyId, groupId) => {
            void taxonomyId;
            navigate(`/explorer?taxonomy=${kind}&group=${encodeURIComponent(groupId)}`);
          }}
        />
      )}
      {tab === "market" && (
        <div style={{ display: "grid", gap: "var(--card-gap)" }}>
          <IDXStatisticsRelease release={adapted.idxInvestorRelease} />
          <IDXDailyStatistics statistics={adapted.idxDailyStatistics} />
          <OfficialMarketContext context={adapted.officialMarketContext} />
        </div>
      )}
      {tab === "flow" && <ForeignFlowSample sample={adapted.foreignFlow} asOf={asOf} />}
      {tab === "structure" && (
        <section className="dash-card" aria-label="Market structure">
          <h2 style={{ margin: "0 0 8px", fontSize: 15 }}>Structure</h2>
          <div style={{ fontSize: 13, lineHeight: 1.6, color: "var(--ink)" }}>
            {sectorCount} sectors · {registryTotal ?? "—"} listing records · {themeCount} captured IDXIC subindustries · {kongloCount} documented Konglo groups.
            Unique members vs eligible members differ per group; see catalog for per-group counts. Theme/Konglo history is not persisted in this bundle; sector history is available.
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            <Link to="/groups" className="btn btn-outline">All groups</Link>
            <Link to="/themes" className="btn btn-outline">Themes catalog</Link>
            <Link to="/maps/konglo" className="btn btn-ghost">Konglo map</Link>
          </div>
          <div className="meta" style={{ marginTop: 8 }}>
            {formatCountLabel(sectorCount, "sector")} · {formatCountLabel(themeCount, "theme")} · {formatCountLabel(kongloCount, "konglo group")} · snapshot {formatSnapshotId(adapted.payload.snapshot_id, adapted.payload.as_of)}
          </div>
        </section>
      )}

      <ResearchEvents events={adapted.researchEvents} limit={5} />
    </main>
  );
}
