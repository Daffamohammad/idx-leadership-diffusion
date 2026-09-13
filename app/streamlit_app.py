"""Read-only Streamlit product harness for IDX Leadership Diffusion.

Run with::

    streamlit run app/streamlit_app.py

The app consumes only local snapshot artifacts and the deterministic demo
fixture. It cannot initiate Sectors or public-provider calls.
"""
from __future__ import annotations

import html
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from app.data_sources import SourceOption, available_sources, load_source
from app.view_models import (
    CONFIRMATION_DATA_GAP,
    DashboardView,
    GroupView,
    InvalidationRow,
    build_dashboard_view,
    data_gap_rollup,
    group_tape_rows,
    invalidation_rows_for,
    render_market_brief,
)


st.set_page_config(
    page_title="IDX Leadership Diffusion",
    page_icon="↗",
    layout="wide",
    initial_sidebar_state="expanded",
)


CSS = """
<style>
:root {
  --ink: #e8edf2;
  --muted: #8d9baa;
  --panel: #111a24;
  --panel-2: #172331;
  --line: rgba(203, 215, 226, .13);
  --amber: #f2b84b;
  --cyan: #4dd2c3;
  --red: #ef7f72;
  --green: #74d9c8;
  --paper: #f4f0e7;
}
.stApp { background: #09111a; color: var(--ink); }
[data-testid="stAppViewContainer"] > .main { background:
  linear-gradient(180deg, rgba(38, 58, 76, .23), transparent 18rem), #09111a; }
[data-testid="stHeader"] { background: rgba(9, 17, 26, .9); }
[data-testid="stSidebar"] { background: #0c151f; border-right: 1px solid var(--line); }
.block-container { max-width: 1480px; padding-top: 1.2rem; padding-bottom: 4rem; }
h1, h2, h3 { font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif !important; letter-spacing: -.025em; }
p, label, button, input, [data-testid="stMarkdownContainer"] { font-family: "Avenir Next", "IBM Plex Sans", sans-serif; }
.product-kicker { color: var(--amber); font-size: .72rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; }
.product-title { color: var(--paper); font: 600 clamp(1.8rem, 3.1vw, 3.2rem)/1.04 "Iowan Old Style", Georgia, serif; margin: .15rem 0 .35rem; }
.product-deck { color: var(--muted); max-width: 760px; font-size: .92rem; }
.meta-line { color: #7f8d9b; font-size: .75rem; letter-spacing: .025em; }
.mode-bar { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; margin-top:.5rem 0 .25rem; }
.mode-pill { display:inline-flex; align-items:center; gap:.4rem; border:1px solid rgba(242,184,75,.55); color:#ffd88d; background: rgba(242,184,75,.10); border-radius: 999px; padding:.42rem .85rem; font: 800 .76rem/1 "Avenir Next", sans-serif; letter-spacing:.13em; text-transform: uppercase; }
.mode-pill .pulse { width:.5rem; height:.5rem; border-radius:50%; background: var(--amber); }
.mode-pill.is-live { border-color: rgba(77,210,195,.65); color:#8de9df; background: rgba(77,210,195,.10); }
.mode-pill.is-live .pulse { background: var(--cyan); }
.mode-pill.is-fixture { border-color: rgba(125,137,148,.55); color:#c0cad4; background: rgba(125,137,148,.10); }
.mode-pill.is-fixture .pulse { background: #c0cad4; }
.mode-pill.is-prototype { border-color: rgba(239,127,114,.55); color:#f5b4ad; background: rgba(239,127,114,.10); }
.mode-pill.is-prototype .pulse { background: #ef7f72; }
.demo-warning { border: 1px solid rgba(242,184,75,.36); background: rgba(242,184,75,.08); padding: .72rem .9rem; color: #f8d89b; font-size: .78rem; margin: .8rem 0 1rem; }
.section-label { color: var(--amber); font-size: .68rem; font-weight: 800; letter-spacing: .17em; text-transform: uppercase; margin: 1.4rem 0 .38rem; display:flex; align-items:center; gap:.6rem; }
.section-label .num { background: rgba(242,184,75,.15); color: var(--amber); border-radius:999px; padding:.1rem .45rem; font-size:.62rem; letter-spacing:.04em; }
.market-read { background: linear-gradient(135deg, rgba(30,46,61,.97), rgba(13,24,35,.97)); border-top: 2px solid var(--amber); border-bottom: 1px solid var(--line); padding: 1.4rem 1.5rem 1.1rem; margin: .25rem 0 1.15rem; }
.market-read h2 { color: var(--paper); font-size: clamp(1.6rem, 2.6vw, 2.4rem); line-height: 1.1; margin: 0 0 .55rem; font-family: "Iowan Old Style", Georgia, serif; font-weight: 600; }
.market-read p { color: #c6d0d9; font-size: 1.02rem; line-height: 1.55; margin: 0 0 .85rem; max-width: 1080px; }
.metric-strip { display:grid; grid-template-columns: repeat(5, minmax(92px,1fr)); border:1px solid var(--line); border-left:0; }
.metric-cell { border-left:1px solid var(--line); padding:.65rem .8rem; background:rgba(7,15,23,.35); }
.metric-value { color:var(--paper); font:600 1.25rem/1.1 "Iowan Old Style", Georgia,serif; }
.metric-label { color:var(--muted); font-size:.64rem; letter-spacing:.09em; text-transform:uppercase; margin-top:.2rem; }
.panel-head { display:flex; justify-content:space-between; align-items:end; border-bottom:1px solid var(--line); padding-bottom:.55rem; margin-bottom:.65rem; }
.panel-title { color:var(--paper); font:600 1.12rem/1.2 "Iowan Old Style",Georgia,serif; }
.panel-note { color:var(--muted); font-size:.68rem; }
.shift-row { display:grid; grid-template-columns:2.25rem 1fr; gap:.7rem; padding:.78rem 0; border-bottom:1px solid var(--line); }
.shift-rank { color:var(--amber); font:700 .78rem/1.3 "Avenir Next",sans-serif; letter-spacing:.08em; }
.shift-name { color:var(--paper); font-weight:700; font-size:.79rem; letter-spacing:.045em; text-transform:uppercase; }
.shift-transition { color:#c7d0d9; font-size:.73rem; margin:.15rem 0; line-height:1.38; }
.shift-evidence { color:var(--muted); font-size:.69rem; line-height:1.35; }
.contradiction-row { display:grid; grid-template-columns:2.25rem auto 1fr; gap:.7rem; padding:.7rem 0; border-bottom:1px solid var(--line); align-items:start; }
.contradiction-rank { color:var(--red); font:700 .78rem/1.3 "Avenir Next",sans-serif; letter-spacing:.08em; }
.contradiction-sev { font:700 .66rem/1 "Avenir Next", sans-serif; letter-spacing:.1em; text-transform:uppercase; padding:.18rem .4rem; border-radius:3px; }
.sev-critical { background: rgba(239,127,114,.18); color:#f5b4ad; border:1px solid rgba(239,127,114,.45); }
.sev-warning { background: rgba(241,189,104,.15); color:#f1bd68; border:1px solid rgba(241,189,104,.4); }
.contradiction-name { color:var(--paper); font-weight:700; font-size:.79rem; letter-spacing:.045em; text-transform:uppercase; }
.contradiction-body { color:#c7d0d9; font-size:.75rem; line-height:1.4; margin-top:.15rem; }
.contradiction-meta { color:var(--muted); font-size:.68rem; margin-top:.15rem; }
.invalidation-card { background: var(--panel); border:1px solid var(--line); border-left:3px solid var(--red); padding:1rem 1.1rem; margin-top:.75rem; }
.invalidation-card h4 { color: var(--paper); font-family: "Iowan Old Style", Georgia, serif; font-size:1rem; margin: 0 0 .35rem; }
.invalidation-intro { color:#c6d0d9; font-size:.85rem; margin-bottom:.55rem; }
.invalidation-row { border-top:1px solid var(--line); padding:.45rem 0; font-size:.75rem; }
.invalidation-row .label { color: var(--amber); font-weight:700; }
.invalidation-row .threshold { color: var(--muted); font-family: "Avenir Next", "IBM Plex Mono", monospace; font-size:.7rem; }
.invalidation-row .rationale { color:#c6d0d9; }
.gap-table { display:grid; grid-template-columns: 11rem 1fr auto; row-gap:.4rem; column-gap:.9rem; align-items:center; font-size:.78rem; }
.gap-table .gap-label { color:var(--paper); font-weight:600; }
.gap-table .gap-status { font:700 .66rem/1 "Avenir Next", sans-serif; letter-spacing:.1em; text-transform:uppercase; padding:.25rem .55rem; border-radius:3px; }
.gap-table .gap-detail { color:#c6d0d9; }
.state-line { display:flex; flex-wrap:wrap; gap:.35rem; margin:.45rem 0 1rem; }
.state-chip { border:1px solid var(--line); background:var(--panel-2); color:#d8e0e7; padding:.28rem .48rem; font-size:.66rem; letter-spacing:.055em; }
.state-chip strong { color:var(--paper); }
.evidence-panel { background:var(--panel); border-left:2px solid var(--cyan); padding:1rem 1.05rem; }
.evidence-panel h3 { font-size:1rem; margin:0 0 .75rem; }
.evidence-row { display:grid; grid-template-columns: 7.5rem 1fr; gap:.55rem; border-top:1px solid var(--line); padding:.55rem 0; font-size:.72rem; }
.evidence-key { color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }
.evidence-val { color:#dce4eb; }
.gap { color:#f1c97e; }
.quality-grid { display:grid; grid-template-columns:repeat(3, minmax(170px,1fr)); gap:.55rem; margin:.75rem 0 1.25rem; }
.quality-item { background:var(--panel); border:1px solid var(--line); padding:.75rem .8rem; }
.quality-name { color:var(--muted); font-size:.66rem; text-transform:uppercase; letter-spacing:.075em; }
.quality-status { color:var(--paper); font-size:.78rem; font-weight:750; margin:.25rem 0; }
.quality-detail { color:#7f8d9b; font-size:.66rem; }
.status-ready { color:#74d9c8; } .status-gap,.status-stale,.status-failed { color:#f1bd68; }
[data-testid="stDataFrame"] { border:1px solid var(--line); }
[data-testid="stMetric"] { background:var(--panel); border-top:1px solid var(--line); padding:.65rem .75rem; }
[data-testid="stMetricLabel"] { color:var(--muted); }
[data-baseweb="tab-list"] { gap:1.1rem; border-bottom:1px solid var(--line); }
[data-baseweb="tab"] { height:2.8rem; padding:0 .25rem; color:#9aa7b4; font-size:.76rem; letter-spacing:.055em; text-transform:uppercase; }
[aria-selected="true"][data-baseweb="tab"] { color:var(--paper); }
@media (max-width: 1100px) { .metric-strip { grid-template-columns:repeat(3,1fr); } .quality-grid { grid-template-columns:repeat(2,1fr); } }
</style>
"""


@st.cache_data(show_spinner=False)
def _cached_view(source_id: str, kind: str, path_text: str, version: float) -> DashboardView:
    del version  # cache invalidation only
    option = SourceOption(source_id=source_id, label=source_id, kind=kind, path=Path(path_text))
    return build_dashboard_view(load_source(option))


def _source_version(option: SourceOption) -> float:
    path = option.path / "manifest.json" if option.path.is_dir() else option.path
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _load_selected_source() -> DashboardView:
    sources = available_sources()
    labels = {source.source_id: source.label for source in sources}
    selected_id = st.sidebar.selectbox(
        "Local data source",
        options=[source.source_id for source in sources],
        format_func=lambda source_id: labels[source_id],
        help="Only persisted local artifacts are available here. This control never calls a provider.",
    )
    option = next(source for source in sources if source.source_id == selected_id)
    st.sidebar.caption("Read-only local source · no live calls")
    return _cached_view(
        option.source_id,
        option.kind,
        str(option.path),
        _source_version(option),
    )


def _header(view: DashboardView) -> None:
    pill_class, label_text = _provider_pill(view.provider_mode)
    as_of = html.escape(view.as_of)
    market = html.escape(view.market_date or "UNAVAILABLE")
    benchmark = html.escape(view.benchmark_date or "UNAVAILABLE")
    st.markdown(
        f"""
        <div class="product-kicker">Indonesian Equities · Market Intelligence</div>
        <div class="product-title">IDX Leadership Diffusion</div>
        <div class="product-deck">Where leadership is moving—and whether participation beneath the index surface confirms, narrows, or contradicts the move.</div>
        <div class="mode-bar">
          <span class="mode-pill {pill_class}"><span class="pulse"></span>{html.escape(label_text)}</span>
          <span class="meta-line">As of {as_of} · market {market} · benchmark {benchmark}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if view.is_demo:
        st.markdown(
            '<div class="demo-warning"><strong>DEMO FIXTURE</strong> · Deterministic synthetic data for product demonstration. It is neither a public-market snapshot nor a Sectors API result.</div>',
            unsafe_allow_html=True,
        )


def _provider_pill(provider_mode: str) -> tuple[str, str]:
    """Map provider mode to (CSS modifier, human label)."""
    if provider_mode == "SECTORS_LIVE":
        return "is-live", "SECTORS LIVE"
    if provider_mode == "SECTORS_FIXTURE":
        return "is-fixture", "SECTORS FIXTURE"
    if provider_mode == "DEMO_FIXTURE":
        return "", "DEMO FIXTURE"
    return "is-prototype", "PUBLIC PROTOTYPE"


def _market_read(view: DashboardView) -> None:
    coverage = f"{view.eligible_count}/{view.total_count}" if view.total_count else "UNAVAILABLE"
    metrics = (
        ("Leading groups", view.leading_count),
        ("Improving groups", view.improving_count),
        ("Broadening groups", view.broadening_count),
        ("Narrowing groups", view.narrowing_count),
        ("Coverage", coverage),
    )
    metric_html = "".join(
        f'<div class="metric-cell"><div class="metric-value">{value}</div><div class="metric-label">{html.escape(label)}</div></div>'
        for label, value in metrics
    )
    bullets = "".join(
        f'<li>{html.escape(point)}</li>' for point in view.supporting_points
    )
    st.markdown(
        f"""
        <div class="section-label"><span class="num">01</span>Market Read</div>
        <div class="market-read">
          <h2>{html.escape(view.headline)}</h2>
          <p>{html.escape(view.market_read)}</p>
          <ul style="margin:0 0 0 1.1rem; padding:0; color:#c6d0d9; font-size:.9rem; line-height:1.55;">{bullets}</ul>
          <div class="metric-strip">{metric_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _leadership_map(view: DashboardView, selected_group_id: str, height: int = 470) -> None:
    group_rows = []
    history_rows = []
    for group in view.groups:
        group_rows.append(
            {
                "group_id": group.group_id,
                "Group": group.name,
                "20D excess return": group.excess_20d,
                "Breadth change": group.breadth_delta,
                "Breadth": group.breadth,
                "Leadership": group.leadership,
                "Diffusion": group.diffusion_detail,
                "Concentration": group.concentration_label,
                "Persistence": group.leadership_persistence,
                "Selected": group.group_id == selected_group_id,
            }
        )
        for point in group.history:
            if point.excess_20d is None or point.breadth_delta is None:
                continue
            history_rows.append(
                {
                    "group_id": group.group_id,
                    "Group": group.name,
                    "As of": point.as_of,
                    "20D excess return": point.excess_20d,
                    "Breadth change": point.breadth_delta,
                    "Selected": group.group_id == selected_group_id,
                }
            )
    frame = pd.DataFrame(group_rows)
    history = pd.DataFrame(history_rows)
    numeric_x = frame["20D excess return"].dropna().abs()
    numeric_y = frame["Breadth change"].dropna().abs()
    x_limit = max(6.0, float(numeric_x.max() if not numeric_x.empty else 6.0) * 1.28)
    y_limit = max(16.0, float(numeric_y.max() if not numeric_y.empty else 16.0) * 1.25)
    quadrants = pd.DataFrame(
        [
            {"x": 0, "x2": x_limit, "y": 0, "y2": y_limit, "fill": "#12382f", "label": "LEADERSHIP · BROADENING"},
            {"x": 0, "x2": x_limit, "y": -y_limit, "y2": 0, "fill": "#392b22", "label": "LEADERSHIP · NARROWING"},
            {"x": -x_limit, "x2": 0, "y": 0, "y2": y_limit, "fill": "#18313c", "label": "RECOVERY · BROADENING"},
            {"x": -x_limit, "x2": 0, "y": -y_limit, "y2": 0, "fill": "#332329", "label": "WEAKNESS · NARROWING"},
        ]
    )
    x_scale = alt.Scale(domain=[-x_limit, x_limit])
    y_scale = alt.Scale(domain=[-y_limit, y_limit])
    background = alt.Chart(quadrants).mark_rect(opacity=0.40).encode(
        x=alt.X("x:Q", scale=x_scale, title="20D excess return vs benchmark (%)"),
        x2="x2:Q",
        y=alt.Y("y:Q", scale=y_scale, title="Breadth change (percentage points)"),
        y2="y2:Q",
        color=alt.Color("fill:N", scale=None, legend=None),
    )
    labels = alt.Chart(quadrants).mark_text(
        align="left", baseline="top", dx=8, dy=8, fontSize=10, fontWeight=700, opacity=.55
    ).encode(x="x:Q", y="y2:Q", text="label:N", color=alt.value("#b5c1cb"))
    axes = (
        alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(color="#8da0b0", opacity=.38).encode(x="zero:Q")
        + alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(color="#8da0b0", opacity=.38).encode(y="zero:Q")
    )
    tails: alt.Chart | None = None
    if not history.empty:
        tails = alt.Chart(history).mark_line(point=False, strokeWidth=1.4).encode(
            x=alt.X("20D excess return:Q", scale=x_scale),
            y=alt.Y("Breadth change:Q", scale=y_scale),
            detail="group_id:N",
            order=alt.Order("As of:T"),
            color=alt.condition("datum.Selected", alt.value("#f2b84b"), alt.value("#718394")),
            opacity=alt.condition("datum.Selected", alt.value(.9), alt.value(.28)),
            tooltip=["Group:N", "As of:T", alt.Tooltip("20D excess return:Q", format="+.1f"), alt.Tooltip("Breadth change:Q", format="+.1f")],
        )
    click = alt.selection_point(fields=["group_id"], on="click", empty=True)
    points = alt.Chart(frame).mark_point(filled=True, stroke="#09111a", strokeWidth=1.5).encode(
        x=alt.X("20D excess return:Q", scale=x_scale),
        y=alt.Y("Breadth change:Q", scale=y_scale),
        color=alt.Color(
            "Leadership:N",
            scale=alt.Scale(
                domain=["LEADING", "IMPROVING", "WEAKENING", "LAGGING", "UNCONFIRMED"],
                range=["#f2b84b", "#4dd2c3", "#ef7f72", "#7d8994", "#566675"],
            ),
            legend=alt.Legend(orient="top", title=None, labelColor="#aeb9c3"),
        ),
        shape=alt.Shape(
            "Diffusion:N",
            scale=alt.Scale(
                domain=["BROADENING", "BROADENING_FIRM", "BROADENING_FRAGILE", "STABLE", "NARROWING", "NARROWING_FIRM", "NARROWING_FRAGILE", "UNCONFIRMED"],
                range=["circle", "circle", "circle", "square", "triangle-down", "triangle-down", "triangle-down", "diamond"],
            ),
            legend=None,
        ),
        size=alt.condition("datum.Selected", alt.value(310), alt.condition(click, alt.value(190), alt.value(95))),
        opacity=alt.condition(click, alt.value(1), alt.value(.35)),
        tooltip=[
            "Group:N", "Leadership:N", "Diffusion:N",
            alt.Tooltip("20D excess return:Q", format="+.1f"),
            alt.Tooltip("Breadth:Q", format=".1f"),
            alt.Tooltip("Breadth change:Q", format="+.1f"),
            "Concentration:N", "Persistence:Q",
        ],
    ).add_params(click)
    selected_label = alt.Chart(frame[frame["Selected"]]).mark_text(
        align="left", dx=11, dy=-10, fontSize=12, fontWeight=700, color="#f8e3b6"
    ).encode(
        x=alt.X("20D excess return:Q", scale=x_scale),
        y=alt.Y("Breadth change:Q", scale=y_scale),
        text="Group:N",
    )
    chart = background + labels + axes
    if tails is not None:
        chart += tails
    chart += points + selected_label
    chart = chart.properties(height=height).configure_view(stroke=None).configure_axis(
        grid=True,
        gridColor="#41505e",
        gridOpacity=.16,
        domainColor="#607180",
        tickColor="#607180",
        labelColor="#9ba9b5",
        titleColor="#bdc7cf",
        labelFont="Avenir Next",
        titleFont="Avenir Next",
    ).configure(background="#0d1721")
    st.altair_chart(chart, width="stretch")


def _material_shifts(view: DashboardView) -> None:
    st.markdown('<div class="panel-head"><div class="panel-title">Material Shifts</div><div class="panel-note">Rules-based · ranked</div></div>', unsafe_allow_html=True)
    if not view.material_shifts:
        st.info("No change met the configured materiality rules.")
        return
    rows = []
    for shift in view.material_shifts:
        transitions = " · ".join(
            item for item in (shift.leadership_transition, shift.diffusion_transition) if item
        ) or "Material evidence change"
        contradiction = f"<br><span style='color:#ef9e91'>Contradiction · {html.escape(shift.contradiction)}</span>" if shift.contradiction else ""
        rows.append(
            f"""
            <div class="shift-row">
              <div class="shift-rank">{shift.rank:02d}</div>
              <div>
                <div class="shift-name">{html.escape(shift.group_name)}</div>
                <div class="shift-transition">{html.escape(transitions)}</div>
                <div class="shift-evidence">{html.escape(shift.primary_evidence)} · {html.escape(shift.secondary_evidence)}{contradiction}</div>
              </div>
            </div>
            """
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def _tape(view: DashboardView) -> None:
    st.markdown(
        '<div class="section-label"><span class="num">03</span>Leadership Tape</div>',
        unsafe_allow_html=True,
    )
    frame = pd.DataFrame(group_tape_rows(view.groups))
    st.dataframe(
        frame,
        width="stretch",
        height=min(480, 38 + 35 * len(frame)),
        hide_index=True,
        column_config={
            "Rank": st.column_config.NumberColumn(format="%d", width="small"),
            "Group": st.column_config.TextColumn(width="medium"),
            "20D Excess": st.column_config.NumberColumn(format="%+.1f%%"),
            "60D Excess": st.column_config.NumberColumn(format="%+.1f%%"),
            "Breadth": st.column_config.NumberColumn(format="%.1f%%"),
            "Δ Breadth": st.column_config.NumberColumn(format="%+.1fpp"),
            "Persistence": st.column_config.NumberColumn(format="%d obs."),
        },
    )


def _contradictions_block(view: DashboardView) -> None:
    """Ranked contradictions block, mirroring the brief contract.

    Pure presentation; rows come from ``DashboardView.contradiction_rows``,
    which is itself derived from the structured :class:`ContradictionView`
    list on each :class:`GroupView`.
    """
    st.markdown(
        '<div class="section-label"><span class="num">02</span>Contradictions</div>'
        '<div class="panel-head"><div class="panel-title">Where evidence disagrees with itself</div>'
        f'<div class="panel-note">{"rows: " + str(len(view.contradiction_rows)) if view.contradiction_rows else "none flagged"}</div></div>',
        unsafe_allow_html=True,
    )
    if not view.contradiction_rows:
        st.info("No contradictions were flagged on the latest observation.")
        return
    for row in view.contradiction_rows[:5]:
        sev_class = "sev-critical" if row.severity == "CRITICAL" else "sev-warning"
        evidence = row.evidence or row.label
        detail_bits = [evidence]
        if row.breadth_delta is not None:
            detail_bits.append(f"breadth {row.breadth_delta:+.1f}pp")
        if row.breadth is not None:
            detail_bits.append(f"current breadth {row.breadth:.1f}%")
        st.markdown(
            f"""
            <div class="contradiction-row">
              <div class="contradiction-rank">{row.rank:02d}</div>
              <div><span class="contradiction-sev {sev_class}">{html.escape(row.severity)}</span></div>
              <div>
                <div class="contradiction-name">{html.escape(row.group_name)} · {html.escape(row.leadership)} / {html.escape(row.diffusion)}</div>
                <div class="contradiction-body">{html.escape(row.label)}</div>
                <div class="contradiction-meta">{' · '.join(html.escape(b) for b in detail_bits)}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _invalidation_block(group: GroupView) -> None:
    """Screen-state invalidation block, mirroring the brief contract."""
    rows = invalidation_rows_for(group)
    st.markdown(
        f"""
        <div class="invalidation-card">
          <h4>Screen Invalidation</h4>
          <div class="invalidation-intro">{html.escape(group.name)} would lose its current {html.escape(group.leadership)} / {html.escape(group.diffusion_detail)} interpretation if:</div>
        """,
        unsafe_allow_html=True,
    )
    for row in rows:
        threshold = (
            f'<div class="threshold">{html.escape(row.threshold)}</div>' if row.threshold else ""
        )
        st.markdown(
            f"""
            <div class="invalidation-row">
              <div class="label">{html.escape(row.condition)}</div>
              {threshold}
              <div class="rationale">{html.escape(row.rationale)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if not rows:
        st.markdown(
            '<div class="invalidation-row"><div class="rationale">No invalidation conditions available.</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _selected_group_control(view: DashboardView, key: str, default: str | None = None) -> str:
    ids = [group.group_id for group in view.groups]
    names = {group.group_id: group.name for group in view.groups}
    requested = default if default in ids else view.highlighted_group_id
    index = ids.index(requested) if requested in ids else 0
    return st.selectbox(
        "Selected group",
        options=ids,
        index=index,
        format_func=lambda group_id: names[group_id],
        key=key,
    )


def _history_frame(group: GroupView) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "As of": point.as_of,
                "20D Excess": point.excess_20d,
                "Breadth": point.breadth,
                "Breadth Change": point.breadth_delta,
            }
            for point in group.history
        ]
    )


def _relative_chart(group: GroupView, height: int = 230) -> None:
    frame = _history_frame(group)
    if frame.empty or frame["20D Excess"].dropna().empty:
        st.info("Relative-performance history is unavailable for this local snapshot.")
        return
    frame["As of"] = pd.to_datetime(frame["As of"])
    line = alt.Chart(frame).mark_line(point=True, color="#f2b84b", strokeWidth=2.3).encode(
        x=alt.X("As of:T", title=None),
        y=alt.Y("20D Excess:Q", title="20D excess (%)"),
        tooltip=[alt.Tooltip("As of:T"), alt.Tooltip("20D Excess:Q", format="+.1f")],
    )
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#91a1ae", opacity=.45).encode(y="y:Q")
    st.altair_chart(_chart_style((line + zero).properties(height=height)), width="stretch")


def _breadth_chart(group: GroupView, height: int = 230) -> None:
    frame = _history_frame(group)
    if frame.empty or frame["Breadth"].dropna().empty:
        st.info("Breadth history is unavailable for this local snapshot.")
        return
    frame["As of"] = pd.to_datetime(frame["As of"])
    chart = alt.Chart(frame).mark_area(
        line={"color": "#4dd2c3", "strokeWidth": 2},
        color=alt.Gradient(
            gradient="linear",
            stops=[alt.GradientStop(color="#4dd2c3", offset=0), alt.GradientStop(color="#102732", offset=1)],
            x1=1, x2=1, y1=0, y2=1,
        ),
        opacity=.7,
    ).encode(
        x=alt.X("As of:T", title=None),
        y=alt.Y("Breadth:Q", title="Outperforming breadth (%)", scale=alt.Scale(domain=[0, 100])),
        tooltip=[alt.Tooltip("As of:T"), alt.Tooltip("Breadth:Q", format=".1f"), alt.Tooltip("Breadth Change:Q", format="+.1f")],
    ).properties(height=height)
    st.altair_chart(_chart_style(chart), width="stretch")


def _constituent_chart(group: GroupView, height: int = 235) -> None:
    rows = [asdict(row) for row in group.constituents if row.excess_20d is not None]
    if not rows:
        st.info("Constituent-level evidence is unavailable in this snapshot.")
        return
    frame = pd.DataFrame(rows).head(12)
    chart = alt.Chart(frame).mark_bar().encode(
        x=alt.X("excess_20d:Q", title="20D excess return (%)"),
        y=alt.Y("ticker:N", sort="-x", title=None),
        color=alt.condition("datum.excess_20d >= 0", alt.value("#4dd2c3"), alt.value("#ef7f72")),
        tooltip=["ticker:N", "company_name:N", alt.Tooltip("excess_5d:Q", format="+.1f"), alt.Tooltip("excess_20d:Q", format="+.1f"), alt.Tooltip("excess_60d:Q", format="+.1f")],
    ).properties(height=height)
    st.altair_chart(_chart_style(chart), width="stretch")


def _chart_style(chart: alt.Chart) -> alt.Chart:
    return chart.configure_view(stroke=None).configure_axis(
        grid=True, gridColor="#41505e", gridOpacity=.16, domainColor="#607180",
        tickColor="#607180", labelColor="#9ba9b5", titleColor="#bdc7cf",
        labelFont="Avenir Next", titleFont="Avenir Next",
    ).configure(background="#0d1721")


def _evidence_panel(group: GroupView) -> None:
    if group.contradictions:
        cn = group.contradictions[0]
        contradiction = f"{cn.label} — {cn.evidence or ''}".rstrip(" —")
    else:
        contradiction = "No configured contradiction triggered."
    if group.invalidation:
        inv = group.invalidation[0]
        invalidation = inv.condition
    else:
        invalidation = "No invalidation condition available."
    rows = (
        ("Leadership", f"{group.leadership} · {group.leadership_persistence} observations", ""),
        ("Diffusion", f"{group.diffusion_detail} · Δ breadth {_format_signed(group.breadth_delta, 'pp')}", ""),
        ("Concentration", f"{group.concentration_label} · top-1 {_format_share(group.top1)} · top-3 {_format_share(group.top3)}", ""),
        ("Persistence", f"Leadership {group.leadership_persistence} · diffusion {group.diffusion_persistence}", ""),
        ("Fundamentals", group.fundamentals, "gap"),
        ("Foreign Flow", group.foreign_flow, "gap"),
        ("Contradiction", contradiction, ""),
        ("Invalidation", invalidation, ""),
    )
    row_html = "".join(
        f'<div class="evidence-row"><div class="evidence-key">{html.escape(key)}</div><div class="evidence-val {klass}">{html.escape(value)}</div></div>'
        for key, value, klass in rows
    )
    st.markdown(
        f'<div class="evidence-panel"><h3>Evidence Contract</h3>{row_html}</div>',
        unsafe_allow_html=True,
    )


def _under_surface(group: GroupView) -> None:
    st.markdown(
        '<div class="section-label"><span class="num">04</span>Under the Surface</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='panel-head'><div><div class='panel-title'>{html.escape(group.name)}</div><div class='panel-note'>{html.escape(group.interpretation)}</div></div><div class='panel-note'>Breadth {html.escape(_format_value(group.breadth, '%'))} · top-1 {html.escape(_format_share(group.top1))}</div></div>",
        unsafe_allow_html=True,
    )
    left, middle, right = st.columns([1.1, 1.1, .95], gap="large")
    with left:
        st.caption("Breadth trajectory")
        _breadth_chart(group)
    with middle:
        st.caption("Leaders / laggards · constituent 20D excess")
        _constituent_chart(group)
    with right:
        _evidence_panel(group)

    # Selected-group contradictions surface here too, mirroring the
    # brief contract's per-group structure.
    if group.contradictions:
        st.markdown("---")
        st.caption("Contradictions for this group")
        for cn in group.contradictions:
            sev_class = "sev-critical" if cn.severity == "CRITICAL" else "sev-warning"
            st.markdown(
                f"""
                <div class="contradiction-row" style="grid-template-columns: auto auto 1fr;">
                  <div><span class="contradiction-sev {sev_class}">{html.escape(cn.severity)}</span></div>
                  <div></div>
                  <div>
                    <div class="contradiction-body">{html.escape(cn.label)}</div>
                    <div class="contradiction-meta">{html.escape(cn.evidence or '')}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")
    _invalidation_block(group)


def overview(view: DashboardView) -> None:
    """The command-center viewport: Market Read → Map+Shifts → Contradictions → Tape → Under the Surface."""
    _market_read(view)

    # 02 — Map + Shifts (side by side) + Contradictions (below).
    selected_id = _selected_group_control(view, "overview_group", view.highlighted_group_id)
    map_col, shifts_col = st.columns([2.1, .9], gap="large")
    with map_col:
        st.markdown(
            '<div class="panel-head"><div class="panel-title">Leadership × Diffusion Map</div>'
            '<div class="panel-note">20D excess × breadth change · click a group to focus Under the Surface</div></div>',
            unsafe_allow_html=True,
        )
        _leadership_map(view, selected_id, height=485)
    with shifts_col:
        _material_shifts(view)
    _contradictions_block(view)

    # 03 — Leadership Tape.
    _tape(view)

    # 04 — Under the Surface (selected group).
    selected = view.group(selected_id)
    if selected:
        _under_surface(selected)


def leadership_map_page(view: DashboardView) -> None:
    st.markdown('<div class="section-label">Cross-sectional Map</div>', unsafe_allow_html=True)
    st.markdown("### Leadership and participation are separate dimensions")
    st.caption("The horizontal axis is benchmark-relative performance. The vertical axis is the change in participating constituents; neither is collapsed into a total score.")
    selected_id = _selected_group_control(view, "map_group", view.highlighted_group_id)
    _leadership_map(view, selected_id, height=620)
    selected = view.group(selected_id)
    if selected:
        st.markdown(
            '<div class="state-line">'
            f'<span class="state-chip">Leadership <strong>{html.escape(selected.leadership)}</strong></span>'
            f'<span class="state-chip">Diffusion <strong>{html.escape(selected.diffusion_detail)}</strong></span>'
            f'<span class="state-chip">Concentration <strong>{html.escape(selected.concentration_label)}</strong></span>'
            f'<span class="state-chip">Persistence <strong>{selected.leadership_persistence} obs.</strong></span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.text(selected.interpretation)


def group_explorer(view: DashboardView) -> None:
    selected_id = _selected_group_control(view, "explorer_group", view.highlighted_group_id)
    group = view.group(selected_id)
    if group is None:
        return
    taxonomy = "  /  ".join(group.taxonomy_path)
    st.markdown('<div class="section-label">Group Explorer</div>', unsafe_allow_html=True)
    st.caption(taxonomy)
    st.markdown(f"## {group.name}")
    st.markdown(
        '<div class="state-line">'
        f'<span class="state-chip">Leadership <strong>{html.escape(group.leadership)}</strong></span>'
        f'<span class="state-chip">Diffusion <strong>{html.escape(group.diffusion_detail)}</strong></span>'
        f'<span class="state-chip">Persistence <strong>{group.leadership_persistence} observations</strong></span>'
        f'<span class="state-chip">Coverage <strong>{group.eligible_count}/{group.total_count}</strong></span>'
        '</div>',
        unsafe_allow_html=True,
    )
    charts, evidence = st.columns([2.1, .9], gap="large")
    with charts:
        relative, breadth = st.columns(2, gap="medium")
        with relative:
            st.markdown('<div class="panel-title">Relative Performance</div>', unsafe_allow_html=True)
            _relative_chart(group, height=260)
        with breadth:
            st.markdown('<div class="panel-title">Breadth</div>', unsafe_allow_html=True)
            _breadth_chart(group, height=260)
        st.markdown('<div class="panel-title" style="margin-top:1.1rem">Constituents</div>', unsafe_allow_html=True)
        if group.constituents:
            frame = pd.DataFrame(
                [
                    {
                        "Ticker": item.ticker,
                        "Company": item.company_name,
                        "5D Excess": item.excess_5d,
                        "20D Excess": item.excess_20d,
                        "60D Excess": item.excess_60d,
                        "Participation": "OUTPERFORMING" if item.participating else "LAGGING",
                    }
                    for item in group.constituents
                ]
            )
            st.dataframe(
                frame,
                width="stretch",
                hide_index=True,
                column_config={
                    "5D Excess": st.column_config.NumberColumn(format="%+.1f%%"),
                    "20D Excess": st.column_config.NumberColumn(format="%+.1f%%"),
                    "60D Excess": st.column_config.NumberColumn(format="%+.1f%%"),
                },
            )
        else:
            st.info("Constituent rows are unavailable in this snapshot artifact.")
    with evidence:
        _evidence_panel(group)
        if group.contradictions:
            st.caption("All contradictions")
            for item in group.contradictions:
                st.warning(f"{item.label} — {item.evidence or ''}".rstrip(" —"))
        st.caption("Screen-state invalidation")
        for item in group.invalidation:
            threshold = f" ({item.threshold})" if item.threshold else ""
            st.text(f"- {item.condition}{threshold}")


def method_quality(view: DashboardView) -> None:
    st.markdown('<div class="section-label">Methodology & Data Quality</div>', unsafe_allow_html=True)
    st.markdown("### The display follows the active local configuration")
    st.caption("No formula is redefined in the UI. Values below are loaded from config/methodology.yaml and the selected snapshot manifest.")
    methodology = view.methodology
    horizons = methodology.get("horizons", {}) if isinstance(methodology, dict) else {}
    breadth = methodology.get("breadth", {}) if isinstance(methodology, dict) else {}
    diffusion = methodology.get("diffusion", {}) if isinstance(methodology, dict) else {}
    concentration = methodology.get("concentration", {}) if isinstance(methodology, dict) else {}
    manifest = view.manifest
    entry = (manifest.get("entries") or [{}])[-1] if isinstance(manifest, dict) else {}
    universe_version = entry.get("universe_version") or manifest.get("universe_version") or "UNAVAILABLE"
    taxonomy_version = entry.get("taxonomy_version") or manifest.get("taxonomy_version") or "UNAVAILABLE"
    method_version = methodology.get("method_version") or entry.get("method_version") or manifest.get("method_version") or "UNAVAILABLE"
    summary_rows = [
        {"Field": "Provider mode", "Value": view.provider_badge},
        {"Field": "Universe", "Value": str(universe_version)},
        {"Field": "Taxonomy", "Value": str(taxonomy_version)},
        {"Field": "Benchmark", "Value": f"snapshot benchmark · {view.benchmark_date or 'UNAVAILABLE'}"},
        {"Field": "Horizons", "Value": f"{horizons.get('short', '—')} / {horizons.get('primary', '—')} / {horizons.get('medium', '—')} trading days"},
        {"Field": "Breadth", "Value": "eligible constituents outperforming the benchmark at the primary horizon"},
        {"Field": "Diffusion", "Value": f"{diffusion.get('mode', 'UNAVAILABLE')} · ±{diffusion.get('broadening_threshold_pp', breadth.get('broadening_threshold_pp', '—'))}pp + constituent floor"},
        {"Field": "Concentration", "Value": f"{concentration.get('mode', 'UNAVAILABLE')} · top-1/top-3 + HHI reported separately"},
        {"Field": "Persistence", "Value": "consecutive observations in current state"},
        {"Field": "Versions", "Value": f"{method_version} · {methodology.get('feature_version', entry.get('feature_version', 'UNAVAILABLE'))}"},
    ]
    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)
    if view.provider_mode == "SECTORS_LIVE":
        live_rows = [
            {"Metric": "Security master", "Value": f"{view.coverage.get('security_master_total', '—')} discovered"},
            {"Metric": "Eligible universe", "Value": f"{view.coverage.get('eligible_securities', '—')} eligible"},
            {"Metric": "Price-history coverage", "Value": f"{view.coverage.get('price_history_coverage_pct', '—')}% usable"},
            {"Metric": "Taxonomy coverage", "Value": f"{view.coverage.get('taxonomy_coverage_pct', '—')}% complete"},
            {"Metric": "Provider provenance", "Value": str(view.provider_provenance.get('provider', 'Sectors'))},
        ]
        st.dataframe(pd.DataFrame(live_rows), width="stretch", hide_index=True)
        warnings = view.data_warnings.get("warnings", [])
        if isinstance(warnings, list) and warnings:
            st.warning(f"Live data warnings: {len(warnings)} persisted warning(s). See the selected snapshot artifacts for full diagnostics.")
    st.markdown('<div class="section-label">Per-layer Status</div>', unsafe_allow_html=True)
    quality_html = []
    for layer in view.quality_layers:
        status_class = "status-ready" if layer.status == "READY" else "status-gap"
        quality_html.append(
            f'<div class="quality-item"><div class="quality-name">{html.escape(layer.layer)}</div><div class="quality-status {status_class}">{html.escape(layer.status)}</div><div class="quality-detail">{html.escape(layer.detail)}</div></div>'
        )
    st.markdown(f'<div class="quality-grid">{"".join(quality_html)}</div>', unsafe_allow_html=True)
    st.markdown("### Known gaps")
    # The rollup derives from the structured DataGapView list on each
    # group, with the worst observed status per frozen category.  This
    # mirrors the brief contract "## Data Gaps" block.
    rollup = data_gap_rollup(view.groups)
    gap_html = "".join(
        f'<div class="gap-label">{html.escape(row["label"])}</div>'
        f'<div class="gap-detail">{html.escape(row["status"].replace("_", " ").title())}</div>'
        f'<div class="gap-status">{html.escape(row["status"])}</div>'
        for row in rollup
    )
    st.markdown(
        f"""
        <div class="quality-grid" style="grid-template-columns: 1fr;">
          <div class="quality-item" style="padding: 0;">
            <div class="gap-table" style="padding: .8rem .9rem;">
              {gap_html}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Categories are frozen in the brief contract (brief-v1).  "
        "Live Sectors data will flip DATA_GAP / NOT_INTEGRATED to READY "
        "for each category it covers; the rollup is derived, not asserted."
    )
    with st.expander("Active methodology configuration"):
        st.json(methodology)
    with st.expander("Selected snapshot manifest"):
        st.json(manifest)


def _sidebar(view: DashboardView) -> None:
    pill_class, label_text = _provider_pill(view.provider_mode)
    st.sidebar.markdown("### Research state")
    st.sidebar.markdown(
        f'<span class="mode-pill {pill_class}" style="margin-bottom:.5rem"><span class="pulse"></span>{html.escape(label_text)}</span>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"As of {view.as_of}")
    if view.is_demo:
        st.sidebar.warning("DEMO FIXTURE · synthetic, deterministic, not live")
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Integrity boundary**")
    st.sidebar.caption("The UI reads local artifacts only. Live credentials and provider clients are outside this process.")
    # The structured data-gap rollup is the authoritative per-category
    # summary.  Render it in the sidebar so the provenance detail is
    # one click away.
    rollup = data_gap_rollup(view.groups)
    with st.sidebar.expander("Data-gap rollup", expanded=False):
        for row in rollup:
            st.sidebar.caption(
                f"**{row['label']}** — `{row['status']}`"
            )
    brief = render_market_brief(view)
    st.sidebar.download_button(
        "Download market brief",
        data=brief,
        file_name=f"idx_market_brief_{view.as_of}_{view.provider_mode.lower()}.md",
        mime="text/markdown",
        width="stretch",
    )


def _format_signed(value: float | None, suffix: str) -> str:
    return "UNAVAILABLE" if value is None else f"{value:+.1f}{suffix}"


def _format_value(value: float | None, suffix: str) -> str:
    return "UNAVAILABLE" if value is None else f"{value:.1f}{suffix}"


def _format_share(value: float | None) -> str:
    return "UNDEFINED" if value is None else f"{value:.0%}"


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        view = _load_selected_source()
    except Exception as exc:  # visible artifact failure, never provider fallback
        st.error(f"Could not load the selected local artifact: {exc}")
        st.stop()
    _sidebar(view)
    _header(view)
    tabs = st.tabs(["Overview", "Leadership Map", "Group Explorer", "Methodology / Quality"])
    with tabs[0]:
        overview(view)
    with tabs[1]:
        leadership_map_page(view)
    with tabs[2]:
        group_explorer(view)
    with tabs[3]:
        method_quality(view)


if __name__ == "__main__":
    main()
