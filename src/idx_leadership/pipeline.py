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

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .aggregation.groups import build_group_snapshots, rank_groups
from .data.manifests import write_manifest
from .data.comparability import check_snapshot_compatibility
from .data.quality import assess_quality
from .data.snapshots import SNAPSHOT_VERSION, SnapshotReader, SnapshotWriter
from .features.relative_strength import compute_excess_returns, compute_ytd_excess_returns
from .analytics.persistence import compute_persistence
from .evidence.builder import build_group_evidence
from .intelligence import build_market_read, build_story_mode
from .models import PriceBasis, ProviderMode
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


def _ticker_set_or_empty(value) -> list[str]:
    """Restore a persisted eligible/outperforming ticker set; legacy rows yield []."""
    if value is None:
        return []
    if isinstance(value, list):
        return sorted({str(ticker) for ticker in value})
    if isinstance(value, float):
        import math
        if math.isnan(value):
            return []
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return []
        if isinstance(parsed, list):
            return sorted({str(ticker) for ticker in parsed})
        return []
    return []
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


def _date_or_none(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return pd.Timestamp(v).date()
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
    price_basis: PriceBasis | str | None = None,
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
    if price_basis is None:
        effective_price_basis = resolve_effective_price_basis(
            meth, resolved_provider_mode
        )
    else:
        try:
            effective_price_basis = PriceBasis(str(price_basis)).value
        except ValueError as exc:
            raise ValueError(
                f"Unsupported requested price basis={price_basis!r}"
            ) from exc
        if (
            resolved_provider_mode
            in {ProviderMode.SECTORS_LIVE, ProviderMode.SECTORS_FIXTURE}
            and effective_price_basis != PriceBasis.CLOSE.value
        ):
            raise ValueError(
                "Sectors snapshots must use close; adjusted_close is only a "
                "compatibility alias for the raw close"
            )
    benchmark_id = universe_cfg.get("benchmark", "^JKSE")
    requested = [row["ticker"] for row in universe_cfg.get("universe", [])]
    wall_today = today_utc()
    as_of_explicit = as_of is not None
    as_of = as_of or wall_today
    lookback_days = max(horizons.values()) + 10
    lookback = pd.Timedelta(days=int(lookback_days * 1.6))
    regular_start = (
        (pd.Timestamp(as_of) - lookback).date()
        if not isinstance(as_of, pd.Timestamp)
        else (as_of - lookback).date()
    )
    # YTD needs the last common trading session of the prior calendar year.
    # Requesting this bounded extra window is deterministic and avoids
    # silently treating a short lookback as a complete YTD baseline.
    ytd_start = date(as_of.year - 1, 12, 20)
    start_date = min(regular_start, ytd_start)

    prices = provider.get_price_history(requested, start=start_date, end=as_of)
    benchmark = provider.get_benchmark_history(benchmark_id, start=start_date, end=as_of)
    taxonomy = provider.get_group_taxonomy()

    # Filter to canonical columns; ensure all dates are date objects
    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    benchmark["date"] = pd.to_datetime(benchmark["date"]).dt.date

    # Quality report
    # Staleness is assessed relative to the snapshot's as-of date so that
    # frozen historical snapshots remain deterministic as wall-clock time
    # advances. Using wall-clock time here made every pinned as_of go STALE
    # ~stale_days after its date (time-bomb).
    quality = assess_quality(
        requested_tickers=requested,
        prices=prices,
        benchmark=benchmark,
        today=as_of,
    )
    # A run that defaults as_of to today during Jakarta trading hours may
    # ingest a still-forming daily bar. Mark it intraday explicitly instead
    # of letting a partial session pose as a final close.
    from .utils.dates import jakarta_session_state

    intraday_build = bool(
        not as_of_explicit and jakarta_session_state() == "OPEN"
    )
    if intraday_build:
        quality.issues.append(
            "intraday_build: snapshot built during the Jakarta trading "
            "session; the latest bars may be partial, not final closes"
        )

    # Per-security features
    features = compute_excess_returns(
        prices,
        benchmark,
        horizons=horizons,
        as_of=as_of,
        security_price_col=effective_price_basis,
        tolerance_days=int(meth.get("as_of_tolerance_days", 7)),
    )
    ytd_features = compute_ytd_excess_returns(
        prices,
        benchmark,
        as_of=as_of,
        security_price_col=effective_price_basis,
        benchmark_price_col="close",
        tolerance_days=int(meth.get("as_of_tolerance_days", 7)),
    )
    if features.empty:
        features = pd.DataFrame(columns=["ticker"])
    if not ytd_features.empty:
        features = features.merge(ytd_features, on="ticker", how="left")
    else:
        for column in (
            "return_ytd",
            "benchmark_return_ytd",
            "excess_return_ytd",
            "return_ytd_start_date",
            "return_ytd_end_date",
        ):
            features[column] = None
    if features.empty:
        _log.warning("no_features_computed as_of=%s", as_of)
    # The aggregation layer merges taxonomy into features internally; do not pre-merge here.

    # Compute eligible ticker set hash from the current universe so the
    # comparability gate can verify membership parity.
    from .providers.market_universe import build_market_universe
    from .providers.capabilities import EventProvider
    acquisition_failed_tickers, acquisition_empty_tickers = _provider_acquisition_sets(
        provider
    )
    # Suspension exclusion requires a capable event provider. Without one
    # the universe is built without suspension filtering and the coverage
    # record says so explicitly (never silently assumed clean).
    event_provider = provider if isinstance(provider, EventProvider) else None
    suspension_check = (
        "checked" if event_provider is not None else "not_supported"
    )
    _universe = build_market_universe(
        security_master_provider=provider,
        cross_section_provider=provider,
        event_provider=event_provider,
        as_of=as_of,
        price_history=prices,
        acquisition_failures=acquisition_failed_tickers,
        acquisition_empties=acquisition_empty_tickers,
    )
    if isinstance(_universe.attrs.get("suspension_check"), str):
        suspension_check = str(_universe.attrs["suspension_check"])
    eligible_tickers = set(
        _universe.loc[_universe["eligible"], "ticker"].astype(str).str.upper().tolist()
    )
    eligible_ticker_set_hash = (
        hashlib.sha256(json.dumps(sorted(eligible_tickers)).encode()).hexdigest()[:16]
        if eligible_tickers
        else "EMPTY"
    )
    eligible_ticker_count = len(eligible_tickers)
    max_obs_lag_days, n_lagging_gt2d = _observation_lag_days(prices, benchmark)
    coverage = _build_pipeline_coverage(
        universe=_universe,
        features=features,
        prices=prices,
        benchmark=benchmark,
        quality=quality,
        as_of=as_of,
        coverage_gate_pct=float(
            meth.get("groups", {}).get("minimum_coverage_pct", 60.0)
        ),
        provider_mode=resolved_provider_mode,
        security_master_diagnostics=getattr(
            provider, "security_master_diagnostics", None
        ),
        close_pagination_diagnostics=getattr(
            provider, "close_pagination_diagnostics", None
        ),
        history_diagnostics=getattr(provider, "history_diagnostics", None),
        benchmark_diagnostics=getattr(provider, "benchmark_diagnostics", None),
        suspension_check=suspension_check,
        intraday_build=intraday_build,
        max_observation_lag_days=max_obs_lag_days,
        tickers_lagging_gt2d=n_lagging_gt2d,
    )

    # Read only earlier, contract-compatible snapshots.  Directory order is
    # not a point-in-time contract and must never select a future snapshot.
    reader = SnapshotReader(root=out_dir)
    current_contract = {
        "snapshot_date": as_of.isoformat(),
        "as_of": as_of.isoformat(),
        "provider": provider_name.value,
        "provider_mode": resolved_provider_mode.value,
        "price_basis": effective_price_basis,
        "universe_version": str(universe_cfg.get("universe_version", "prototype-v1")),
        "taxonomy_version": str(universe_cfg.get("taxonomy_version", "prototype-v1")),
        "eligibility_version": eligibility_version,
        "method_version": method_version,
        "feature_version": feature_version,
        "leadership_version": leadership_version,
        "diffusion_version": diffusion_version,
        "concentration_version": concentration_version,
        "eligible_ticker_set_hash": eligible_ticker_set_hash,
    }
    (
        previous_snapshots_by_group,
        history_by_group,
        comparison_audit,
        previous_date,
    ) = _load_compatible_history(reader, current_contract)

    # The group denominator is the policy-eligible taxonomy, while the raw
    # frame remains available for transparent candidate counts.  Filtering at
    # this boundary keeps policy-excluded members from silently entering a
    # group metric merely because the provider returned their price history.
    raw_candidate_taxonomy = taxonomy.copy()
    if "ticker" in taxonomy.columns:
        taxonomy = taxonomy[
            taxonomy["ticker"].astype(str).str.upper().isin(eligible_tickers)
        ].copy()

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
            concentration_cfg.get("signed_denominator_epsilon", 1e-9)
        ),
        concentration_signed_min_net_to_gross=float(
            concentration_cfg.get("signed_min_net_to_gross", 0.05)
        ),
        concentration_price_col=effective_price_basis,
        taxonomy_level=str(meth.get("groups", {}).get("primary_taxonomy_level", "sector")),
        raw_candidate_taxonomy=raw_candidate_taxonomy,
        acquisition_failed_tickers=acquisition_failed_tickers,
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
        price_basis=effective_price_basis,
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
        eligible_ticker_set_hash=eligible_ticker_set_hash,
        eligible_ticker_count=eligible_ticker_count,
        raw_ticker_count=int(coverage["raw_candidate_constituents"]),
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
    _atomic_json(target / "coverage.json", coverage)
    _atomic_json(
        target / "evidence.json",
        [item.model_dump(mode="json") for item in evidence],
    )
    _atomic_json(target / "market_read.json", market_read.to_dict())
    _atomic_json(target / "story_mode.json", story.to_dict())
    _atomic_json(target / "comparability.json", comparison_audit)
    # COMPLETE is written last, after every sidecar, so a crash anywhere
    # above leaves a bundle that loads with complete=false instead of
    # masquerading as finished.
    _atomic_text(target / "COMPLETE", "complete\n")

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
        "coverage": coverage,
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


def _pagination_completeness(value: Any) -> str | None:
    """Normalize a provider pagination-completeness flag without coupling.

    Providers that track paging (Sectors) expose COMPLETE/PARTIAL/UNKNOWN;
    others expose nothing and keep the None default.
    """
    if value in ("COMPLETE", "PARTIAL", "UNKNOWN"):
        return str(value)
    return None


def _build_pipeline_coverage(
    *,
    universe: pd.DataFrame,
    features: pd.DataFrame,
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    quality: Any,
    as_of: date,
    coverage_gate_pct: float,
    provider_mode: ProviderMode,
    security_master_diagnostics: Any | None = None,
    close_pagination_diagnostics: Any | None = None,
    history_diagnostics: Any | None = None,
    benchmark_diagnostics: Any | None = None,
    suspension_check: str = "not_supported",
    max_observation_lag_days: int | None = None,
    tickers_lagging_gt2d: int = 0,
    intraday_build: bool = False,
) -> dict[str, Any]:
    """Persist the same denominator contract for the generic pipeline.

    The market-wide script has its own provider diagnostics, while
    ``build_snapshot`` is also used by the offline harness.  Keeping the
    denominator fields here prevents that path from rendering coverage as
    zero simply because it does not have Sectors pagination metadata.
    """
    raw_count = int(len(universe))
    eligible = (
        universe["eligible"].astype(bool)
        if "eligible" in universe.columns
        else pd.Series(False, index=universe.index)
    )
    status = universe.get("acquisition_status")
    if status is not None:
        policy_excluded = int((status == "POLICY_EXCLUDED").sum())
        acquisition_failed = int((status == "ACQUISITION_FAILED").sum())
        acquisition_empty = int((status == "ACQUISITION_EMPTY").sum())
        acquired = int((status == "ACQUIRED").sum())
    else:
        policy_excluded = int((~eligible).sum())
        acquisition_failed = 0
        acquisition_empty = 0
        acquired = int(eligible.sum())
    policy_eligible = max(0, raw_count - policy_excluded)

    eligible_tickers = set(
        universe.loc[eligible, "ticker"].astype(str).tolist()
    ) if "ticker" in universe.columns else set()
    observed_tickers: set[str] = set()
    if not features.empty and "ticker" in features.columns:
        observed = features[features["ticker"].astype(str).isin(eligible_tickers)]
        valid_columns = [
            column
            for column in ("return_20d", "return_60d")
            if column in observed.columns
        ]
        if valid_columns:
            observed = observed.dropna(subset=valid_columns)
        observed_tickers = set(observed["ticker"].astype(str).tolist())
    observed_count = len(observed_tickers)
    coverage_pct = (
        round(observed_count / policy_eligible * 100.0, 2)
        if policy_eligible
        else 0.0
    )

    latest_security_date: str | None = None
    stale_security_count = 0
    if not prices.empty and {"ticker", "date"}.issubset(prices.columns):
        dates = pd.to_datetime(prices["date"], errors="coerce")
        latest_by_ticker = (
            pd.DataFrame({"ticker": prices["ticker"], "date": dates})
            .dropna(subset=["date"])
            .groupby("ticker")["date"]
            .max()
        )
        if not latest_by_ticker.empty:
            latest_security_date = latest_by_ticker.max().date().isoformat()
            stale_security_count = int(
                ((pd.Timestamp(as_of) - latest_by_ticker).dt.days > 30).sum()
            )
    benchmark_dates = (
        pd.to_datetime(benchmark["date"], errors="coerce").dropna()
        if not benchmark.empty and "date" in benchmark.columns
        else pd.Series(dtype="datetime64[ns]")
    )
    latest_benchmark_date = (
        benchmark_dates.max().date().isoformat()
        if not benchmark_dates.empty
        else None
    )
    exclusion_reasons: dict[str, int] = {}
    if "exclusion_reason" in universe.columns:
        excluded = universe.loc[~eligible, "exclusion_reason"]
        exclusion_reasons = {
            str(key): int(value) for key, value in excluded.value_counts().items()
        }

    taxonomy_columns = [
        column
        for column in ("sector", "subsector", "industry", "subindustry")
        if column in universe.columns
    ]
    taxonomy_complete = (
        int(universe[taxonomy_columns].notna().all(axis=1).sum())
        if taxonomy_columns
        else 0
    )
    sm_diagnostics = security_master_diagnostics or {}
    close_diagnostics = close_pagination_diagnostics or {}
    history_diag = history_diagnostics or {}
    benchmark_diag = benchmark_diagnostics or {}
    sm_completeness = _pagination_completeness(
        sm_diagnostics.get("pagination_completeness")
    )
    close_completeness = _pagination_completeness(
        close_diagnostics.get("pagination_completeness")
    )
    window_capped = bool(history_diag.get("window_capped_to_90_calendar_days", False))
    benchmark_window_capped = bool(
        benchmark_diag.get("window_capped_to_90_calendar_days", False)
    )
    window_capped_any = bool(window_capped or benchmark_window_capped)
    pagination_incomplete = (
        (sm_completeness is not None and sm_completeness != "COMPLETE")
        or (close_completeness is not None and close_completeness != "COMPLETE")
    )
    # Thread multi-window + per-symbol diagnostics so the five coverage
    # states stay distinguishable: complete vs pagination-incomplete vs
    # window-capped vs provider-unavailable vs partial-symbol.
    history_windows_requested = history_diag.get("windows_requested")
    history_windows_completed = history_diag.get("windows_completed")
    history_windows_failed = history_diag.get("windows_failed")
    history_failed_symbols = history_diag.get("failed_symbols") or []
    history_empty_symbols = history_diag.get("empty_symbols") or []
    history_failed_count = len(history_failed_symbols)
    history_empty_count = len(history_empty_symbols)
    history_returned_symbols = history_diag.get("returned_symbols")
    history_blocked = bool(history_diag.get("blocked", False))
    history_requested_symbols = history_diag.get("requested_symbols")
    try:
        requested_int = (
            int(history_requested_symbols)
            if history_requested_symbols is not None
            else None
        )
    except (TypeError, ValueError):
        requested_int = None
    try:
        returned_int = (
            int(history_returned_symbols)
            if history_returned_symbols is not None
            else None
        )
    except (TypeError, ValueError):
        returned_int = None
    provider_unavailable = bool(
        history_blocked
        or (
            requested_int is not None
            and requested_int > 0
            and returned_int == 0
        )
    )
    partial_symbols = bool(
        (history_failed_count > 0 or history_empty_count > 0)
        or (acquisition_failed > 0 or acquisition_empty > 0)
    )
    if provider_unavailable:
        coverage_state = "PROVIDER_UNAVAILABLE"
    elif pagination_incomplete and window_capped_any:
        coverage_state = "PAGINATION_INCOMPLETE_WINDOW_CAPPED"
    elif pagination_incomplete:
        coverage_state = "PAGINATION_INCOMPLETE"
    elif window_capped_any:
        coverage_state = "WINDOW_CAPPED"
    elif partial_symbols:
        coverage_state = "PARTIAL_SYMBOLS"
    else:
        coverage_state = "COMPLETE"
    return {
        "as_of": as_of.isoformat(),
        "provider_mode": provider_mode.value,
        "is_prefix_sample": False,
        "discovered_count": raw_count,
        "used_count": raw_count,
        "discovered_universe_disclosure": (
            f"Configured prototype universe: {raw_count} candidates; not full IDX coverage."
        ),
        "security_master_pagination_completeness": sm_completeness,
        "close_pagination_completeness": close_completeness,
        "pagination_incomplete": pagination_incomplete,
        "history_window_capped_90d": window_capped,
        "history_window_capped_note": (
            "Price/benchmark history truncated by partial window failure; "
            "YTD baselines may be unavailable."
            if window_capped
            else None
        ),
        "suspension_check": suspension_check,
        "intraday_build": bool(intraday_build),
        "max_observation_lag_days": max_observation_lag_days,
        "tickers_lagging_gt2d": int(tickers_lagging_gt2d),
        "benchmark_window_capped_90d": benchmark_window_capped,
        "history_windows_requested": history_windows_requested,
        "history_windows_completed": history_windows_completed,
        "history_windows_failed": history_windows_failed,
        "history_failed_symbols_count": history_failed_count,
        "history_empty_symbols_count": history_empty_count,
        "history_returned_symbols": returned_int,
        "history_provider_unavailable": provider_unavailable,
        "history_partial_symbols": partial_symbols,
        "coverage_state": coverage_state,
        "security_master_total": raw_count,
        "history_requested_securities": int(quality.requested_securities),
        "securities_with_any_price_history": int(quality.loaded_securities),
        "securities_with_usable_price_history": int(quality.usable_securities),
        "eligible_securities": int(eligible.sum()),
        "excluded_securities": policy_excluded,
        "exclusion_reasons": exclusion_reasons,
        "taxonomy_complete_securities": taxonomy_complete,
        "taxonomy_coverage_pct": round(
            taxonomy_complete / max(1, raw_count) * 100.0, 2
        ),
        "latest_available_security_trade_date": latest_security_date,
        "latest_available_benchmark_date": (
            latest_benchmark_date
            or (
                quality.benchmark_latest_date.isoformat()
                if quality.benchmark_latest_date
                else None
            )
        ),
        "stale_security_count": stale_security_count,
        "duplicate_rows": int(quality.duplicate_ticker_date_rows),
        "price_history_coverage_pct": float(quality.coverage_pct),
        "raw_candidate_constituents": raw_count,
        "policy_eligible_constituents": policy_eligible,
        "policy_excluded_constituents": policy_excluded,
        "acquisition_failed_constituents": acquisition_failed,
        "acquisition_empty_constituents": acquisition_empty,
        "acquired_constituents": acquired,
        "observed_eligible_features": observed_count,
        "coverage_pct": coverage_pct,
        "coverage_gate_60pct_met": coverage_pct >= float(coverage_gate_pct),
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
            # Reject future snapshots before compatibility checking.
            raw_date = entry.get("as_of") or ""
            try:
                snap_as_of = date.fromisoformat(str(raw_date))
            except (TypeError, ValueError):
                snap_as_of = None
            if snap_as_of is None or snap_as_of >= date.fromisoformat(current_contract.get("as_of", "9999-99-99")):
                audit["snapshots_checked"].append({
                    "snapshot_id": snapshot_path.name,
                    "status": "INCOMPATIBLE",
                    "reasons": ["snapshot is not earlier than current"],
                })
                continue
            result = check_snapshot_compatibility(current_contract, entry)
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
        group_return_ytd=_none_if_nan(row.get("group_return_ytd")),
        group_excess_return_ytd=_none_if_nan(row.get("group_excess_return_ytd")),
        benchmark_return_ytd=_none_if_nan(row.get("benchmark_return_ytd")),
        ytd_start_date=_date_or_none(row.get("ytd_start_date")),
        ytd_eligible_count=_none_if_nan_int(row.get("ytd_eligible_count")) or 0,
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
        breadth_eligible_tickers=_ticker_set_or_empty(row.get("breadth_eligible_tickers")),
        breadth_outperforming_tickers=_ticker_set_or_empty(row.get("breadth_outperforming_tickers")),
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


def resolve_effective_price_basis(
    methodology: dict[str, Any], provider_mode: ProviderMode | str
) -> str:
    """Resolve the security-price column used by a snapshot calculation.

    Sectors exposes only ``close``. Its normalized ``adjusted_close`` column
    is a compatibility alias for that raw value, not evidence of adjustment.
    Live and Sectors-fixture modes therefore calculate on ``close``; public
    prototype and demo fixture modes retain the methodology default.
    """

    mode = (
        provider_mode
        if isinstance(provider_mode, ProviderMode)
        else ProviderMode(str(provider_mode))
    )
    configured = methodology.get("price_basis", PriceBasis.ADJUSTED_CLOSE.value)
    if mode in {ProviderMode.SECTORS_LIVE, ProviderMode.SECTORS_FIXTURE}:
        configured = PriceBasis.CLOSE.value
    try:
        return PriceBasis(str(configured)).value
    except ValueError as exc:
        raise ValueError(
            f"Unsupported effective price basis={configured!r} for mode={mode.value}"
        ) from exc


def _atomic_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    tmp.replace(path)


def _atomic_text(path: Path, value: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value, encoding="utf-8")
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


def _observation_lag_days(
    prices: pd.DataFrame, benchmark: pd.DataFrame
) -> tuple[int | None, int]:
    """Measure per-ticker end-date dispersion vs the benchmark end date.

    Returns (max_lag_days, n_tickers_lagging_more_than_2d). ``None`` max
    means the lag is uncomputable (empty frames). This is disclosure only:
    within-tolerance staleness stays in the metrics, but its magnitude is
    now visible in coverage instead of silent.
    """
    try:
        if prices is None or prices.empty or benchmark is None or benchmark.empty:
            return None, 0
        if "ticker" not in prices.columns or "date" not in prices.columns:
            return None, 0
        if "date" not in benchmark.columns:
            return None, 0
        price_dates = pd.to_datetime(prices["date"], errors="coerce")
        bench_dates = pd.to_datetime(benchmark["date"], errors="coerce").dropna()
        if bench_dates.empty:
            return None, 0
        bench_end = bench_dates.max().date()
        latest_by_ticker = (
            pd.DataFrame({"ticker": prices["ticker"], "date": price_dates})
            .dropna(subset=["date"])
            .groupby("ticker")["date"]
            .max()
        )
        if latest_by_ticker.empty:
            return None, 0
        lags = [(pd.Timestamp(bench_end) - ts).days for ts in latest_by_ticker]
        lags = [lag for lag in lags if lag is not None and lag >= 0]
        if not lags:
            return None, 0
        return int(max(lags)), int(sum(1 for lag in lags if lag > 2))
    except Exception:  # noqa: BLE001 - disclosure must never break a build
        return None, 0


def _provider_acquisition_sets(provider: Any) -> tuple[set[str], set[str]]:
    """Read optional provider diagnostics without coupling the engine to Sectors.

    Providers that can distinguish a failed request from an empty response
    expose those rows through ``history_diagnostics``.  Other providers keep
    the empty sets, preserving the source-neutral pipeline contract.
    """
    diagnostics = getattr(provider, "history_diagnostics", {}) or {}
    failed: set[str] = set()
    for item in diagnostics.get("failed_symbols", []) or []:
        ticker = item.get("ticker") if isinstance(item, dict) else item
        if ticker:
            failed.add(str(ticker).upper())
    empty = {
        str(ticker).upper()
        for ticker in (diagnostics.get("empty_symbols", []) or [])
        if ticker
    }
    return failed, empty


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
                "group_return_ytd": s.group_return_ytd,
                "group_excess_return_ytd": s.group_excess_return_ytd,
                "benchmark_return_ytd": s.benchmark_return_ytd,
                "ytd_start_date": s.ytd_start_date,
                "ytd_eligible_count": s.ytd_eligible_count,
                "breadth_positive": s.breadth_positive,
                "breadth_outperforming": s.breadth_outperforming,
                "breadth_delta": s.breadth_delta,
                "breadth_total_count": s.breadth_total_count,
                "breadth_eligible_count": s.breadth_eligible_count,
                "breadth_missing_count": s.breadth_missing_count,
                "breadth_positive_count": s.breadth_positive_count,
                "breadth_outperforming_count": s.breadth_outperforming_count,
                "breadth_improving_count": s.breadth_improving_count,
                "breadth_eligible_tickers": json.dumps(sorted(s.breadth_eligible_tickers)),
                "breadth_outperforming_tickers": json.dumps(sorted(s.breadth_outperforming_tickers)),
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
