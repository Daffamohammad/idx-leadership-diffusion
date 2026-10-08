"""Independently recalculate the frozen Sectors return and diffusion asset.

This verifier reads only the recorded sample and released analysis. It uses
direct close arithmetic and integer-count thresholds, not the builder's return
helpers, signal classifiers, or data-normalization functions.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any


HORIZONS = {"5d": 5, "20d": 20, "60d": 60}
ACTION_KEYS = ("split", "right", "bonus", "dividend", "capital_reduction", "consolidat", "spin_off", "spinoff")
ACTION_DATE_KEYS = ("ex_date", "effective_date", "action_date", "date", "distribution_date", "record_date", "payment_date")


def _load(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value, raw


def _actions(stock: dict[str, Any]) -> list[dict[str, str]]:
    payload = stock.get("corporate_actions", {}).get("response", {}).get("corporate_actions", {})
    result = []
    if not isinstance(payload, dict):
        return result
    for kind, rows in payload.items():
        normalized = str(kind).lower().replace("-", "_").replace(" ", "_")
        if not any(key in normalized for key in ACTION_KEYS):
            continue
        for row in rows if isinstance(rows, list) else [rows]:
            if not isinstance(row, dict):
                continue
            value = next((row.get(key) for key in ACTION_DATE_KEYS if row.get(key)), None)
            if isinstance(value, str):
                try:
                    action_date = date.fromisoformat(value[:10]).isoformat()
                except ValueError:
                    continue
                result.append({"type": normalized, "date": action_date})
    return sorted(result, key=lambda row: (row["date"], row["type"]))


def _window(
    stock: dict[str, Any], benchmark: dict[str, float], benchmark_dates: list[str],
    target: str, sessions: int, actions: list[dict[str, str]],
) -> dict[str, Any]:
    rows_by_date = {
        str(row["date"]): float(row["close"])
        for row in stock.get("prices", [])
        if isinstance(row, dict) and row.get("date") and row.get("close") is not None
    }
    stock_dates = sorted(rows_by_date)
    if target not in rows_by_date:
        return {"return_pct": None, "excess_return_pct": None, "start_date": None,
                "end_date": target, "exclusion_reason": "NO_CLOSE_ON_BENCHMARK_SESSION"}
    if target not in benchmark_dates:
        raise ValueError(f"benchmark is missing replay date {target}")
    stock_end_index = stock_dates.index(target)
    benchmark_end_index = benchmark_dates.index(target)
    if stock_end_index < sessions or benchmark_end_index < sessions:
        return {"return_pct": None, "excess_return_pct": None, "start_date": None,
                "end_date": target, "exclusion_reason": "INSUFFICIENT_HISTORY"}
    stock_start = stock_dates[stock_end_index - sessions]
    benchmark_start = benchmark_dates[benchmark_end_index - sessions]
    if stock_start != benchmark_start:
        return {"return_pct": None, "excess_return_pct": None, "start_date": stock_start,
                "end_date": target, "exclusion_reason": "NO_MATCHING_BENCHMARK_BASELINE"}
    action = next((row for row in actions if stock_start < row["date"] <= target), None)
    if action:
        return {"return_pct": None, "excess_return_pct": None, "start_date": stock_start,
                "end_date": target,
                "exclusion_reason": f"MECHANICAL_ACTION_{action['type'].upper()}_{action['date']}"}
    stock_return = (rows_by_date[target] / rows_by_date[stock_start] - 1) * 100
    benchmark_return = (benchmark[target] / benchmark[benchmark_start] - 1) * 100
    return {"return_pct": round(stock_return, 8),
            "excess_return_pct": round(stock_return - benchmark_return, 8),
            "start_date": stock_start, "end_date": target, "exclusion_reason": None}


def oracle_state(delta_count: int | None, cohort_size: int | None) -> str:
    if delta_count is None or cohort_size is None or cohort_size < 5:
        return "UNCONFIRMED"
    floor = max(2, (cohort_size + 9) // 10)
    if delta_count * 10 >= cohort_size and abs(delta_count) >= floor:
        return "BROADENING_FIRM"
    if delta_count * 10 <= -cohort_size and abs(delta_count) >= floor:
        return "NARROWING_FIRM"
    if delta_count * 10 >= cohort_size:
        return "BROADENING_FRAGILE"
    if delta_count * 10 <= -cohort_size:
        return "NARROWING_FRAGILE"
    return "STABLE"


def _close_enough(actual: Any, expected: Any) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    return abs(float(actual) - float(expected)) <= 1.1e-7


def _verify_ytd(sample: dict[str, Any], analysis: dict[str, Any], baseline_path: Path | None,
                mismatches: list[dict[str, Any]]) -> tuple[int, int, str]:
    ytd = analysis.get("ytd") or {}
    if baseline_path is None:
        if ytd.get("status") != "NOT_AVAILABLE":
            mismatches.append({"field": "ytd.status", "actual": ytd.get("status"),
                               "expected": "NOT_AVAILABLE or a supplied baseline asset"})
        return 0, 0, str(ytd.get("status", "MISSING"))

    baseline, baseline_raw = _load(baseline_path.resolve(strict=True))
    baseline_hash = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    if baseline.get("schema_version") != "sectors-ytd-baseline-v1":
        raise ValueError("YTD baseline schema is not sectors-ytd-baseline-v1")
    if baseline.get("as_of") != sample.get("as_of"):
        raise ValueError("YTD baseline and sample end dates differ")
    if ytd.get("source_asset_sha256") != baseline_hash:
        raise ValueError("analysis does not bind to the supplied YTD baseline bytes")
    index_row = baseline.get("ihsg")
    if not isinstance(index_row, dict) or not index_row.get("date") or not index_row.get("close"):
        if ytd.get("status") != "NOT_AVAILABLE_NO_NATIVE_IHSG_BASELINE":
            mismatches.append({"field": "ytd.status", "actual": ytd.get("status"),
                               "expected": "NOT_AVAILABLE_NO_NATIVE_IHSG_BASELINE"})
        return 0, 0, str(ytd.get("status", "MISSING"))
    baseline_date = str(index_row["date"])
    end_date = str(sample["as_of"])
    if not baseline_date.startswith("2025-"):
        raise ValueError("YTD baseline is not an observed 2025 session")
    benchmark = {str(row["date"]): float(row["close"])
                 for row in sample.get("price_history", {}).get("ihsg", [])
                 if row.get("date") and row.get("close") is not None}
    if baseline_date not in {row.get("date") for row in baseline.get("stocks", [])}:
        # Stock responses need only have at least one row on the shared index date.
        raise ValueError("no stock response in the YTD baseline records the IHSG baseline session")
    if end_date not in benchmark or float(index_row["close"]) <= 0:
        raise ValueError("native sample IHSG endpoint or YTD baseline close is missing")
    benchmark_return = (benchmark[end_date] / float(index_row["close"]) - 1) * 100
    stock_baselines: dict[str, list[dict[str, Any]]] = {}
    for row in baseline.get("stocks", []):
        if isinstance(row, dict) and row.get("ticker"):
            stock_baselines.setdefault(str(row["ticker"]), []).append(row)
    stocks = {str(row["ticker"]): row for row in sample.get("stocks", [])}
    ytd_tickers = sample.get("coverage", {}).get("ytd", {}).get("tickers")
    if isinstance(ytd_tickers, list):
        ytd_tickers = set(map(str, ytd_tickers))
        stocks = {ticker: row for ticker, row in stocks.items() if ticker in ytd_tickers}
    groups: dict[str, list[str]] = {}
    for ticker, stock in stocks.items():
        groups.setdefault(str(stock["sector"]), []).append(ticker)
    actual_groups = {str(row["sector"]): row for row in ytd.get("groups", [])}
    contributor_checks = 0
    group_checks = 0
    for sector, tickers in sorted(groups.items()):
        actual_group = actual_groups.get(sector)
        if actual_group is None:
            mismatches.append({"field": "ytd.group_missing", "sector": sector})
            continue
        actual_contributors = {str(row["ticker"]): row for row in actual_group.get("contributors", [])}
        if set(actual_contributors) != set(tickers):
            mismatches.append({"field": "ytd.contributor_inventory", "sector": sector,
                               "actual": sorted(actual_contributors), "expected": sorted(tickers)})
        eligible = []
        for ticker in sorted(tickers):
            stock = stocks[ticker]
            rows = stock_baselines.get(ticker, [])
            base_rows = [row for row in rows if row.get("date") == baseline_date]
            end_rows = [row for row in stock.get("prices", [])
                        if row.get("date") == end_date and row.get("close") is not None]
            action = next((row for row in sorted(_actions(stock), key=lambda item: (item["type"], item["date"]))
                           if baseline_date < row["date"] <= end_date), None)
            reason = None
            if len(base_rows) != 1:
                reason = "NO_MATCHING_2025_STOCK_BASELINE" if not base_rows else "DUPLICATE_2025_STOCK_BASELINE"
            elif len(end_rows) != 1:
                reason = "NO_SAMPLE_ENDPOINT_CLOSE" if not end_rows else "DUPLICATE_SAMPLE_ENDPOINT_CLOSE"
            elif action:
                reason = f"MECHANICAL_ACTION_{action['type'].upper()}_{action['date']}"
            if reason:
                expected = {"return_pct": None, "excess_return_pct": None,
                            "eligible": False, "exclusion_reason": reason}
            else:
                raw_return = (float(end_rows[0]["close"]) / float(base_rows[0]["close"]) - 1) * 100
                expected = {"return_pct": round(raw_return, 8),
                            "excess_return_pct": round(raw_return - benchmark_return, 8),
                            "eligible": True, "exclusion_reason": None}
                eligible.append(expected)
            actual = actual_contributors.get(ticker, {})
            contributor_checks += 1
            for field, value in expected.items():
                matches = (_close_enough(actual.get(field), value)
                           if field in {"return_pct", "excess_return_pct"} else actual.get(field) == value)
                if not matches:
                    mismatches.append({"field": f"ytd.contributors.{field}", "sector": sector,
                                       "ticker": ticker, "actual": actual.get(field), "expected": value})
        expected_count = len(eligible)
        enough = expected_count >= 5
        group_expected = {
            "eligible_contributors": expected_count,
            "requested_constituents": len(tickers),
            "stock_return_pct": round(sum(row["return_pct"] for row in eligible) / expected_count, 8) if enough else None,
            "benchmark_return_pct": round(benchmark_return, 8) if enough else None,
            "excess_return_pct": round(sum(row["excess_return_pct"] for row in eligible) / expected_count, 8) if enough else None,
            "status": "PASS" if enough else "UNCONFIRMED_BELOW_FIVE_CONTRIBUTORS",
        }
        group_checks += 1
        for field, value in group_expected.items():
            matches = (_close_enough(actual_group.get(field), value)
                       if field in {"stock_return_pct", "benchmark_return_pct", "excess_return_pct"}
                       else actual_group.get(field) == value)
            if not matches:
                mismatches.append({"field": f"ytd.groups.{field}", "sector": sector,
                                   "actual": actual_group.get(field), "expected": value})
    if set(actual_groups) != set(groups):
        mismatches.append({"field": "ytd.sector_inventory", "actual": sorted(actual_groups),
                           "expected": sorted(groups)})
    if ytd.get("baseline_date") != baseline_date:
        mismatches.append({"field": "ytd.baseline_date", "actual": ytd.get("baseline_date"),
                           "expected": baseline_date})
    if not ytd.get("method"):
        mismatches.append({"field": "ytd.method", "actual": ytd.get("method"), "expected": "documented method"})
    expected_status = "PASS" if stock_baselines else "PARTIAL_NO_MATCHING_STOCK_BASELINES"
    if ytd.get("status") != expected_status:
        mismatches.append({"field": "ytd.status", "actual": ytd.get("status"), "expected": expected_status})
    return contributor_checks, group_checks, str(ytd.get("status", "MISSING"))


def verify(*, sample_path: Path, analysis_path: Path,
           ytd_baseline_path: Path | None = None) -> dict[str, Any]:
    sample, sample_raw = _load(sample_path.resolve(strict=True))
    analysis, _ = _load(analysis_path.resolve(strict=True))
    actual_sample_hash = hashlib.sha256(sample_raw).hexdigest()
    if analysis.get("schema_version") != "sectors-signal-analysis-v1":
        raise ValueError("analysis schema is not sectors-signal-analysis-v1")
    if analysis.get("sources", {}).get("recorded_sample_sha256") != actual_sample_hash:
        raise ValueError("analysis does not bind to the supplied recorded sample")

    benchmark_rows = sample.get("price_history", {}).get("ihsg", [])
    benchmark = {str(row["date"]): float(row["close"])
                 for row in benchmark_rows if row.get("date") and row.get("close") is not None}
    benchmark_dates = sorted(benchmark)
    stocks = {str(row["ticker"]): row for row in sample.get("stocks", [])}
    sectors: dict[str, list[str]] = {}
    actions = {ticker: _actions(stock) for ticker, stock in stocks.items()}
    for ticker, stock in stocks.items():
        sectors.setdefault(str(stock["sector"]), []).append(ticker)

    mismatches: list[dict[str, Any]] = []
    checks = {"member_window_values": 0, "sector_return_aggregates": 0,
              "diffusion_states_and_cohorts": 0, "daily_observations": 0,
              "weekly_observations": 0, "ytd_contributor_values": 0,
              "ytd_group_aggregates": 0, "concentration_values": 0,
              "cohort_lists": 0, "leadership_states": 0, "map_values": 0}
    expected_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    def expected(ticker: str, target: str, horizon: str) -> dict[str, Any]:
        key = (ticker, target, horizon)
        if key not in expected_cache:
            expected_cache[key] = _window(stocks[ticker], benchmark, benchmark_dates,
                                          target, HORIZONS[horizon], actions[ticker])
        return expected_cache[key]

    for cadence in ("daily", "weekly"):
        observations = analysis.get(cadence)
        if not isinstance(observations, list):
            raise ValueError(f"analysis {cadence} replay is not a list")
        checks[f"{cadence}_observations"] = len(observations)
        previous_date = None
        for observation in observations:
            target = str(observation.get("date"))
            if observation.get("previous_date") != previous_date:
                mismatches.append({"cadence": cadence, "date": target,
                                   "field": "previous_date", "actual": observation.get("previous_date"),
                                   "expected": previous_date})
            group_rows = {str(row["sector"]): row for row in observation.get("groups", [])}
            if set(group_rows) != set(sectors):
                mismatches.append({"cadence": cadence, "date": target, "field": "sector_inventory"})
            for sector, tickers in sectors.items():
                group = group_rows.get(sector)
                if group is None:
                    continue
                requested = len(tickers)
                if group.get("requested_constituents") != requested:
                    mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                       "field": "requested_constituents",
                                       "actual": group.get("requested_constituents"),
                                       "expected": requested})
                member_rows = {str(row["ticker"]): row for row in group.get("contributors", [])}
                if set(member_rows) != set(tickers):
                    mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                       "field": "constituent_inventory"})
                for horizon in HORIZONS:
                    eligible = []
                    for ticker in tickers:
                        expected_reading = expected(ticker, target, horizon)
                        actual_reading = member_rows.get(ticker, {}).get("returns", {}).get(horizon, {})
                        checks["member_window_values"] += 1
                        for field in ("return_pct", "excess_return_pct", "start_date", "end_date", "exclusion_reason"):
                            value_matches = (_close_enough(actual_reading.get(field), expected_reading[field])
                                             if field in {"return_pct", "excess_return_pct"}
                                             else actual_reading.get(field) == expected_reading[field])
                            if not value_matches:
                                mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                                   "ticker": ticker, "horizon": horizon, "field": field,
                                                   "actual": actual_reading.get(field),
                                                   "expected": expected_reading[field]})
                        if expected_reading["exclusion_reason"] is None:
                            eligible.append((ticker, expected_reading))
                    metric = group.get("returns", {}).get(horizon, {})
                    expected_count = len(eligible)
                    enough = expected_count >= 5
                    benchmark_return = None
                    if enough:
                        start_date = eligible[0][1]["start_date"]
                        benchmark_return = (benchmark[target] / benchmark[start_date] - 1) * 100
                    expected_values = {
                        "eligible_contributors": expected_count,
                        "stock_return_pct": (sum(row["return_pct"] for _, row in eligible) / expected_count) if enough else None,
                        "benchmark_return_pct": benchmark_return if enough else None,
                        "excess_return_pct": (sum(row["excess_return_pct"] for _, row in eligible) / expected_count) if enough else None,
                    }
                    checks["sector_return_aggregates"] += 1
                    for field, value in expected_values.items():
                        matches = (_close_enough(metric.get(field), round(value, 8) if value is not None else None)
                                   if field != "eligible_contributors" else metric.get(field) == value)
                        if not matches:
                            mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                               "horizon": horizon, "field": f"returns.{field}",
                                               "actual": metric.get(field), "expected": value})

                current20 = {ticker: expected(ticker, target, "20d") for ticker in tickers}
                concentration_names = sorted(ticker for ticker in tickers if current20[ticker]["exclusion_reason"] is None)
                concentration = group.get("concentration_v2")
                if len(concentration_names) >= 5:
                    signed = [current20[ticker]["return_pct"] for ticker in concentration_names]
                    absolute = sorted([abs(value) for value in signed], reverse=True)
                    gross = sum(absolute)
                    values = {"requested_constituent_count": len(concentration_names), "contributor_count": len(concentration_names),
                              "missing_constituent_count": 0, "gross_absolute_return": round(gross, 8), "net_signed_return": round(sum(signed),8),
                              "top1_abs_share": round(sum(absolute[:1])/gross,4) if gross else None,
                              "top3_abs_share": round(sum(absolute[:3])/gross,4) if gross else None,
                              "top5_abs_share": round(sum(absolute[:5])/gross,4) if gross else None,
                              "hhi": round(sum((value/gross)**2 for value in absolute),4) if gross else None}
                    for field,value in values.items():
                        checks["concentration_values"] += 1
                        if not concentration or not _close_enough(concentration.get(field),value):
                            mismatches.append({"cadence":cadence,"date":target,"sector":sector,
                                               "field":f"concentration_v2.{field}","actual":concentration.get(field) if concentration else None,"expected":value})
                elif concentration is not None:
                    mismatches.append({"cadence":cadence,"date":target,"sector":sector,"field":"concentration_below_floor"})
                paired = []
                if previous_date:
                    previous20 = {ticker: expected(ticker, previous_date, "20d") for ticker in tickers}
                    paired = sorted(ticker for ticker in tickers
                                    if current20[ticker]["exclusion_reason"] is None
                                    and previous20[ticker]["exclusion_reason"] is None)
                else:
                    previous20 = {}
                current_count = (sum(current20[ticker]["excess_return_pct"] > 0 for ticker in paired)
                                 if len(paired) >= 5 else None)
                previous_count = (sum(previous20[ticker]["excess_return_pct"] > 0 for ticker in paired)
                                  if len(paired) >= 5 else None)
                delta = current_count - previous_count if current_count is not None and previous_count is not None else None
                expected_diffusion = {
                    "outperforming_count": current_count,
                    "previous_outperforming_count": previous_count,
                    "change_count": delta,
                    "eligible_count": len(paired) if len(paired) >= 5 else 0,
                    "breadth_pct": round(current_count / len(paired) * 100, 8) if current_count is not None else None,
                    "previous_breadth_pct": round(previous_count / len(paired) * 100, 8) if previous_count is not None else None,
                    "state": oracle_state(delta, len(paired)),
                }
                checks["diffusion_states_and_cohorts"] += 1
                actual_diffusion = group.get("diffusion", {})
                actual_cohort = group.get("comparison_cohorts", {}).get("diffusion_tickers")
                if actual_cohort != paired:
                    mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                       "field": "comparison_cohorts.diffusion_tickers",
                                       "actual": actual_cohort, "expected": paired})
                for field, value in expected_diffusion.items():
                    matches = (_close_enough(actual_diffusion.get(field), value)
                               if field.endswith("_pct") else actual_diffusion.get(field) == value)
                    if not matches:
                        mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                           "field": f"diffusion.{field}",
                                           "actual": actual_diffusion.get(field), "expected": value})
                # Independent leadership, map, and cohort checks: the builder's
                # return helpers and signal classifiers are not used here.
                valid = {horizon: sorted(ticker for ticker in tickers
                                         if expected(ticker, target, horizon)["exclusion_reason"] is None)
                         for horizon in HORIZONS}
                leadership_cohort = sorted(set(valid["5d"]) & set(valid["20d"]) & set(valid["60d"]))
                map_cohort = sorted(set(valid["20d"]) & set(valid["60d"]))
                actual_cohorts = group.get("comparison_cohorts", {})
                for field, value in (("leadership_tickers", leadership_cohort),
                                     ("map_tickers", map_cohort)):
                    checks["cohort_lists"] += 1
                    if actual_cohorts.get(field) != value:
                        mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                           "field": f"comparison_cohorts.{field}",
                                           "actual": actual_cohorts.get(field), "expected": value})
                lead_means = {}
                for horizon in HORIZONS:
                    readings = [expected(ticker, target, horizon)["excess_return_pct"]
                                for ticker in leadership_cohort]
                    lead_means[horizon] = (sum(readings) / len(readings)) if readings else None
                enough_leadership = len(leadership_cohort) >= 5
                if not enough_leadership or any(lead_means[h] is None for h in HORIZONS):
                    expected_leadership = "UNCONFIRMED"
                elif lead_means["20d"] > 0 and lead_means["5d"] - lead_means["60d"] >= 1.0:
                    expected_leadership = "LEADING"
                elif lead_means["20d"] <= 0 and lead_means["5d"] - lead_means["60d"] >= 1.0:
                    expected_leadership = "IMPROVING"
                elif lead_means["20d"] <= 0:
                    expected_leadership = "LAGGING"
                else:
                    expected_leadership = "WEAKENING"
                checks["leadership_states"] += 1
                if group.get("leadership_state") != expected_leadership:
                    mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                       "field": "leadership_state",
                                       "actual": group.get("leadership_state"),
                                       "expected": expected_leadership})
                if len(map_cohort) >= 5:
                    map_20 = sum(expected(ticker, target, "20d")["excess_return_pct"]
                                 for ticker in map_cohort) / len(map_cohort)
                    map_60 = sum(expected(ticker, target, "60d")["excess_return_pct"]
                                 for ticker in map_cohort) / len(map_cohort)
                    expected_map = {
                        "cohort_tickers": map_cohort,
                        "eligible_contributors": len(map_cohort),
                        "x_60d_excess_pct": round(map_60, 8),
                        "y_relative_momentum_pct": round(map_20 - map_60, 8),
                    }
                else:
                    expected_map = None
                if map_cohort:
                    desc_60 = sum(expected(ticker, target, "60d")["excess_return_pct"]
                                  for ticker in map_cohort) / len(map_cohort)
                    expected_descriptive = {
                        "cohort_tickers": map_cohort,
                        "eligible_contributors": len(map_cohort),
                        "x_60d_excess_pct": round(desc_60, 8),
                        "y_relative_momentum_pct": round(sum(
                            expected(ticker, target, "20d")["excess_return_pct"]
                            - expected(ticker, target, "60d")["excess_return_pct"]
                            for ticker in map_cohort) / len(map_cohort), 8),
                    }
                else:
                    expected_descriptive = None
                checks["map_values"] += 1
                actual_map = group.get("map")
                if (actual_map is None) != (expected_map is None):
                    mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                       "field": "map.presence",
                                       "actual": actual_map is not None, "expected": expected_map is not None})
                elif expected_map is not None:
                    for field, value in expected_map.items():
                        matches = (_close_enough(actual_map.get(field), value)
                                   if field.endswith("_pct") else actual_map.get(field) == value)
                        if not matches:
                            mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                               "field": f"map.{field}",
                                               "actual": actual_map.get(field), "expected": value})
                checks["map_values"] += 1
                actual_descriptive = group.get("descriptive_map")
                if (actual_descriptive is None) != (expected_descriptive is None):
                    mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                       "field": "descriptive_map.presence",
                                       "actual": actual_descriptive is not None,
                                       "expected": expected_descriptive is not None})
                elif expected_descriptive is not None:
                    for field, value in expected_descriptive.items():
                        matches = (_close_enough(actual_descriptive.get(field), value)
                                   if field.endswith("_pct") else actual_descriptive.get(field) == value)
                        if not matches:
                            mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                               "field": f"descriptive_map.{field}",
                                               "actual": actual_descriptive.get(field), "expected": value})
                if len(concentration_names) >= 5:
                    ordered = sorted(
                        ((ticker, current20[ticker]["return_pct"]) for ticker in concentration_names),
                        key=lambda row: (-abs(row[1]), row[0]),
                    )
                    signed_gross = sum(abs(value) for _, value in ordered)
                    signed_net = sum(value for _, value in ordered)
                    # The builder uses the 1e-9 stability epsilon from
                    # config/methodology.yaml; replicate it here.
                    stable = abs(signed_net) > 1e-9 and abs(signed_net) / signed_gross >= 0.05
                    expected_signed = {
                        "top_absolute_contributor": ordered[0][0],
                        "top1_signed_share": round(ordered[0][1] / signed_net, 4) if stable else None,
                        "top3_signed_share": (round(sum(value for _, value in ordered[:3]) / signed_net, 4)
                                              if stable and len(ordered) >= 3 else None),
                        "signed_denominator_ratio": round(abs(signed_net) / signed_gross, 8),
                        "status": "DEFINED",
                        "signed_attribution_status": "DEFINED" if stable else "UNDEFINED_UNSTABLE_DENOMINATOR",
                    }
                    for field, value in expected_signed.items():
                        checks["concentration_values"] += 1
                        matches = (_close_enough(concentration.get(field), value)
                                   if field in {"top1_signed_share", "top3_signed_share", "signed_denominator_ratio"}
                                   else (concentration or {}).get(field) == value)
                        if not matches:
                            mismatches.append({"cadence": cadence, "date": target, "sector": sector,
                                               "field": f"concentration_v2.{field}",
                                               "actual": concentration.get(field) if concentration else None,
                                               "expected": value})
            previous_date = target

    ytd_contributors, ytd_groups, ytd_status = _verify_ytd(
        sample, analysis, ytd_baseline_path, mismatches
    )
    checks["ytd_contributor_values"] = ytd_contributors
    checks["ytd_group_aggregates"] = ytd_groups

    return {
        "status": "PASS" if not mismatches else "FAIL",
        "sample_sha256": actual_sample_hash,
        "counts": checks,
        "ytd_status": ytd_status,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
        "method": "Independent close arithmetic and pure integer-count diffusion thresholds; production helpers and classifiers are not imported.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--ytd-baseline", type=Path)
    args = parser.parse_args()
    try:
        report = verify(sample_path=args.sample, analysis_path=args.analysis,
                        ytd_baseline_path=args.ytd_baseline)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "REFUSED", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
