import { useMemo } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useSnapshot } from "../data/SnapshotProvider";
import type { TaxonomyGroupAggregate, TaxonomyMembershipData, TaxonomyView } from "../data/snapshot";
import { LeadershipChip, DiffusionChip, DataStatusChip } from "../components/StatusChips";
import { EmptyState } from "../components/EmptyState";
import { formatDateLabel, formatEnumLabel } from "../data/format";
import { EvidenceBadge } from "../components/EvidenceModel";
import type { TaxonomyKind } from "../data/snapshot";

const TAXONOMY_BY_PARAM: Record<string, TaxonomyKind> = {
  THEMES: "THEMES",
  KONGLO: "KONGLO",
};

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

const headerLink: React.CSSProperties = {
  display: "inline-block",
  fontFamily: "Geist Mono, ui-monospace, monospace",
  fontSize: 10,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  padding: "4px 9px",
  borderRadius: 3,
  border: "1px solid #dfe2e1",
  color: "#202325",
  background: "#fff",
  textDecoration: "none",
  minHeight: 24,
  boxSizing: "border-box",
};

export default function ThemesExplorer() {
  const { data } = useSnapshot();
  const location = useLocation();
  const [params, setParams] = useSearchParams();

  // The path is canonical (/themes or /konglo); ?taxonomy= stays accepted so
  // older share links keep working and then normalize on the next interaction.
  const paramKind = TAXONOMY_BY_PARAM[(params.get("taxonomy") ?? "").toUpperCase()];
  const taxonomyKind: TaxonomyKind =
    paramKind ?? (location.pathname === "/konglo" ? "KONGLO" : "THEMES");
  const basePath = taxonomyKind === "KONGLO" ? "/konglo" : "/themes";
  const taxonomyId = taxonomyKind.toLowerCase();
  const taxonomyView: TaxonomyView | undefined = data?.taxonomyViews?.[taxonomyId];
  const groups = taxonomyView?.groups ?? [];
  const filter = params.get("filter") ?? "";
  const selectedGroupId = params.get("group");

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const membershipsByGroup = useMemo(() => {
    const map = new Map<string, TaxonomyMembershipData[]>();
    if (!taxonomyView) return map;
    for (const member of taxonomyView.memberships ?? []) {
      const list = map.get(member.taxonomy_group_id) ?? [];
      list.push(member);
      map.set(member.taxonomy_group_id, list);
    }
    return map;
  }, [taxonomyView]);

  // Group name/code search plus ticker search that reaches every membership,
  // including secondary memberships.
  const filteredGroups = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return groups;
    return groups.filter((g) => {
      if (g.taxonomy_group_name.toLowerCase().includes(f)) return true;
      if (g.taxonomy_group_id.toLowerCase().includes(f)) return true;
      return (membershipsByGroup.get(g.taxonomy_group_id) ?? []).some((m) =>
        m.ticker.toLowerCase().includes(f),
      );
    });
  }, [groups, filter, membershipsByGroup]);

  const selected: TaxonomyGroupAggregate | undefined = useMemo(() => {
    const fromMatch = groups.find((g) => g.taxonomy_group_id === selectedGroupId);
    if (fromMatch) return fromMatch;
    return filteredGroups[0] ?? groups[0];
  }, [groups, filteredGroups, selectedGroupId]);

  const selectedMembers = selected
    ? membershipsByGroup.get(selected.taxonomy_group_id) ?? []
    : [];

  const kindLabel = taxonomyKind === "KONGLO" ? "Konglo" : "Themes";
  const singularLabel = taxonomyKind === "KONGLO" ? "Konglo group" : "Theme";
  const catalogPath = `/groups?taxonomy=${taxonomyKind}`;
  const mapPath = taxonomyKind === "KONGLO" ? "/maps/konglo" : "/maps/themes";

  const relationshipRecorded = selectedMembers.filter((m) => m.relationship?.trim()).length;
  const sourcedMembers = selectedMembers.filter((m) => m.source?.startsWith("http")).length;
  const datedMembers = selectedMembers.filter((m) => m.source_as_of).length;
  const confidences = selectedMembers.map((m) => m.confidence).filter((c) => Number.isFinite(c));

  if (!taxonomyView || !groups.length) {
    return (
      <EmptyState
        label="Catalog"
        title={`${kindLabel} taxonomy not available`}
        body="The current snapshot does not expose this taxonomy view. Verify that the snapshot pipeline emitted its groups for this snapshot."
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
            {kindLabel} Catalog · {taxonomyView.taxonomy_version}
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
          {taxonomyKind === "KONGLO" ? "Verified corporate ecosystems" : "Theme browser"}
        </h1>
        <p style={{ margin: 0, color: "#686e73", fontSize: 13, maxWidth: 720 }}>
          {taxonomyKind === "KONGLO"
            ? "A deliberately narrow research lens: a group is included only when an official company source supports the relationship. It is not an official IDX classification, a complete beneficial-ownership graph, or a claim that every company is controlled in the same legal manner."
            : "Static analyst-defined themes for cross-sector pattern exploration. Aggregate metrics use the current snapshot, while the membership lens is not an authoritative taxonomy. Multiple memberships are allowed and never double-counted across themes."}
        </p>
        <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span style={headerLink}>Source kind · {formatEnumLabel(taxonomyView.source_kind)}</span>
          <span style={headerLink}>Policy · {formatEnumLabel(taxonomyView.membership_policy ?? "—")}</span>
          <span style={headerLink}>Source as of · {formatDateLabel(taxonomyView.source_as_of ?? null)}</span>
          <Link to={mapPath} style={headerLink}>Map view ↗</Link>
          <Link to={`/map?taxonomy=${taxonomyKind}&mode=groups`} style={headerLink}>Rotation ↗</Link>
          <Link to={catalogPath} style={headerLink}>Table / heatmap ↗</Link>
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
              onChange={(e) => setParam("filter", e.target.value)}
              placeholder={`Filter ${kindLabel.toLowerCase()} or ticker…`}
              aria-label={`Filter ${kindLabel} by group name, code or ticker`}
              style={{
                width: "100%",
                padding: "7px 10px",
                border: "1px solid #dfe2e1",
                borderRadius: 4,
                background: "#fff",
                fontFamily: "Geist Mono, ui-monospace, monospace",
                fontSize: 12,
                boxSizing: "border-box",
                minHeight: 34,
              }}
            />
            <div style={{ marginTop: 8, fontSize: 10, color: "#8f8f8f" }}>
              {filteredGroups.length} of {groups.length} groups
              {filter.trim() ? " match" : ""}
            </div>
          </div>
          <ul
            role="list"
            aria-label={`${kindLabel} list`}
            style={{ listStyle: "none", margin: 0, padding: 0, maxHeight: 520, overflowY: "auto" }}
          >
            {filteredGroups.length === 0 && (
              <li style={{ padding: "16px 12px", fontSize: 12, color: "#8f8f8f" }}>
                No group or ticker matches “{filter}”.
              </li>
            )}
            {filteredGroups.map((g) => {
              const isSelected = g.taxonomy_group_id === selected?.taxonomy_group_id;
              return (
                <li key={g.taxonomy_group_id} style={{ borderBottom: "1px solid #ececec" }}>
                  <Link
                    to={`${basePath}?group=${encodeURIComponent(g.taxonomy_group_id)}${filter ? `&filter=${encodeURIComponent(filter)}` : ""}`}
                    aria-current={isSelected ? "true" : undefined}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 10,
                      padding: "10px 12px",
                      textDecoration: "none",
                      background: isSelected ? "#f4f3ed" : "transparent",
                      borderLeft: isSelected ? "3px solid #202325" : "3px solid transparent",
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, color: "#202325", fontWeight: 500 }}>
                        {g.taxonomy_group_name}
                      </div>
                      <div style={{ fontSize: 10, color: "#8f8f8f", marginTop: 2 }}>
                        {g.taxonomy_group_id} · {g.eligible_constituent_count} / {g.constituent_count} eligible
                      </div>
                    </div>
                    <LeadershipChip state={asLeadership(g.leadership_state)} small />
                  </Link>
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
                <div className="eyebrow-muted" style={{ marginBottom: 6 }}>
                  Catalog summary · {formatSnapshotIdSafe(taxonomyView)}
                </div>
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
                  Code · {selected.taxonomy_group_id}
                </div>
                <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Link
                    to={`/explorer?taxonomy=${taxonomyKind}&group=${encodeURIComponent(selected.taxonomy_group_id)}`}
                    style={{
                      display: "inline-block",
                      padding: "9px 13px",
                      border: "1px solid #202325",
                      color: "#202325",
                      textDecoration: "none",
                      fontSize: 12,
                      borderRadius: 4,
                    }}
                  >
                    Open full detail →
                  </Link>
                  <Link
                    to={`/map?taxonomy=${taxonomyKind}&mode=groups`}
                    style={{ ...headerLink, padding: "9px 13px", fontSize: 11 }}
                  >
                    Rotation →
                  </Link>
                </div>
              </header>

              <div
                className="themes-detail-metrics"
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                  gap: 12,
                  marginBottom: 18,
                }}
              >
                <Metric label="20D excess" value={fmtSignedPct(selected.excess_return_20d)} color={signColor(selected.excess_return_20d)} />
                <Metric label="60D excess" value={fmtSignedPct(selected.excess_return_60d)} color={signColor(selected.excess_return_60d)} />
                <Metric
                  label="Breadth"
                  value={selected.breadth_outperforming === null || selected.breadth_outperforming === undefined ? "—" : `${selected.breadth_outperforming.toFixed(1)}%`}
                />
                <Metric label="Δ Breadth" value={fmtSignedPct(selected.breadth_delta)} color={signColor(selected.breadth_delta)} />
                <Metric
                  label="Concentration"
                  value={
                    selected.concentration_top3 === null ||
                    selected.concentration_top3 === undefined ||
                    !Number.isFinite(selected.concentration_top3)
                      ? "—"
                      : `${selected.concentration_top3.toFixed(0)}%`
                  }
                />
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
              </div>

              <div style={{ marginBottom: 14 }}>
                <div className="eyebrow-muted" style={{ marginBottom: 6 }}>Coverage</div>
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
                  <div className="eyebrow-muted" style={{ marginBottom: 6 }}>Membership breakdown</div>
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
                        <span style={{ fontFamily: "Geist Mono, monospace", color: "#5a5a5a" }}>{v}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div style={{ marginBottom: 14 }}>
                <div className="eyebrow-muted" style={{ marginBottom: 6 }}>Membership evidence</div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#4d4d4d", lineHeight: 1.7 }}>
                  <li>
                    {selectedMembers.length} membership record{selectedMembers.length === 1 ? "" : "s"} ·{" "}
                    {sourcedMembers} with an official source URL · {datedMembers} with a source date.
                  </li>
                  <li>
                    Confidence range{" "}
                    {confidences.length
                      ? `${Math.round(Math.min(...confidences) * 100)}–${Math.round(Math.max(...confidences) * 100)}%`
                      : "—"}{" "}
                    exactly as stored; it is never raised to strengthen a claim.
                  </li>
                  <li style={{ color: relationshipRecorded === 0 ? "#7a5010" : "#4d4d4d" }}>
                    {relationshipRecorded === 0
                      ? "Relationship subtype (control / subsidiary / affiliate / cross-shareholding / founder-director / ecosystem) is not recorded for any member in this snapshot, so every row stays Unresolved rather than being inferred from a job title or a similar name."
                      : `${relationshipRecorded} member${relationshipRecorded === 1 ? "" : "s"} carry a recorded relationship subtype; the rest stay Unresolved.`}
                  </li>
                </ul>
              </div>

              <div style={{ marginBottom: 14 }}>
                <div className="eyebrow-muted" style={{ marginBottom: 6 }}>Definition and version</div>
                <div style={{ fontSize: 12, color: "#4d4d4d", lineHeight: 1.7 }}>
                  <div>Version · {taxonomyView.taxonomy_version}</div>
                  <div>Membership policy · {formatEnumLabel(taxonomyView.membership_policy ?? "—")}</div>
                  <div>Source kind · {formatEnumLabel(taxonomyView.source_kind)}</div>
                  <div>Source as of · {formatDateLabel(taxonomyView.source_as_of ?? null)}</div>
                  <div style={{ color: "#686e73", marginTop: 6 }}>
                    Inclusion and exclusion criteria, per-member source URLs and dates are reviewable
                    on the full detail route; this panel is a catalog summary only.
                  </div>
                </div>
              </div>

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
              label="Group detail"
              title={`Select a ${singularLabel.toLowerCase()}`}
              body={`Pick a ${singularLabel.toLowerCase()} from the list on the left to see its coverage, state, and analytical breakdown.`}
            />
          )}
        </div>
      </div>
    </section>
  );
}

function formatSnapshotIdSafe(view: TaxonomyView): string {
  return `${view.taxonomy_id} · ${view.taxonomy_version}`;
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
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
    </div>
  );
}
