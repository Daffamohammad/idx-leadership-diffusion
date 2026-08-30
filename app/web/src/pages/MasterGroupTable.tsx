import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useSnapshot } from "../data/SnapshotProvider";
import type { SectorData } from "../data/adapter";
import { LeadershipChip, DiffusionChip, DataStatusChip } from "../components/StatusChips";
import { EmptyState } from "../components/EmptyState";

type SortKey =
  | "name"
  | "leadership"
  | "prevLeadership"
  | "transition"
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
  color: "#686e73",
  padding: "8px 10px",
  textAlign: "left",
  borderBottom: "1px solid #dfe2e1",
  background: "#faf9f6",
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
  color: "#202325",
  whiteSpace: "nowrap",
  verticalAlign: "middle",
};

const MISSING = Number.NEGATIVE_INFINITY;

function fmtPct(v: number | null | undefined): string {
  return v === null || v === undefined || !Number.isFinite(v)
    ? "—"
    : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function signColor(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "#8f8f8f";
  if (v > 0) return "#1a6e62";
  if (v < 0) return "#8f2424";
  return "#5a5a5a";
}

// durable contract: returns the absolute-move top-3 share rendered as a 0–100% string,
// or "—" when no concentration is available. Used by every row in the column.
function top3Label(c: number | null | undefined): string {
  return c === null || c === undefined || !Number.isFinite(c)
    ? "—"
    : `${(c * 100).toFixed(0)}%`;
}

// durable contract: turns (Leadership, PrevLeadership) into a short transition tag
// used both in the dedicated Transition column and as a sort key.
function transitionLabel(s: SectorData): string {
  return !s.prevLeadership || s.prevLeadership === s.leadership
    ? "—"
    : `${s.prevLeadership} → ${s.leadership}`;
}

// durable contract: groups data quality into READY / READY_WITH_GAPS / DATA_GAP
// using the diff between eligible and raw constituents. Drives the chip column.
function dataStatusForSector(s: SectorData): "READY" | "READY_WITH_GAPS" | "DATA_GAP" {
  if (s.eligibleConstituents === 0) return "DATA_GAP";
  if (s.diffusion === "UNCONFIRMED") return "READY_WITH_GAPS";
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
    case "excess20d":
      return mult * ((a.excess20d ?? MISSING) - (b.excess20d ?? MISSING));
    case "excess60d":
      return mult * ((a.excess60d ?? MISSING) - (b.excess60d ?? MISSING));
    case "breadth":
      return mult * ((a.breadth ?? MISSING) - (b.breadth ?? MISSING));
    case "breadthDelta": {
      const da = (a.breadth ?? 0) - (a.prevBreadth ?? a.breadth ?? 0);
      const db = (b.breadth ?? 0) - (b.prevBreadth ?? b.breadth ?? 0);
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
  const sectors: SectorData[] = data?.sectors ?? [];
  const [sortKey, setSortKey] = useState<SortKey>("excess20d");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [filter, setFilter] = useState("");
  const rows = useMemo(() => {
    const filtered = filter
      ? sectors.filter((s) => s.name.toLowerCase().includes(filter.toLowerCase()))
      : sectors;
    return [...filtered].sort((a, b) => compare(a, b, sortKey, sortDir));
  }, [sectors, sortKey, sortDir, filter]);

  if (!sectors.length) {
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

  return (
    <section style={{ padding: "0 0 80px" }}>
      <header style={{ marginBottom: 24 }}>
        <div
          style={{
            fontFamily: "Geist Mono, ui-monospace, monospace",
            fontSize: 11,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "#8f8f8f",
          }}
        >
          Master Group Table
        </div>
        <h1
          style={{
            margin: "4px 0 6px",
            fontSize: 26,
            letterSpacing: "-.03em",
            fontWeight: 500,
            color: "#202325",
          }}
        >
          Analytical scanner
        </h1>
        <p style={{ margin: 0, color: "#686e73", fontSize: 13, maxWidth: 720 }}>
          Sortable cross-section of every group. Read columns left-to-right to evaluate
          leadership, breadth, diffusion, concentration, and confirmation independently.
        </p>
      </header>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter groups…"
          aria-label="Filter groups by name"
          style={{
            padding: "7px 10px",
            border: "1px solid #dfe2e1",
            borderRadius: 4,
            background: "#fff",
            fontFamily: "Geist Mono, ui-monospace, monospace",
            fontSize: 12,
            width: 240,
          }}
        />
        <span style={{ color: "#8f8f8f", fontSize: 11 }}>
          {rows.length} of {sectors.length} groups · sorted by {sortKey}
          {arrow(sortKey)}
        </span>
      </div>

      <div
        style={{
          overflowX: "auto",
          border: "1px solid #dfe2e1",
          borderRadius: 6,
          background: "#fff",
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
              <th style={headerCell} onClick={() => handleSort("name")} role="button">
                Group{arrow("name")}
              </th>
              <th style={headerCell} onClick={() => handleSort("leadership")} role="button">
                Leadership{arrow("leadership")}
              </th>
              <th style={headerCell} onClick={() => handleSort("prevLeadership")} role="button">
                Prev{arrow("prevLeadership")}
              </th>
              <th style={headerCell} onClick={() => handleSort("transition")} role="button">
                Transition{arrow("transition")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                onClick={() => handleSort("excess20d")}
                role="button"
              >
                20D Excess{arrow("excess20d")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                onClick={() => handleSort("excess60d")}
                role="button"
              >
                60D Excess{arrow("excess60d")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                onClick={() => handleSort("breadth")}
                role="button"
              >
                Breadth{arrow("breadth")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                onClick={() => handleSort("breadthDelta")}
                role="button"
              >
                Δ Breadth{arrow("breadthDelta")}
              </th>
              <th style={headerCell} onClick={() => handleSort("diffusion")} role="button">
                Diffusion{arrow("diffusion")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                onClick={() => handleSort("concentration")}
                role="button"
              >
                Top-3{arrow("concentration")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                onClick={() => handleSort("confirmation")}
                role="button"
              >
                Confirmation{arrow("confirmation")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                onClick={() => handleSort("eligible")}
                role="button"
              >
                Elig / Total{arrow("eligible")}
              </th>
              <th
                style={{ ...headerCell, textAlign: "right" }}
                onClick={() => handleSort("coverage")}
                role="button"
              >
                Coverage{arrow("coverage")}
              </th>
              <th style={headerCell}>Data</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const breadthDelta = (s.breadth ?? 0) - (s.prevBreadth ?? s.breadth ?? 0);
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
                      to={`/explorer?group=${encodeURIComponent(s.id)}`}
                      style={{ color: "#202325", textDecoration: "none", borderBottom: "1px dotted #b9c0be" }}
                    >
                      {s.name}
                    </Link>
                  </td>
                  <td style={bodyCell}>
                    <LeadershipChip state={s.leadership} small />
                  </td>
                  <td style={{ ...bodyCell, color: "#686e73", fontSize: 11 }}>
                    {s.prevLeadership ?? "—"}
                  </td>
                  <td style={{ ...bodyCell, fontSize: 11, color: "#202325" }}>
                    {transitionLabel(s)}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(s.excess20d) }}>
                    {fmtPct(s.excess20d)}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(s.excess60d) }}>
                    {fmtPct(s.excess60d)}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right" }}>{breadthText}</td>
                  <td style={{ ...bodyCell, textAlign: "right", color: signColor(breadthDelta) }}>
                    {fmtPct(breadthDelta)}
                  </td>
                  <td style={bodyCell}>
                    <DiffusionChip state={s.diffusion} small />
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right" }}>
                    {top3Label(s.concentration)}
                  </td>
                  <td style={{ ...bodyCell, color: "#5a5a5a", fontSize: 11 }}>
                    {s.foreignFlow.replace("_", " ")}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: "#5a5a5a" }}>
                    {s.eligibleConstituents}/{s.constituents}
                  </td>
                  <td style={{ ...bodyCell, textAlign: "right", color: "#5a5a5a" }}>
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

      <p style={{ marginTop: 12, color: "#8f8f8f", fontSize: 11, lineHeight: 1.5 }}>
        Concentration column reflects absolute-move top-3 share (equal-weighted group return).
        Breadth Δ requires a comparable prior snapshot — where comparability is unavailable,
        diffusion displays as UNCONFIRMED. Confirmation is a sample-only foreign-flow signal,
        labeled accordingly.
      </p>
    </section>
  );
}