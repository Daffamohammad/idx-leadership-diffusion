import { Link, NavLink } from "react-router";
import { useState } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  ActivityLogIcon,
  ArchiveIcon,
  BarChartIcon,
  CubeIcon,
  DashboardIcon,
  FileTextIcon,
  GridIcon,
  LayersIcon,
  MagnifyingGlassIcon,
  MixIcon,
  TableIcon,
} from "@radix-ui/react-icons";
import ThemeToggle from "./ThemeToggle";
import LocalProfile from "./LocalProfile";
import TickerSearch from "./TickerSearch";
import { BrandLockup } from "./BrandMark";
import type { SnapshotContextValue } from "../data/SnapshotContext";
import { normalizeDataStatus } from "../data/snapshot";
import { formatDateLabel, formatEnumLabel } from "../data/format";

const navGroups = [
  {
    label: "Sectors",
    items: [
      { path: "/sectors", label: "Sectors dashboard", Icon: DashboardIcon },
      { path: "/sources", label: "Coverage & sources", Icon: ActivityLogIcon },
    ],
  },
  {
    label: "IDX context",
    items: [
      { path: "/overview", label: "Overview", Icon: DashboardIcon },
      { path: "/what-changed", label: "What Changed", Icon: ActivityLogIcon },
      { path: "/movers", label: "Market Movers", Icon: BarChartIcon },
      { path: "/foreign", label: "Foreign Flow", Icon: BarChartIcon },
      { path: "/ownership", label: "Ownership", Icon: MixIcon },
    ],
  },
  {
    label: "Map",
    items: [
      { path: "/heatmap", label: "Stock Heatmap", Icon: GridIcon },
      { path: "/map", label: "Leadership Map", Icon: LayersIcon },
    ],
  },
  {
    label: "Catalog",
    items: [
      { path: "/konglo", label: "Konglo Catalog", Icon: MixIcon },
      { path: "/themes", label: "IDXIC Subindustries", Icon: ArchiveIcon },
      { path: "/explorer", label: "Group Explorer", Icon: BarChartIcon },
      { path: "/groups", label: "All Groups", Icon: TableIcon },
      { path: "/tickers", label: "Ticker Explorer", Icon: MagnifyingGlassIcon },
    ],
  },
  {
    label: "Guide",
    items: [{ path: "/methodology", label: "Methodology", Icon: FileTextIcon }],
  },
];

interface Props {
  children: React.ReactNode;
  taxonomy: "Sector" | "Industry";
  onTaxonomyChange: (t: "Sector" | "Industry") => void;
  snap: SnapshotContextValue;
}

function formatAsOf(asOf: string | null | undefined): string {
  return formatDateLabel(asOf);
}

function formatProviderMode(mode: string | undefined): string {
  switch (mode) {
    case "PUBLIC_PROTOTYPE":
      return "Recorded release";
    case "DEMO_FIXTURE":
      return "Recorded data";
    case "SECTORS_FIXTURE":
      return "Recorded data";
    case "SECTORS_LIVE":
      return "Live Sectors";
    default:
      return "Market data";
  }
}

export default function AppShell({ children, taxonomy, onTaxonomyChange, snap }: Props) {
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const asOf = formatAsOf(snap.data?.payload.as_of);
  const providerMode = snap.data?.payload.manifest?.entries?.[0]?.provider_mode;
  const providerLabel = formatProviderMode(providerMode);
  const qualityStatus = normalizeDataStatus(snap.data?.payload.quality.status);
  const availableTaxonomies = new Set(
    snap.data?.payload.groups.map((group) => group.taxonomy_level.toLowerCase()) ?? [],
  );
  const canToggleTaxonomy =
    availableTaxonomies.has("sector") && availableTaxonomies.has("industry");
  const taxonomyAvailable = availableTaxonomies.has(taxonomy.toLowerCase());
  const displayedTaxonomy = taxonomyAvailable ? taxonomy : "Sector";
  const dotColor =
    qualityStatus === "READY"
      ? "#178477"
      : qualityStatus === "READY_WITH_GAPS" || qualityStatus === "PARTIAL"
        ? "var(--accent-ink)"
        : qualityStatus === "STALE" || qualityStatus === "FAILED"
          ? "var(--down)"
          : snap.loading
            ? "var(--muted)"
            : snap.error
              ? "var(--down)"
              : "var(--muted)";

  return (
    <Tooltip.Provider delayDuration={150}>
    <div style={{ display: "flex", height: "100%", background: "var(--bg)" }}>
      <aside
        className="desktop-only"
        aria-label="Primary"
        style={{
          width: sidebarExpanded ? 208 : 60,
          flexShrink: 0,
          background: "var(--surface)",
          borderRight: "1px solid var(--line)",
          display: "flex",
          flexDirection: "column",
          transition: "width 180ms ease",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: sidebarExpanded ? "18px 18px 16px" : "16px 14px",
            borderBottom: "1px solid var(--line)",
          }}
        >
          <Link to="/" aria-label="Back to landing page" title="Back to landing page (Home)" style={{ color: "inherit", textDecoration: "none" }}>
            <BrandLockup compact={!sidebarExpanded} />
          </Link>
        </div>
        <nav style={{ padding: "12px 6px", flex: 1, minHeight: 0, overflowY: "auto", display: "grid", gap: 10, alignContent: "start" }}>
          {navGroups.map((group) => (
            <div key={group.label} role="group" aria-label={group.label} className="rail-nav-group">
              {sidebarExpanded && <div className="rail-nav-group-label">{group.label}</div>}
              {group.items.map((item) => (
                <Tooltip.Root key={item.path}>
                  <Tooltip.Trigger asChild>
                    <NavLink
                      to={item.path}
                      title={sidebarExpanded ? undefined : item.label}
                      aria-label={item.label}
                      className="rail-link"
                    >
                      {({ isActive }) => (
                        <>
                          <span className="rail-icon" aria-hidden="true">
                            <item.Icon width={16} height={16} />
                          </span>
                          {sidebarExpanded && <span>{item.label}</span>}
                          {isActive && <span className="sr-only">(current)</span>}
                        </>
                      )}
                    </NavLink>
                  </Tooltip.Trigger>
                  {!sidebarExpanded && (
                    <Tooltip.Portal>
                      <Tooltip.Content side="right" sideOffset={8} style={{ background: "var(--ink)", color: "var(--bg)", fontSize: 12, padding: "6px 10px", borderRadius: 6, zIndex: 100 }}>
                        {item.label}
                        <Tooltip.Arrow style={{ fill: "var(--ink)" }} />
                      </Tooltip.Content>
                    </Tooltip.Portal>
                  )}
                </Tooltip.Root>
              ))}
            </div>
          ))}
        </nav>
        <div
          style={{
            padding: sidebarExpanded ? 18 : 16,
            borderTop: "1px solid var(--line)",
            whiteSpace: "nowrap",
          }}
        >
          {sidebarExpanded && (
            <div className="eyebrow-muted" style={{ lineHeight: 1.8 }}>
              {providerLabel}
              <br />
              Indonesia
              <br />
              EOD
            </div>
          )}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              marginTop: sidebarExpanded ? 10 : 0,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: dotColor,
                display: "inline-block",
                flexShrink: 0,
              }}
            />
            {sidebarExpanded && (
              <span className="eyebrow" style={{ color: dotColor }}>
                {snap.loading
                  ? "Loading"
                  : snap.error
                    ? "Release not loaded"
                    : "Recorded"}
              </span>
            )}
          </div>
          {sidebarExpanded && <div className="eyebrow-muted">{asOf}</div>}
          <LocalProfile compact={!sidebarExpanded} />
        </div>
      </aside>
      <div
        style={{
          minWidth: 0,
          flex: 1,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <header
          className="workspace-header"
          style={{
            minHeight: 45,
            padding: "8px 22px",
            background: "var(--surface)",
            borderBottom: "1px solid var(--line)",
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "center",
          }}
        >
          <button
            onClick={() => setSidebarExpanded((value) => !value)}
            className="desktop-only"
            aria-label={sidebarExpanded ? "Minimize sidebar" : "Expand sidebar"}
            title={sidebarExpanded ? "Minimize sidebar" : "Expand sidebar"}
            type="button"
            style={{
              border: "1px solid var(--line)",
              borderRadius: 5,
              background: "var(--surface)",
              width: 30,
              height: 30,
              cursor: "pointer",
              fontSize: 13,
              color: "var(--ink)",
            }}
          >
            {sidebarExpanded ? "‹" : "›"}
          </button>
          <button
            type="button"
            onClick={() => setMobileNavOpen((value) => !value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setMobileNavOpen(false);
            }}
            className="mobile-only"
            aria-label={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileNavOpen}
            aria-controls="mobile-nav"
            title={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"}
            style={{
              border: "1px solid var(--line)",
              background: "transparent",
              minWidth: 32,
              height: 28,
              cursor: "pointer",
              fontSize: 14,
              padding: "0 8px",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {mobileNavOpen ? "✕" : "☰"}
          </button>
          <Link
            to="/"
            title="Back to homepage"
            className="btn-sheen workspace-home"
            style={{
              color: "var(--ink)",
              textDecoration: "none",
              border: "1px solid var(--line)",
              padding: "4px 8px",
              fontSize: 11,
              display: "inline-block",
            }}
          >
            ⌂ Home
          </Link>
          <TickerSearch registry={snap.data?.listingRegistry ?? null} />
          <span className="eyebrow-muted tabnum workspace-asof">{asOf}</span>
          <span className="workspace-separator" style={{ color: "var(--muted)" }}>|</span>
          <button
            type="button"
            onClick={() => {
              if (canToggleTaxonomy) {
                onTaxonomyChange(taxonomy === "Sector" ? "Industry" : "Sector");
              }
            }}
            className="eyebrow"
            disabled={!canToggleTaxonomy}
            aria-label={
              canToggleTaxonomy
                ? `Switch taxonomy, currently ${displayedTaxonomy}`
                : `${displayedTaxonomy} taxonomy`
            }
            title={
              canToggleTaxonomy
                ? "Switch between Sector and Industry"
                : "Selected-release taxonomy"
            }
            style={{
              border: 0,
              background: "transparent",
              cursor: canToggleTaxonomy ? "pointer" : "default",
              padding: 0,
              opacity: canToggleTaxonomy ? 1 : 0.65,
            }}
          >
            {displayedTaxonomy}{canToggleTaxonomy ? " ▾" : ""}
          </button>
          <span className="eyebrow-muted desktop-only workspace-group-meta">
            | {snap.data?.sectors.length ?? "—"} {displayedTaxonomy.toLowerCase()} groups | EOD
          </span>
          <span
            style={{
              marginLeft: "auto",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
            className="eyebrow-muted desktop-only"
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: dotColor,
                display: "inline-block",
              }}
            />
            {snap.loading
              ? "Loading snapshot…"
              : snap.error
                ? "Release not loaded"
                : "Recorded · " + asOf}
          </span>
          <ThemeToggle />
          <div className="mobile-only"><LocalProfile compact /></div>
          <button
            className="btn-sheen"
            style={{
              border: "1px solid var(--line)",
              background: "transparent",
              padding: "4px 10px",
              fontSize: 11,
              cursor: "pointer",
            }}
            onClick={() => window.location.reload()}
          >
            Refresh
          </button>
        </header>
        {mobileNavOpen && (
          <nav
            id="mobile-nav"
            aria-label="Primary"
            className="mobile-nav-panel"
            style={{
              borderBottom: "1px solid var(--line)",
              background: "var(--surface)",
              padding: "8px 12px 12px",
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") setMobileNavOpen(false);
            }}
          >
            <div
              style={{
                display: "grid",
                gap: 4,
              }}
            >
              {navGroups.map((group) => (
                <div key={group.label} role="group" aria-label={group.label} className="mobile-nav-group">
                  <div className="rail-nav-group-label">{group.label}</div>
                  {group.items.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileNavOpen(false)}
                      aria-label={item.label}
                      className="rail-link"
                      style={{ minHeight: 44 }}
                    >
                      <span className="rail-icon" aria-hidden="true">
                        <item.Icon width={16} height={16} />
                      </span>
                      {item.label}
                    </NavLink>
                  ))}
                </div>
              ))}
            </div>
          </nav>
        )}
        <main className="scroll-thin workspace-main" style={{ flex: 1, overflowY: "auto" }}>
          {snap.error ? (
            <div
              style={{
                padding: "48px 32px",
                maxWidth: 720,
                margin: "0 auto",
                color: "var(--ink)",
              }}
            >
              <div
                className="eyebrow-muted"
                style={{ color: "var(--down)", marginBottom: 8 }}
              >
                SNAPSHOT UNAVAILABLE
              </div>
              <h1
                style={{
                  fontSize: 26,
                  letterSpacing: "-.04em",
                  margin: "0 0 12px",
                }}
              >
                No snapshot JSON loaded
              </h1>
              <p style={{ color: "var(--muted)", lineHeight: 1.6 }}>
                {snap.error}
              </p>
              <pre
                style={{
                  fontFamily: "Geist Mono, monospace",
                  fontSize: 12,
                  background: "var(--surface-subtle)",
                  border: "1px solid var(--line)",
                  padding: "12px 14px",
                  marginTop: 18,
                  whiteSpace: "pre-wrap",
                }}
              >
                {`.venv/bin/python -m scripts.export_snapshot_json --latest\n.venv/bin/python -m scripts.build_snapshot_index`}
              </pre>
            </div>
          ) : snap.loading ? (
            <div
              role="status"
              aria-live="polite"
              style={{
                padding: "48px 32px",
                maxWidth: 720,
                margin: "0 auto",
                color: "var(--muted)",
                fontFamily: "Geist Mono, monospace",
                fontSize: 12,
              }}
            >
              Loading latest snapshot…
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </div>
    </Tooltip.Provider>
  );
}
