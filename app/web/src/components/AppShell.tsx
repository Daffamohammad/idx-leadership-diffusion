import { Link, NavLink } from "react-router";
import { useState } from "react";
import ThemeToggle from "./ThemeToggle";
import { BrandLockup } from "./BrandMark";
import type { SnapshotContextValue } from "../data/SnapshotContext";
import { normalizeDataStatus } from "../data/snapshot";
import { formatDateLabel, formatEnumLabel } from "../data/format";

const navItems = [
  { path: "/what-changed", label: "What Changed", index: "01" },
  { path: "/overview", label: "Overview", index: "02" },
  { path: "/map", label: "Leadership Map", index: "03" },
  { path: "/maps/konglo", label: "Konglo Map", index: "04" },
  { path: "/maps/themes", label: "Themes Map", index: "05" },
  { path: "/themes", label: "Themes Explorer", index: "06" },
  { path: "/explorer", label: "Groups", index: "07" },
  { path: "/groups", label: "Groups Table", index: "08" },
  { path: "/methodology", label: "Methodology", index: "09" },
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
      return "Public prototype";
    case "DEMO_FIXTURE":
      return "Demo fixture";
    case "SECTORS_FIXTURE":
      return "Sectors fixture";
    case "SECTORS_LIVE":
      return "Live Sectors";
    default:
      return "Market data";
  }
}

export default function AppShell({ children, taxonomy, onTaxonomyChange, snap }: Props) {
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const asOf = formatAsOf(snap.data?.payload.as_of);
  const providerMode = snap.data?.payload.manifest?.entries?.[0]?.provider_mode;
  const providerLabel = formatProviderMode(providerMode);
  const qualityStatus = normalizeDataStatus(snap.data?.payload.quality.status);
  const statusLabel = qualityStatus ? formatEnumLabel(qualityStatus) : null;
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
        ? "#7a5010"
        : qualityStatus === "STALE" || qualityStatus === "FAILED"
          ? "#8f2424"
          : snap.loading
            ? "#7c858c"
            : snap.error
              ? "#8f2424"
              : "#7c858c";

  return (
    <div style={{ display: "flex", height: "100%", background: "#ffffff" }}>
      <aside
        className="desktop-only"
        style={{
          width: sidebarExpanded ? 188 : 54,
          flexShrink: 0,
          background: "#ffffff",
          borderRight: "1px solid #dfe2e1",
          display: "flex",
          flexDirection: "column",
          transition: "width 180ms ease",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: sidebarExpanded ? "18px 18px 16px" : "16px 14px",
            borderBottom: "1px solid #dfe2e1",
          }}
        >
          <BrandLockup compact={!sidebarExpanded} />
        </div>
        <nav style={{ padding: "12px 0", flex: 1 }}>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              title={item.label}
              style={({ isActive }) => ({
                display: "flex",
                gap: 10,
                padding: "9px 15px",
                borderLeft: isActive
                  ? "2px solid #f26a3d"
                  : "2px solid transparent",
                background: isActive ? "#f1eeea" : "transparent",
                color: isActive ? "#16191c" : "#686e73",
                textDecoration: "none",
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                transition: "background 0.2s ease, color 0.2s ease",
              })}
            >
              {({ isActive }) => (
                <>
                  <span
                    className="eyebrow-muted"
                    style={{
                      width: 16,
                      color: isActive ? "#f26a3d" : undefined,
                      transition: "color 0.2s ease",
                    }}
                  >
                    {item.index}
                  </span>
                  {sidebarExpanded && item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div
          style={{
            padding: sidebarExpanded ? 18 : 16,
            borderTop: "1px solid #dfe2e1",
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
                    ? "Unavailable"
                    : (statusLabel ?? "Ready")}
              </span>
            )}
          </div>
          {sidebarExpanded && <div className="eyebrow-muted">{asOf}</div>}
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
            padding: "0 22px",
            background: "#ffffff",
            borderBottom: "1px solid #dfe2e1",
            display: "flex",
            gap: 12,
            alignItems: "center",
          }}
        >
          <button
            onClick={() => setSidebarExpanded((value) => !value)}
            className="desktop-only"
            aria-label={sidebarExpanded ? "Minimize sidebar" : "Expand sidebar"}
            title={sidebarExpanded ? "Minimize sidebar" : "Expand sidebar"}
            style={{
              border: "1px solid #dfe2e1",
              background: "transparent",
              width: 25,
              height: 25,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {sidebarExpanded ? "‹" : "›"}
          </button>
          <Link
            to="/"
            title="Back to homepage"
            className="btn-sheen workspace-home"
            style={{
              color: "#16191c",
              textDecoration: "none",
              border: "1px solid #dfe2e1",
              padding: "4px 8px",
              fontSize: 11,
              display: "inline-block",
            }}
          >
            ⌂ Home
          </Link>
          <span className="eyebrow-muted tabnum workspace-asof">{asOf}</span>
          <span className="workspace-separator" style={{ color: "#dfe2e1" }}>|</span>
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
                : `${displayedTaxonomy} taxonomy; Industry data is not in this snapshot`
            }
            title={
              canToggleTaxonomy
                ? "Switch between Sector and Industry"
                : "Industry data is not in the current snapshot"
            }
            style={{
              border: 0,
              background: "transparent",
              cursor: canToggleTaxonomy ? "pointer" : "not-allowed",
              padding: 0,
              opacity: canToggleTaxonomy ? 1 : 0.65,
            }}
          >
            {displayedTaxonomy}{canToggleTaxonomy ? " ▾" : ""}
          </button>
          <span className="eyebrow-muted desktop-only">
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
                ? "Snapshot unavailable"
            : providerLabel + " · " + (statusLabel ?? "Ready") + " · Snapshot " + (snap.snapshotId ?? "—")}
          </span>
          <ThemeToggle />
          <button
            className="btn-sheen"
            style={{
              border: "1px solid #dfe2e1",
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
        <main className="scroll-thin workspace-main" style={{ flex: 1, overflowY: "auto" }}>
          {snap.error ? (
            <div
              style={{
                padding: "48px 32px",
                maxWidth: 720,
                margin: "0 auto",
                color: "#16191c",
              }}
            >
              <div
                className="eyebrow-muted"
                style={{ color: "#8f2424", marginBottom: 8 }}
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
              <p style={{ color: "#4d4d4d", lineHeight: 1.6 }}>
                {snap.error}
              </p>
              <pre
                style={{
                  fontFamily: "Geist Mono, monospace",
                  fontSize: 12,
                  background: "#fafafa",
                  border: "1px solid #ebebeb",
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
                color: "#686e73",
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
  );
}
