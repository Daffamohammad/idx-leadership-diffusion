"""Build a deterministic, Sectors-only leadership and diffusion asset.

The saved 66-stock universe is retrospective. Returns use unadjusted Sectors
closes and native Sectors IHSG observations; no other price provider is read.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

import pandas as pd

from idx_leadership.data.releases import canonical_json_bytes
from idx_leadership.features.concentration_v2 import compute_concentration_v2
from idx_leadership.features.returns import compute_returns
from idx_leadership.models.enums import DiffusionStateV2
from idx_leadership.signals.diffusion_v2 import classify_diffusion_v2
from idx_leadership.signals.leadership import classify_leadership


SCHEMA = "sectors-signal-analysis-v1"
HORIZONS = {"5d": 5, "20d": 20, "60d": 60}
REPLAY_CALENDAR_DAYS = 28
MINIMUM_CONTRIBUTORS = 5
MECHANICAL_ACTION_KEYS = {
    "stock_split", "split", "reverse_split", "reverse_stock_split",
    "right_issue", "rights_issue", "bonus", "bonus_issue", "stock_bonus",
    "stock_dividend", "dividend", "upcoming_dividend", "capital_reduction",
    "stock_consolidation", "consolidation", "spin_off", "spinoff",
}
ACTION_DATE_FIELDS = (
    "ex_date", "effective_date", "action_date", "date", "distribution_date",
    "record_date", "payment_date",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _parse_actions(stock: dict[str, Any]) -> list[dict[str, str]]:
    root = stock.get("corporate_actions", {}).get("response", {}).get("corporate_actions", {})
    if not isinstance(root, dict):
        return []
    actions: list[dict[str, str]] = []
    for raw_kind, raw_rows in root.items():
        kind = str(raw_kind).strip().lower().replace("-", "_").replace(" ", "_")
        if kind not in MECHANICAL_ACTION_KEYS and not any(
            token in kind for token in ("split", "right", "bonus", "consolidat", "capital_reduction", "dividend")
        ):
            continue
        rows = raw_rows if isinstance(raw_rows, list) else [raw_rows]
        for row in rows:
            if not isinstance(row, dict):
                continue
            event_date = next((row.get(key) for key in ACTION_DATE_FIELDS if row.get(key)), None)
            if not isinstance(event_date, str):
                continue
            try:
                parsed = date.fromisoformat(event_date[:10])
            except ValueError:
                continue
            actions.append({"type": kind, "date": parsed.isoformat()})
    return [
        {"type": kind, "date": day}
        for kind, day in sorted(set((row["type"], row["date"]) for row in actions))
    ]


def _action_in_window(actions: list[dict[str, str]], start: str, end: str) -> dict[str, str] | None:
    # The base close already incorporates an action on the starting session.
    for action in actions:
        if start < action["date"] <= end:
            return action
    return None


def _return_map(frame: pd.DataFrame, target: date) -> dict[str, dict[str, Any]]:
    if frame.empty:
        return {}
    result = compute_returns(
        frame,
        horizons=HORIZONS,
        price_col="close",
        as_of=target,
        tolerance_days=0,
    )
    return {str(row["ticker"]): row.to_dict() for _, row in result.iterrows()}


def _member_window(
    stock: dict[str, Any],
    action_rows: list[dict[str, str]],
    stock_returns: dict[str, Any] | None,
    benchmark_return: dict[str, Any],
    label: str,
    target: str,
) -> dict[str, Any]:
    if stock_returns is None:
        return {"return_pct": None, "excess_return_pct": None, "start_date": None,
                "end_date": target, "exclusion_reason": "NO_CLOSE_ON_BENCHMARK_SESSION"}
    value = stock_returns.get(f"return_{label}")
    stock_start = stock_returns.get(f"return_{label}_start_date")
    benchmark_start = benchmark_return.get(f"return_{label}_start_date")
    stock_end = stock_returns.get("as_of")
    benchmark_end = benchmark_return.get("as_of")
    if value is None or pd.isna(value) or stock_start is None:
        reason = "INSUFFICIENT_HISTORY"
    elif stock_end != benchmark_end or stock_end != date.fromisoformat(target):
        reason = "NO_MATCHING_BENCHMARK_END_DATE"
    elif stock_start != benchmark_start:
        reason = "NO_MATCHING_BENCHMARK_BASELINE"
    else:
        action = _action_in_window(action_rows, stock_start.isoformat(), stock_end.isoformat())
        if action:
            reason = f"MECHANICAL_ACTION_{action['type'].upper()}_{action['date']}"
        else:
            return {
                "return_pct": round(float(value), 8),
                "excess_return_pct": round(float(value) - float(benchmark_return[f"return_{label}"]), 8),
                "start_date": stock_start.isoformat(),
                "end_date": stock_end.isoformat(),
                "exclusion_reason": None,
            }
    return {"return_pct": None, "excess_return_pct": None,
            "start_date": stock_start.isoformat() if stock_start else None,
            "end_date": stock_end.isoformat() if stock_end else target,
            "exclusion_reason": reason}


def _replay_dates(benchmark: pd.DataFrame, as_of: str) -> tuple[list[date], list[date]]:
    cutoff = date.fromisoformat(as_of) - timedelta(days=REPLAY_CALENDAR_DAYS)
    dates = sorted(
        date.fromisoformat(str(value))
        for value in benchmark["date"].unique()
        if cutoff <= date.fromisoformat(str(value)) <= date.fromisoformat(as_of)
    )
    if not dates or dates[-1].isoformat() != as_of:
        raise ValueError("native IHSG history does not contain the sample as-of session")
    weekly: dict[tuple[int, int], date] = {}
    for day in dates:
        iso = day.isocalendar()
        weekly[(iso.year, iso.week)] = day
    return dates, list(weekly.values())


def _validate_selection(
    *,
    sample: dict[str, Any],
    market: dict[str, Any],
    market_hash: str,
    selection_plan_path: Path | None,
) -> None:
    selection = sample["selection"]
    replacements = selection.get("replacements", {})
    by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in market.get("records", []):
        ticker = str(row.get("ticker") or "").upper()
        try:
            market_cap = float(row.get("market_cap") or 0)
            close = float(row.get("close") or 0)
        except (TypeError, ValueError):
            continue
        sector = (row.get("taxonomy") or {}).get("sector")
        if (row.get("signal_eligible") is True
                and row.get("instrument_type") == "LISTED_STOCK"
                and row.get("traded") is True
                and row.get("last_trade_date") == market.get("as_of")
                and close > 0 and market_cap > 0
                and re.fullmatch(r"[A-Z]{4,6}\.JK", ticker)):
            by_sector[str(sector)].append(row)
    actual_by_sector: dict[str, set[str]] = defaultdict(set)
    for row in sample["stocks"]:
        actual_by_sector[str(row["sector"])].add(str(row["ticker"]).upper())
    if set(by_sector) != set(actual_by_sector):
        raise ValueError("sample sector inventory differs from the frozen market selection source")
    for sector, eligible in by_sector.items():
        ranked = sorted(eligible, key=lambda row: (-float(row["market_cap"]), str(row["ticker"]).upper()))
        expected = {str(row["ticker"]).upper() for row in ranked[:6]}
        for replacement in replacements.get(sector, []):
            removed = str(replacement.get("removed") or "").upper()
            selected = str(replacement.get("selected") or "").upper()
            if removed not in expected or selected not in {str(row["ticker"]).upper() for row in ranked[6:]}:
                raise ValueError(f"sample replacement is not supported by the frozen market source: {sector}")
            expected.remove(removed)
            expected.add(selected)
        if actual_by_sector[sector] != expected or len(actual_by_sector[sector]) != 6:
            raise ValueError(f"sample membership does not match the frozen top-six selection: {sector}")

    if selection_plan_path is None:
        return
    plan = _json(selection_plan_path)
    if plan.get("market_release_source", {}).get("sha256") != market_hash:
        raise ValueError("recording plan does not bind to the frozen selection-market source")
    if plan.get("selection_release_id") != selection.get("membership_release_id"):
        raise ValueError("recording plan selection release differs from recorded membership provenance")
    for sector, record in plan.get("selections", {}).items():
        expected = {str(ticker).upper() for ticker in record.get("selected", [])}
        for replacement in replacements.get(sector, []):
            expected.discard(str(replacement.get("removed") or "").upper())
            expected.add(str(replacement.get("selected") or "").upper())
        if actual_by_sector.get(sector) != expected:
            raise ValueError(f"recorded membership differs from the hash-bound frozen selection plan: {sector}")


def _baseline_reading(
    sample: dict[str, Any],
    baseline_path: Path | None,
    action_map: dict[str, list[dict[str, str]]],
    groups: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if baseline_path is None:
        return {
            "status": "NOT_AVAILABLE",
            "baseline_date": None,
            "reason": "No matching prior-year Sectors stock and native IHSG baseline is recorded.",
            "groups": [],
        }
    baseline_raw = baseline_path.read_bytes()
    baseline = _json(baseline_path)
    if baseline.get("schema_version") != "sectors-ytd-baseline-v1":
        raise ValueError("YTD baseline asset has an unsupported schema")
    index_row = baseline.get("ihsg")
    if not isinstance(index_row, dict) or not index_row.get("date") or not index_row.get("close"):
        return {
            "status": "NOT_AVAILABLE_NO_NATIVE_IHSG_BASELINE",
            "baseline_date": None,
            "reason": baseline.get("reason") or "The recorded native IHSG baseline response contained no 2025 close.",
            "source_asset_sha256": _sha(baseline_raw),
            "gaps": baseline.get("gaps", []),
        }
    base_date = str(index_row["date"])
    if not base_date.startswith("2025-"):
        raise ValueError("YTD baseline must use the last observed 2025 IHSG session")
    end_date = str(sample["as_of"])
    bench_end = next((row["close"] for row in sample["price_history"]["ihsg"] if row["date"] == end_date), None)
    if bench_end is None or float(index_row["close"]) <= 0:
        raise ValueError("YTD baseline cannot be compared with the sample's native IHSG endpoint")
    benchmark_return = (float(bench_end) / float(index_row["close"]) - 1) * 100
    stock_baselines = {
        str(row.get("ticker")): row
        for row in baseline.get("stocks", [])
        if isinstance(row, dict) and row.get("ticker") and row.get("date") == base_date
    }
    result_groups = []
    for sector, members in sorted(groups.items()):
        contributors = []
        for member in members:
            ticker = str(member["ticker"])
            start = stock_baselines.get(ticker)
            end = next((row["close"] for row in member["prices"] if row["date"] == end_date), None)
            action = _action_in_window(action_map.get(ticker, []), base_date, end_date)
            reason = None
            if start is None:
                reason = "NO_MATCHING_2025_STOCK_BASELINE"
            elif end is None:
                reason = "NO_SAMPLE_ENDPOINT_CLOSE"
            elif action:
                reason = f"MECHANICAL_ACTION_{action['type'].upper()}_{action['date']}"
            if reason:
                contributors.append({"ticker": ticker, "return_pct": None, "excess_return_pct": None,
                                    "eligible": False, "exclusion_reason": reason})
            else:
                raw_return = (float(end) / float(start["close"]) - 1) * 100
                contributors.append({"ticker": ticker, "return_pct": round(raw_return, 8),
                                    "excess_return_pct": round(raw_return - benchmark_return, 8),
                                    "eligible": True, "exclusion_reason": None})
        eligible = [row for row in contributors if row["eligible"]]
        enough = len(eligible) >= MINIMUM_CONTRIBUTORS
        result_groups.append({
            "sector": sector,
            "eligible_contributors": len(eligible),
            "requested_constituents": len(members),
            "stock_return_pct": round(sum(row["return_pct"] for row in eligible) / len(eligible), 8) if enough else None,
            "benchmark_return_pct": round(benchmark_return, 8) if enough else None,
            "excess_return_pct": round(sum(row["excess_return_pct"] for row in eligible) / len(eligible), 8) if enough else None,
            "status": "PASS" if enough else "UNCONFIRMED_BELOW_FIVE_CONTRIBUTORS",
            "contributors": contributors,
        })
    return {
        "status": "PASS" if stock_baselines else "PARTIAL_NO_MATCHING_STOCK_BASELINES",
        "baseline_date": base_date,
        "end_date": end_date,
        "benchmark_return_pct": round(benchmark_return, 8),
        "source_asset_sha256": _sha(baseline_raw),
        "gaps": baseline.get("gaps", []),
        "groups": result_groups,
        "method": "Equal-weighted raw-price returns; stock closes must share the last observed 2025 IHSG baseline date. Mechanical-action windows are excluded; fewer than five eligible contributors are unconfirmed.",
    }


def build(
    *,
    sample_path: Path,
    selection_market_path: Path,
    out: Path,
    ytd_baseline_path: Path | None = None,
    selection_plan_path: Path | None = None,
) -> dict[str, Any]:
    sample_path = sample_path.resolve(strict=True)
    selection_market_path = selection_market_path.resolve(strict=True)
    sample_raw = sample_path.read_bytes()
    source_market_raw = selection_market_path.read_bytes()
    sample = _json(sample_path)
    market = _json(selection_market_path)
    if sample.get("schema_version") != "sectors-recorded-sample-v1":
        raise ValueError("recorded Sectors sample has an unsupported schema")
    if market.get("schema_version") != "market-workspace-v1":
        raise ValueError("frozen selection-market source has an unsupported schema")
    sample_source_hash = sample.get("sources", {}).get("market_release_source_sha256")
    market_hash = _sha(source_market_raw)
    if sample_source_hash != market_hash:
        raise ValueError("recorded sample hash does not match the frozen selection-market source")
    if market.get("as_of") != sample.get("selection", {}).get("selected_market_cap_date"):
        raise ValueError("selection-market source date differs from the frozen selection date")
    if sample.get("as_of") != sample.get("selection", {}).get("membership_release_session"):
        raise ValueError("recorded sample and frozen membership session differ")

    stocks = sample.get("stocks")
    if not isinstance(stocks, list) or len(stocks) != 66:
        raise ValueError("Sectors analysis requires all 66 recorded sample members")
    if len({row.get("ticker") for row in stocks}) != 66:
        raise ValueError("recorded Sectors sample contains duplicate stock tickers")
    sector_counts: dict[str, int] = defaultdict(int)
    for stock in stocks:
        sector_counts[str(stock.get("sector"))] += 1
    if len(sector_counts) != 11 or any(value != 6 for value in sector_counts.values()):
        raise ValueError("recorded Sectors sample must retain six names in each of 11 sectors")

    # Validate the frozen membership against the original hash-bound market
    # rows and the original selection plan where it is available.
    market_rows = {str(row.get("ticker")): row for row in market.get("records", []) if isinstance(row, dict)}
    _validate_selection(sample=sample, market=market, market_hash=market_hash,
                        selection_plan_path=selection_plan_path)
    replacements = sample.get("selection", {}).get("replacements", {})
    for stock in stocks:
        ticker = str(stock.get("ticker"))
        source_row = market_rows.get(ticker)
        if source_row is None or (source_row.get("taxonomy") or {}).get("sector") != stock.get("sector"):
            replaced_from = next((
                row.get("removed")
                for row in replacements.get(str(stock.get("sector")), [])
                if row.get("selected") == ticker
            ), None)
            if replaced_from is None:
                raise ValueError(f"selection evidence does not match the frozen market source: {ticker}")

    benchmark_rows = sample.get("price_history", {}).get("ihsg", [])
    if not benchmark_rows:
        raise ValueError("recorded sample contains no native Sectors IHSG observations")
    benchmark = pd.DataFrame([
        {"ticker": "IHSG", "date": row["date"], "close": row["close"]}
        for row in benchmark_rows
        if isinstance(row, dict) and row.get("date") and row.get("close") is not None
    ])
    benchmark["date"] = pd.to_datetime(benchmark["date"]).dt.date
    benchmark = benchmark.sort_values("date").drop_duplicates("date", keep="last")
    as_of = str(sample["as_of"])
    all_dates, weekly_dates = _replay_dates(benchmark, as_of)
    cutoff = date.fromisoformat(as_of) - timedelta(days=REPLAY_CALENDAR_DAYS)
    replay_dates = [day for day in all_dates if day >= cutoff]
    weekly_dates = [day for day in weekly_dates if day >= cutoff]
    if not replay_dates:
        raise ValueError("recorded sample has no native IHSG sessions in the replay window")

    price_records: list[dict[str, Any]] = []
    by_ticker = {str(stock["ticker"]): stock for stock in stocks}
    action_map = {ticker: _parse_actions(stock) for ticker, stock in by_ticker.items()}
    for ticker, stock in by_ticker.items():
        for row in stock.get("prices", []):
            if row.get("close") is None:
                continue
            price_records.append({"ticker": ticker, "date": row["date"], "close": row["close"]})
    prices = pd.DataFrame(price_records)
    if prices.empty:
        raise ValueError("recorded sample contains no Sectors stock closes")
    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    prices = prices.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")

    calculated: dict[str, dict[str, dict[str, Any]]] = {}
    for target in replay_dates:
        target_iso = target.isoformat()
        benchmark_rows_for_date = _return_map(benchmark.rename(columns={"ticker": "ticker"}), target)
        benchmark_return = benchmark_rows_for_date.get("IHSG")
        if not benchmark_return or benchmark_return.get("as_of") != target:
            raise ValueError(f"native IHSG returns unavailable at replay date {target_iso}")
        stock_returns = _return_map(prices, target)
        calculated[target_iso] = {}
        for ticker, stock in by_ticker.items():
            values = {}
            for label in HORIZONS:
                values[label] = _member_window(
                    stock,
                    action_map[ticker],
                    stock_returns.get(ticker),
                    benchmark_return,
                    label,
                    target_iso,
                )
            calculated[target_iso][ticker] = values

    cohort_exclusions: dict[str, list[dict[str, str]]] = {}
    for sector in sorted(sector_counts):
        sector_tickers = sorted(ticker for ticker, stock in by_ticker.items() if stock["sector"] == sector)
        cohort_exclusions[sector] = []
        for ticker in sector_tickers:
            action_windows = [
                (day.isoformat(), label, calculated[day.isoformat()][ticker][label]["exclusion_reason"])
                for day in replay_dates for label in HORIZONS
                if calculated[day.isoformat()][ticker][label]["exclusion_reason"]
                and calculated[day.isoformat()][ticker][label]["exclusion_reason"].startswith("MECHANICAL_ACTION_")
            ]
            if action_windows:
                first = action_windows[0]
                cohort_exclusions[sector].append({
                    "ticker": ticker,
                    "first_unavailable_date": first[0],
                    "horizon": first[1],
                    "reason": first[2],
                })

    def build_series(dates: list[date], mode: str) -> list[dict[str, Any]]:
        output = []
        for index, target in enumerate(dates):
            target_iso = target.isoformat()
            previous_iso = dates[index - 1].isoformat() if index else None
            groups_out = []
            for sector in sorted(sector_counts):
                sector_tickers = sorted(ticker for ticker, stock in by_ticker.items() if stock["sector"] == sector)
                valid_by_horizon = {
                    label: [ticker for ticker in sector_tickers
                            if calculated[target_iso][ticker][label]["exclusion_reason"] is None]
                    for label in HORIZONS
                }
                leadership_cohort = sorted(set.intersection(*(set(valid_by_horizon[label]) for label in HORIZONS)))
                map_cohort = sorted(set(valid_by_horizon["20d"]) & set(valid_by_horizon["60d"]))
                previous_20d = set()
                if previous_iso is not None:
                    previous_20d = {
                        ticker for ticker in sector_tickers
                        if calculated[previous_iso][ticker]["20d"]["exclusion_reason"] is None
                    }
                diffusion_cohort = sorted(set(valid_by_horizon["20d"]) & previous_20d)
                contributors = []
                member_by_ticker = {ticker: by_ticker[ticker] for ticker in sorted(by_ticker) if by_ticker[ticker]["sector"] == sector}
                for ticker, stock in member_by_ticker.items():
                    windows = calculated[target_iso][ticker]
                    contributors.append({
                        "ticker": ticker,
                        "company_name": stock.get("company_name"),
                        "contributes_20d": ticker in valid_by_horizon["20d"],
                        "contributes_to_leadership": ticker in leadership_cohort,
                        "contributes_to_60d_map": ticker in map_cohort,
                        "contributes_to_diffusion_comparison": ticker in diffusion_cohort,
                        "returns": windows,
                    })
                metric_values: dict[str, dict[str, float | None]] = {}
                contributor_counts = {}
                for label in HORIZONS:
                    tickers = valid_by_horizon[label]
                    rows = [calculated[target_iso][ticker][label] for ticker in tickers]
                    contributor_counts[label] = len(tickers)
                    enough_horizon = len(tickers) >= MINIMUM_CONTRIBUTORS
                    if enough_horizon and rows:
                        raw_mean = sum(float(row["return_pct"]) for row in rows) / len(rows)
                        excess_mean = sum(float(row["excess_return_pct"]) for row in rows) / len(rows)
                        target_benchmark = _return_map(benchmark, target).get("IHSG", {})
                        bench_value = target_benchmark.get(f"return_{label}")
                        metric_values[label] = {
                            "stock_return_pct": round(raw_mean, 8),
                            "benchmark_return_pct": round(float(bench_value), 8) if bench_value is not None else None,
                            "excess_return_pct": round(excess_mean, 8),
                            "eligible_contributors": len(tickers),
                        }
                    else:
                        metric_values[label] = {"stock_return_pct": None, "benchmark_return_pct": None,
                                                "excess_return_pct": None, "eligible_contributors": len(tickers)}
                enough_leadership = len(leadership_cohort) >= MINIMUM_CONTRIBUTORS
                leadership_values = {
                    label: (sum(float(calculated[target_iso][ticker][label]["excess_return_pct"])
                                for ticker in leadership_cohort) / len(leadership_cohort))
                    if enough_leadership else None
                    for label in HORIZONS
                }
                enough_diffusion = len(diffusion_cohort) >= MINIMUM_CONTRIBUTORS
                count = sum(
                    calculated[target_iso][ticker]["20d"]["excess_return_pct"] > 0
                    for ticker in diffusion_cohort
                ) if enough_diffusion else None
                previous_count = None
                delta_count = None
                if enough_diffusion and previous_iso is not None:
                    previous_count = sum(
                        calculated[previous_iso][ticker]["20d"]["excess_return_pct"] > 0
                        for ticker in diffusion_cohort
                    )
                    delta_count = count - previous_count
                breadth_pct = round(count / len(diffusion_cohort) * 100, 8) if enough_diffusion else None
                previous_breadth_pct = round(previous_count / len(diffusion_cohort) * 100, 8) if enough_diffusion and previous_count is not None else None
                diffusion = classify_diffusion_v2(
                    breadth_current=breadth_pct,
                    breadth_previous=previous_breadth_pct,
                    group_size=len(diffusion_cohort),
                    eligible=enough_diffusion and previous_count is not None,
                    breadth_change_count=delta_count,
                )
                leadership = classify_leadership(
                    excess_return_20d=leadership_values["20d"],
                    excess_return_5d=leadership_values["5d"],
                    excess_return_60d=leadership_values["60d"],
                    eligible=enough_leadership,
                )
                map_values = None
                if len(map_cohort) >= MINIMUM_CONTRIBUTORS:
                    map_20 = sum(float(calculated[target_iso][ticker]["20d"]["excess_return_pct"]) for ticker in map_cohort) / len(map_cohort)
                    map_60 = sum(float(calculated[target_iso][ticker]["60d"]["excess_return_pct"]) for ticker in map_cohort) / len(map_cohort)
                    map_values = {"cohort_tickers": map_cohort,
                                  "eligible_contributors": len(map_cohort),
                                  "x_60d_excess_pct": round(map_60, 8),
                                  "y_relative_momentum_pct": round(map_20 - map_60, 8)}
                concentration = None
                concentration_tickers = valid_by_horizon["20d"]
                if len(concentration_tickers) >= MINIMUM_CONTRIBUTORS:
                    rows = []
                    for ticker in concentration_tickers:
                        reading = calculated[target_iso][ticker]["20d"]
                        stock = by_ticker[ticker]
                        prices_by_date = {row["date"]: row["close"] for row in stock.get("prices", [])}
                        start_close = prices_by_date.get(reading["start_date"])
                        end_close = prices_by_date.get(reading["end_date"])
                        rows.extend([
                            {"ticker": ticker, "date": reading["start_date"], "close": start_close},
                            {"ticker": ticker, "date": reading["end_date"], "close": end_close},
                        ])
                    concentration = compute_concentration_v2(
                        pd.DataFrame(rows), group_tickers=concentration_tickers, horizon=1,
                        as_of=target, price_col="close",
                    ).to_dict()
                groups_out.append({
                    "sector": sector,
                    "requested_constituents": 6,
                    "eligible_contributors": len(valid_by_horizon["20d"]),
                    "contributor_counts": contributor_counts,
                    "comparison_cohorts": {
                        "leadership_tickers": leadership_cohort,
                        "map_tickers": map_cohort,
                        "diffusion_tickers": diffusion_cohort,
                    },
                    "signal_status": "PASS" if len(valid_by_horizon["20d"]) >= MINIMUM_CONTRIBUTORS else "UNCONFIRMED_BELOW_FIVE_CONTRIBUTORS",
                    "returns": metric_values,
                    "descriptive_returns": {
                        label: {
                            "stock_return_pct": round(sum(float(calculated[target_iso][ticker][label]["return_pct"]) for ticker in names) / len(names), 8) if names else None,
                            "excess_return_pct": round(sum(float(calculated[target_iso][ticker][label]["excess_return_pct"]) for ticker in names) / len(names), 8) if names else None,
                            "eligible_contributors": len(names),
                        } for label, names in valid_by_horizon.items()
                    },
                    "descriptive_map": {
                        "cohort_tickers": map_cohort,
                        "eligible_contributors": len(map_cohort),
                        "x_60d_excess_pct": round(sum(float(calculated[target_iso][ticker]["60d"]["excess_return_pct"]) for ticker in map_cohort) / len(map_cohort), 8),
                        "y_relative_momentum_pct": round(sum(float(calculated[target_iso][ticker]["20d"]["excess_return_pct"]) - float(calculated[target_iso][ticker]["60d"]["excess_return_pct"]) for ticker in map_cohort) / len(map_cohort), 8),
                    } if map_cohort else None,
                    "map": map_values,
                    "diffusion": {
                        "outperforming_count": count,
                        "previous_outperforming_count": previous_count,
                        "change_count": delta_count,
                        "eligible_count": len(diffusion_cohort) if enough_diffusion else 0,
                        "breadth_pct": breadth_pct,
                        "previous_breadth_pct": previous_breadth_pct,
                        "state": diffusion.value if isinstance(diffusion, DiffusionStateV2) else str(diffusion),
                    },
                    "leadership_state": leadership.value if hasattr(leadership, "value") else str(leadership),
                    "concentration_v2": concentration,
                    "contributors": contributors,
                })
            output.append({"date": target_iso, "mode": mode, "previous_date": previous_iso, "groups": groups_out})
        return output

    daily = build_series(replay_dates, "daily")
    weekly = build_series(weekly_dates, "weekly")
    ytd = _baseline_reading(sample, ytd_baseline_path, action_map, {
        sector: [by_ticker[ticker] for ticker in sorted(by_ticker) if by_ticker[ticker]["sector"] == sector]
        for sector in sorted(sector_counts)
    })
    methodology = [
        "The 66 names were selected using market capitalization observed on 2026-10-02 and are replayed retrospectively; this is not a point-in-time universe.",
        "Returns use raw Sectors daily closes and native Sectors IHSG closes, with shared observed start and end dates. No adjusted-price series is claimed.",
        "A split, rights issue, bonus, cash dividend, or other listed mechanical corporate action inside a return window excludes that name from the affected window.",
        "Each replay comparison uses the same eligible names at its paired dates; that cohort may change between date pairs when a price or action window changes eligibility. All 66 names remain listed in the constituent inspector, with exclusion reasons.",
        "Sector returns are equal-weighted across fixed eligible contributors. Leadership and diffusion are unconfirmed below five contributors; missing observations are never filled.",
        "YTD is shown only when each stock and native IHSG share an observed prior-year baseline date; unsupported baselines remain explicit gaps.",
    ]
    asset = {
        "schema_version": SCHEMA,
        "action_events": action_map,
        "as_of": as_of,
        "label": "Sectors leadership and diffusion · recorded 66-stock sample",
        "sources": {
            "recorded_sample_sha256": _sha(sample_raw),
            "selection_market_source_sha256": market_hash,
            "provider": "Sectors API",
            "price_basis": "raw daily close",
            "benchmark": "native Sectors IHSG close",
        },
        "selection": {
            "stock_count": 66,
            "stocks_per_sector": 6,
            "membership_release_session": sample["selection"]["membership_release_session"],
            "membership_as_of": sample["selection"]["membership_as_of"],
            "selected_market_cap_date": sample["selection"]["selected_market_cap_date"],
            "retrospective": True,
        },
        "contract": {
            "horizons_sessions": HORIZONS,
            "replay_calendar_days": REPLAY_CALENDAR_DAYS,
            "minimum_contributors": MINIMUM_CONTRIBUTORS,
            "fixed_comparison_cohort": "same eligible names at each paired replay date",
            "cohort_may_change_between_pairs": True,
            "leadership": "existing classify_leadership contract",
            "diffusion": "existing classify_diffusion_v2 contract with exact integer count changes",
            "concentration": "existing concentration_v2 absolute and signed attribution contract",
        },
        "corporate_action_exclusions": cohort_exclusions,
        "comparison_cohort_rule": "Each replay comparison uses the same eligible names at its paired dates; the 66-name membership itself stays frozen. Missing and action-affected observations are excluded by date and remain disclosed.",
        "ytd": ytd,
        "daily": daily,
        "weekly": weekly,
        "methodology": methodology,
    }
    raw = canonical_json_bytes(asset) + b"\n"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    return {
        "status": "PASS",
        "schema_version": SCHEMA,
        "action_events": action_map,
        "as_of": as_of,
        "sample_sha256": _sha(sample_raw),
        "selection_market_sha256": market_hash,
        "asset_sha256": _sha(raw),
        "asset_bytes": len(raw),
        "stock_count": 66,
        "sectors": len(sector_counts),
        "daily_replay_dates": len(daily),
        "weekly_replay_dates": len(weekly),
        "latest_20d_contributor_counts": {row["sector"]: row["eligible_contributors"] for row in daily[-1]["groups"]},
        "ytd_status": ytd["status"],
        "output": str(out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--selection-market", required=True, type=Path)
    parser.add_argument("--ytd-baseline", type=Path)
    parser.add_argument("--selection-plan", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(sample_path=args.sample, selection_market_path=args.selection_market,
                       out=args.out, ytd_baseline_path=args.ytd_baseline,
                       selection_plan_path=args.selection_plan)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SECTORS_ANALYSIS_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
