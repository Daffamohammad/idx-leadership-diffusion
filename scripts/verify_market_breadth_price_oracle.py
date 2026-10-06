"""Independently reconcile price-based market breadth against its price vintage."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def verify(*, market_path: Path, prices_path: Path, benchmark_path: Path,
           breadth_path: Path, source_manifest_path: Path, validation_path: Path) -> dict[str, Any]:
    market = _read(market_path)
    breadth = _read(breadth_path)
    source_manifest = _read(source_manifest_path)
    validation = _read(validation_path)
    as_of = str(market.get("as_of", ""))
    if not as_of or breadth.get("as_of") != as_of:
        raise ValueError("market, breadth, and selected dates do not agree")

    price_hash = _sha(prices_path)
    benchmark_hash = _sha(benchmark_path)
    source_manifest_hash = _sha(source_manifest_path)
    validation_hash = _sha(validation_path)
    panel_files = {
        "prices.csv": price_hash,
        "benchmark.csv": benchmark_hash,
        "source_manifest.json": source_manifest_hash,
    }
    recorded_files = {
        name: (source_manifest.get("files", {}).get(name) or {}).get("sha256")
        for name in panel_files
        if name in {"prices.csv", "benchmark.csv"}
    }
    validation_inputs = (validation.get("input_hashes") or {}).get("panel_files")
    if recorded_files != {key: panel_files[key] for key in recorded_files}:
        raise ValueError("source manifest does not bind the supplied price and benchmark files")
    if validation.get("status") != "PASS" or validation_inputs != panel_files:
        raise ValueError("PASS validation report does not bind the supplied panel files")
    recorded_sources = breadth.get("sources") or {}
    if (
        recorded_sources.get("adjusted_price_panel_sha256") != price_hash
        or recorded_sources.get("ihsg_panel_sha256") != benchmark_hash
    ):
        raise ValueError("breadth asset does not bind the supplied price and benchmark files")

    prices = pd.read_csv(prices_path, parse_dates=["date"])
    benchmark = pd.read_csv(benchmark_path, parse_dates=["date"])
    required_price = {"ticker", "date", "close", "adjusted_close"}
    if not required_price.issubset(prices.columns) or not {"date", "close"}.issubset(benchmark.columns):
        raise ValueError("panel is missing adjusted stock or benchmark closes")
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    prices["date"] = prices["date"].dt.strftime("%Y-%m-%d")
    benchmark["date"] = benchmark["date"].dt.strftime("%Y-%m-%d")
    if prices.duplicated(["ticker", "date"]).any() or benchmark.duplicated(["date"]).any():
        raise ValueError("panel contains duplicate ticker/date or benchmark-date rows")
    if (
        prices["close"].isna().any()
        or not prices["close"].map(math.isfinite).all()
        or (prices["close"] <= 0).any()
        or prices["adjusted_close"].isna().any()
        or not prices["adjusted_close"].map(math.isfinite).all()
        or (prices["adjusted_close"] <= 0).any()
        or benchmark["close"].isna().any()
        or not benchmark["close"].map(math.isfinite).all()
        or (benchmark["close"] <= 0).any()
    ):
        raise ValueError("panel contains missing or non-positive prices")

    benchmark_sessions = sorted(benchmark["date"].astype(str).unique())
    if not benchmark_sessions or benchmark_sessions[-1] != as_of or as_of not in benchmark_sessions:
        raise ValueError("benchmark sessions do not end on the selected date")
    benchmark_session_set = set(benchmark_sessions)
    off_benchmark_prices = prices[~prices["date"].astype(str).isin(benchmark_session_set)]
    off_benchmark_dates = sorted(off_benchmark_prices["date"].astype(str).unique())
    target_index = benchmark_sessions.index(as_of)
    close = prices.pivot(index="ticker", columns="date", values="adjusted_close")
    traded = {
        str(row["ticker"]).upper()
        for row in market.get("records", [])
        if row.get("traded") is True and row.get("last_trade_date", as_of) == as_of
    }
    cutoff = (date.fromisoformat(as_of) - timedelta(weeks=52)).isoformat()
    windows = {
        "5d": benchmark_sessions[max(0, target_index - 5):target_index],
        "20d": benchmark_sessions[max(0, target_index - 20):target_index],
        "60d": benchmark_sessions[max(0, target_index - 60):target_index],
        "52w": [day for day in benchmark_sessions if cutoff <= day < as_of],
    }
    if benchmark_sessions[0] > cutoff:
        raise ValueError("benchmark vintage starts after the 52-calendar-week cutoff")
    ytd_base = str((source_manifest.get("sessions") or {}).get("ytd_baseline_date", ""))
    if not ytd_base or ytd_base not in benchmark_sessions:
        raise ValueError("prior-year YTD baseline is not an observed benchmark session")
    diagnostics = source_manifest.get("diagnostics") or {}
    failed_symbols = sorted(str(ticker).upper() for ticker in diagnostics.get("failed_symbols", []))
    quarantined_symbols = sorted(str(ticker).upper() for ticker in diagnostics.get("quarantined_symbols", []))
    requested_count = int((source_manifest.get("counts") or {}).get("requested", 0))
    downloaded_count = int((source_manifest.get("counts") or {}).get("downloaded", 0))
    if (
        prices["ticker"].nunique() != downloaded_count
        or len(failed_symbols) != int((source_manifest.get("counts") or {}).get("failed", -1))
        or len(quarantined_symbols) != int((source_manifest.get("counts") or {}).get("quarantined", 0))
        or set(failed_symbols).intersection(quarantined_symbols)
        or downloaded_count + len(failed_symbols) + len(quarantined_symbols) != requested_count
    ):
        raise ValueError("requested, downloaded, failed, and quarantined ticker counts do not reconcile")

    requested_start = str((source_manifest.get("window") or {}).get("start", ""))
    observed_start = str(prices["date"].min())
    analysis_start = max(requested_start, observed_start)
    analysis_sessions = [day for day in benchmark_sessions if analysis_start <= day <= as_of]
    if not analysis_sessions or analysis_sessions[-1] != as_of:
        raise ValueError("fixed-cohort analysis window does not reach the selected session")
    signal_tickers = {
        str(row["ticker"]).upper()
        for row in market.get("records", [])
        if row.get("signal_eligible") is True
    }
    complete = close.reindex(columns=analysis_sessions).notna().all(axis=1)
    fixed_tickers = sorted(signal_tickers.intersection(close.index[complete].astype(str)))
    fixed_breadth = breadth.get("historical_price_breadth") or {}
    fixed_ticker_hash = hashlib.sha256(json.dumps(fixed_tickers, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if (
        fixed_tickers != fixed_breadth.get("cohort_tickers")
        or len(fixed_tickers) != fixed_breadth.get("cohort_count")
        or fixed_ticker_hash != fixed_breadth.get("cohort_sha256")
        or fixed_breadth.get("start") != analysis_sessions[0]
        or fixed_breadth.get("end") != analysis_sessions[-1]
        or len(fixed_breadth.get("sessions", [])) != len(analysis_sessions)
    ):
        raise ValueError("fixed price cohort or its session bounds differ from the independent reconstruction")
    fixed_prices = close.loc[fixed_tickers, analysis_sessions]
    fixed_path_checks = 0
    for index, day in enumerate(analysis_sessions):
        actual = fixed_breadth["sessions"][index]
        if actual.get("as_of") != day or actual.get("eligible_count") != len(fixed_tickers):
            raise ValueError(f"fixed price breadth session identity or denominator differs on {day}")
        if index == 0:
            expected = {"advancers": None, "unchanged": None, "decliners": None, "net_advances": None, "moving_count": 0}
        else:
            returns = fixed_prices[day] / fixed_prices[analysis_sessions[index - 1]] - 1.0
            up = int((returns > 0).sum())
            flat = int((returns == 0).sum())
            down = int((returns < 0).sum())
            expected = {"advancers": up, "unchanged": flat, "decliners": down, "net_advances": up - down, "moving_count": up + down}
        if any(actual.get(key) != value for key, value in expected.items()):
            raise ValueError(f"fixed price breadth counts differ from independent calculation on {day}")
        fixed_path_checks += 1

    reported = breadth.get("new_highs_lows", {}).get("items", {})
    if set(windows) - set(reported):
        raise ValueError("breadth asset is missing one or more supported horizons")
    outcomes: dict[str, Any] = {}
    for horizon, prior_dates in windows.items():
        if not prior_dates:
            raise ValueError(f"no prior benchmark sessions for {horizon}")
        actual = reported[horizon]
        expected_start = prior_dates[0]
        expected_end = prior_dates[-1]
        if actual.get("start") != expected_start or actual.get("end") != expected_end:
            raise ValueError(f"{horizon} range dates do not match observed benchmark sessions")
        current = close.get(as_of, pd.Series(dtype=float))
        eligible: list[str] = []
        highs: list[str] = []
        lows: list[str] = []
        for ticker in sorted(traded):
            if ticker not in close.index or ticker not in current.index or pd.isna(current.loc[ticker]):
                continue
            if any(day not in close.columns for day in prior_dates):
                continue
            prior = close.loc[ticker, prior_dates]
            if prior.isna().any():
                continue
            eligible.append(ticker)
            if float(current.loc[ticker]) > float(prior.max()):
                highs.append(ticker)
            if float(current.loc[ticker]) < float(prior.min()):
                lows.append(ticker)

        actual_highs = [str(row["ticker"]).upper() for row in actual.get("new_highs", [])]
        actual_lows = [str(row["ticker"]).upper() for row in actual.get("new_lows", [])]
        matched = (
            len(eligible) == actual.get("eligible_count")
            and len(highs) == actual.get("new_high_count")
            and len(lows) == actual.get("new_low_count")
            and set(highs) == set(actual_highs)
            and set(lows) == set(actual_lows)
        )
        if not matched:
            raise ValueError(f"independent {horizon} eligibility or strict-break lists differ")
        outcomes[horizon] = {
            "prior_start": expected_start,
            "prior_end": expected_end,
            "prior_sessions": len(prior_dates),
            "eligible_count": len(eligible),
            "new_high_count": len(highs),
            "new_high_tickers": highs,
            "new_low_count": len(lows),
            "new_low_tickers": lows,
            "asset_lists_match": True,
        }

    fixed = breadth.get("historical_price_breadth", {})
    coverage = breadth.get("coverage", {})
    diagnostics = source_manifest.get("diagnostics") or {}
    failed_symbols = sorted(str(ticker).upper() for ticker in diagnostics.get("failed_symbols", []))
    signal_eligible = {
        str(row["ticker"]).upper()
        for row in market.get("records", [])
        if row.get("signal_eligible") is True
    }
    check_statuses = {
        key: str(value.get("status"))
        for key, value in (validation.get("checks") or {}).items()
        if isinstance(value, dict) and value.get("status") is not None
    }
    corporate_actions = source_manifest.get("corporate_actions") or {}
    divergence_counts = corporate_actions.get("divergent_row_counts") or {}
    source_counts = source_manifest.get("counts") or {}
    return {
        "schema_version": "independent-market-breadth-oracle-v1",
        "status": "PASS",
        "method": "Independent pandas pivot and direct strict comparisons; no production builder or classifier imported.",
        "as_of": as_of,
        "calendar_lookback_days": 364,
        "52w_cutoff_inclusive": cutoff,
        "selected_session_excluded_from_prior_ranges": True,
        "strict_break_rule": "current adjusted close > prior maximum for highs; < prior minimum for lows; ties excluded",
        "source_hashes": {
            "prices.csv": price_hash,
            "benchmark.csv": benchmark_hash,
            "source_manifest.json": source_manifest_hash,
            "validation.json": validation_hash,
        },
        "validation_status": validation["status"],
        "benchmark": {
            "first_session": benchmark_sessions[0],
            "last_session": benchmark_sessions[-1],
            "session_count": len(benchmark_sessions),
        },
        "panel_calendar_alignment": {
            "stock_rows_on_nonbenchmark_dates": int(len(off_benchmark_prices)),
            "nonbenchmark_dates": off_benchmark_dates,
            "calculation_treatment": "Price breadth uses only the observed benchmark-session index; these off-index stock rows are not used, and missing observations are not filled.",
        },
        "fixed_price_cohort": {
            "eligible_count": len(fixed_tickers),
            "cohort_tickers": fixed_tickers,
            "cohort_sha256": fixed_ticker_hash,
            "analysis_start": analysis_sessions[0],
            "analysis_end": analysis_sessions[-1],
            "analysis_sessions": len(analysis_sessions),
            "excluded_signal_eligible_incomplete_history": len(signal_tickers - set(fixed_tickers)),
            "daily_breadth_sessions_independently_reconciled": fixed_path_checks,
        },
        "acquisition_coverage": {
            "status": "PARTIAL" if failed_symbols or diagnostics.get("quarantined_symbols") else "COMPLETE",
            "requested_window": source_manifest.get("window"),
            "observed_stock_price_start": str(prices["date"].min()),
            "observed_stock_price_end": str(prices["date"].max()),
            "observed_unique_tickers": int(prices["ticker"].nunique()),
            "universe_sha256": source_manifest.get("universe_sha256"),
            "universe_version": source_manifest.get("universe_version"),
            "counts": source_counts,
            "failed_symbols": failed_symbols,
            "failed_signal_eligible_symbols": sorted(signal_eligible.intersection(failed_symbols)),
            "quarantined_symbols": sorted(str(ticker).upper() for ticker in diagnostics.get("quarantined_symbols", [])),
            "quarantine_reasons": diagnostics.get("quarantine_reasons", {}),
            "price_basis": source_manifest.get("price_basis"),
            "corporate_action_series_divergences": {
                "ticker_count": len(divergence_counts),
                "row_count": sum(int(value) for value in divergence_counts.values()),
                "treatment": "Raw close and provider-adjusted close are retained separately; these divergence counts are provider-series diagnostics, not an independent corporate-action audit.",
            },
            "validation_check_statuses": check_statuses,
            "ytd_baseline_date": ytd_base,
        },
        "selected_session_traded_price_ranges": outcomes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("market", "prices", "benchmark", "breadth", "source-manifest", "validation", "out"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            market_path=args.market,
            prices_path=args.prices,
            benchmark_path=args.benchmark,
            breadth_path=args.breadth,
            source_manifest_path=args.source_manifest,
            validation_path=args.validation,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": result["status"],
            "source_hashes": result["source_hashes"],
            "horizons": {
                key: {name: row[name] for name in ("eligible_count", "new_high_count", "new_low_count", "asset_lists_match")}
                for key, row in result["selected_session_traded_price_ranges"].items()
            },
            "out": str(args.out),
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"MARKET_BREADTH_ORACLE_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
