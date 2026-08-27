"""End-to-end pipeline orchestrator.

`build_snapshot` performs:

1. Pull prices + benchmark from a provider
2. Pull taxonomy
3. Compute per-security features
4. Aggregate to groups
5. Classify leadership and diffusion
6. Rank groups
7. Compare to prior snapshot (if any) → transitions
8. Write durable snapshot
9. Build and persist change digest

This is the single source of truth for producing a snapshot; the
scripts and the UI both call it.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .aggregation.groups import build_group_snapshots, rank_groups
from .data.manifests import write_manifest
from .data.comparability import assess_snapshot_comparability
from .data.quality import assess_quality
from .data.snapshots import SNAPSHOT_VERSION, SnapshotReader, SnapshotWriter
from .features.relative_strength import compute_excess_returns
from .analytics.persistence import compute_persistence
from .evidence.builder import build_group_evidence
from .intelligence import build_market_read, build_story_mode
from .models import ProviderMode
from .providers.base import MarketDataProvider
from .signals.change_digest import build_change_digest
from .signals.transitions import build_transition_events
from .utils import data_root, get_logger, load_yaml

def _none_if_nan(v):
    import math
    if v is None:
        return None
    try:
        if math.isnan(v):
            return None
    except (TypeError, ValueError):
        return v
    return v




def _none_if_nan_str(v):
    if v is None:
        return None
    if isinstance(v, float):
        import math
        if math.isnan(v):
            return None
    return v
def _none_if_nan_int(v):
    import math
    if v is None:
        return None
    try:
        if math.isnan(v):
            return None
    except (TypeError, ValueError):
        return v
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _diffusion_v2_or_none(v):
    from .models import DiffusionStateV2

    value = _none_if_nan_str(v)
    if value is None:
        return None
    try:
        return DiffusionStateV2(value)
    except (TypeError, ValueError):
        return None



from .utils.dates import asof_resolve, today_utc

_log = get_logger(__name__)


DEFAULT_HORIZONS = {"5d": 5, "20d": 20, "60d": 60}


def build_snapshot(
    provider: MarketDataProvider,
    *,
    as_of: Optional[date] = None,
    universe_path: str | Path = "config/universe.yaml",
    methodology_path: str | Path = "config/methodology.yaml",
    out_dir: Optional[Path] = None,
    snapshot_id: Optional[str] = None,
    provider_mode: ProviderMode | str | None = None,
) -> dict[str, Any]:
    """Run the end-to-end snapshot pipeline.

    Returns the loaded snapshot dict (with key 'change_digest').
    """
    universe_cfg = load_yaml(universe_path)
    meth = load_yaml(methodology_path)
    horizons = _resolve_horizons(meth)
    diffusion_cfg = meth.get("diffusion", {})
    concentration_cfg = meth.get("concentration", {})
    method_version = str(meth.get("method_version", "methodology-v1"))
    feature_version = str(meth.get("feature_version", "features-v1"))
    schema_version = str(meth.get("schema_version", "schemas-v1"))
    eligibility_version = str(meth.get("eligibility_version", "eligibility-v1"))
    leadership_version = str(meth.get("leadership_version", "leadership-v1"))
    diffusion_version = str(meth.get("diffusion_version", "diffusion-v2"))
    concentration_version = str(meth.get("concentration_version", "concentration-v3"))
    provider_name = (
        provider.name_enum()
        if hasattr(provider, "name_enum")
        else _safe_provider_name(provider)
    )
    resolved_provider_mode = _resolve_provider_mode(provider, provider_mode)
    benchmark_id = universe_cfg.get("benchmark", "^JKSE")
    requested = [row["ticker"] for row in universe_cfg.get("universe", [])]
    today = today_utc()
    as_of = as_of or today
    lookback_days = max(horizons.values()) + 10
    lookback = pd.Timedelta(days=int(lookback_days * 1.6))
    start_date = (pd.Timestamp(as_of) - lookback).date() if not isinstance(as_of, pd.Timestamp) else (as_of - lookback).date()

    prices = provider.get_price_history(requested, start=start_date, end=as_of)
    benchmark = provider.get_benchmark_history(benchmark_id, start=start_date, end=as_of)
    taxonomy = provider.get_group_taxonomy()

    # Filter to canonical columns; ensure all dates are date objects
    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    benchmark["date"] = pd.to_datetime(benchmark["date"]).dt.date

    # Quality report
    quality = assess_quality(
        requested_tickers=requested,
        prices=prices,
        benchmark=benchmark,
        today=today,
    )

    # Per-security features
    features = compute_excess_returns(
        prices,
        benchmark,
        horizons=horizons,
        as_of=as_of,
        security_price_col=str(meth.get("price_basis", "adjusted_close")),
        tolerance_days=int(meth.get("as_of_tolerance_days", 7)),
    )
    if features.empty:
        _log.warning("no_features_computed as_of=%s", as_of)
    # The aggregation layer merges taxonomy into features internally; do not pre-merge here.

    # Read only earlier, contract-compatible snapshots.  Directory order is
    # not a point-in-time contract and must never select a future snapshot.
    reader = SnapshotReader(root=out_dir)
    current_contract = {
        "snapshot_date": as_of.isoformat(),
        "as_of": as_of.isoformat(),
        "provider": provider_name.value,
        "provider_mode": resolved_provider_mode.value,
        "universe_version": str(universe_cfg.get("universe_version", "prototype-v1")),
        "taxonomy_version": str(universe_cfg.get("taxonomy_version", "prototype-v1")),
        "eligibility_version": eligibility_version,
        "method_version": method_version,
        "feature_version": feature_version,
        "leadership_version": leadership_version,
        "diffusion_version": diffusion_version,
        "concentration_version": concentration_version,
    }
    (
        previous_snapshots_by_group,
        history_by_group,
        comparison_audit,
        previous_date,
    ) = _load_compatible_history(reader, current_contract)

    # Build current group snapshots
    snapshots = build_group_snapshots(
        features=features,
        taxonomy=taxonomy,
        snapshot_date=as_of,
        prices=prices,
        horizons=horizons,
        min_constituents=int(meth.get("groups", {}).get("minimum_constituents", 4)),
        min_coverage_pct=float(meth.get("groups", {}).get("minimum_coverage_pct", 60.0)),
        previous_groups=list(previous_snapshots_by_group.values()),
        broadening_threshold_pp=float(
            diffusion_cfg.get(
                "broadening_threshold_pp",
                meth.get("breadth", {}).get("broadening_threshold_pp", 10.0),
            )
        ),
        narrowing_threshold_pp=float(
            diffusion_cfg.get(
                "narrowing_threshold_pp",
                meth.get("breadth", {}).get("narrowing_threshold_pp", -10.0),
            )
        ),
        acceleration_threshold_pp=float(meth.get("leadership", {}).get("acceleration_threshold_pp", 1.0)),
        excess_return_improving=float(meth.get("leadership", {}).get("excess_return_improving", 0.0)),
        excess_return_leading=float(meth.get("leadership", {}).get("excess_return_leading", 0.0)),
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
        concentration_signed_denominator_epsilon=float(
            concentration_cfg.get("signed_denominator_epsilon", 1e-8)
        ),
        concentration_signed_min_net_to_gross=float(
            concentration_cfg.get("signed_min_net_to_gross", 0.05)
        ),
        concentration_price_col=str(meth.get("price_basis", "adjusted_close")),
        taxonomy_level=str(meth.get("groups", {}).get("primary_taxonomy_level", "sector")),
    )
    snapshots = rank_groups(snapshots)

    # Persistence is a count of consecutive observations including current.
    for snapshot in snapshots:
        persistence = compute_persistence(
            snapshot.group_id,
            snapshot,
            history_by_group.get(snapshot.group_id, []),
        )
        snapshot.leadership_persistence = max(
            1, int(persistence.leadership_persistence_snapshots)
        )
        snapshot.diffusion_persistence = max(
            1, int(persistence.diffusion_persistence_snapshots)
        )

    # Transitions
    transitions = build_transition_events(
        current=snapshots,
        previous_by_group=previous_snapshots_by_group,
        materiality_breadth_delta_pp=float(
            meth.get("materiality", {}).get("breadth_delta_min_pp", 10.0)
        ),
        materiality_excess_delta_pp=float(
            meth.get("materiality", {}).get("excess_return_delta_min_pp", 1.5)
        ),
        materiality_rank_delta_min=int(
            meth.get("materiality", {}).get("rank_delta_min", 3)
        ),
    )

    # Persist
    writer = SnapshotWriter(root=out_dir)
    sid = snapshot_id or f"snap_{as_of.isoformat()}"
    target = writer.write(
        snapshot_id=sid,
        as_of=as_of,
        provider=provider_name,
        provider_mode=resolved_provider_mode,
        universe_version=str(universe_cfg.get("universe_version", "prototype-v1")),
        taxonomy_version=str(universe_cfg.get("taxonomy_version", "prototype-v1")),
        eligibility_version=eligibility_version,
        method_version=method_version,
        feature_version=feature_version,
        leadership_version=leadership_version,
        diffusion_version=diffusion_version,
        concentration_version=concentration_version,
        schema_version=schema_version,
        coverage_status=quality.status,
        coverage_pct=quality.coverage_pct,
        prices=prices,
        benchmark=benchmark,
        security_master=provider.get_security_master(),
        features=features,
        groups=_snapshots_to_df(snapshots),
        transitions=_transitions_to_df(transitions),
        notes=";".join(quality.issues) if quality.issues else None,
    )

    # Change digest
    change_digest = build_change_digest(
        transitions,
        as_of=as_of.isoformat(),
        previous=previous_date,
    )
    evidence = [
        build_group_evidence(
            snapshot,
            previous=previous_snapshots_by_group.get(snapshot.group_id),
            provider_mode=resolved_provider_mode,
        )
        for snapshot in snapshots
    ]
    market_read = build_market_read(change_digest)
    story = build_story_mode(change_digest, evidence)
    _atomic_json(target / "change_digest.json", change_digest.to_dict())
    _atomic_json(target / "quality.json", quality.to_dict())
    _atomic_json(
        target / "evidence.json",
        [item.model_dump(mode="json") for item in evidence],
    )
    _atomic_json(target / "market_read.json", market_read.to_dict())
    _atomic_json(target / "story_mode.json", story.to_dict())
    _atomic_json(target / "comparability.json", comparison_audit)

    # Aggregate manifest. A caller-provided root is isolated from the
    # checked-in/default artifact tree (important for tests and exports).
    aggregated = reader.aggregate_manifest()
    if out_dir is not None:
        write_manifest(aggregated, path=Path(out_dir) / "manifest.json")
    else:
        write_manifest(aggregated)

    _log.info("snapshot_complete id=%s as_of=%s status=%s coverage_pct=%.1f",
              sid, as_of, quality.status.value, quality.coverage_pct)
    return {
        "snapshot_id": sid,
        "as_of": as_of.isoformat(),
        "quality": quality.to_dict(),
        "change_digest": change_digest.to_dict(),
        "market_read": market_read.to_dict(),
        "story_mode": story.to_dict(),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "comparability": comparison_audit,
        "provider_mode": resolved_provider_mode.value,
        "groups": _snapshots_to_df(snapshots),
        "transitions": _transitions_to_df(transitions),
    }


def _resolve_horizons(meth: dict[str, Any]) -> dict[str, int]:
    h = meth.get("horizons", {})
    return {
        "5d": int(h.get("short", 5)),
        "20d": int(h.get("primary", 20)),
        "60d": int(h.get("medium", 60)),
    }


def _load_compatible_history(
    reader: SnapshotReader,
    current_contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[Any]], dict[str, Any], str | None]:
    candidates: list[tuple[str, Path, dict[str, Any], dict[str, Any]]] = []
    audit: dict[str, Any] = {
        "status": "NO_COMPARABLE_HISTORY",
        "current_contract": current_contract,
        "snapshots_checked": [],
    }
    for snapshot_path in reader.list_snapshots():
        try:
            loaded = reader.load(snapshot_path.name)
            root_manifest = loaded.get("manifest", {})
            entries = root_manifest.get("entries", [])
            if not entries:
                audit["snapshots_checked"].append(
                    {
                        "snapshot_id": snapshot_path.name,
                        "status": "INCOMPATIBLE",
                        "reasons": ["manifest has no entry"],
                    }
                )
                continue
            entry = entries[0]
            result = assess_snapshot_comparability(current_contract, entry)
            audit["snapshots_checked"].append(
                {
                    "snapshot_id": snapshot_path.name,
                    **result.to_dict(),
                }
            )
            if result.comparable:
                candidates.append((str(entry.get("as_of")), snapshot_path, entry, loaded))
        except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError) as exc:
            audit["snapshots_checked"].append(
                {
                    "snapshot_id": snapshot_path.name,
                    "status": "INCOMPATIBLE",
                    "reasons": [f"snapshot unreadable: {exc}"],
                }
            )

    candidates.sort(key=lambda item: item[0])
    history_by_group: dict[str, list[Any]] = {}
    previous_by_group: dict[str, Any] = {}
    previous_date: str | None = None
    for candidate_date, _, _, loaded in candidates:
        groups = loaded.get("groups", pd.DataFrame())
        if groups is None or groups.empty:
            continue
        current_candidate: dict[str, Any] = {}
        for _, row in groups.iterrows():
            snapshot = _row_to_group_snapshot(row)
            history_by_group.setdefault(snapshot.group_id, []).append(snapshot)
            current_candidate[snapshot.group_id] = snapshot
        previous_by_group = current_candidate
        previous_date = candidate_date

    if candidates:
        audit["status"] = "COMPATIBLE"
        audit["selected_previous"] = candidates[-1][1].name
        audit["selected_previous_as_of"] = previous_date
    else:
        audit["selected_previous"] = None
        audit["selected_previous_as_of"] = None
    return previous_by_group, history_by_group, audit, previous_date


def _row_to_group_snapshot(row: pd.Series):
    from .models import (
        ConcentrationMetrics,
        DiffusionState,
        GroupSnapshot,
        LeadershipState,
    )

    snapshot_date = _none_if_nan_str(row.get("snapshot_date"))
    if snapshot_date is None:
        raise ValueError("group row missing snapshot_date")
    snapshot_date = pd.Timestamp(snapshot_date).date()
    taxonomy_path = row.get("taxonomy_path", [])
    if not isinstance(taxonomy_path, list):
        taxonomy_path = []
    concentration = ConcentrationMetrics(
        top1_contribution_share=_none_if_nan(row.get("top1_contribution_share")),
        top3_contribution_share=_none_if_nan(row.get("top3_contribution_share")),
        top5_contribution_share=_none_if_nan(row.get("top5_contribution_share")),
        top1_signed_share=_none_if_nan(row.get("top1_signed_share")),
        top3_signed_share=_none_if_nan(row.get("top3_signed_share")),
        hhi_contribution=_none_if_nan(row.get("hhi_contribution")),
        contributor_count=_none_if_nan_int(row.get("contributor_count")) or 0,
        convention=_none_if_nan_str(row.get("convention")) or "absolute_move",
        status=_none_if_nan_str(row.get("concentration_status")) or "UNDEFINED",
        signed_attribution_status=(
            _none_if_nan_str(row.get("signed_attribution_status")) or "UNDEFINED"
        ),
    )
    return GroupSnapshot(
        snapshot_date=snapshot_date,
        taxonomy_level=_none_if_nan_str(row.get("taxonomy_level")) or "sector",
        taxonomy_path=taxonomy_path,
        group_id=str(row["group_id"]),
        group_name=_none_if_nan_str(row.get("group_name")),
        constituent_count=_none_if_nan_int(row.get("constituent_count")) or 0,
        eligible_count=_none_if_nan_int(row.get("eligible_count")) or 0,
        missing_count=_none_if_nan_int(row.get("missing_count")) or 0,
        group_return_equal_weight=_none_if_nan(row.get("group_return_equal_weight")),
        group_excess_return=_none_if_nan(row.get("group_excess_return")),
        group_excess_return_5d=_none_if_nan(row.get("group_excess_return_5d")),
        group_excess_return_20d=_none_if_nan(row.get("group_excess_return_20d")),
        group_excess_return_60d=_none_if_nan(row.get("group_excess_return_60d")),
        relative_strength_level=_none_if_nan(row.get("group_excess_return")),
        breadth_positive=_none_if_nan(row.get("breadth_positive")),
        breadth_outperforming=_none_if_nan(row.get("breadth_outperforming")),
        breadth_delta=_none_if_nan(row.get("breadth_delta")),
        breadth_total_count=_none_if_nan_int(row.get("breadth_total_count")) or 0,
        breadth_eligible_count=_none_if_nan_int(row.get("breadth_eligible_count")) or 0,
        breadth_missing_count=_none_if_nan_int(row.get("breadth_missing_count")) or 0,
        breadth_positive_count=_none_if_nan_int(row.get("breadth_positive_count")) or 0,
        breadth_outperforming_count=(
            _none_if_nan_int(row.get("breadth_outperforming_count")) or 0
        ),
        breadth_improving_count=_none_if_nan_int(row.get("breadth_improving_count")) or 0,
        concentration=concentration,
        leadership_state=LeadershipState(
            _none_if_nan_str(row.get("leadership_state")) or "UNCONFIRMED"
        ),
        diffusion_state=DiffusionState(
            _none_if_nan_str(row.get("diffusion_state")) or "UNCONFIRMED"
        ),
        diffusion_state_v2=_diffusion_v2_or_none(row.get("diffusion_state_v2")),
        leadership_rank=_none_if_nan_int(row.get("leadership_rank")),
        change_rank=_none_if_nan_int(row.get("change_rank")),
        leadership_persistence=(
            _none_if_nan_int(row.get("leadership_persistence")) or 1
        ),
        diffusion_persistence=(
            _none_if_nan_int(row.get("diffusion_persistence")) or 1
        ),
        method_version=_none_if_nan_str(row.get("method_version")) or "methodology-v1",
        feature_version=_none_if_nan_str(row.get("feature_version")) or "features-v1",
    )


def _resolve_provider_mode(
    provider: MarketDataProvider,
    explicit: ProviderMode | str | None,
) -> ProviderMode:
    if explicit is not None:
        return explicit if isinstance(explicit, ProviderMode) else ProviderMode(str(explicit))
    candidate = getattr(provider, "provider_mode", None) or getattr(provider, "mode", None)
    if candidate is not None:
        return candidate if isinstance(candidate, ProviderMode) else ProviderMode(str(candidate))
    name = str(getattr(provider, "name", "")).lower()
    if name in {"sectors_fixture", "sectors-fixture"}:
        return ProviderMode.SECTORS_FIXTURE
    if name == "sectors":
        return ProviderMode.SECTORS_LIVE
    if name in {"demo", "demo_fixture"}:
        return ProviderMode.DEMO_FIXTURE
    return ProviderMode.PUBLIC_PROTOTYPE


def _atomic_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    tmp.replace(path)


def _safe_provider_name(provider) -> Any:
    from .models import ProviderName
    name = getattr(provider, "name", "abstract")
    mapping = {
        "yfinance": ProviderName.YFINANCE,
        "public": ProviderName.YFINANCE,
        "sectors": ProviderName.SECTORS,
        "sectors_fixture": ProviderName.FIXTURE,
        "fixture": ProviderName.FIXTURE,
        "demo": ProviderName.FIXTURE,
    }
    return mapping.get(name, ProviderName.YFINANCE)


def _snapshots_to_df(snapshots) -> pd.DataFrame:
    rows: list[dict] = []
    for s in snapshots:
        rows.append(
            {
                "snapshot_date": s.snapshot_date,
                "taxonomy_level": s.taxonomy_level,
                "taxonomy_path": s.taxonomy_path,
                "group_id": s.group_id,
                "group_name": s.group_name,
                "constituent_count": s.constituent_count,
                "eligible_count": s.eligible_count,
                "missing_count": s.missing_count,
                "group_return_equal_weight": s.group_return_equal_weight,
                "group_excess_return": s.group_excess_return,
                "group_excess_return_5d": s.group_excess_return_5d,
                "group_excess_return_20d": s.group_excess_return_20d,
                "group_excess_return_60d": s.group_excess_return_60d,
                "breadth_positive": s.breadth_positive,
                "breadth_outperforming": s.breadth_outperforming,
                "breadth_delta": s.breadth_delta,
                "breadth_total_count": s.breadth_total_count,
                "breadth_eligible_count": s.breadth_eligible_count,
                "breadth_missing_count": s.breadth_missing_count,
                "breadth_positive_count": s.breadth_positive_count,
                "breadth_outperforming_count": s.breadth_outperforming_count,
                "breadth_improving_count": s.breadth_improving_count,
                "top1_contribution_share": s.concentration.top1_contribution_share,
                "top3_contribution_share": s.concentration.top3_contribution_share,
                "top5_contribution_share": s.concentration.top5_contribution_share,
                "top1_signed_share": s.concentration.top1_signed_share,
                "top3_signed_share": s.concentration.top3_signed_share,
                "hhi_contribution": s.concentration.hhi_contribution,
                "contributor_count": s.concentration.contributor_count,
                "convention": s.concentration.convention,
                "concentration_status": s.concentration.status,
                "signed_attribution_status": s.concentration.signed_attribution_status,
                "leadership_state": s.leadership_state.value,
                "diffusion_state": s.diffusion_state.value,
                "diffusion_state_v2": (
                    s.diffusion_state_v2.value
                    if s.diffusion_state_v2 is not None
                    else None
                ),
                "leadership_rank": s.leadership_rank,
                "change_rank": s.change_rank,
                "leadership_persistence": s.leadership_persistence,
                "diffusion_persistence": s.diffusion_persistence,
                "method_version": s.method_version,
                "feature_version": s.feature_version,
            }
        )
    return pd.DataFrame(rows)


def _transitions_to_df(transitions) -> pd.DataFrame:
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
                "leadership_transition": t.leadership_transition,
                "diffusion_transition": t.diffusion_transition,
                "breadth_delta": t.breadth_delta,
                "relative_strength_delta": t.relative_strength_delta,
                "rank_delta": t.rank_delta,
                "materiality_label": t.materiality_label.value,
                "materiality_reason": t.materiality_reason,
                "primary_evidence": t.primary_evidence,
                "secondary_evidence": t.secondary_evidence,
                "data_gaps": t.data_gaps,
                "contradictory": t.contradictory,
                "transition_version": t.transition_version,
            }
        )
    return pd.DataFrame(rows)
