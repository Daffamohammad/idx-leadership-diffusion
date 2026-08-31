"""Build a live Sectors-backed IDX leadership/diffusion snapshot.

The command is deliberately explicit about paid work:

    .venv/bin/python -m scripts.build_market_snapshot \
        --allow-live --allow-credit-spend --with-tavily

Without ``--as-of`` the runner first asks Sectors for its latest available
full-universe close and uses that observed market date. A requested date that
has no data fails clearly; it is never silently relabelled as current.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from idx_leadership.aggregation.groups import build_group_snapshots, rank_groups
from idx_leadership.data.manifests import write_manifest
from idx_leadership.data.quality import QualityReport, assess_quality
from idx_leadership.data.snapshots import SnapshotReader, SnapshotWriter
from idx_leadership.evidence.builder import build_evidence_table
from idx_leadership.features.relative_strength import compute_excess_returns
from idx_leadership.models import (
    ConcentrationMetrics,
    DiffusionState,
    DiffusionStateV2,
    GroupSnapshot,
    LeadershipState,
    ProviderMode,
    ProviderName,
)
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.market_universe import (
    EligibilityConfig,
    build_market_universe,
    eligibility_summary,
)
from idx_leadership.providers.sectors import SectorsProvider
from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.providers.tavily_client import TavilyClient, TavilyError
from idx_leadership.pipeline import resolve_effective_price_basis
from idx_leadership.signals.change_digest import build_change_digest
from idx_leadership.signals.transitions import build_transition_events
from idx_leadership.utils import data_root, get_logger, load_project_env, load_yaml
import hashlib
from idx_leadership.utils.errors import ProviderError
from idx_leadership.data.comparability import check_snapshot_compatibility

_log = get_logger(__name__)

DEFAULT_MAX_ESTIMATED_CREDITS = SectorsClient.DEFAULT_MAX_ESTIMATED_CREDITS
COMPANIES_PAGE_SIZE = 200
CLOSE_PAGE_SIZE = 30


class FullLiveGateError(ProviderError):
    """Raised before snapshot persistence when a strict live gate fails."""

    def __init__(self, blockers: list[dict[str, str]]) -> None:
        self.blockers = blockers
        reason = blockers[0]["reason"] if blockers else "full-live data gate failed"
        super().__init__(reason)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build_market_snapshot")
    parser.add_argument("--as-of", default=None, help="Exact market date YYYY-MM-DD.")
    parser.add_argument("--config", default="config/providers.yaml")
    parser.add_argument("--methodology", default="config/methodology.yaml")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Snapshot root. Defaults to data/snapshots so the local UI can read it.",
    )
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Enable Sectors HTTP requests for this run.",
    )
    parser.add_argument(
        "--allow-credit-spend",
        action="store_true",
        help="Second explicit gate for paid Sectors/Tavily requests.",
    )
    parser.add_argument(
        "--max-estimated-credits",
        type=float,
        default=DEFAULT_MAX_ESTIMATED_CREDITS,
        help="Hard client-side Sectors credit ceiling; never above 1000 (default: 1000).",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Print the bounded live-call estimate and exit without any HTTP request.",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Block snapshot persistence unless the full-live data gates pass.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional page cap for bounded smoke runs; default fetches all pages.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Optional symbol cap for a bounded live smoke; default uses the full master.",
    )
    parser.add_argument(
        "--min-history-days",
        type=int,
        default=60,
        help="Minimum unique daily observations for eligibility.",
    )
    parser.add_argument(
        "--stale-trading-days",
        type=int,
        default=30,
        help="Maximum calendar age of a latest security trade.",
    )
    parser.add_argument(
        "--min-median-daily-value",
        type=float,
        default=100_000_000.0,
        help="IDR median daily close*volume liquidity floor; use 0 to disable.",
    )
    parser.add_argument(
        "--history-workers",
        type=int,
        default=None,
        help="Override concurrent Sectors daily requests; config default is used otherwise.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore local Sectors response caches after the live gates pass.",
    )
    parser.add_argument(
        "--with-tavily",
        action="store_true",
        help="Run a small official-domain web-context pass and store it separately.",
    )
    parser.add_argument(
        "--tavily-max-queries",
        type=int,
        default=1,
        help="Maximum basic Tavily context queries (default 1).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_project_env()
    validation_error = _validate_args(args)
    if validation_error:
        print(validation_error, file=sys.stderr)
        return 2

    requested_as_of = date.fromisoformat(args.as_of) if args.as_of else None
    snapshot_root = Path(args.out_dir) if args.out_dir else data_root() / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    preflight = _live_credit_preflight(
        snapshot_root=snapshot_root,
        config_path=args.config,
        requested_as_of=requested_as_of,
        max_pages=args.max_pages,
        max_symbols=args.max_symbols,
        max_estimated_credits=args.max_estimated_credits,
    )
    print(json.dumps({"live_credit_preflight": preflight}, indent=2, default=str))
    if preflight["status"] == "BLOCKED":
        print(f"BLOCKED {preflight['reason']}", file=sys.stderr)
        return 2
    if args.preflight_only:
        print("LIVE_PREFLIGHT_COMPLETE no Sectors HTTP requests made")
        return 0
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ledger_path = data_root() / "raw" / "sectors_live" / f"{stamp}_request_ledger.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    provider: SectorsProvider | None = None
    try:
        provider = build_provider_from_config(
            args.config,
            mode=ProviderMode.SECTORS_LIVE,
            allow_live=True,
            max_pages=args.max_pages,
            force_refresh=args.force_refresh,
            max_estimated_credits=args.max_estimated_credits,
        )
        # The factory returns the concrete class for the selected mode. Keep a
        # clear guard here so this runner cannot accidentally emit a live label
        # for another provider.
        if not isinstance(provider, SectorsProvider):
            raise ProviderError("SECTORS_LIVE did not construct SectorsProvider")
        if args.history_workers is not None:
            provider.history_workers = max(1, args.history_workers)
        provider.ledger.path = ledger_path

        latest_close = provider.get_latest_market_close()
        observed_latest = _latest_date(latest_close)
        if observed_latest is None:
            raise ProviderError("Sectors latest full-universe close returned no dated rows")
        if requested_as_of is not None:
            current_close = provider.get_full_universe_close(requested_as_of)
            if current_close.empty:
                raise ProviderError(
                    "requested market date has no Sectors close rows: "
                    f"requested={requested_as_of.isoformat()} latest_observed={observed_latest.isoformat()}"
                )
            as_of = requested_as_of
        else:
            # The first close request is date discovery only. A full-live
            # run must then fetch the complete cross-section for that date;
            # otherwise omitting --as-of silently produces a first-page
            # sample while presenting it as the latest full universe.
            current_close = provider.get_full_universe_close(observed_latest)
            if current_close.empty:
                raise ProviderError(
                    "Sectors latest full-universe close returned no rows for "
                    f"observed date={observed_latest.isoformat()}"
                )
            as_of = observed_latest
        provider.set_source_as_of(as_of)

        master_all = provider.get_security_master()
        if not master_all:
            raise ProviderError("Sectors security master returned no rows")
        master = _limit_master(master_all, args.max_symbols)
        all_tickers = [entry.ticker for entry in master]
        history_tickers = [
            entry.ticker
            for entry in master
            if entry.common_equity_status != "NON_COMMON_EQUITY"
        ]
        if not history_tickers:
            raise ProviderError("no non-common-equity candidates remain for price history")

        methodology = load_yaml(args.methodology)
        effective_price_basis = resolve_effective_price_basis(
            methodology, ProviderMode.SECTORS_LIVE
        )
        horizons = _resolve_horizons(methodology)
        history_start = as_of - timedelta(days=90)
        history = provider.get_price_history(
            history_tickers,
            start=history_start,
            end=as_of,
        )
        ihsg = provider.get_benchmark_history(
            "IHSG", start=history_start, end=as_of
        )
        if ihsg.empty:
            raise ProviderError("Sectors native IHSG history returned no rows")

        median_value_floor = (
            args.min_median_daily_value if args.min_median_daily_value > 0 else None
        )
        eligibility_cfg = EligibilityConfig(
            lookback_history_days=args.min_history_days,
            stale_trading_days=args.stale_trading_days,
            min_history_days=args.min_history_days,
            min_median_daily_value=median_value_floor,
        )
        suspension_warning: str | None = None
        failed_tickers = {
            entry["ticker"] for entry in provider.history_diagnostics.get("failed_symbols", [])
        }
        empty_tickers = set(provider.history_diagnostics.get("empty_symbols", []))
        try:
            universe = build_market_universe(
                security_master_provider=provider,
                cross_section_provider=provider,
                event_provider=provider,
                as_of=as_of,
                config=eligibility_cfg,
                price_history=history,
                security_master=master,
                acquisition_failures=failed_tickers,
                acquisition_empties=empty_tickers,
            )
        except ProviderError as exc:
            # Suspension data is an eligibility input, but the absence of the
            # optional event endpoint must remain visible rather than making a
            # usable price snapshot impossible. No suspension exclusion is
            # inferred in this branch.
            suspension_warning = f"suspensions_unavailable={str(exc)[:240]}"
            universe = build_market_universe(
                security_master_provider=provider,
                cross_section_provider=provider,
                event_provider=None,
                as_of=as_of,
                config=eligibility_cfg,
                price_history=history,
                security_master=master,
                acquisition_failures=failed_tickers,
                acquisition_empties=empty_tickers,
            )

        eligible_tickers = set(
            universe.loc[universe["eligible"], "ticker"].astype(str).tolist()
        )
        features_all = compute_excess_returns(
            history,
            ihsg,
            horizons=horizons,
            as_of=as_of,
            security_price_col=effective_price_basis,
            tolerance_days=int(methodology.get("as_of_tolerance_days", 7)),
        )
        if features_all.empty:
            raise ProviderError("Sectors history produced no return features")
        taxonomy_columns = ["ticker", "sector", "subsector", "industry", "subindustry"]
        taxonomy_frame = universe[taxonomy_columns].copy()
        taxonomy_frame = taxonomy_frame.rename(columns={"subindustry": "sub_industry"})
        features_all = features_all.merge(
            taxonomy_frame, on="ticker", how="left"
        )
        features = features_all[features_all["ticker"].isin(eligible_tickers)].copy()
        if features.empty:
            raise ProviderError("eligibility filter left no securities with usable features")

        # The raw candidate taxonomy preserves the full universe for
        # disclosure. The policy-eligible taxonomy is the denominator for
        # the 60% coverage gate. Acquisition-failed tickers remain in the
        # policy-eligible set as missing data.
        raw_candidate_taxonomy = taxonomy_frame.copy()
        raw_candidate_taxonomy["group_id"] = raw_candidate_taxonomy["sector"]
        taxonomy = raw_candidate_taxonomy[
            raw_candidate_taxonomy["ticker"].astype(str).isin(eligible_tickers)
        ].copy()
        # Build the current fingerprint FIRST (including eligible ticker
        # set hash) so the comparability gate can verify membership parity
        # before any prior snapshot affects downstream calculations.
        current_eligible_tickers = set(
            universe.loc[universe["eligible"], "ticker"].astype(str).tolist()
        )
        current_eligible_hash = (
            hashlib.sha256(
                json.dumps(sorted(current_eligible_tickers)).encode()
            ).hexdigest()[:16]
            if current_eligible_tickers
            else "EMPTY"
        )
        # Build the current fingerprint with all version fields so the
        # resolver can reject mismatches BEFORE loading any prior data.
        current_fingerprint = {
            "provider_mode": ProviderMode.SECTORS_LIVE.value,
            "price_basis": effective_price_basis,
            "eligible_ticker_set_hash": current_eligible_hash,
            "eligible_ticker_count": len(current_eligible_tickers),
            "method_version": str(
                methodology.get("method_version", "methodology-v3")
            ),
            "feature_version": str(
                methodology.get("feature_version", "features-v3")
            ),
            "leadership_version": str(
                methodology.get("leadership_version", "leadership-v2")
            ),
            "diffusion_version": str(
                methodology.get("diffusion_version", "diffusion-v2")
            ),
            "concentration_version": str(
                methodology.get("concentration_version", "concentration-v3")
            ),
            "eligibility_version": str(
                methodology.get("eligibility_version", "eligibility-v2-live")
            ),
            "universe_version": "sectors-v2-live",
            "taxonomy_version": "sectors-companies-query-values-v1",
        }
        previous_groups, previous_by_group, previous_source = _resolve_previous_groups(
            snapshot_root=snapshot_root,
            current_as_of=as_of,
            current_fingerprint=current_fingerprint,
            history=history,
            benchmark=ihsg,
            taxonomy=taxonomy,
            features_all=features_all,
            prices=history,
            horizons=horizons,
            methodology=methodology,
        )

        group_kwargs = _group_kwargs(
            methodology, horizons, price_basis=effective_price_basis
        )
        snapshots = build_group_snapshots(
            features=features,
            taxonomy=taxonomy,
            raw_candidate_taxonomy=raw_candidate_taxonomy,
            acquisition_failed_tickers=failed_tickers,
            snapshot_date=as_of,
            prices=history,
            horizons=horizons,
            previous_groups=previous_groups,
            **group_kwargs,
        )
        snapshots = rank_groups(snapshots)
        if not snapshots:
            raise ProviderError("group aggregation returned no groups")
        transitions = build_transition_events(
            current=snapshots,
            previous_by_group=previous_by_group,
            materiality_breadth_delta_pp=float(
                methodology.get("materiality", {}).get("breadth_delta_min_pp", 10.0)
            ),
            materiality_excess_delta_pp=float(
                methodology.get("materiality", {}).get("excess_return_delta_min_pp", 1.5)
            ),
            materiality_rank_delta_min=int(
                methodology.get("materiality", {}).get("rank_delta_min", 3)
            ),
        )
        digest = build_change_digest(
            transitions,
            as_of=as_of.isoformat(),
            previous=previous_source,
        )
        evidence = build_evidence_table(
            snapshots,
            provider_mode=ProviderMode.SECTORS_LIVE,
            previous_by_group=previous_by_group,
        )

        quality = assess_quality(
            requested_tickers=history_tickers,
            prices=history,
            benchmark=ihsg,
            today=as_of,
            stale_days=args.stale_trading_days,
            min_history_days=args.min_history_days,
        )
        coverage = _coverage_report(
            master=master,
            universe=universe,
            history=history,
            quality=quality,
            as_of=as_of,
            provider=provider,
            requested_history_tickers=history_tickers,
            min_history_days=args.min_history_days,
        )
        warnings = _data_warnings(
            provider=provider,
            universe=universe,
            quality=quality,
            current_close=current_close,
            as_of=as_of,
            suspension_warning=suspension_warning,
        )

        if args.require_complete:
            blockers = _full_live_data_gate(
                provider=provider,
                master=master,
                history_tickers=history_tickers,
                history=history,
                benchmark=ihsg,
                current_close=current_close,
                quality=quality,
                coverage=coverage,
                expected_price_basis=effective_price_basis,
                as_of=as_of,
                min_history_days=args.min_history_days,
            )
            if blockers:
                # This is deliberately before sensitivity, Tavily, and the
                # SnapshotWriter. A failed full-live gate may leave only the
                # request ledger/cache evidence; it cannot create a snapshot,
                # aggregate manifest, browser export, or index update.
                raise FullLiveGateError(blockers)

        sensitivity = _build_sensitivity_report(
            baseline=snapshots,
            master=master,
            universe=universe,
            features_all=features_all,
            history=history,
            benchmark=ihsg,
            taxonomy=taxonomy,
            as_of=as_of,
            horizons=horizons,
            methodology=methodology,
            previous_groups=previous_groups,
            group_kwargs=group_kwargs,
            price_basis=effective_price_basis,
            default_floor=median_value_floor,
            min_history_days=args.min_history_days,
            stale_trading_days=args.stale_trading_days,
        )

        tavily_report = _run_tavily(
            args=args,
            snapshots=snapshots,
            as_of=as_of,
        )
        if tavily_report.get("ledger_path"):
            tavily_ledger_path = Path(str(tavily_report["ledger_path"]))
        else:
            tavily_ledger_path = None

        enriched_master = _enrich_master(master, history)
        snapshot_id = f"snap_sectors_{as_of.isoformat()}"
        writer = SnapshotWriter(root=snapshot_root)
        # Compute the eligible ticker set hash for membership parity
        # checks across snapshots.
        eligible_tickers = set(
            universe.loc[universe["eligible"], "ticker"].astype(str).tolist()
        )
        eligible_hash = hashlib.sha256(
            json.dumps(sorted(eligible_tickers)).encode()
        ).hexdigest()[:16] if eligible_tickers else "EMPTY"
        target = writer.write(
            snapshot_id=snapshot_id,
            as_of=as_of,
            provider=ProviderName.SECTORS,
            provider_mode=ProviderMode.SECTORS_LIVE,
            price_basis=effective_price_basis,
            universe_version="sectors-v2-live",
            taxonomy_version="sectors-companies-query-values-v1",
            eligibility_version=str(
                methodology.get("eligibility_version", "eligibility-v2-live")
            ),
            method_version=str(methodology.get("method_version", "methodology-v1")),
            feature_version=str(methodology.get("feature_version", "features-v1")),
            leadership_version=str(methodology.get("leadership_version", "leadership-v1")),
            diffusion_version=str(methodology.get("diffusion_version", "diffusion-v1")),
            concentration_version=str(
                methodology.get("concentration_version", "concentration-v1")
            ),
            schema_version=str(methodology.get("schema_version", "schemas-v1")),
            coverage_status=quality.status,
            coverage_pct=quality.coverage_pct,
            prices=history,
            benchmark=ihsg,
            security_master=enriched_master,
            features=features,
            groups=_snapshots_to_df(snapshots),
            transitions=_transitions_to_df(transitions),
            notes="; ".join(warnings)[:2000] if warnings else None,
            eligible_ticker_set_hash=eligible_hash,
            eligible_ticker_count=len(eligible_tickers),
            raw_ticker_count=len(universe),
        )

        close_frame = current_close[current_close["ticker"].isin(all_tickers)].copy()
        _write_csv(close_frame, target / "close.csv")
        _write_csv(universe, target / "universe.csv")
        _write_json(target / "coverage.json", coverage)
        _write_json(
            target / "comparability.json",
            _build_comparability(
                as_of=as_of,
                previous_source=previous_source,
                previous_groups=previous_groups,
                snapshot_root=snapshot_root,
                universe=universe,
            ),
        )
        _write_json(target / "quality.json", quality.to_dict())
        _write_json(target / "data_warnings.json", {"warnings": warnings})
        _write_json(target / "provider_provenance.json", _provenance(
            provider=provider,
            as_of=as_of,
            quality=quality,
            coverage=coverage,
            history=history,
            benchmark=ihsg,
            current_close=current_close,
            previous_source=previous_source,
        ))
        _write_json(target / "security_master_diagnostics.json", provider.security_master_diagnostics)
        _write_json(target / "history_diagnostics.json", provider.history_diagnostics)
        _write_json(target / "methodology_sensitivity.json", sensitivity)
        _write_json(target / "change_digest.json", digest.to_dict())
        _write_json(
            target / "evidence.json",
            [item.model_dump(mode="json") for item in evidence],
        )
        _write_json(target / "tavily_context.json", tavily_report)

        sector_entries = [asdict(entry) for entry in provider.ledger.entries()]
        _write_json(target / "api_credit_audit.json", _credit_audit(sector_entries, provider))
        _write_json(target / "endpoints.json", _endpoint_report(sector_entries))
        provider.ledger.flush()

        if tavily_ledger_path is not None:
            # The Tavily helper flushes its ledger before returning; this
            # branch is only a durable pointer for the snapshot provenance.
            pass

        report = _markdown_report(
            as_of=as_of,
            snapshots=snapshots,
            universe=universe,
            quality=quality,
            coverage=coverage,
            warnings=warnings,
            previous_source=previous_source,
        )
        _write_text(target / "report.md", report)

        reader = SnapshotReader(root=snapshot_root)
        write_manifest(reader.aggregate_manifest(), path=snapshot_root / "manifest.json")
        print(
            f"LIVE_SNAPSHOT_COMPLETE snapshot={snapshot_id} as_of={as_of.isoformat()} "
            f"universe={len(master)} eligible={int(universe['eligible'].sum())} "
            f"quality={quality.status.value} coverage={quality.coverage_pct:.2f}%"
        )
        print(f"snapshot_dir={target}")
        print(json.dumps({"coverage": coverage, "warnings": warnings}, default=str))
        return 0
    except FullLiveGateError as exc:
        if provider is not None:
            provider.ledger.flush()
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "FULL_LIVE",
                    "phase": "data_gate",
                    "blockers": exc.blockers,
                    "next_action": exc.blockers[0]["next_action"],
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    except (ProviderError, ValueError, OSError, KeyError) as exc:
        if provider is not None:
            provider.ledger.flush()
        if args.require_complete:
            message = str(exc)
            code = (
                "CREDIT_BUDGET_EXCEEDED"
                if "credit budget" in message.lower()
                else "LIVE_PROVIDER_REQUEST_FAILED"
            )
            print(
                json.dumps(
                    {
                        "status": "BLOCKED",
                        "mode": "FULL_LIVE",
                        "phase": "request_or_pipeline",
                        "blockers": [
                            {
                                "code": code,
                                "reason": message,
                                "next_action": (
                                    "Review the request ledger and provider response; "
                                    "resolve the cause, then rerun the network-free preflight "
                                    "before approving another live request."
                                ),
                            }
                        ],
                        "next_action": (
                            "Review the request ledger and provider response; resolve the "
                            "cause, then rerun the network-free preflight before approving "
                            "another live request."
                        ),
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
        else:
            print(f"BUILD_BLOCKED {exc}", file=sys.stderr)
        return 2


def _validate_args(args: argparse.Namespace) -> str | None:
    if not args.preflight_only and not args.allow_live:
        return "BLOCKED SECTORS_LIVE requires --allow-live"
    if not args.preflight_only and not args.allow_credit_spend:
        return "BLOCKED live refresh requires --allow-credit-spend"
    if not math.isfinite(args.max_estimated_credits) or args.max_estimated_credits < 0:
        return "BLOCKED --max-estimated-credits must be finite and non-negative"
    if args.max_estimated_credits > DEFAULT_MAX_ESTIMATED_CREDITS:
        return "BLOCKED --max-estimated-credits cannot exceed 1000"
    if not args.preflight_only and not os.environ.get("SECTORS_API_KEY", "").strip():
        return "BLOCKED SECTORS_API_KEY is unavailable (save it in .env or export it)"
    if args.max_pages is not None and args.max_pages < 1:
        return "BLOCKED --max-pages must be at least 1"
    if args.max_symbols is not None and args.max_symbols < 1:
        return "BLOCKED --max-symbols must be at least 1"
    if args.min_history_days < 1:
        return "BLOCKED --min-history-days must be at least 1"
    if args.stale_trading_days < 0:
        return "BLOCKED --stale-trading-days must be non-negative"
    if args.history_workers is not None and args.history_workers < 1:
        return "BLOCKED --history-workers must be at least 1"
    if args.tavily_max_queries < 1:
        return "BLOCKED --tavily-max-queries must be at least 1"
    if args.with_tavily and not args.preflight_only and not os.environ.get("TAVILY_API_KEY", "").strip():
        return "BLOCKED --with-tavily requires TAVILY_API_KEY"
    return None


def _live_credit_preflight(
    *,
    snapshot_root: Path,
    config_path: str,
    requested_as_of: date | None,
    max_pages: int | None,
    max_symbols: int | None,
    max_estimated_credits: float,
) -> dict[str, Any]:
    """Estimate the live runner's baseline reserve without opening HTTP."""

    universe_size, universe_source = _known_live_universe_size(snapshot_root, config_path)
    master_size = universe_size
    if max_pages is not None:
        master_size = min(master_size, max_pages * COMPANIES_PAGE_SIZE)
    history_symbols = min(master_size, max_symbols) if max_symbols is not None else master_size
    company_pages = _bounded_pages(master_size, COMPANIES_PAGE_SIZE, max_pages)
    # Identity and complete-taxonomy structured screener passes are both
    # budgeted. The taxonomy pass can be skipped when direct fields are
    # complete, so this is deliberately conservative.
    company_requests = company_pages * 2
    latest_close_requests = 1
    full_universe_close_pages = _bounded_pages(universe_size, CLOSE_PAGE_SIZE, max_pages)
    components = {
        "companies_identity_and_taxonomy": company_requests,
        "latest_close_probe": latest_close_requests,
        "full_universe_close_pages": full_universe_close_pages,
        "daily_history_calls": history_symbols,
        "native_ihsg_history_call": 1,
        "suspensions_call": 1,
    }
    planned = float(sum(components.values()))
    status = "READY" if planned <= max_estimated_credits else "BLOCKED"
    reason = None
    if status == "BLOCKED":
        reason = (
            f"baseline live reserve {planned:.0f} exceeds cap "
            f"{max_estimated_credits:.0f}; reduce --max-symbols/--max-pages or omit --as-of"
        )
    return {
        "status": status,
        "cap": max_estimated_credits,
        "planned_baseline_reserve": planned,
        "headroom_for_retries": max(0.0, max_estimated_credits - planned),
        "universe_size_for_plan": universe_size,
        "universe_size_source": universe_source,
        "master_size_after_page_cap": master_size,
        "history_symbols_after_cap": history_symbols,
        "components": components,
        "companies_cost_basis": "DOCUMENTED: structured screener = 1 credit per page",
        "retry_policy": "Each retry reserves again; the client hard-stops at the cap.",
        "tavily_cost_scope": "Separate provider budget; excluded from Sectors credits.",
        "reason": reason,
    }


def _bounded_pages(total: int, page_size: int, max_pages: int | None) -> int:
    pages = math.ceil(total / page_size) if total else 0
    return min(pages, max_pages) if max_pages is not None else pages


def _known_live_universe_size(snapshot_root: Path, config_path: str) -> tuple[int, str]:
    """Use persisted discovered-universe metadata before config fallback.

    ``security_master.json`` can intentionally be a prefix sample (for
    example, 500 used rows from 962 discovered rows).  Planning from that
    used-row count would under-reserve the unbounded company pagination path,
    so the preflight prefers the persisted discovered count/diagnostics.
    """

    try:
        reader = SnapshotReader(root=snapshot_root)
        live_candidates: list[tuple[date, Path]] = []
        for path in reader.list_snapshots():
            try:
                manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
                entry = (manifest.get("entries") or [{}])[-1]
                mode = manifest.get("provider_mode") or entry.get("provider_mode")
                if mode != ProviderMode.SECTORS_LIVE.value:
                    continue
                raw_date = entry.get("as_of") or manifest.get("latest_date")
                live_candidates.append((date.fromisoformat(str(raw_date)), path))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
        if live_candidates:
            _, latest = sorted(live_candidates)[-1]
            master = json.loads((latest / "security_master.json").read_text(encoding="utf-8"))
            discovered_candidates: list[int] = []
            for filename, key in (
                ("coverage.json", "discovered_count"),
                ("security_master_diagnostics.json", "unique_rows"),
            ):
                try:
                    payload = json.loads((latest / filename).read_text(encoding="utf-8"))
                except (OSError, TypeError, ValueError, json.JSONDecodeError):
                    continue
                value = payload.get(key) if isinstance(payload, dict) else None
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    value = 0
                if value > 0:
                    discovered_candidates.append(value)
            if isinstance(master, list) and master:
                discovered = max([len(master), *discovered_candidates])
                source = (
                    f"persisted live snapshot {latest.name} discovered metadata"
                    if discovered > len(master)
                    else f"persisted live snapshot {latest.name}"
                )
                return discovered, source
    except (OSError, ValueError, TypeError):
        pass
    try:
        config = load_yaml(config_path)
        fallback = int((config.get("refresh_plan") or {}).get("universe_size", 0))
    except (OSError, TypeError, ValueError):
        fallback = 0
    return max(0, fallback), "config refresh_plan.universe_size"


def _full_live_data_gate(
    *,
    provider: SectorsProvider,
    master: list[Any],
    history_tickers: list[str],
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    current_close: pd.DataFrame,
    quality: QualityReport,
    coverage: dict[str, Any],
    expected_price_basis: str,
    as_of: date,
    min_history_days: int,
) -> list[dict[str, str]]:
    """Return strict full-live blockers without touching snapshot outputs."""

    blockers: list[dict[str, str]] = []

    def add(code: str, reason: str, next_action: str) -> None:
        blockers.append({"code": code, "reason": reason, "next_action": next_action})

    master_pagination = str(
        provider.security_master_diagnostics.get("pagination_completeness") or "UNKNOWN"
    )
    if master_pagination != "COMPLETE":
        add(
            "SECURITY_MASTER_PAGINATION_INCOMPLETE",
            f"security-master pagination is {master_pagination}; the full universe is not certified.",
            "Resolve pagination metadata or provider paging, then rerun full-live preflight and refresh.",
        )

    close_pagination = str(
        provider.close_pagination_diagnostics.get("completeness") or "UNKNOWN"
    )
    if close_pagination != "COMPLETE":
        add(
            "CLOSE_PAGINATION_INCOMPLETE",
            f"market-close pagination is {close_pagination}; the as-of cross-section is not complete.",
            "Fetch every close page for the observed market date, then rerun the full-live gate.",
        )

    history_diagnostics = provider.history_diagnostics or {}
    failed = history_diagnostics.get("failed_symbols") or []
    empty = history_diagnostics.get("empty_symbols") or []
    counts = (
        history.groupby("ticker")["date"].nunique()
        if {"ticker", "date"}.issubset(history.columns)
        else pd.Series(dtype=int)
    )
    insufficient = [
        ticker
        for ticker in history_tickers
        if int(counts.get(ticker, 0)) < min_history_days
    ]
    if failed or empty or insufficient:
        add(
            "HISTORY_INCOMPLETE",
            "history is incomplete: "
            f"failed={len(failed)}, empty={len(empty)}, "
            f"below_{min_history_days}d={len(insufficient)}.",
            "Resolve the provider history failures and rerun; do not use an imputed or alternate-provider prior.",
        )
    if int(history_diagnostics.get("duplicate_symbol_date_rows") or 0) > 0:
        add(
            "HISTORY_DUPLICATES",
            "history contains duplicate ticker/date observations.",
            "Deduplicate or correct the provider response and rerun the full-live gate.",
        )

    if quality.invalid_prices:
        add(
            "INVALID_PRICE_DATA",
            f"{quality.invalid_prices} history rows contain non-positive prices.",
            "Correct or reject invalid provider rows, then rerun the full-live gate.",
        )

    def declared_bases(frame: pd.DataFrame) -> set[str]:
        if "price_basis" not in frame.columns:
            return set()
        return {
            str(value)
            for value in frame["price_basis"].dropna().tolist()
            if str(value).strip()
        }

    basis_frames = {
        "history": declared_bases(history),
        "market close": declared_bases(current_close),
        "benchmark": declared_bases(benchmark),
    }
    bad_basis = {
        label: values
        for label, values in basis_frames.items()
        if values != {expected_price_basis}
    }
    if bad_basis:
        detail = "; ".join(
            f"{label}={sorted(values) if values else ['missing']}"
            for label, values in bad_basis.items()
        )
        add(
            "PRICE_BASIS_UNCERTAIN",
            f"declared price basis does not consistently match {expected_price_basis}: {detail}.",
            "Confirm the provider price-basis contract and rerun; do not relabel a different basis.",
        )

    benchmark_dates = (
        pd.to_datetime(benchmark["date"], errors="coerce").dropna().dt.date
        if "date" in benchmark.columns
        else pd.Series(dtype=object)
    )
    if benchmark.empty or benchmark_dates.empty:
        add(
            "BENCHMARK_MISSING",
            "native IHSG benchmark history is empty or undated.",
            "Resolve the native benchmark endpoint before requesting a full-live snapshot.",
        )
    elif max(benchmark_dates) != as_of:
        add(
            "BENCHMARK_DATE_MISMATCH",
            f"latest IHSG benchmark date is {max(benchmark_dates).isoformat()}, expected {as_of.isoformat()}.",
            "Use a market date with a matching native IHSG observation; do not forward-fill the benchmark.",
        )
    elif str(benchmark.get("source", pd.Series(dtype=object)).iloc[0] if "source" in benchmark.columns and not benchmark.empty else "") != "sectors":
        add(
            "BENCHMARK_SOURCE_INVALID",
            "benchmark is not sourced from the native Sectors endpoint.",
            "Fetch native IHSG history and rerun; do not substitute a Yahoo or cross-sectional proxy.",
        )

    close_dates = (
        pd.to_datetime(current_close["date"], errors="coerce").dropna().dt.date
        if "date" in current_close.columns
        else pd.Series(dtype=object)
    )
    if current_close.empty or close_dates.empty or set(close_dates) != {as_of}:
        add(
            "CLOSE_DATE_MISMATCH",
            f"market-close rows are not a complete dated cross-section for {as_of.isoformat()}.",
            "Fetch the requested market date from the native close endpoint and rerun the gate.",
        )

    missing_taxonomy = int(
        provider.security_master_diagnostics.get("missing_taxonomy_rows") or 0
    )
    if missing_taxonomy:
        add(
            "TAXONOMY_ENRICHMENT_INCOMPLETE",
            f"{missing_taxonomy} security-master rows are missing one or more taxonomy fields.",
            "Complete taxonomy enrichment before publishing the full-live universe.",
        )

    if quality.status.value != "READY":
        add(
            "QUALITY_STATUS_NOT_READY",
            f"overall provider quality is {quality.status.value}; issues={'; '.join(quality.issues[:3]) or 'unreported'}.",
            "Resolve every quality issue, then rerun the network-free preflight before another live request.",
        )

    cap = provider.client.max_estimated_credits
    reserved = provider.client.budget_reserved_credits
    if cap is not None and reserved > float(cap) + 1e-9:
        add(
            "CREDIT_CEILING_EXCEEDED",
            f"reserved request credits {reserved:.2f} exceed the client ceiling {float(cap):.2f}.",
            "Reduce the bounded request or wait for a fresh preflight; never continue past the credit ceiling.",
        )

    # Keep the report useful even if a future provider implementation changes
    # the quality object without updating the detailed checks above.
    if coverage.get("pagination_incomplete") and not any(
        item["code"] in {"SECURITY_MASTER_PAGINATION_INCOMPLETE", "CLOSE_PAGINATION_INCOMPLETE"}
        for item in blockers
    ):
        add(
            "COVERAGE_PAGINATION_INCOMPLETE",
            "coverage diagnostics report incomplete pagination.",
            "Resolve pagination completeness and rerun the full-live gate.",
        )
    return blockers


def _limit_master(master: list[Any], max_symbols: int | None) -> list[Any]:
    if max_symbols is None:
        return master
    return master[:max_symbols]


def _resolve_horizons(methodology: dict[str, Any]) -> dict[str, int]:
    horizons = methodology.get("horizons", {})
    return {
        "5d": int(horizons.get("short", 5)),
        "20d": int(horizons.get("primary", 20)),
        "60d": int(horizons.get("medium", 60)),
    }


def _group_kwargs(
    methodology: dict[str, Any],
    horizons: dict[str, int],
    *,
    price_basis: str | None = None,
) -> dict[str, Any]:
    breadth = methodology.get("breadth", {})
    diffusion = methodology.get("diffusion", {})
    floor = diffusion.get("constituent_floor", {})
    leadership = methodology.get("leadership", {})
    groups = methodology.get("groups", {})
    concentration = methodology.get("concentration", {})
    return {
        "min_constituents": int(groups.get("minimum_constituents", 4)),
        "min_coverage_pct": float(groups.get("minimum_coverage_pct", 60.0)),
        "broadening_threshold_pp": float(breadth.get("broadening_threshold_pp", 10.0)),
        "narrowing_threshold_pp": float(breadth.get("narrowing_threshold_pp", -10.0)),
        "acceleration_threshold_pp": float(leadership.get("acceleration_threshold_pp", 1.0)),
        "excess_return_improving": float(leadership.get("excess_return_improving", 0.0)),
        "excess_return_leading": float(leadership.get("excess_return_leading", 0.0)),
        "concentration_horizon": int(horizons.get("20d", 20)),
        "method_version": str(methodology.get("method_version", "methodology-v1")),
        "feature_version": str(methodology.get("feature_version", "features-v1")),
        "diffusion_mode": str(diffusion.get("mode", "legacy")),
        "diffusion_constituent_fraction": float(floor.get("fraction", 0.10)),
        "diffusion_minimum_constituents": int(floor.get("minimum", 2)),
        "concentration_mode": str(concentration.get("mode", "absolute_move")),
        "concentration_signed_denominator_epsilon": float(
            concentration.get("signed_denominator_epsilon", 1e-8)
        ),
        "concentration_signed_min_net_to_gross": float(
            concentration.get("signed_min_net_to_gross", 0.05)
        ),
        "concentration_price_col": price_basis
        or str(methodology.get("price_basis", "adjusted_close")),
    }


def _resolve_previous_groups(
    *,
    snapshot_root: Path,
    current_as_of: date,
    current_fingerprint: dict[str, Any],
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    taxonomy: pd.DataFrame,
    features_all: pd.DataFrame,
    prices: pd.DataFrame,
    horizons: dict[str, int],
    methodology: dict[str, Any],
) -> tuple[list[GroupSnapshot], dict[str, GroupSnapshot], str | None]:
    """Resolve the previous comparable snapshot.

    The resolver enforces full version compatibility BEFORE selecting a
    candidate. Any prior snapshot whose manifest versions differ from
    the current fingerprint (method, feature, leadership, diffusion,
    concentration, eligibility, universe, taxonomy, or eligible ticker
    set hash) is rejected. Only fully compatible candidates are loaded.
    """
    reader = SnapshotReader(root=snapshot_root)
    candidates: list[tuple[date, Path]] = []
    for path in reader.list_snapshots():
        try:
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entry = (manifest.get("entries") or [{}])[-1]
        mode = manifest.get("provider_mode") or entry.get("provider_mode")
        if mode != ProviderMode.SECTORS_LIVE.value:
            continue
        raw_date = entry.get("as_of") or manifest.get("latest_date")
        try:
            as_of = date.fromisoformat(str(raw_date))
        except (TypeError, ValueError):
            continue
        if as_of < current_as_of:
            candidates.append((as_of, path))
    if candidates:
        # Reject candidates that fail the shared fail-closed compat check.
        # Walk the list sorted newest-first; the first fully compatible
        # candidate wins.
        compatible_candidates: list[tuple[date, Path]] = []
        for cand_date, cand_path in sorted(candidates, reverse=True):
            try:
                cand_manifest = json.loads(
                    (cand_path / "manifest.json").read_text(encoding="utf-8")
                )
                cand_entry = (cand_manifest.get("entries") or [{}])[-1]
            except (OSError, json.JSONDecodeError):
                continue
            result = check_snapshot_compatibility(current_fingerprint, cand_entry)
            if result.comparable:
                compatible_candidates.append((cand_date, cand_path))
        if not compatible_candidates:
            _log.info(
                "compat_gate no compatible prior found"
            )
            return [], {}, None
        previous_date, previous_path = compatible_candidates[0]
        frame = reader.load(previous_path.name).get("groups", pd.DataFrame())
        previous = _groups_from_frame(frame)
        return previous, {item.group_id: item for item in previous}, previous_date.isoformat()

    # No persisted comparable snapshot exists. Do NOT fabricate a multi-snapshot
    # trail from an intra-window prior observation. Return empty and let the
    # caller record INCOMPARABLE_INTRA_WINDOW so the UI can show no trajectory.
    return [], {}, None


def _common_dates(prices: pd.DataFrame, benchmark: pd.DataFrame) -> list[date]:
    if prices.empty or benchmark.empty:
        return []
    left = set(pd.to_datetime(prices["date"], errors="coerce").dropna().dt.date)
    right = set(pd.to_datetime(benchmark["date"], errors="coerce").dropna().dt.date)
    return sorted(left.intersection(right))


def _groups_from_frame(frame: pd.DataFrame) -> list[GroupSnapshot]:
    if frame is None or frame.empty:
        return []
    out: list[GroupSnapshot] = []
    for _, row in frame.iterrows():
        try:
            snapshot_date = pd.Timestamp(row.get("snapshot_date")).date()
        except (TypeError, ValueError):
            continue
        leadership = _enum_or_default(
            LeadershipState, row.get("leadership_state"), LeadershipState.UNCONFIRMED
        )
        diffusion = _enum_or_default(
            DiffusionState, row.get("diffusion_state"), DiffusionState.UNCONFIRMED
        )
        raw_v2 = _clean(row.get("diffusion_state_v2"))
        diffusion_v2 = None
        if raw_v2:
            try:
                diffusion_v2 = DiffusionStateV2(str(raw_v2))
            except ValueError:
                diffusion_v2 = None
        concentration = ConcentrationMetrics(
            top1_contribution_share=_float_or_none(row.get("top1_contribution_share")),
            top3_contribution_share=_float_or_none(row.get("top3_contribution_share")),
            top5_contribution_share=_float_or_none(row.get("top5_contribution_share")),
            top1_signed_share=_float_or_none(row.get("top1_signed_share")),
            top3_signed_share=_float_or_none(row.get("top3_signed_share")),
            hhi_contribution=_float_or_none(row.get("hhi_contribution")),
            convention=str(_clean(row.get("convention")) or "absolute_move"),
            status=str(_clean(row.get("concentration_status")) or "UNDEFINED"),
            signed_attribution_status=str(
                _clean(row.get("signed_attribution_status")) or "UNDEFINED"
            ),
        )
        out.append(
            GroupSnapshot(
                snapshot_date=snapshot_date,
                taxonomy_level=str(_clean(row.get("taxonomy_level")) or "sector"),
                group_id=str(row.get("group_id")),
                group_name=_clean(row.get("group_name")),
                constituent_count=int(_clean(row.get("constituent_count")) or 0),
                eligible_count=int(_clean(row.get("eligible_count")) or 0),
                missing_count=int(_clean(row.get("missing_count")) or 0),
                group_return_equal_weight=_float_or_none(row.get("group_return_equal_weight")),
                group_excess_return=_float_or_none(row.get("group_excess_return")),
                group_excess_return_5d=_float_or_none(row.get("group_excess_return_5d")),
                group_excess_return_20d=_float_or_none(row.get("group_excess_return_20d")),
                group_excess_return_60d=_float_or_none(row.get("group_excess_return_60d")),
                breadth_positive=_float_or_none(row.get("breadth_positive")),
                breadth_outperforming=_float_or_none(row.get("breadth_outperforming")),
                breadth_delta=_float_or_none(row.get("breadth_delta")),
                breadth_total_count=int(_clean(row.get("breadth_total_count")) or 0),
                breadth_eligible_count=int(_clean(row.get("breadth_eligible_count")) or 0),
                breadth_missing_count=int(_clean(row.get("breadth_missing_count")) or 0),
                breadth_positive_count=int(_clean(row.get("breadth_positive_count")) or 0),
                breadth_outperforming_count=int(
                    _clean(row.get("breadth_outperforming_count")) or 0
                ),
                breadth_improving_count=int(_clean(row.get("breadth_improving_count")) or 0),
                concentration=concentration,
                leadership_state=leadership,
                diffusion_state=diffusion,
                diffusion_state_v2=diffusion_v2,
                leadership_rank=_int_or_none(row.get("leadership_rank")),
                change_rank=_int_or_none(row.get("change_rank")),
                leadership_persistence=int(_clean(row.get("leadership_persistence")) or 1),
                diffusion_persistence=int(_clean(row.get("diffusion_persistence")) or 1),
                method_version=str(_clean(row.get("method_version")) or "methodology-v1"),
                feature_version=str(_clean(row.get("feature_version")) or "features-v1"),
            )
        )
    return out


def _build_sensitivity_report(
    *,
    baseline: list[GroupSnapshot],
    master: list[Any],
    universe: pd.DataFrame,
    features_all: pd.DataFrame,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    taxonomy: pd.DataFrame,
    as_of: date,
    horizons: dict[str, int],
    methodology: dict[str, Any],
    previous_groups: list[GroupSnapshot],
    group_kwargs: dict[str, Any],
    price_basis: str,
    default_floor: float | None,
    min_history_days: int,
    stale_trading_days: int,
) -> dict[str, Any]:
    baseline_by_group = {item.group_id: item for item in baseline}
    base_ids = {item.group_id for item in baseline}
    variants: list[dict[str, Any]] = []

    baseline_tickers = set(
        universe.loc[universe["eligible"], "ticker"].astype(str).tolist()
    )

    def run_variant(
        label: str,
        *,
        feature_frame: pd.DataFrame,
        variant_previous: list[GroupSnapshot] | None = previous_groups,
        parameters: dict[str, Any] | None = None,
        **overrides: Any,
    ) -> None:
        kwargs = dict(group_kwargs)
        kwargs.update(overrides)
        result = rank_groups(
            build_group_snapshots(
                features=feature_frame,
                taxonomy=taxonomy,
                snapshot_date=as_of,
                prices=history,
                horizons=horizons,
                previous_groups=variant_previous,
                **kwargs,
            )
        )
        result_by_group = {item.group_id: item for item in result}
        comparable = sorted(base_ids.intersection(result_by_group))
        lead_changed = [
            group
            for group in comparable
            if result_by_group[group].leadership_state
            != baseline_by_group[group].leadership_state
        ]
        diff_changed = [
            group
            for group in comparable
            if result_by_group[group].diffusion_state
            != baseline_by_group[group].diffusion_state
        ]
        agreement = (
            sum(
                result_by_group[group].leadership_state
                == baseline_by_group[group].leadership_state
                and result_by_group[group].diffusion_state
                == baseline_by_group[group].diffusion_state
                for group in comparable
            )
            / len(comparable)
            * 100.0
            if comparable
            else None
        )
        variants.append(
            {
                "label": label,
                "parameters": parameters or overrides,
                "comparable_groups": len(comparable),
                "state_agreement_pct": round(agreement, 2) if agreement is not None else None,
                "leadership_changed_groups": lead_changed,
                "diffusion_changed_groups": diff_changed,
                "result_groups": len(result),
            }
        )

    run_variant(
        "minimum_group_size_2",
        feature_frame=features_all[features_all["ticker"].isin(baseline_tickers)],
        min_constituents=2,
    )
    run_variant(
        "minimum_group_size_6",
        feature_frame=features_all[features_all["ticker"].isin(baseline_tickers)],
        min_constituents=6,
    )
    run_variant(
        "coverage_floor_50_pct",
        feature_frame=features_all[features_all["ticker"].isin(baseline_tickers)],
        min_coverage_pct=50.0,
    )
    run_variant(
        "coverage_floor_75_pct",
        feature_frame=features_all[features_all["ticker"].isin(baseline_tickers)],
        min_coverage_pct=75.0,
    )
    run_variant(
        "breadth_threshold_5pp",
        feature_frame=features_all[features_all["ticker"].isin(baseline_tickers)],
        broadening_threshold_pp=5.0,
        narrowing_threshold_pp=-5.0,
    )
    run_variant(
        "breadth_threshold_15pp",
        feature_frame=features_all[features_all["ticker"].isin(baseline_tickers)],
        broadening_threshold_pp=15.0,
        narrowing_threshold_pp=-15.0,
    )
    run_variant(
        "leadership_acceleration_0_5pp",
        feature_frame=features_all[features_all["ticker"].isin(baseline_tickers)],
        acceleration_threshold_pp=0.5,
    )
    run_variant(
        "leadership_acceleration_2pp",
        feature_frame=features_all[features_all["ticker"].isin(baseline_tickers)],
        acceleration_threshold_pp=2.0,
    )

    def rebuild_eligibility(*, min_days: int, stale_days: int) -> tuple[pd.DataFrame, set[str]]:
        rebuilt = build_market_universe(
            security_master_provider=_StaticMasterProvider(master),
            cross_section_provider=_StaticCrossSectionProvider(),
            event_provider=None,
            as_of=as_of,
            config=EligibilityConfig(
                lookback_history_days=min_days,
                min_history_days=min_days,
                stale_trading_days=stale_days,
                min_median_daily_value=default_floor,
            ),
            price_history=history,
            security_master=master,
        )
        tickers = set(rebuilt.loc[rebuilt["eligible"], "ticker"].astype(str))
        return rebuilt, tickers

    for label, min_days in (("minimum_history_45d", 45), ("minimum_history_75d", 75)):
        rebuilt, tickers = rebuild_eligibility(min_days=min_days, stale_days=stale_trading_days)
        run_variant(
            label,
            feature_frame=features_all[features_all["ticker"].isin(tickers)],
            parameters={
                "min_history_days": min_days,
                "eligible_securities": int(rebuilt["eligible"].sum()),
            },
        )

    for label, stale_days in (("stale_tolerance_7d", 7), ("stale_tolerance_60d", 60)):
        rebuilt, tickers = rebuild_eligibility(min_days=min_history_days, stale_days=stale_days)
        run_variant(
            label,
            feature_frame=features_all[features_all["ticker"].isin(tickers)],
            parameters={
                "stale_trading_days": stale_days,
                "eligible_securities": int(rebuilt["eligible"].sum()),
            },
        )

    alternate_horizons = {"5d": 5, "20d": 10, "60d": 40}
    alternate_features = compute_excess_returns(
        history,
        benchmark,
        horizons=alternate_horizons,
        as_of=as_of,
        security_price_col=price_basis,
        tolerance_days=7,
    ).merge(
        taxonomy.drop(columns=["group_id"], errors="ignore"),
        on="ticker",
        how="left",
    )
    run_variant(
        "lookback_horizon_10d_primary_40d_medium",
        feature_frame=alternate_features[alternate_features["ticker"].isin(baseline_tickers)],
        parameters={"horizons": alternate_horizons},
    )

    no_liquidity_cfg = EligibilityConfig(
        min_history_days=min_history_days,
        stale_trading_days=stale_trading_days,
        min_median_daily_value=None,
    )
    no_liquidity_universe = build_market_universe(
        security_master_provider=_StaticMasterProvider(master),
        cross_section_provider=_StaticCrossSectionProvider(),
        event_provider=None,
        as_of=as_of,
        config=no_liquidity_cfg,
        price_history=history,
        security_master=master,
    )
    no_liq_tickers = set(
        no_liquidity_universe.loc[no_liquidity_universe["eligible"], "ticker"].astype(str)
    )
    run_variant(
        "liquidity_filter_disabled",
        feature_frame=features_all[features_all["ticker"].isin(no_liq_tickers)],
        parameters={
            "min_median_daily_value": None,
            "eligible_securities": int(no_liquidity_universe["eligible"].sum()),
        },
    )
    return {
        "as_of": as_of.isoformat(),
        "baseline": {
            "groups": len(baseline),
            "leadership_states": _state_counts(baseline, "leadership_state"),
            "diffusion_states": _state_counts(baseline, "diffusion_state"),
            "liquidity_floor_idr": default_floor,
        },
        "variants": variants,
        "unsupported_dimensions": [
            {
                "dimension": "weighting_scheme",
                "status": "NOT_APPLICABLE",
                "note": "Current production methodology exposes equal-weight aggregation only; no alternate weighting scheme is supported.",
            }
        ],
        "robustness_note": (
            "Agreement is point-in-time state agreement against the live baseline; "
            "no forward returns were used and no parameter was selected for visual fit."
        ),
    }


class _StaticMasterProvider:
    def __init__(self, master: list[Any]) -> None:
        self._master = master

    def get_security_master(self) -> list[Any]:
        return self._master


class _StaticCrossSectionProvider:
    def get_full_universe_close(self, as_of: date) -> pd.DataFrame:
        return pd.DataFrame()


def _state_counts(items: Iterable[Any], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = getattr(item, field)
        key = value.value if hasattr(value, "value") else str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _run_tavily(
    *, args: argparse.Namespace, snapshots: list[GroupSnapshot], as_of: date
) -> dict[str, Any]:
    if not args.with_tavily:
        return {
            "status": "NOT_REQUESTED",
            "provider": "tavily",
            "quantitative_use": False,
            "responses": [],
            "records": [],
        }
    ledger_path = data_root() / "raw" / "tavily" / f"{as_of.isoformat()}_request_ledger.jsonl"
    client = TavilyClient(
        allow_live=True,
        ledger=RequestLedger(path=ledger_path),
        # Bound every HTTP attempt, including retries, while allowing the
        # requested number of basic queries to complete in the normal path.
        max_http_requests=max(
            1,
            int(args.tavily_max_queries)
            * (TavilyClient.DEFAULT_MAX_RETRIES + 1),
        ),
    )
    queries = [
        (
            "Indonesia Stock Exchange IDX sector classification official taxonomy",
            ["idx.co.id", "ojk.go.id", "docs.sectors.app"],
        )
    ]
    leaders = [
        item
        for item in snapshots
        if item.leadership_state in {LeadershipState.LEADING, LeadershipState.IMPROVING}
    ]
    if leaders and len(queries) < args.tavily_max_queries:
        group = leaders[0].group_id.replace("_", " ")
        queries.append(
            (
                f"Indonesia {group} sector market context official {as_of.isoformat()}",
                ["idx.co.id", "ojk.go.id", "sectors.app"],
            )
        )
    responses: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for query, domains in queries[: args.tavily_max_queries]:
        try:
            response = client.search(
                query,
                search_depth="basic",
                topic="finance",
                max_results=3,
                include_domains=domains,
                include_answer=False,
                include_raw_content=False,
            )
            responses.append(response.to_dict())
            records.extend(_context_records(response))
        except TavilyError as exc:
            errors.append(
                {
                    "code": exc.code,
                    "status": exc.status,
                    "endpoint": exc.endpoint,
                    "message": str(exc),
                }
            )
    client.ledger.flush()
    return {
        "status": "READY" if responses and not errors else ("PARTIAL" if responses else "FAILED"),
        "provider": "tavily",
        "quantitative_use": False,
        "as_of": as_of.isoformat(),
        "responses": responses,
        "records": records,
        "errors": errors,
        "ledger_path": str(ledger_path),
        "http_requests_made": client.http_requests_made,
        "max_http_requests": client.max_http_requests,
        "source_policy": ["idx.co.id", "ojk.go.id", "sectors.app", "docs.sectors.app"],
    }


def _context_records(response: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in response.results:
        records.append(
            {
                "source_type": "WEB_CONTEXT",
                "provider": "tavily",
                "url": result.get("url"),
                "title": result.get("title"),
                "content": result.get("content"),
                "relevance_score": result.get("score"),
                "retrieved_at": response.retrieved_at,
                "request_id": response.request_id,
                "quantitative_use": False,
            }
        )
    return records


def _build_comparability(
    *,
    as_of: date,
    previous_source: str | None,
    previous_groups: list[GroupSnapshot],
    snapshot_root: Path,
    universe: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Emit structured comparability metadata for every snapshot."""
    from idx_leadership.data.snapshots import SnapshotReader

    reasons: list[str] = []
    selected_previous: str | None = None
    warnings: list[str] = []
    comparable = False

    reader = SnapshotReader(root=snapshot_root)
    candidates: list[tuple[date, Path]] = []
    for path in reader.list_snapshots():
        try:
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entry = (manifest.get("entries") or [{}])[-1]
        mode = manifest.get("provider_mode") or entry.get("provider_mode")
        if mode != ProviderMode.SECTORS_LIVE.value:
            continue
        raw_date = entry.get("as_of") or manifest.get("latest_date")
        try:
            as_of_d = date.fromisoformat(str(raw_date))
        except (TypeError, ValueError):
            continue
        if as_of_d < as_of:
            candidates.append((as_of_d, path))

    # Read the current snapshot's manifest for the "current" side of the
    # comparability check. Without this, both sides would use the previous
    # snapshot's version stamps and the check would trivially pass.
    current_entry: dict[str, Any] = {}
    snapshot_id = f"snap_sectors_{as_of.isoformat()}"
    current_manifest_path = snapshot_root / snapshot_id / "manifest.json"
    if current_manifest_path.exists():
        try:
            current_manifest = json.loads(
                current_manifest_path.read_text(encoding="utf-8")
            )
            current_entry = (current_manifest.get("entries") or [{}])[-1]
        except (OSError, json.JSONDecodeError):
            pass

    # P2 fix: current-side metadata must be fail-closed. A missing or
    # incomplete current manifest must NOT yield COMPATIBLE.
    if not current_entry:
        comparable = False
        reasons.append(
            "current manifest missing or unreadable (fail-closed)"
        )
    else:
        # P1 fix: _build_comparability must use the shared
        # check_snapshot_compatibility helper, which checks provider_mode
        # and all required fields including eligible_ticker_set_hash.
        # This replaces the duplicated manual compat loop below.
        if previous_source and previous_groups:
            try:
                prior_path = snapshot_root / previous_source
                if prior_path.exists():
                    prior_manifest = json.loads(
                        (prior_path / "manifest.json").read_text(encoding="utf-8")
                    )
                    prior_entry = (prior_manifest.get("entries") or [{}])[-1]
                    result = check_snapshot_compatibility(current_entry, prior_entry)
                    if result.comparable:
                        comparable = True
                        selected_previous = previous_source
                    else:
                        reasons.extend(result.reasons)
                else:
                    reasons.append("previous snapshot manifest not found")
            except (OSError, json.JSONDecodeError):
                reasons.append("previous manifest unreadable")

    if not comparable and not reasons:
        reasons.append("no persisted comparable snapshot found")
        warnings.append(
            "intra-window prior observation is not multi-snapshot history; "
            "trajectory UI disabled"
        )

    return {
        "as_of": as_of.isoformat(),
        "comparison_kind": "persisted_snapshot" if comparable else "none",
        "status": "COMPATIBLE" if comparable else "INCOMPARABLE",
        "selected_previous": selected_previous,
        "previous_intra_window_source": previous_source,
        "previous_groups": [g.group_id for g in previous_groups],
        "reasons": reasons,
        "warnings": warnings,
        "policy_universe_hash": hashlib.sha256(
            json.dumps(
                {
                    "provider_mode": ProviderMode.SECTORS_LIVE.value,
                    "universe_version": "sectors-v2-live",
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16],
        "eligible_ticker_set_hash": current_entry.get("eligible_ticker_set_hash", "EMPTY"),
        "eligible_ticker_count": current_entry.get("eligible_ticker_count", 0),
        "raw_ticker_count": current_entry.get("raw_ticker_count", 0),
    }


def _coverage_report(
    *,
    master: list[Any],
    universe: pd.DataFrame,
    history: pd.DataFrame,
    quality: QualityReport,
    as_of: date,
    provider: SectorsProvider,
    requested_history_tickers: list[str],
    min_history_days: int,
) -> dict[str, Any]:
    complete_taxonomy = universe[list(("sector", "subsector", "industry", "subindustry"))].notna().all(axis=1)
    latest_dates = pd.to_datetime(history["date"], errors="coerce") if not history.empty else pd.Series(dtype="datetime64[ns]")
    latest_trade = latest_dates.max().date().isoformat() if not latest_dates.dropna().empty else None
    counts = history.groupby("ticker")["date"].nunique() if not history.empty else pd.Series(dtype=int)
    usable = int(sum(int(counts.get(ticker, 0)) >= min_history_days for ticker in requested_history_tickers))
    stale_count = 0
    if not universe.empty and "latest_trade_date" in universe.columns:
        parsed = pd.to_datetime(universe["latest_trade_date"], errors="coerce")
        stale_count = int(((pd.Timestamp(as_of) - parsed).dt.days > 30).fillna(False).sum())
    acq_col = universe.get("acquisition_status")
    policy_excluded = 0
    acq_failed = 0
    acq_empty = 0
    acquired = 0
    if acq_col is not None:
        policy_excluded = int((acq_col == "POLICY_EXCLUDED").sum())
        acq_failed = int((acq_col == "ACQUISITION_FAILED").sum())
        acq_empty = int((acq_col == "ACQUISITION_EMPTY").sum())
        acquired = int((acq_col == "ACQUIRED").sum())
    policy_eligible = (len(universe) - policy_excluded) if not universe.empty else 0
    # observed_eligible_features: only tickers with usable features
    # (ACQUIRED). Acquisition failures and empties are in the denominator
    # as missing data, not in the numerator.
    observed_eligible_features = acquired
    # Prefix sample disclosure: when max_symbols caps the universe, the
    # coverage report must make the partial-sample nature visible.
    raw_discovered_count = provider.security_master_diagnostics.get("unique_rows")
    try:
        discovered_count = int(raw_discovered_count)
    except (TypeError, ValueError):
        discovered_count = len(master)
    # Discovery metadata is advisory. Never let a malformed or stale value
    # claim that the used sample is larger than the rows actually loaded.
    discovered_count = max(len(master), discovered_count)
    is_prefix_sample = len(master) < discovered_count
    master_pagination = list(provider.security_master_diagnostics.get("pagination") or [])
    close_pagination = (
        [dict(provider.close_pagination_diagnostics)]
        if provider.close_pagination_diagnostics
        else []
    )
    master_pagination_completeness = _pagination_completeness(master_pagination)
    close_pagination_completeness = _pagination_completeness(close_pagination)
    return {
        "as_of": as_of.isoformat(),
        "provider": "Sectors v2",
        "provider_mode": ProviderMode.SECTORS_LIVE.value,
        "is_prefix_sample": is_prefix_sample,
        "discovered_count": discovered_count,
        "used_count": len(master),
        "discovered_universe_disclosure": (
            f"Partial universe: {len(master)} of {discovered_count} discovered; "
            "prefix sample; not full IDX coverage."
            if is_prefix_sample
            else f"Full universe: {len(master)} of {discovered_count} discovered."
        ),
        "security_master_pagination_completeness": master_pagination_completeness,
        "close_pagination_completeness": close_pagination_completeness,
        "pagination_incomplete": (
            master_pagination_completeness in {"PARTIAL", "UNKNOWN"}
            or close_pagination_completeness in {"PARTIAL", "UNKNOWN"}
        ),
        "security_master_total": len(master),
        "history_requested_securities": len(requested_history_tickers),
        "securities_with_any_price_history": int(history["ticker"].nunique()) if not history.empty else 0,
        "securities_with_usable_price_history": usable,
        "eligible_securities": int(universe["eligible"].sum()) if not universe.empty else 0,
        "excluded_securities": int((~universe["eligible"]).sum()) if not universe.empty else 0,
        "exclusion_reasons": (
            universe.loc[~universe["eligible"], "exclusion_reason"].value_counts().to_dict()
            if not universe.empty
            else {}
        ),
        "taxonomy_complete_securities": int(complete_taxonomy.sum()) if not universe.empty else 0,
        "taxonomy_coverage_pct": round(float(complete_taxonomy.mean() * 100.0), 2) if not universe.empty else 0.0,
        "latest_available_security_trade_date": latest_trade,
        "latest_available_benchmark_date": quality.benchmark_latest_date.isoformat() if quality.benchmark_latest_date else None,
        "stale_security_count": stale_count,
        "duplicate_rows": quality.duplicate_ticker_date_rows,
        "price_history_coverage_pct": round(
            usable / max(1, len(requested_history_tickers)) * 100.0, 2
        ),
        "raw_candidate_constituents": len(universe) if not universe.empty else 0,
        "policy_eligible_constituents": policy_eligible,
        "policy_excluded_constituents": policy_excluded,
        "acquisition_failed_constituents": acq_failed,
        "acquisition_empty_constituents": acq_empty,
        "acquired_constituents": acquired,
        "observed_eligible_features": observed_eligible_features,
        "coverage_pct": round(
            (observed_eligible_features / max(1, policy_eligible)) * 100.0, 2
        ) if policy_eligible > 0 else 0.0,
        "coverage_gate_60pct_met": (
            (observed_eligible_features / max(1, policy_eligible)) >= 0.60
        ) if policy_eligible > 0 else False,
        "security_master_diagnostics": provider.security_master_diagnostics,
        "history_diagnostics": provider.history_diagnostics,
    }


def _pagination_completeness(diagnostics: list[dict[str, Any]]) -> str | None:
    """Roll up endpoint pagination without treating missing metadata as complete."""

    if not diagnostics:
        return None
    values = {str(item.get("completeness") or "UNKNOWN") for item in diagnostics}
    if "PARTIAL" in values:
        return "PARTIAL"
    if "UNKNOWN" in values:
        return "UNKNOWN"
    return "COMPLETE" if values == {"COMPLETE"} else "UNKNOWN"


def _data_warnings(
    *,
    provider: SectorsProvider,
    universe: pd.DataFrame,
    quality: QualityReport,
    current_close: pd.DataFrame,
    as_of: date,
    suspension_warning: str | None,
) -> list[str]:
    warnings = list(quality.issues)
    if suspension_warning:
        warnings.append(suspension_warning)
    diagnostics = provider.security_master_diagnostics
    if diagnostics.get("instrument_classification_unverified_rows"):
        warnings.append("instrument_type=UNKNOWN / VERIFY for company rows without an explicit instrument field")
    if diagnostics.get("missing_taxonomy_rows"):
        warnings.append(f"missing_taxonomy_rows={diagnostics['missing_taxonomy_rows']}")
    if diagnostics.get("duplicate_ticker_rows"):
        warnings.append(f"duplicate_ticker_rows={diagnostics['duplicate_ticker_rows']}")
    if diagnostics.get("pagination_completeness") in {"PARTIAL", "UNKNOWN"}:
        warnings.append(
            "security_master_pagination="
            f"{diagnostics['pagination_completeness']}"
        )
    close_pagination = provider.close_pagination_diagnostics
    if close_pagination.get("completeness") in {"PARTIAL", "UNKNOWN"}:
        warnings.append(f"close_pagination={close_pagination.get('completeness')}")
    if not current_close.empty and "date" in current_close.columns:
        dates = pd.to_datetime(current_close["date"], errors="coerce").dropna()
        if not dates.empty and dates.max().date() != as_of:
            warnings.append(
                f"close_latest_date_mismatch={dates.max().date().isoformat()} expected={as_of.isoformat()}"
            )
    warnings.append("Sectors close is treated as raw close; corporate-action adjustment semantics are UNKNOWN / VERIFY")
    return list(dict.fromkeys(str(item) for item in warnings if item))


def _enrich_master(master: list[Any], history: pd.DataFrame) -> list[Any]:
    if history.empty:
        return master
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["daily_value"] = pd.to_numeric(frame.get("close"), errors="coerce") * pd.to_numeric(
        frame.get("volume"), errors="coerce"
    )
    grouped = frame.dropna(subset=["ticker", "date"]).groupby("ticker")
    updates: dict[str, dict[str, Any]] = {}
    for ticker, rows in grouped:
        valid_value = rows["daily_value"].dropna()
        latest = rows.sort_values("date").iloc[-1]
        updates[str(ticker)] = {
            "first_trade_date": rows["date"].min().date(),
            "last_trade_date": rows["date"].max().date(),
            "market_cap": _float_or_none(latest.get("market_cap")),
            "average_daily_value": _float_or_none(valid_value.mean()) if not valid_value.empty else None,
        }
    return [item.model_copy(update=updates.get(item.ticker, {})) for item in master]


def _provenance(
    *,
    provider: SectorsProvider,
    as_of: date,
    quality: QualityReport,
    coverage: dict[str, Any],
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    current_close: pd.DataFrame,
    previous_source: str | None,
) -> dict[str, Any]:
    return {
        "provider": "Sectors",
        "provider_mode": ProviderMode.SECTORS_LIVE.value,
        "as_of": as_of.isoformat(),
        "universe_endpoint": "/v2/companies/",
        "taxonomy_endpoint": "/v2/companies/?where=...&include_query_values=true",
        "price_endpoint": "/v2/daily/{symbol}/",
        "benchmark_endpoint": "/v2/index-daily/ihsg/",
        "current_close_endpoint": "/v2/close/",
        "benchmark_source": str(benchmark["source"].iloc[0]) if not benchmark.empty and "source" in benchmark.columns else "sectors",
        "price_basis": "close (raw; adjusted semantics UNKNOWN / VERIFY)",
        "security_history_latest": _latest_date(history).isoformat() if _latest_date(history) else None,
        "current_close_latest": _latest_date(current_close).isoformat() if _latest_date(current_close) else None,
        "quality_status": quality.status.value,
        "coverage": coverage,
        "previous_comparison": previous_source,
        "credit_balance": "UNAVAILABLE — only request ledger estimates are recorded",
        "instrument_type": "UNKNOWN / VERIFY unless explicit vendor field or obvious non-common marker exists",
    }


def _credit_audit(entries: list[dict[str, Any]], provider: SectorsProvider) -> dict[str, Any]:
    by_endpoint: dict[str, dict[str, Any]] = {}
    for entry in entries:
        endpoint = str(entry.get("endpoint", "UNKNOWN"))
        bucket = by_endpoint.setdefault(
            endpoint,
            {
                "requests": 0,
                "cache_hits": 0,
                "estimated_credits": 0.0,
                "budget_reserved_credits": 0.0,
                "statuses": {},
            },
        )
        bucket["requests"] += 1
        bucket["cache_hits"] += int(bool(entry.get("cache_hit")))
        bucket["estimated_credits"] += float(entry.get("estimated_credit_cost") or 0.0)
        bucket["budget_reserved_credits"] += float(
            entry.get("budget_reserved_credit_cost") or 0.0
        )
        status = str(entry.get("status", "UNKNOWN"))
        bucket["statuses"][status] = bucket["statuses"].get(status, 0) + 1
    documented_total = round(
        sum(float(item.get("estimated_credit_cost") or 0.0) for item in entries), 2
    )
    reserved_total = round(
        sum(float(item.get("budget_reserved_credit_cost") or 0.0) for item in entries),
        2,
    )
    return {
        "provider_mode": ProviderMode.SECTORS_LIVE.value,
        "ledger_path": str(provider.ledger.path),
        "ledger_entries": len(entries),
        "requests": sum(int(item["requests"]) for item in by_endpoint.values()),
        "cache_hits": sum(int(item["cache_hits"]) for item in by_endpoint.values()),
        "estimated_credits_total": documented_total,
        "budget_reserved_credits_total": reserved_total,
        "budget_limit": provider.client.max_estimated_credits,
        "credit_balance": "UNAVAILABLE",
        "by_endpoint": by_endpoint,
        "note": (
            "Estimated credits use documented per-endpoint rules. The separate "
            "budget reserve includes retry attempts and is a client-side ceiling; "
            "balance/actual debit was not exposed to this client."
        ),
    }


def _endpoint_report(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "provider": "sectors",
            "endpoint": entry.get("endpoint"),
            "status": entry.get("status"),
            "rows": entry.get("rows_returned"),
            "cache_hit": entry.get("cache_hit"),
            "estimated_credit_cost": entry.get("estimated_credit_cost"),
            "budget_reserved_credit_cost": entry.get("budget_reserved_credit_cost"),
            "error": entry.get("error"),
        }
        for entry in entries
    ]


def _markdown_report(
    *,
    as_of: date,
    snapshots: list[GroupSnapshot],
    universe: pd.DataFrame,
    quality: QualityReport,
    coverage: dict[str, Any],
    warnings: list[str],
    previous_source: str | None,
) -> str:
    lines = [
        f"# Live Sectors Market Snapshot — {as_of.isoformat()}",
        "",
        "- **Provider:** Sectors v2 (`SECTORS_LIVE`)",
        "- **Benchmark:** Sectors native `/v2/index-daily/ihsg/`",
        f"- **Universe:** {coverage['security_master_total']} discovered; {coverage['eligible_securities']} eligible",
        f"- **Price-history coverage:** {coverage['price_history_coverage_pct']:.2f}% usable",
        f"- **Quality:** {quality.status.value} ({quality.coverage_pct:.2f}%)",
        f"- **Comparison observation:** {previous_source or 'none'}",
        "",
        "## Group leadership / diffusion",
        "",
        "| group | leadership | diffusion | excess 20D | breadth | eligible / total | rank |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in snapshots:
        diffusion = item.diffusion_state_v2.value if item.diffusion_state_v2 else item.diffusion_state.value
        excess = "—" if item.group_excess_return is None else f"{item.group_excess_return:.2f}%"
        breadth = "—" if item.breadth_outperforming is None else f"{item.breadth_outperforming:.1f}%"
        lines.append(
            f"| {item.group_id} | {item.leadership_state.value} | {diffusion} | {excess} | {breadth} | "
            f"{item.eligible_count} / {item.constituent_count} | {item.leadership_rank or '—'} |"
        )
    lines.extend(["", "## Exclusions", ""])
    exclusions = universe.loc[~universe["eligible"], "exclusion_reason"].value_counts().to_dict()
    if exclusions:
        lines.extend(f"- `{reason}`: {count}" for reason, count in exclusions.items())
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _snapshots_to_df(snapshots: Iterable[GroupSnapshot]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in snapshots:
        rows.append(
            {
                "snapshot_date": item.snapshot_date,
                "taxonomy_level": item.taxonomy_level,
                "taxonomy_path": "|".join(item.taxonomy_path),
                "group_id": item.group_id,
                "group_name": item.group_name,
                "constituent_count": item.constituent_count,
                "raw_candidate_count": item.raw_candidate_count,
                "policy_eligible_count": item.policy_eligible_count,
                "acquisition_failed_count": item.acquisition_failed_count,
                "eligible_count": item.eligible_count,
                "missing_count": item.missing_count,
                "coverage_pct": round(
                    (item.eligible_count / max(1, item.policy_eligible_count)) * 100.0, 2
                ) if item.policy_eligible_count > 0 else 0.0,
                "coverage_gate_60pct_met": (
                    (item.eligible_count / max(1, item.policy_eligible_count)) >= 0.60
                ) if item.policy_eligible_count > 0 else False,
                "group_return_equal_weight": item.group_return_equal_weight,
                "leadership_state": item.leadership_state.value,
                "diffusion_state": item.diffusion_state.value,
                "diffusion_state_v2": item.diffusion_state_v2.value if item.diffusion_state_v2 else None,
                "group_excess_return": item.group_excess_return,
                "group_excess_return_5d": item.group_excess_return_5d,
                "group_excess_return_20d": item.group_excess_return_20d,
                "group_excess_return_60d": item.group_excess_return_60d,
                "breadth_positive": item.breadth_positive,
                "breadth_outperforming": item.breadth_outperforming,
                "breadth_delta": item.breadth_delta,
                "breadth_total_count": item.breadth_total_count,
                "breadth_eligible_count": item.breadth_eligible_count,
                "breadth_missing_count": item.breadth_missing_count,
                "breadth_positive_count": item.breadth_positive_count,
                "breadth_outperforming_count": item.breadth_outperforming_count,
                "breadth_improving_count": item.breadth_improving_count,
                "leadership_rank": item.leadership_rank,
                "change_rank": item.change_rank,
                "leadership_persistence": item.leadership_persistence,
                "diffusion_persistence": item.diffusion_persistence,
                "top1_contribution_share": item.concentration.top1_contribution_share,
                "top3_contribution_share": item.concentration.top3_contribution_share,
                "top5_contribution_share": item.concentration.top5_contribution_share,
                "top1_signed_share": item.concentration.top1_signed_share,
                "top3_signed_share": item.concentration.top3_signed_share,
                "hhi_contribution": item.concentration.hhi_contribution,
                "convention": item.concentration.convention,
                "concentration_status": item.concentration.status,
                "signed_attribution_status": item.concentration.signed_attribution_status,
                "method_version": item.method_version,
                "feature_version": item.feature_version,
            }
        )
    return pd.DataFrame(rows)


def _transitions_to_df(transitions: Iterable[Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in transitions:
        rows.append(
            {
                "current_date": item.current_date,
                "previous_date": item.previous_date,
                "taxonomy_level": item.taxonomy_level,
                "group_id": item.group_id,
                "previous_leadership_state": item.previous_leadership_state.value,
                "current_leadership_state": item.current_leadership_state.value,
                "previous_diffusion_state": item.previous_diffusion_state.value,
                "current_diffusion_state": item.current_diffusion_state.value,
                "previous_diffusion_state_v2": item.previous_diffusion_state_v2.value if item.previous_diffusion_state_v2 else None,
                "current_diffusion_state_v2": item.current_diffusion_state_v2.value if item.current_diffusion_state_v2 else None,
                "diffusion_transition_v2": item.diffusion_transition_v2,
                "leadership_transition": item.leadership_transition,
                "diffusion_transition": item.diffusion_transition,
                "breadth_delta": item.breadth_delta,
                "relative_strength_delta": item.relative_strength_delta,
                "rank_delta": item.rank_delta,
                "materiality_label": item.materiality_label.value,
                "materiality_reason": item.materiality_reason,
            }
        )
    return pd.DataFrame(rows)


def _latest_date(frame: pd.DataFrame) -> date | None:
    if frame is None or frame.empty or "date" not in frame.columns:
        return None
    values = pd.to_datetime(frame["date"], errors="coerce").dropna()
    return values.max().date() if not values.empty else None


def _enum_or_default(enum_type: Any, value: Any, default: Any) -> Any:
    try:
        return enum_type(str(_clean(value)))
    except (TypeError, ValueError):
        return default


def _clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _float_or_none(value: Any) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if pd.notna(result) else None


def _int_or_none(value: Any) -> int | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(path)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temp, index=False)
    temp.replace(path)


if __name__ == "__main__":
    sys.exit(main())
