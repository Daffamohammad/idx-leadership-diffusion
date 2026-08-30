import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useSnapshot } from "../data/SnapshotProvider";
import type { TaxonomyGroupAggregate, TaxonomyView } from "../data/snapshot";
import { LeadershipChip, DiffusionChip, DataStatusChip } from "../components/StatusChips";
import { EmptyState } from "../components/EmptyState";
import { formatDateLabel, formatEnumLabel } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";

const THEMES_TAXONOMY_ID = "themes";

// Durable formatter contracts reused across the page.
function fmtSignedPct(v: number | null | undefined): string {
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

function asLeadership(state: string) {
  return state as "LEADING" | "IMPROVING" | "WEAKENING" | "LAGGING" | "UNCONFIRMED";
}

function asDiffusion(state: string) {
  return state as "BROADENING" | "STABLE" | "NARROWING" | "UNCONFIRMED";
}

function asDataStatus(state: string) {
  return state as "READY" | "READY_WITH_GAPS" | "DATA_GAP" | "STALE" | "FAILED" | "UNAVAILABLE" | "PARTIAL";
}

export default function ThemesExplorer() {
  const { data } = useSnapshot();
  const taxonomyView: TaxonomyView | undefined = data?.taxonomyViews?.[THEMES_TAXONOMY_ID];
  const groups = taxonomyView?.groups ?? [];
  const [filter, setFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(groups[0]?.taxonomy_group_id ?? null);

  const filteredGroups = useMemo(() => {
    const f = filter.toLowerCase();
    return groups.filter((g) =>
      !f ? true : g.taxonomy_group_name.toLowerCase().includes(f),
    );
  }, [groups, filter]);

  const selected: TaxonomyGroupAggregate | undefined = useMemo(() => {
    const fromList = filteredGroups.find((g) => g.taxonomy_group_id === selectedId);
    if (fromList) return fromList;
    return filteredGroups[0] ?? groups.find((g) => g.taxonomy_group_id === selectedId);
  }, [filteredGroups, selectedId, groups]);

  if (!taxonomyView || !groups.length) {
    return (
      <EmptyState
        label="Themes Explorer"
        title="Themes taxonomy not available"
        body="The current snapshot does not expose a themes view. Verify that build_taxonomy_views.py emitted themes.json for this snapshot."
      />
    );
  }

  return (
    <section style={{ padding: "0 0 80px" }}>
      <header style={{ marginBottom: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div
            style={{
              fontFamily: "Geist Mono, ui-monospace, monospace",
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#8f8f8f",
            }}
          >
            Themes Explorer · {taxonomyView.taxonomy_version}
          </div>
          <EvidenceBadge kind="PROTOTYPE" compact />
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
          Theme browser
        </h1>
        <p style={{ margin: 0, color: "#686e73", fontSize: 13, maxWidth: 720 }}>
          Static analyst-defined themes for cross-sector pattern exploration. Aggregate metrics use
          the current snapshot, while the membership lens is not an authoritative taxonomy. Multiple
          memberships are allowed and never double-counted across themes.
        </p>
        <div style={{ marginTop: 10 }}>
          <span
            style={{
              display: "inline-block",
              fontFamily: "Geist Mono, ui-monospace, monospace",
              fontSize: 10,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              padding: "3px 8px",
              borderRadius: 3,
              border: "1px solid #dfe2e1",
              color: "#7a5010",
              background: "#fff",
            }}
          >
            Source kind · {formatEnumLabel(taxonomyView.source_kind)}
          </span>
          <Link
            to="/maps/themes"
            style={{
              marginLeft: 8,
              display: "inline-block",
              fontFamily: "Geist Mono, ui-monospace, monospace",
              fontSize: 10,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              padding: "3px 8px",
              borderRadius: 3,
              border: "1px solid #dfe2e1",
              color: "#202325",
              background: "#fff",
              textDecoration: "none",
            }}
          >
            Map view ↗
          </Link>
        </div>
      </header>

      <div
        className="themes-browser-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "320px 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        <aside
          style={{
            border: "1px solid #dfe2e1",
            borderRadius: 6,
            background: "#fff",
            overflow: "hidden",
          }}
        >
          <div style={{ padding: "10px 12px", borderBottom: "1px solid #dfe2e1" }}>
            <input
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter themes…"
              aria-label="Filter themes by name"
              style={{
                width: "100%",
                padding: "6px 10px",
                border: "1px solid #dfe2e1",
                borderRadius: 4,
                background: "#fff",
                fontFamily: "Geist Mono, ui-monospace, monospace",
                fontSize: 12,
                boxSizing: "border-box",
              }}
            />
            <div style={{ marginTop: 8, fontSize: 10, color: "#8f8f8f" }}>
              {filteredGroups.length} of {groups.length} themes
            </div>
          </div>
          <ul
            role="listbox"
            aria-label="Theme list"
            style={{ listStyle: "none", margin: 0, padding: 0, maxHeight: 520, overflowY: "auto" }}
          >
            {filteredGroups.map((g) => {
              const isSelected = g.taxonomy_group_id === selected?.taxonomy_group_id;
              return (
                <li
                  key={g.taxonomy_group_id}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => setSelectedId(g.taxonomy_group_id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedId(g.taxonomy_group_id);
                    }
                  }}
                  tabIndex={0}
                  style={{
                    padding: "10px 12px",
                    borderBottom: "1px solid #ececec",
                    cursor: "pointer",
                    background: isSelected ? "#f4f3ed" : "transparent",
                    borderLeft: isSelected ? "3px solid #202325" : "3px solid transparent",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, color: "#202325", fontWeight: 500 }}>
                      {g.taxonomy_group_name}
                    </div>
                    <div style={{ fontSize: 10, color: "#8f8f8f", marginTop: 2 }}>
                      {g.eligible_constituent_count} / {g.constituent_count} eligible
                    </div>
                  </div>
                  <LeadershipChip state={asLeadership(g.leadership_state)} small />
                </li>
              );
            })}
          </ul>
        </aside>

        <div
          style={{
            border: "1px solid #dfe2e1",
            borderRadius: 6,
            background: "#fff",
            padding: 22,
          }}
        >
          {selected ? (
            <>
              <header style={{ marginBottom: 16 }}>
                <h2
                  style={{
                    margin: 0,
                    fontSize: 20,
                    letterSpacing: "-.02em",
                    fontWeight: 500,
                    color: "#202325",
                  }}
                >
                  {selected.taxonomy_group_name}
                </h2>
                <div
                  style={{
                    marginTop: 6,
                    fontFamily: "Geist Mono, ui-monospace, monospace",
                    fontSize: 10,
                    color: "#8f8f8f",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                  }}
                >
                  ID · {selected.taxonomy_group_id}
                </div>
              </header>

              <div
                className="themes-detail-metrics"
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                  gap: 12,
                  marginBottom: 18,
                }}
              >
                <Metric label="20D Excess" value={fmtSignedPct(selected.excess_return_20d)} color={signColor(selected.excess_return_20d)} />
                <Metric label="60D Excess" value={fmtSignedPct(selected.excess_return_60d)} color={signColor(selected.excess_return_60d)} />
                <Metric
                  label="Breadth"
                  value={selected.breadth_outperforming === null || selected.breadth_outperforming === undefined ? "—" : `${selected.breadth_outperforming.toFixed(1)}%`}
                />
                <Metric label="Δ Breadth" value={fmtSignedPct(selected.breadth_delta)} color={signColor(selected.breadth_delta)} />
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 12,
                  flexWrap: "wrap",
                  alignItems: "center",
                  padding: "10px 0",
                  borderTop: "1px solid #ececec",
                  borderBottom: "1px solid #ececec",
                  marginBottom: 16,
                }}
              >
                <span style={{ fontSize: 11, color: "#686e73" }}>Leadership</span>
                <LeadershipChip state={asLeadership(selected.leadership_state)} small />
                <span style={{ fontSize: 11, color: "#686e73" }}>Diffusion</span>
                <DiffusionChip state={asDiffusion(selected.diffusion_state)} small />
                <span style={{ fontSize: 11, color: "#686e73" }}>Data</span>
                <DataStatusChip status={asDataStatus(selected.data_quality)} />
                <span style={{ fontSize: 11, color: "#686e73" }}>Top-3</span>
                <span
                  style={{
                    fontFamily: "Geist Mono, ui-monospace, monospace",
                    fontSize: 11,
                    color: "#202325",
                  }}
                >
                  {selected.concentration_top3 === null ? "—" : `${(selected.concentration_top3 * 100).toFixed(0)}%`}
                </span>
              </div>

              <div style={{ marginBottom: 14 }}>
                <div
                  style={{
                    fontFamily: "Geist Mono, ui-monospace, monospace",
                    fontSize: 10,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "#8f8f8f",
                    marginBottom: 6,
                  }}
                >
                  Coverage
                </div>
                <div style={{ fontSize: 12, color: "#202325", lineHeight: 1.6 }}>
                  {selected.eligible_constituent_count} eligible constituents out of {selected.constituent_count}
                  {" "}({selected.coverage_pct.toFixed(0)}% mapped).{" "}
                  {selected.off_scale ? (
                    <span style={{ color: "#7a5010" }}>
                      Group is off-scale — value appears outside the standard map axis.
                    </span>
                  ) : null}
                </div>
              </div>

              {selected.membership_kind_breakdown ? (
                <div style={{ marginBottom: 14 }}>
                  <div
                    style={{
                      fontFamily: "Geist Mono, ui-monospace, monospace",
                      fontSize: 10,
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                      color: "#8f8f8f",
                      marginBottom: 6,
                    }}
                  >
                    Membership breakdown
                  </div>
                  <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                    {Object.entries(selected.membership_kind_breakdown).map(([k, v]) => (
                      <li
                        key={k}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          padding: "4px 0",
                          borderBottom: "1px dotted #ececec",
                          fontSize: 12,
                          color: "#202325",
                        }}
                      >
                        <span>{formatEnumLabel(k)}</span>
                        <span
                          style={{
                            fontFamily: "Geist Mono, ui-monospace, monospace",
                            color: "#5a5a5a",
                          }}
                        >
                          {v}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {selected.sample_foreign_flow_idr !== null && selected.sample_foreign_flow_idr !== undefined ? (
                <div
                  style={{
                    padding: "10px 12px",
                    background: "#faf9f6",
                    border: "1px solid #ececec",
                    borderRadius: 4,
                    fontSize: 11,
                    color: "#5a5a5a",
                    lineHeight: 1.55,
                  }}
                >
                  <strong style={{ color: "#202325" }}>Foreign-flow sample:</strong>{" "}
                  {formatEnumLabel(selected.sample_foreign_flow_direction)} ({selected.sample_foreign_flow_idr.toLocaleString("id-ID")} IDR).
                  Sample is bounded to published top-buy / top-sell lists and does not represent
                  full market totals.
                </div>
              ) : null}
            </>
          ) : (
            <EmptyState
              label="Theme detail"
              title="Select a theme"
              body="Pick a theme from the list on the left to see its coverage, state, and analytical breakdown."
            />
          )}
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div
      style={{
        border: "1px solid #ececec",
        borderRadius: 4,
        padding: "8px 10px",
        background: "#faf9f6",
      }}
    >
      <div
        style={{
          fontFamily: "Geist Mono, ui-monospace, monospace",
          fontSize: 9,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "#8f8f8f",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "Geist Mono, ui-monospace, monospace",
          fontSize: 16,
          fontWeight: 500,
          color: color ?? "#202325",
        }}
      >
        {value}
      </div>
    </div>
  );
}
