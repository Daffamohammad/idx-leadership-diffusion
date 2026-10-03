import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useSnapshot } from "../data/SnapshotProvider";
import type { SectorData, TaxonomyGroupData } from "../data/adapter";
import type { TaxonomyKind } from "../data/snapshot";
import { LeadershipChip, DiffusionChip, DataStatusChip } from "../components/StatusChips";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceModel";
import { WindowCapNotice } from "../components/SnapshotNotices";
import MarketHeatmap from "../components/MarketHeatmap";
import { formatCountLabel, formatEnumLabel, formatPercent } from "../data/format";
import {
  clearCatalogFocus,
  peekCatalogFocus,
  rememberCatalogFocus,
  rememberCatalogUrl,
} from "../data/catalogFocus";

type SortKey =
  | "name"
  | "leadership"
  | "prevLeadership"
  | "transition"
  | "excessYtd"
  | "excess20d"
  | "excess60d"
  | "breadth"
  | "breadthDelta"
  | "diffusion"
  | "concentration"
  | "concentrationDelta"
  | "confirmation"
  | "eligible"
  | "coverage";

type SortDir = "asc" | "desc";

const headerCell: React.CSSProperties = {
  fontFamily: "Geist Mono, ui-monospace, monospace",
  fontSize: 10,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "var(--muted)",
  padding: "8px 10px",
  textAlign: "left",
  borderBottom: "1px solid var(--line)",
  background: "var(--surface-subtle)",
  cursor: "pointer",
  userSelect: "none",
  whiteSpace: "nowrap",
  position: "sticky",
  top: 0,
};

const bodyCell: React.CSSProperties = {
  padding: "9px 10px",
  fontSize: 12,
  fontFamily: "Geist Mono, ui-monospace, monospace",
  borderBottom: "1px solid #ececec",
  color: "var(--ink)",
  whiteSpace: "nowrap",
  verticalAlign: "middle",
};

const MISSING = Number.NEGATIVE_INFINITY;

function breadthDeltaFor(s: SectorData): number | null {
  if (
    s.breadth === null ||
    s.breadth === undefined ||
    s.prevBreadth === undefined ||
    !Number.isFinite(s.breadth) ||
    !Number.isFinite(s.prevBreadth)
  ) {
    return null;
  }
  return s.breadth - s.prevBreadth;
}

function signColor(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "var(--muted)";
  if (v > 0) return "var(--up)";
  if (v < 0) return "var(--down)";
  return "var(--muted)";
}

// The adapter exposes concentration on a 0–100 percentage scale.
function top3Label(c: number | null | undefined): string {
  return c === null || c === undefined || !Number.isFinite(c)
    ? "—"
    : `${c.toFixed(0)}%`;
}

// durable contract: turns (Leadership, PrevLeadership) into a short transition tag
// used both in the dedicated Transition column and as a sort key.
function transitionLabel(s: SectorData): string {
  return !s.prevLeadership || s.prevLeadership === s.leadership
    ? "—"
    : `${formatEnumLabel(s.prevLeadership)} → ${formatEnumLabel(s.leadership)}`;
}

// durable contract: groups data quality into READY / READY_WITH_GAPS / DATA_GAP
// using the diff between eligible and raw constituents. Drives the chip column.
function dataStatusForSector(s: SectorData): "READY" | "READY_WITH_GAPS" | "DATA_GAP" {
  if (s.eligibleConstituents === 0) return "DATA_GAP";
  if (s.diffusion === "UNCONFIRMED" || s.missingConstituents > 0) {
    return "READY_WITH_GAPS";
  }
  return "READY";
}

function compare(a: SectorData, b: SectorData, key: SortKey, dir: SortDir): number {
  const mult = dir === "asc" ? 1 : -1;
  switch (key) {
    case "name":
      return mult * a.name.localeCompare(b.name);
    case "leadership":
      return mult * a.leadership.localeCompare(b.leadership);
    case "prevLeadership":
      return mult * (a.prevLeadership ?? "ZZ").localeCompare(b.prevLeadership ?? "ZZ");
    case "transition":
      return mult * transitionLabel(a).localeCompare(transitionLabel(b));
    case "excessYtd":
      return mult * ((a.excessYtd ?? MISSING) - (b.excessYtd ?? MISSING));
    case "excess20d":
      return mult * ((a.excess20d ?? MISSING) - (b.excess20d ?? MISSING));
    case "excess60d":
      return mult * ((a.excess60d ?? MISSING) - (b.excess60d ?? MISSING));
    case "breadth":
      return mult * ((a.breadth ?? MISSING) - (b.breadth ?? MISSING));
    case "breadthDelta": {
      const da = breadthDeltaFor(a) ?? MISSING;
      const db = breadthDeltaFor(b) ?? MISSING;
      return mult * (da - db);
    }
    case "diffusion":
      return mult * a.diffusion.localeCompare(b.diffusion);
    case "concentration":
      return mult * ((a.concentration ?? MISSING) - (b.concentration ?? MISSING));
    case "concentrationDelta":
      // prev concentration is not exposed by the adapter; stable null comparison
      return mult * 0;
    case "confirmation":
      return mult * a.foreignFlow.localeCompare(b.foreignFlow);
    case "eligible":
      return mult * (a.eligibleConstituents - b.eligibleConstituents);
    case "coverage": {
      const ca = a.eligibleConstituents / Math.max(a.constituents, 1);
      const cb = b.eligibleConstituents / Math.max(b.constituents, 1);
      return mult * (ca - cb);
    }
  }
}

export default function MasterGroupTable() {
  const { data } = useSnapshot();
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const taxonomy = ((params.get("taxonomy") ?? "SECTOR").toUpperCase() as TaxonomyKind);
  const activeTaxonomy: TaxonomyKind = taxonomy === "KONGLO" || taxonomy === "THEMES" ? taxonomy : "SECTOR";
  const view = params.get("view") === "heatmap" ? "heatmap" : "table";
  const filter = params.get("filter") ?? "";
  const sectors: SectorData[] = data?.sectors ?? [];
  const taxonomyGroups: TaxonomyGroupData[] = useMemo(() => {
    if (!data) return [];
    return Object.values(data.taxonomyGroups).filter((g) => g.taxonomyKind === activeTaxonomy)
      .sort((a, b) => b.constituents - a.constituents || a.id.localeCompare(b.id));
  }, [data, activeTaxonomy]);
  const [sortKey, setSortKey] = useState<SortKey>("excess20d");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [taxSort, setTaxSort] = useState<"name" | "members" | "excess20d" | "excess60d" | "breadth">("members");
  const [taxDir, setTaxDir] = useState<SortDir>("desc");
  const setFilter = (v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set("filter", v); else next.delete("filter");
    setParams(next, { replace: true });
  };
  const setTaxonomy = (k: TaxonomyKind) => {
    const next = new URLSearchParams(params);
    next.set("taxonomy", k);
    setParams(next, { replace: true });
  };
  const setView = (v: "table" | "heatmap") => {
    const next = new URLSearchParams(params);
    next.set("view", v);
    setParams(next, { replace: true });
  };
  const rows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const filtered = q
      ? sectors.filter(
          (s) =>
            s.name.toLowerCase().includes(q) ||
            s.id.toLowerCase().includes(q) ||
            // Ticker and company-name search has to reach sector members too;
            // matching only the group name leaves ?taxonomy=SECTOR&filter=TICKER empty.
            (data?.constituentsByGroup[s.id] ?? []).some(
              (c) => c.ticker.toLowerCase().includes(q) || c.name.toLowerCase().includes(q),
            ),
        )
      : sectors;
    return [...filtered].sort((a, b) => compare(a, b, sortKey, sortDir));
  }, [sectors, sortKey, sortDir, filter, data]);
  const taxRows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const filtered = q
      ? taxonomyGroups.filter((g) =>
          g.name.toLowerCase().includes(q) || g.id.toLowerCase().includes(q) ||
          g.memberships?.some((m) => m.ticker.toLowerCase().includes(q)),
        )
      : taxonomyGroups;
    const mult = taxDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      switch (taxSort) {
        case "name": return mult * a.name.localeCompare(b.name);
        case "members": return mult * (a.constituents - b.constituents);
        case "excess20d": return mult * ((a.excess20d ?? Number.NEGATIVE_INFINITY) - (b.excess20d ?? Number.NEGATIVE_INFINITY));
        case "excess60d": return mult * ((a.excess60d ?? Number.NEGATIVE_INFINITY) - (b.excess60d ?? Number.NEGATIVE_INFINITY));
        case "breadth": return mult * ((a.breadth ?? Number.NEGATIVE_INFINITY) - (b.breadth ?? Number.NEGATIVE_INFINITY));
      }
    });
  }, [taxonomyGroups, filter, taxSort, taxDir]);
  const uniqueTickers = useMemo(() => {
    const set = new Set<string>();
    for (const g of taxonomyGroups) for (const m of g.memberships ?? []) set.add(m.ticker);
    return set.size;
  }, [taxonomyGroups]);
  const searchRef = useRef<HTMLInputElement>(null);
  const focusHandledRef = useRef(false);
  // Remember this catalog's own URL so a detail view can come straight back to
  // the same tab, filter, view and sort.
  useEffect(() => {
    rememberCatalogUrl(location.pathname, location.search);
  }, [location.pathname, location.search]);
  // Closing a detail view restores focus to the row that opened it. Rows may
  // appear a render after mount (snapshot still loading), so this retries until
  // the row exists or the data has settled; then it falls back to search.
  useEffect(() => {
    if (focusHandledRef.current) return;
    const pending = peekCatalogFocus();
    if (!pending) {
      focusHandledRef.current = true;
      return;
    }
    const target = Array.from(document.querySelectorAll<HTMLElement>("[data-group-id]"))
      .find((el) => el.getAttribute("data-group-id") === pending);
    if (target) {
      focusHandledRef.current = true;
      clearCatalogFocus();
      target.focus({ preventScroll: false });
      target.scrollIntoView({ block: "center", behavior: "auto" });
      return;
    }
    // Snapshot still loading: keep the pending id and try again next render.
    if (!data) return;
    focusHandledRef.current = true;
    clearCatalogFocus();
    searchRef.current?.focus();
  }, [data]);
  const totalMemberships = useMemo(() => taxonomyGroups.reduce((s, g) => s + g.constituents, 0), [taxonomyGroups]);
  const eligibleTotal = useMemo(() => taxonomyGroups.reduce((s, g) => s + (g.eligible ?? 0), 0), [taxonomyGroups]);

  if (!sectors.length && !taxonomyGroups.length) {
    return (
      <EmptyState
        label="Master Group Table"
        title="No groups available"
        body="The current snapshot does not expose any group metrics. Verify the snapshot pipeline emitted groups."
      />
    );
  }

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(
        key === "name" || key === "leadership" || key === "diffusion" || key === "transition"
          ? "asc"
          : "desc",
      );
    }
  };

  const arrow = (key: SortKey) => (sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : "");
  const sortLabel = (key: SortKey): string => key === "excessYtd"
    ? "YTD excess"
    : key === "excess20d"
      ? "20D excess"
      : key === "excess60d"
        ? "60D excess"
        : formatEnumLabel(key);
  const sortableHeader = (key: SortKey) => ({
    onClick: () => handleSort(key),
    tabIndex: 0,
    role: "button" as const,
    "aria-sort": (sortKey === key
      ? sortDir === "asc" ? "ascending" : "descending"
      : "none") as "ascending" | "descending" | "none",
    "aria-label": `Sort by ${sortLabel(key)}`,
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleSort(key);
      }
    },
  });

  return (
    <section className="content-shell" style={{ padding: "28px var(--page-gutter) 80px" }}>
      <header style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div
            style={{
              fontFamily: "Geist Mono, ui-monospace, monospace",
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--muted)",
            }}
          >
            Master Group Table
          </div>
          <EvidenceBadge kind="SNAPSHOT" compact />
        </div>
        <h1
          style={{
            margin: "4px 0 6px",
            fontSize: 26,
            letterSpacing: "-.03em",
            fontWeight: 500,
            color: "var(--ink)",
          }}
        >
          Analytical scanner
        </h1>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: 13, maxWidth: 720 }}>
          Sortable cross-section of every group in the real persisted market snapshot. Read columns
          left-to-right to evaluate leadership, breadth, diffusion, concentration, and confirmation independently.
        </p>
      </header>

      <div style={{ marginBottom: 14 }}>
        <WindowCapNotice data={data} compact />
      </div>

      <div className="tabs" role="tablist" aria-label="Catalog taxonomy" style={{ marginBottom: 12 }}>
        {(["SECTOR", "KONGLO", "THEMES"] as TaxonomyKind[]).map((k) => (
          <button key={k} role="tab" aria-selected={activeTaxonomy === k} className="tab" onClick={() => setTaxonomy(k)}>
            {k === "SECTOR" ? "Sectors" : k === "KONGLO" ? "Konglo" : "Themes"}
          </button>
        ))}
        <span style={{ marginLeft: "auto", display: "flex", gap: 6 }} role="group" aria-label="Catalog view">
          <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")} className="btn btn-outline" style={{ minHeight: 32, padding: "4px 10px", fontSize: 12 }}>Table</button>
          <button type="button" aria-pressed={view === "heatmap"} onClick={() => setView("heatmap")} className="btn btn-outline" style={{ minHeight: 32, padding: "4px 10px", fontSize: 12 }}>Heatmap</button>
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <input
          ref={searchRef}
          id="catalog-search"
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search group or ticker…"
          aria-label="Search groups or tickers"
          style={{
            padding: "7px 10px",
            border: "1px solid var(--line)",
            borderRadius: 4,
            background: "var(--surface)",
            fontFamily: "Geist Mono, ui-monospace, monospace",
            fontSize: 12,
            width: 260,
          }}
        />
        <span style={{ color: "var(--muted)", fontSize: 11 }}>
          {activeTaxonomy === "SECTOR"
            ? `${rows.length} of ${sectors.length} groups · sorted by ${sortLabel(sortKey)}${arrow(sortKey)}`
            : `${taxRows.length} of ${taxonomyGroups.length} groups · ${totalMemberships} memberships · ${uniqueTickers} unique tickers · ${eligibleTotal} eligible`}
        </span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 14 }}>
          {activeTaxonomy === "KONGLO" && <Link to="/konglo" style={{ fontSize: 12 }}>Browse catalog →</Link>}
          {activeTaxonomy === "THEMES" && <Link to="/themes" style={{ fontSize: 12 }}>Browse catalog →</Link>}
          <Link to={`/map?taxonomy=${activeTaxonomy}`} style={{ fontSize: 12 }}>Open rotation →</Link>
        </span>
      </div>

      {view === "heatmap" && data && (
        <MarketHeatmap
          taxonomyGroups={data.taxonomyGroups}
          taxonomyNames={{ SECTOR: "Sector", KONGLO: "Konglo", THEMES: "Themes" }}
          taxonomyKindsById={Object.fromEntries(Object.entries(data.taxonomyViews).map(([id, v]) => [id, v.taxonomy_kind]))}
          foreignFlow={data.foreignFlow}
          asOf={data.payload.as_of}
          onSelectGroup={(kind, taxonomyId, groupId) => {
            void taxonomyId;
            rememberCatalogFocus(groupId);
            navigate(`/explorer?taxonomy=${kind}&group=${encodeURIComponent(groupId)}`);
          }}
        />
      )}

      {view === "table" && activeTaxonomy !== "SECTOR" && (
        <div className="table-scroll" style={{ border: "1px solid var(--line)", borderRadius: 6, background: "var(--surface)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 860 }} aria-label={`${activeTaxonomy} catalog`}>
            <thead>
              <tr>
                <th style={headerCell}><button type="button" onClick={() => { setTaxSort("name"); setTaxDir(taxDir === "asc" ? "desc" : "asc"); }} style={{ all: "unset", cursor: "pointer" }}>Group · code{taxSort === "name" ? (taxDir === "asc" ? " ▲" : " ▼") : ""}</button></th>
                <th style={{ ...headerCell, textAlign: "right" }}><button type="button" onClick={() => { setTaxSort("members"); setTaxDir(taxDir === "asc" ? "desc" : "asc"); }} style={{ all: "unset", cursor: "pointer" }}>Members{taxSort === "members" ? (taxDir === "asc" ? " ▲" : " ▼") : ""}</button></th>
                <th style={{ ...headerCell, textAlign: "right" }}>20D excess</th>
                <th style={{ ...headerCell, textAlign: "right" }}>60D excess</th>
                <th style={{ ...headerCell, textAlign: "right" }}>Breadth</th>
                <th style={headerCell}>Rotation</th>
                <th style={headerCell}>Detail</th>
              </tr>
            </thead>
            <tbody>
              {taxRows.map((g) => (
                <tr key={g.id}>
                  <td style={{ ...bodyCell, fontWeight: 600 }}>{g.name}<span style={{ display: "block", fontWeight: 400, fontSize: 11, color: "var(--muted)" }}>{g.id} · {g.taxonomyVersion}</span></td>
                  <td style={{ ...bodyCell, textAlign: "right" }} className="tabnum">{g.eligible}/{g.constituents}</td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(g.excess20d) }} className="tabnum">{formatPercent(g.excess20d)}</td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(g.excess60d) }} className="tabnum">{formatPercent(g.excess60d)}</td>
                  <td style={{ ...bodyCell, textAlign: "right" }} className="tabnum">{g.breadth === null ? "—" : `${g.breadth.toFixed(1)}%`}</td>
                  <td style={bodyCell}><Link to={`/map?taxonomy=${g.taxonomyKind}`}>Rotation →</Link></td>
                  <td style={bodyCell}>
                    <Link
                      data-group-id={g.id}
                      to={`/explorer?taxonomy=${g.taxonomyKind}&group=${encodeURIComponent(g.id)}`}
                      onClick={() => rememberCatalogFocus(g.id)}
                    >
                      Open →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ padding: "8px 12px", color: "var(--muted)", fontSize: 11 }}>Overlapping themes do not represent unique market share. Missing metrics show — (neutral), never red or zero. Areas sized by member count where market cap is unavailable.</p>
        </div>
      )}

      {view === "table" && activeTaxonomy === "SECTOR" && (
      <div
        style={{
          overflowX: "auto",
          border: "1px solid var(--line)",
          borderRadius: 6,
          background: "var(--surface)",
        }}
      >
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            minWidth: 1320,
          }}
          aria-label="Master group table"
        >
          <thead>
            <tr>
              <th style={headerCell} {...sortableHeader("name")}>
                Group{arrow("name")}
              </th>
              <th style={headerCell} {...sortableHeader("leadership")}>
                Leadership{arrow("leadership")}
              </th>
              <th style={headerCell} {...sortableHeader("prevLeadership")}>
                Prev{arrow("prevLeadership")}
              </th>
              <th style={headerCell} {...sortableHeader("transition")}>
                Transition{arrow("transition")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("excessYtd")}
              >
                YTD Excess{arrow("excessYtd")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("excess20d")}
              >
                20D Excess{arrow("excess20d")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("excess60d")}
              >
                60D Excess{arrow("excess60d")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("breadth")}
              >
                Breadth{arrow("breadth")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("breadthDelta")}
              >
                Δ Breadth (%){arrow("breadthDelta")}
              </th>
              <th style={headerCell} {...sortableHeader("diffusion")}>
                Diffusion{arrow("diffusion")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("concentration")}
              >
                Top-3{arrow("concentration")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("confirmation")}
              >
                Confirmation{arrow("confirmation")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("eligible")}
              >
                Elig / Total{arrow("eligible")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                {...sortableHeader("coverage")}
              >
                Coverage{arrow("coverage")}
              </th>
              <th style={headerCell}>Data</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const breadthDelta = breadthDeltaFor(s);
              const coveragePct = s.constituents > 0
                ? (s.eligibleConstituents / s.constituents) * 100
                : 0;
              const breadthText = s.breadth === null || s.breadth === undefined
                ? "—"
                : `${s.breadth.toFixed(1)}%`;
              return (
                <tr key={s.id}>
                  <td style={{ ...bodyCell, fontWeight: 500 }}>
                    <Link
                      data-group-id={s.id}
                      to={`/explorer?taxonomy=SECTOR&group=${encodeURIComponent(s.id)}`}
                      onClick={() => rememberCatalogFocus(s.id)}
                      style={{ color: "var(--ink)", textDecoration: "none", borderBottom: "1px dotted #b9c0be" }}
                    >
                      {s.name}
                    </Link>
                  </td>
                  <td style={bodyCell}>
                    <LeadershipChip state={s.leadership} small />
                  </td>
                  <td style={{ ...bodyCell, color: "var(--muted)", fontSize: 11 }}>
                    {formatEnumLabel(s.prevLeadership)}
                  </td>
                  <td style={{ ...bodyCell, fontSize: 11, color: "var(--ink)" }}>
                    {transitionLabel(s)}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(s.excessYtd) }}>
                    {formatPercent(s.excessYtd)}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(s.excess20d) }}>
                    {formatPercent(s.excess20d)}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(s.excess60d) }}>
                    {formatPercent(s.excess60d)}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right" }}>{breadthText}</td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(breadthDelta) }}>
                    {formatPercent(breadthDelta)}
                  </td>
                  <td style={bodyCell}>
                    <DiffusionChip state={s.diffusion} small />
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right" }}>
                    {top3Label(s.concentration)}
                  </td>
                  <td style={{ ...bodyCell, color: "var(--muted)", fontSize: 11 }}>
                    {formatEnumLabel(s.foreignFlow)}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: "var(--muted)" }}>
                    {s.eligibleConstituents}/{s.constituents}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: "var(--muted)" }}>
                    {coveragePct.toFixed(0)}%
                  </td>
                  <td style={bodyCell}>
                    <DataStatusChip status={dataStatusForSector(s)} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      )}

      <p style={{ marginTop: 12, color: "var(--muted)", fontSize: 11, lineHeight: 1.5 }}>
        Concentration column reflects absolute-move top-3 share (equal-weighted group return).
        Breadth Δ requires a comparable prior snapshot — where comparability is unavailable,
        diffusion displays as Unconfirmed. Confirmation is a sample-only foreign-flow signal,
        labeled accordingly.
      </p>
    </section>
  );
}
