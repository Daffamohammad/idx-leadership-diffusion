// MarketOverview — three-card dashboard + tabbed detail.
// Cards: market snapshot (~44%), movers (~28%), rankings (~28%).
// Below: Overview / Market / Flow / Structure tabs with actual content.
// Research/events stay separate and context-only.

import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import MarketHeatmap from "../components/MarketHeatmap";
import ForeignFlowSample from "../components/ForeignFlowSample";
import IDXStatisticsRelease from "../components/IDXStatisticsRelease";
import IDXDailyStatistics from "../components/IDXDailyStatistics";
import OfficialMarketContext from "../components/OfficialMarketContext";
import ResearchEvents from "../components/ResearchEvents";
import type { TaxonomyKind } from "../data/snapshot";
import { formatCountLabel, formatDateLabel, formatEnumLabel, formatPercent, formatSnapshotId } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";

const KIND_LABELS: Record<TaxonomyKind, string> = {
  SECTOR: "Sector",
  KONGLO: "Konglo",
  THEMES: "Themes",
};

type DetailTab = "overview" | "market" | "flow" | "structure";

function signColor(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "var(--muted)";
  if (v > 0) return "var(--up)";
  if (v < 0) return "var(--down)";
  return "var(--muted)";
}

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

  // Data-driven YTD disclosure: report the baseline only when the bundle
  // actually carries YTD excess values. Never assume a prior-year baseline.
  const ytdSummary = useMemo(() => {
    if (!adapted) return null;
    const dated = adapted.sectors.filter((s) => s.ytdStartDate);
    if (!dated.length) return null;
    const baselines = new Set(dated.map((s) => (s.ytdStartDate ?? "").slice(0, 10)));
    if (baselines.size !== 1) return null;
    return {
      baseline: [...baselines][0],
      covered: dated.length,
      total: adapted.sectors.length,
    };
  }, [adapted]);

  const movers = useMemo(() => {
    if (!adapted) return { leaders: [], laggards: [], eligible: 0 };
    const rows = adapted.sectors.map((s) => ({
      id: s.id,
      name: s.name,
      kind: "SECTOR" as TaxonomyKind,
      excess20d: s.excess20d,
      eligible: s.eligibleConstituents,
    }));
    const valid = rows.filter((r) => r.excess20d !== null && Number.isFinite(r.excess20d));
    const eligible = rows.reduce((sum, r) => sum + (r.eligible ?? 0), 0);
    const sorted = [...valid].sort((a, b) => (b.excess20d ?? 0) - (a.excess20d ?? 0));
    return { leaders: sorted.slice(0, 3), laggards: sorted.slice(-3).reverse(), eligible };
  }, [adapted]);

  const rankings = useMemo(() => {
    if (!adapted) return [];
    if (rankKind === "SECTOR") {
      return [...adapted.sectors]
        .map((s) => ({ id: s.id, name: s.name, kind: "SECTOR" as TaxonomyKind, excess20d: s.excess20d, members: s.constituents, eligible: s.eligibleConstituents }))
        .sort((a, b) => (b.excess20d ?? Number.NEGATIVE_INFINITY) - (a.excess20d ?? Number.NEGATIVE_INFINITY))
        .slice(0, 5);
    }
    return Object.values(adapted.taxonomyGroups)
      .filter((g) => g.taxonomyKind === rankKind)
      .map((g) => ({ id: g.id, name: g.name, kind: g.taxonomyKind, excess20d: g.excess20d, members: g.constituents, eligible: g.eligible }))
      .sort((a, b) => (b.excess20d ?? Number.NEGATIVE_INFINITY) - (a.excess20d ?? Number.NEGATIVE_INFINITY))
      .slice(0, 5);
  }, [adapted, rankKind]);

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
        <Link to="/methodology">Review methodology</Link>
      </main>
    );
  }

  const asOf = formatDateLabel(adapted.payload.as_of);
  const providerMode = adapted.payload.manifest?.entries?.[0]?.provider_mode ?? "PUBLIC_PROTOTYPE";
  const quality = adapted.payload.quality?.status ?? null;
  const taxonomyKindsById: Record<string, TaxonomyKind> = {};
  for (const [taxonomyId, view] of Object.entries(adapted.taxonomyViews)) {
    taxonomyKindsById[taxonomyId] = view.taxonomy_kind;
  }
  const registryTotal = adapted.listingRegistry?.listedCount ?? adapted.listingRegistry?.persistedCount ?? null;
  const sectorCount = adapted.sectors.length;
  const kongloCount = Object.values(adapted.taxonomyGroups).filter((g) => g.taxonomyKind === "KONGLO").length;
  const themeCount = Object.values(adapted.taxonomyGroups).filter((g) => g.taxonomyKind === "THEMES").length;
  const stale = quality === "STALE" || quality === "FAILED" || quality === "PARTIAL" || quality === "READY_WITH_GAPS";

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
            {stale && (
              <span style={{ border: "1px solid #d5c59d", borderRadius: 20, padding: "4px 9px", color: "var(--accent-ink)", fontFamily: "Geist Mono, monospace", fontSize: 10 }}>
                {formatEnumLabel(quality)} · review details
              </span>
            )}
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
              {registryTotal !== null ? `${registryTotal} listed records` : "registry count unavailable"} ·{" "}
              {movers.eligible > 0 ? `${movers.eligible} eligible sector constituents` : "eligible count from bundle"} ·{" "}
              quality {formatEnumLabel(quality)}. Complete=false in this bundle; figures are bundle values, not hardcoded targets.
            </div>
          </details>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link to="/map" className="btn btn-outline">Leadership map</Link>
          <Link to="/explorer" className="btn btn-primary">Group explorer</Link>
        </div>
      </header>

      <div className="dash-grid" aria-label="Market dashboard">
        <section className="dash-card" aria-labelledby="dash-market-title">
          <div className="eyebrow-muted">Market snapshot · 20D window</div>
          <h2 id="dash-market-title">Market and benchmark</h2>
          <div style={{ display: "grid", gap: 8, fontSize: 13, color: "var(--ink)" }}>
            <div>Data as of <strong className="tabnum">{asOf}</strong> · {formatEnumLabel(providerMode)}</div>
            <div>{sectorCount} sectors · {registryTotal !== null ? `${registryTotal} listed records` : "registry unavailable"}</div>
            <div className="meta">
              {ytdSummary ? (
                <>
                  Sector history covers 20D/60D/YTD excess vs IHSG, with the YTD
                  baseline at <strong className="tabnum">{ytdSummary.baseline}</strong>.{" "}
                  No intraday chart is shown and no IHSG level is invented.
                </>
              ) : (
                <>
                  Sector history covers 20D/60D excess vs IHSG. YTD is not available in
                  this bundle (no prior-year baseline); no intraday chart is shown and
                  no IHSG level is invented.
                </>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
              <Link to="/map" className="btn btn-outline">Open rotation</Link>
              <Link to="/methodology" className="btn btn-ghost">Methodology</Link>
            </div>
          </div>
        </section>

        <section className="dash-card" aria-labelledby="dash-movers-title">
          <div className="eyebrow-muted">Sample movers · 20D excess vs IHSG</div>
          <h2 id="dash-movers-title">Leaders and laggards</h2>
          <div className="meta" style={{ marginBottom: 8 }}>
            {movers.eligible > 0 ? `${movers.eligible} eligible sector constituents` : "Eligible sample from bundle"} · not index-point attribution.
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            {movers.leaders.map((m) => (
              <Link key={`lead-${m.id}`} to={`/explorer?taxonomy=${m.kind}&group=${encodeURIComponent(m.id)}`} style={{ display: "flex", justifyContent: "space-between", gap: 8, textDecoration: "none", color: "inherit", padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                <span style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.name}</span>
                <span className="tabnum" style={{ fontFamily: "Geist Mono, monospace", fontSize: 12, color: signColor(m.excess20d) }}>{formatPercent(m.excess20d)}</span>
              </Link>
            ))}
            {movers.laggards.map((m) => (
              <Link key={`lag-${m.id}`} to={`/explorer?taxonomy=${m.kind}&group=${encodeURIComponent(m.id)}`} style={{ display: "flex", justifyContent: "space-between", gap: 8, textDecoration: "none", color: "inherit", padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                <span style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.name}</span>
                <span className="tabnum" style={{ fontFamily: "Geist Mono, monospace", fontSize: 12, color: signColor(m.excess20d) }}>{formatPercent(m.excess20d)}</span>
              </Link>
            ))}
            {!movers.leaders.length && <div className="meta">No valid 20D excess values in this bundle — shown as Not available, not zero.</div>}
          </div>
        </section>

        <section className="dash-card" aria-labelledby="dash-rank-title">
          <div className="eyebrow-muted">Group rankings · 20D excess</div>
          <h2 id="dash-rank-title">Sector / Konglo / Theme</h2>
          <div role="group" aria-label="Ranking taxonomy" style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
            {(["SECTOR", "KONGLO", "THEMES"] as TaxonomyKind[]).map((k) => (
              <button key={k} type="button" aria-pressed={rankKind === k} onClick={() => setRankKind(k)} className="btn btn-outline" style={{ minHeight: 32, padding: "4px 10px", fontSize: 12, borderColor: rankKind === k ? "var(--accent)" : undefined }}>
                {KIND_LABELS[k]}
              </button>
            ))}
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            {rankings.map((r, i) => (
              <Link key={r.id} to={`/explorer?taxonomy=${r.kind}&group=${encodeURIComponent(r.id)}`} style={{ display: "flex", justifyContent: "space-between", gap: 8, textDecoration: "none", color: "inherit", padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                <span style={{ fontSize: 13 }}><span className="tabnum" style={{ color: "var(--muted)", marginRight: 6 }}>{i + 1}</span>{r.name}</span>
                <span className="tabnum" style={{ fontFamily: "Geist Mono, monospace", fontSize: 12, color: signColor(r.excess20d) }}>{formatPercent(r.excess20d)}</span>
              </Link>
            ))}
            {!rankings.length && <div className="meta">No groups for {KIND_LABELS[rankKind]} in this bundle.</div>}
          </div>
          <div className="meta" style={{ marginTop: 8 }}>Breadth shown elsewhere is % outperforming, not advancers/decliners.</div>
        </section>
      </div>

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
          foreignFlow={adapted.foreignFlow}
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
            {sectorCount} sectors / {registryTotal ?? "—"} memberships · {themeCount} themes (analyst-defined prototype) · {kongloCount} konglo groups (analyst-defined prototype).
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
