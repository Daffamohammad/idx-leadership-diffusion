"""Build a real Sectors-native market snapshot.

Drives the full pipeline (eligibility → features → groups →
leadership → diffusion → concentration → transitions → evidence)
using the live SectorsProvider.

Usage:

  python -m scripts.build_market_snapshot --as-of 2026-08-20 --allow-live

By default the Sectors client refuses to make live HTTP calls
(`allow_live=False`); `--allow-live` is required.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.aggregation.groups import build_group_snapshots, rank_groups
from idx_leadership.data.manifests import write_manifest
from idx_leadership.data.quality import assess_quality
from idx_leadership.data.snapshots import SnapshotReader, SnapshotWriter
from idx_leadership.evidence.builder import build_evidence_table
from idx_leadership.features.relative_strength import compute_excess_returns
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.providers.market_universe import EligibilityConfig, build_market_universe
from idx_leadership.signals.change_digest import build_change_digest
from idx_leadership.signals.transitions import build_transition_events
from idx_leadership.utils import data_root, get_logger, load_yaml
from idx_leadership.utils.errors import ProviderError

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_market_snapshot")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--config", default="config/providers.yaml")
    parser.add_argument("--universe", default="config/universe.yaml")
    parser.add_argument("--methodology", default="config/methodology.yaml")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument(
        "--min-history-days", type=int, default=60,
        help="Eligibility filter: minimum days of price history.",
    )
    parser.add_argument(
        "--stale-trading-days", type=int, default=30,
        help="Eligibility filter: stale-trading threshold in days.",
    )
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    out_dir = Path(args.out_dir) if args.out_dir else (data_root() / "snapshots" / "sectors" / as_of.isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    methodology = load_yaml(args.methodology)
    horizons = {
        "5d": int(methodology.get("horizons", {}).get("short", 5)),
        "20d": int(methodology.get("horizons", {}).get("primary", 20)),
        "60d": int(methodology.get("horizons", {}).get("medium", 60)),
    }
    diffusion_cfg = methodology.get("diffusion", {})
    concentration_cfg = methodology.get("concentration", {})
    method_version = str(methodology.get("method_version", "methodology-v1"))
    feature_version = str(methodology.get("feature_version", "features-v1"))

    provider = build_provider_from_config(args.config, preferred="sectors", allow_live=args.allow_live)
    cfg = EligibilityConfig(
        lookback_history_days=args.min_history_days,
        stale_trading_days=args.stale_trading_days,
        min_history_days=args.min_history_days,
    )
    try:
        universe = build_market_universe(
            security_master_provider=provider,
            cross_section_provider=provider,
            event_provider=provider,
            as_of=as_of,
            config=cfg,
        )
    except ProviderError as e:
        print(f"BUILD_BLOCKED provider_error={e}", file=sys.stderr)
        return 2

    universe.to_csv(out_dir / "universe.csv", index=False)
    eligible = universe[universe["eligible"]]
    print(f"universe total={len(universe)} eligible={len(eligible)} excluded={len(universe) - len(eligible)}")

    # Current cross-section is used for coverage and the durable close.csv.
    cs = provider.get_full_universe_close(as_of)
    if cs.empty:
        print("BUILD_BLOCKED empty_cross_section", file=sys.stderr)
        return 2
    cs.to_csv(out_dir / "close.csv", index=False)

    # Returns need a history window, not just the as-of cross-section.
    # The Sectors provider reconstructs this from daily close cross-sections.
    history_start = (
        pd.Timestamp(as_of) - pd.Timedelta(days=int(max(horizons.values()) * 1.6))
    ).date()
    history = provider.get_price_history(
        eligible["ticker"].tolist(), start=history_start, end=as_of
    )
    ihsg = provider.get_benchmark_history(
        "IHSG", start=history_start, end=as_of
    )
    if ihsg.empty:
        # Keep the failure explicit. A one-row proxy would silently make all
        # 5/20/60D excess-return features unavailable.
        print("BUILD_BLOCKED empty_ihsg_history", file=sys.stderr)
        return 2
    ihsg.to_csv(out_dir / "ihsg.csv", index=False)

    # Features + groups
    features = compute_excess_returns(
        history, ihsg, horizons=horizons, as_of=as_of
    )
    if features.empty:
        print("BUILD_BLOCKED no_features", file=sys.stderr)
        return 2
    features = features.merge(
        universe[["ticker", "sector", "subsector", "industry", "sub_industry"]],
        on="ticker", how="left",
    )
    features.to_csv(out_dir / "features.csv", index=False)

    snapshots = build_group_snapshots(
        features=features,
        taxonomy=universe.rename(columns={"sector": "group_id"})[["ticker", "group_id"]],
        snapshot_date=as_of,
        prices=history,
        horizons=horizons,
        min_constituents=int(methodology.get("groups", {}).get("minimum_constituents", 4)),
        min_coverage_pct=float(methodology.get("groups", {}).get("minimum_coverage_pct", 60.0)),
        broadening_threshold_pp=float(methodology.get("breadth", {}).get("broadening_threshold_pp", 10.0)),
        narrowing_threshold_pp=float(methodology.get("breadth", {}).get("narrowing_threshold_pp", -10.0)),
        acceleration_threshold_pp=float(methodology.get("leadership", {}).get("acceleration_threshold_pp", 1.0)),
        excess_return_improving=float(methodology.get("leadership", {}).get("excess_return_improving", 0.0)),
        excess_return_leading=float(methodology.get("leadership", {}).get("excess_return_leading", 0.0)),
        concentration_horizon=int(horizons.get("20d", 20)),
        method_version=method_version,
        feature_version=feature_version,
        diffusion_mode=str(diffusion_cfg.get("mode", "legacy")),
        diffusion_constituent_fraction=float(
            diffusion_cfg.get("constituent_floor", {}).get("fraction", 0.10)
        ),
        diffusion_minimum_constituents=int(
            diffusion_cfg.get("constituent_floor", {}).get("minimum", 2)
        ),
        concentration_mode=str(concentration_cfg.get("mode", "absolute_move")),
    )
    snapshots = rank_groups(snapshots)
    evidence = build_evidence_table(snapshots)

    # Compare with the previous snapshot for transitions
    reader = SnapshotReader(root=data_root() / "snapshots" / "sectors")
    prev_by_group: dict[str, Any] = {}
    if reader.list_snapshots():
        prev = reader.list_snapshots()[-1]
        try:
            prev_data = reader.load(prev.name)
            prev_groups = prev_data.get("groups", pd.DataFrame())
            for _, row in prev_groups.iterrows():
                from idx_leadership.models import (
                    ConcentrationMetrics,
                    DiffusionState,
                    GroupSnapshot,
                    LeadershipState,
                    DiffusionStateV2,
                )
                raw_v2 = row.get("diffusion_state_v2")
                diffusion_v2 = None
                if pd.notna(raw_v2):
                    try:
                        diffusion_v2 = DiffusionStateV2(raw_v2)
                    except (TypeError, ValueError):
                        diffusion_v2 = None
                prev_by_group[row["group_id"]] = GroupSnapshot(
                    snapshot_date=row["snapshot_date"],
                    group_id=row["group_id"],
                    leadership_state=LeadershipState(row.get("leadership_state", "UNCONFIRMED")),
                    diffusion_state=DiffusionState(row.get("diffusion_state", "UNCONFIRMED")),
                    diffusion_state_v2=diffusion_v2,
                    breadth_outperforming=row.get("breadth_outperforming"),
                    breadth_delta=row.get("breadth_delta"),
                    relative_strength_level=row.get("group_excess_return"),
                    concentration=ConcentrationMetrics(),
                    leadership_rank=row.get("leadership_rank"),
                )
        except Exception:  # noqa: BLE001
            pass

    transitions = build_transition_events(current=snapshots, previous_by_group=prev_by_group)
    digest = build_change_digest(
        transitions,
        as_of=as_of.isoformat(),
        previous=str(prev_by_group[next(iter(prev_by_group))].snapshot_date) if prev_by_group else None,
    )

    # Quality
    quality = assess_quality(
        requested_tickers=universe["ticker"].tolist(),
        prices=cs,
        benchmark=ihsg,
        today=as_of,
    )

    # Persist (atomic)
    writer = SnapshotWriter(root=data_root() / "snapshots" / "sectors")
    sid = f"sectors_{as_of.isoformat()}"
    target = writer.write(
        snapshot_id=sid,
        as_of=as_of,
        provider="sectors",
        universe_version="prototype-v1",
        taxonomy_version="sectors-v1",
        method_version=method_version,
        feature_version=feature_version,
        coverage_status=quality.status,
        coverage_pct=quality.coverage_pct,
        prices=cs,
        benchmark=ihsg,
        security_master=provider.get_security_master(),
        features=features,
        groups=_snapshots_to_df(snapshots),
        transitions=_transitions_to_df(transitions),
        notes=";".join(quality.issues) if quality.issues else None,
    )
    (target / "change_digest.json").write_text(json.dumps(digest.to_dict(), default=str, indent=2), encoding="utf-8")
    (target / "quality.json").write_text(json.dumps(quality.to_dict(), default=str, indent=2), encoding="utf-8")
    (target / "evidence.json").write_text(
        json.dumps([e.model_dump(mode="json") for e in evidence], default=str, indent=2),
        encoding="utf-8",
    )

    # Markdown report
    lines: list[str] = []
    lines.append(f"# Market Snapshot — {as_of.isoformat()}")
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- candidate securities: {len(universe)}")
    lines.append(f"- eligible: {len(eligible)} ({len(eligible) / max(1, len(universe)) * 100:.1f}%)")
    lines.append(f"- excluded: {len(universe) - len(eligible)}")
    excl = universe[~universe["eligible"]]["exclusion_reason"].value_counts().to_dict()
    if excl:
        lines.append(f"- exclusion reasons: {excl}")
    lines.append(f"- quality status: {quality.status.value}")
    lines.append("")
    lines.append("## Group States (top 10 by leadership rank)")
    lines.append("")
    lines.append("| group | leadership | diffusion | excess 20D | breadth_outperforming | leadership_rank |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for s in sorted(snapshots, key=lambda x: (x.leadership_rank if x.leadership_rank else 1_000_000))[:10]:
        lines.append(
            f"| {s.group_id} | {s.leadership_state.value} | {s.diffusion_state.value} | "
            f"{s.group_excess_return:.2f} | "
            f"{s.breadth_outperforming if s.breadth_outperforming is not None else '—'} | "
            f"{s.leadership_rank if s.leadership_rank else '—'} |"
        )
    lines.append("")
    lines.append("## Material transitions")
    lines.append("")
    for bucket in ("new_leaders", "lost_leadership", "upgrades", "downgrades", "broadening", "narrowing"):
        items = getattr(digest, bucket, [])
        if not items:
            continue
        lines.append(f"### {bucket}")
        for r in items:
            lines.append(f"- {r['group_id']} — {r.get('materiality_reason', '')}")
    if not any(getattr(digest, b) for b in ("new_leaders", "lost_leadership", "upgrades", "downgrades", "broadening", "narrowing")):
        lines.append("(none material)")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")

    # Aggregate manifest
    aggregated = reader.aggregate_manifest()
    write_manifest(aggregated, path=reader.root / "manifest.json")
    if provider.ledger:
        provider.ledger.flush()
    print(f"snapshot_complete dir={target}")
    return 0


def _snapshots_to_df(snapshots) -> "pd.DataFrame":
    import pandas as pd
    rows: list[dict] = []
    for s in snapshots:
        rows.append(
            {
                "snapshot_date": s.snapshot_date,
                "taxonomy_level": s.taxonomy_level,
                "group_id": s.group_id,
                "group_name": s.group_name,
                "constituent_count": s.constituent_count,
                "eligible_count": s.eligible_count,
                "missing_count": s.missing_count,
                "group_return_equal_weight": s.group_return_equal_weight,
                "leadership_state": s.leadership_state.value,
                "diffusion_state": s.diffusion_state.value,
                "diffusion_state_v2": (
                    s.diffusion_state_v2.value
                    if s.diffusion_state_v2 is not None
                    else None
                ),
                "group_excess_return": s.group_excess_return,
                "group_excess_return_5d": s.group_excess_return_5d,
                "group_excess_return_20d": s.group_excess_return_20d,
                "group_excess_return_60d": s.group_excess_return_60d,
                "breadth_positive": s.breadth_positive,
                "breadth_outperforming": s.breadth_outperforming,
                "breadth_delta": s.breadth_delta,
                "leadership_rank": s.leadership_rank,
                "change_rank": s.change_rank,
                "top1_contribution_share": s.concentration.top1_contribution_share,
                "top3_contribution_share": s.concentration.top3_contribution_share,
                "top5_contribution_share": s.concentration.top5_contribution_share,
                "top1_signed_share": s.concentration.top1_signed_share,
                "top3_signed_share": s.concentration.top3_signed_share,
                "hhi_contribution": s.concentration.hhi_contribution,
                "convention": s.concentration.convention,
                "method_version": s.method_version,
                "feature_version": s.feature_version,
            }
        )
    return pd.DataFrame(rows)


def _transitions_to_df(transitions) -> "pd.DataFrame":
    import pandas as pd
    rows: list[dict] = []
    for t in transitions:
        rows.append(
            {
                "current_date": t.current_date,
                "previous_date": t.previous_date,
                "taxonomy_level": t.taxonomy_level,
                "group_id": t.group_id,
                "previous_leadership_state": t.previous_leadership_state.value,
                "current_leadership_state": t.current_leadership_state.value,
                "previous_diffusion_state": t.previous_diffusion_state.value,
                "current_diffusion_state": t.current_diffusion_state.value,
                "leadership_transition": t.leadership_transition,
                "diffusion_transition": t.diffusion_transition,
                "previous_diffusion_state_v2": (
                    t.previous_diffusion_state_v2.value
                    if t.previous_diffusion_state_v2 is not None
                    else None
                ),
                "current_diffusion_state_v2": (
                    t.current_diffusion_state_v2.value
                    if t.current_diffusion_state_v2 is not None
                    else None
                ),
                "diffusion_transition_v2": t.diffusion_transition_v2,
                "breadth_delta": t.breadth_delta,
                "relative_strength_delta": t.relative_strength_delta,
                "rank_delta": t.rank_delta,
                "materiality_label": t.materiality_label.value,
                "materiality_reason": t.materiality_reason,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    sys.exit(main())
