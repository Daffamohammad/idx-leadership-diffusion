"""Build release-bound official daily breadth and fixed-cohort price context."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _directional_snapshot(traded: list[dict[str, Any]]) -> dict[str, Any]:
    categories = {
        "advancing": [row for row in traded if isinstance(row.get("return_1d"), (int, float)) and row["return_1d"] > 0],
        "unchanged": [row for row in traded if isinstance(row.get("return_1d"), (int, float)) and row["return_1d"] == 0],
        "declining": [row for row in traded if isinstance(row.get("return_1d"), (int, float)) and row["return_1d"] < 0],
    }
    value_rows = {key: [row for row in rows if isinstance(row.get("value_idr"), (int, float))] for key, rows in categories.items()}
    category_values = {key: sum(float(row["value_idr"]) for row in rows) for key, rows in value_rows.items()}
    denominator = sum(category_values.values())
    shares = {key: (value / denominator * 100.0 if denominator > 0 else None) for key, value in category_values.items()}
    constituents = {
        key: sorted(({
            "ticker": str(row["ticker"]).upper(),
            "company_name": str(row.get("company_name") or row["ticker"]),
            "return_1d_pct": float(row["return_1d"]),
            "value_idr": float(row["value_idr"]) if isinstance(row.get("value_idr"), (int, float)) else None,
        } for row in rows), key=lambda row: row["ticker"])
        for key, rows in categories.items()
    }
    return {
        "categories": categories,
        "moving": categories["advancing"] + categories["unchanged"] + categories["declining"],
        "category_values": category_values,
        "denominator_idr": denominator,
        "coverage_count": sum(len(rows) for rows in value_rows.values()),
        "value_shares": shares,
        "constituents": constituents,
    }


def _breaks_range(current: float, prior_values: list[float], *, side: str) -> bool:
    if not prior_values:
        return False
    if side == "high":
        return current > max(prior_values)
    if side == "low":
        return current < min(prior_values)
    raise ValueError(f"unsupported range-break side: {side}")


def _complete_history_tickers(close: pd.DataFrame, candidates: set[str], prior_dates: list[str]) -> list[str]:
    if not prior_dates:
        return []
    return sorted(
        ticker for ticker in candidates
        if ticker in close.index and close.loc[ticker, prior_dates].notna().all()
    )


def _calendar_window_sessions(benchmark_sessions: list[str], start: str, end: str) -> list[str]:
    """Return observed benchmark sessions in [start, end), including a non-session start."""
    return [day for day in benchmark_sessions if start <= day < end]


def _covers_calendar_window_start(benchmark_sessions: list[str], start: str) -> bool:
    """Require the benchmark vintage to begin on or before the requested cutoff."""
    return bool(benchmark_sessions) and benchmark_sessions[0] <= start


def _date_column(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.strftime("%Y-%m-%d")
    return result


def _parse_idx_daily_totals(path: Path, *, expected_date: str) -> dict[str, Any]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ValueError("SOURCE_UNAVAILABLE: extracting official daily totals requires pdfplumber") from exc
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    date_match = re.search(r"\b(\d{2}\s+[A-Za-z]+\s+\d{4})\b", text)
    if not date_match or datetime.strptime(date_match.group(1), "%d %B %Y").date().isoformat() != expected_date:
        raise ValueError(f"IDX daily-statistics date does not match {expected_date}: {path.name}")
    volume_match = re.search(r"Volume\s+.*?([\d,]+)\s*\(million shares\)", text, re.I | re.S)
    value_match = re.search(r"Value\s+([\d,]+)\s+[\d,]+\s*\(billion IDR\)", text, re.I | re.S)
    frequency_match = re.search(r"Frequency\s+([\d,]+)\s*\(thousand times\)", text, re.I | re.S)
    if not all((volume_match, value_match, frequency_match)):
        raise ValueError(f"IDX daily-statistics summary totals were not parsed from {path.name}")
    return {
        "as_of": expected_date,
        "turnover_idr": int(value_match.group(1).replace(",", "")) * 1_000_000_000,
        "volume_shares": int(volume_match.group(1).replace(",", "")) * 1_000_000,
        "frequency_trades": int(frequency_match.group(1).replace(",", "")) * 1_000,
        "published_units": {"turnover": "billion IDR, rounded to whole billion", "volume": "million shares, rounded to whole million", "frequency": "thousand trades, rounded to whole thousand"},
        "scope": "Total stock trading in regular, cash and negotiated markets, as stated on IDX Daily Statistics page 1.",
        "source_file": path.name,
        "source_sha256": _sha(path),
    }


def _load_official_market_totals(foreign: dict[str, Any], evidence_dir: Path, *, as_of: str) -> list[dict[str, Any]]:
    rows = sorted([row for row in foreign.get("daily", []) if row.get("as_of", "") <= as_of], key=lambda row: row["as_of"])
    observed_dates = [str(row.get("as_of")) for row in rows]
    if len(observed_dates) != len(set(observed_dates)):
        raise ValueError("official daily statistics source contains duplicate sessions")
    if len(rows) < 21:
        raise ValueError("IDX daily-statistics evidence has fewer than 20 preceding sessions plus the selected session")
    selected = rows[-21:]
    result = []
    for row in selected:
        day = str(row["as_of"])
        compact_date = date.fromisoformat(day).strftime("%y%m%d")
        expected_hash = row.get("source", {}).get("sha256")
        paths = sorted(evidence_dir.rglob(f"*{compact_date}*.pdf"))
        match = next((path for path in paths if _sha(path) == expected_hash), None)
        if match is None:
            raise ValueError(f"missing hash-matched official IDX PDF evidence for {day}")
        result.append(_parse_idx_daily_totals(match, expected_date=day))
    expected = [row["as_of"] for row in rows[-21:]]
    if [row["as_of"] for row in result] != expected or result[-1]["as_of"] != as_of:
        raise ValueError("IDX daily-statistics market totals do not form the selected 21-session sequence")
    return result


def build(*, market_path: Path, foreign_path: Path, stock_summary_path: Path,
          prices_path: Path, benchmark_path: Path, statistics_pdf_dir: Path, out: Path) -> dict[str, Any]:
    market = json.loads(market_path.read_text(encoding="utf-8"))
    foreign = json.loads(foreign_path.read_text(encoding="utf-8"))
    as_of = str(market["as_of"])
    if as_of != "2026-10-02" or foreign.get("as_of") != as_of:
        raise ValueError("market breadth requires the October 2 market and foreign-flow releases")

    records = market.get("records", [])
    traded = [row for row in records if row.get("traded") is True and row.get("last_trade_date", as_of) == as_of]
    directional = _directional_snapshot(traded)
    advancers = directional["categories"]["advancing"]
    unchanged = directional["categories"]["unchanged"]
    decliners = directional["categories"]["declining"]
    moving = directional["moving"]
    if (len(advancers), len(unchanged), len(decliners), len(moving)) != (
        market["breadth"]["advancers"], market["breadth"]["flat"],
        market["breadth"]["decliners"], market["breadth"]["traded_count"],
    ):
        raise ValueError("official breadth categories do not reconcile to the selected market release")

    def sum_field(rows: list[dict[str, Any]], key: str) -> float:
        return sum(float(row[key]) for row in rows if isinstance(row.get(key), (int, float)))

    total_value = directional["denominator_idr"]
    value_rows_count = directional["coverage_count"]
    category_values = directional["category_values"]
    value_shares = directional["value_shares"]
    if total_value > 0 and abs(sum(value_shares.values()) - 100.0) > 0.01:
        raise ValueError("traded-value shares fail to reconcile")
    volume_complete = len(traded) > 0 and all(isinstance(row.get("volume_shares"), (int, float)) for row in traded)
    frequency_complete = len(traded) > 0 and all(isinstance(row.get("frequency_trades"), (int, float)) for row in traded)
    official_market_totals = _load_official_market_totals(foreign, statistics_pdf_dir.resolve(strict=True), as_of=as_of)
    prior_market_totals = official_market_totals[:-1]
    current_market_totals = official_market_totals[-1]
    average_turnover = sum(row["turnover_idr"] for row in prior_market_totals) / len(prior_market_totals)

    prices = _date_column(pd.read_csv(prices_path, parse_dates=["date"]))
    benchmark = _date_column(pd.read_csv(benchmark_path, parse_dates=["date"]))
    if not {"ticker", "date", "adjusted_close"}.issubset(prices.columns) or not {"date", "close"}.issubset(benchmark.columns):
        raise ValueError("public price vintage is missing adjusted stock or IHSG closes")
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    if prices.duplicated(["ticker", "date"]).any() or benchmark.duplicated(["date"]).any():
        raise ValueError("price vintage contains duplicate ticker or benchmark sessions")
    if prices["adjusted_close"].isna().any() or (prices["adjusted_close"] <= 0).any() or benchmark["close"].isna().any() or (benchmark["close"] <= 0).any():
        raise ValueError("price vintage contains invalid prices")
    benchmark_sessions = sorted(benchmark["date"].astype(str).unique())
    if not benchmark_sessions or benchmark_sessions[-1] != as_of:
        raise ValueError("benchmark does not reach the selected session")
    close = prices.pivot(index="ticker", columns="date", values="adjusted_close")
    ticker_names = {str(row["ticker"]).upper(): str(row.get("company_name") or row["ticker"]) for row in records}
    record_by_ticker = {str(row["ticker"]).upper(): row for row in records}

    # Price-breadth cohort is frozen at the selected release and complete on
    # every benchmark session in the full acquired vintage.
    requested_history_start = "2025-09-01"
    available_price_start = str(prices["date"].min())
    first_day = (date.fromisoformat(as_of) - timedelta(weeks=52)).isoformat()
    actual_history_start = max(requested_history_start, available_price_start)
    analysis_sessions = [day for day in benchmark_sessions if actual_history_start <= day <= as_of]
    if len(analysis_sessions) < 60:
        raise ValueError("validated public price vintage has fewer than 60 sessions")
    signal_tickers = {
        ticker for ticker, row in record_by_ticker.items()
        if row.get("signal_eligible") is True
    }
    common = close.reindex(columns=analysis_sessions).notna().all(axis=1)
    fixed_tickers = sorted(signal_tickers.intersection(close.index[common].astype(str)))
    if not fixed_tickers:
        raise ValueError("no fixed price cohort has complete 52-week histories")
    cohort_prices = close.loc[fixed_tickers, analysis_sessions]
    history = []
    for index, day in enumerate(analysis_sessions):
        if index == 0:
            history.append({"as_of": day, "advancers": None, "unchanged": None, "decliners": None, "net_advances": None, "moving_count": 0, "eligible_count": len(fixed_tickers)})
            continue
        daily_return = cohort_prices[day] / cohort_prices[analysis_sessions[index - 1]] - 1.0
        up = int((daily_return > 0).sum())
        flat = int((daily_return == 0).sum())
        down = int((daily_return < 0).sum())
        history.append({"as_of": day, "advancers": up, "unchanged": flat, "decliners": down,
                        "net_advances": up - down, "moving_count": up + down, "eligible_count": len(fixed_tickers)})

    historical_high_lows: dict[str, Any] = {}
    target_index = benchmark_sessions.index(as_of)
    cutoff_52w = first_day
    horizon_sessions = {
        "5d": benchmark_sessions[max(0, target_index - 5):target_index],
        "20d": benchmark_sessions[max(0, target_index - 20):target_index],
        "60d": benchmark_sessions[max(0, target_index - 60):target_index],
        "52w": _calendar_window_sessions(benchmark_sessions, cutoff_52w, as_of),
    }
    target_price = close.get(as_of, pd.Series(dtype=float))
    active_tickers = {str(row["ticker"]).upper() for row in traded}
    for horizon, prior_dates in horizon_sessions.items():
        if horizon == "52w" and (
            not prior_dates or not _covers_calendar_window_start(benchmark_sessions, cutoff_52w)
        ):
            continue
        rows: list[dict[str, Any]] = []
        current_eligible = [ticker for ticker in sorted(active_tickers) if ticker in target_price.index and pd.notna(target_price.loc[ticker])]
        eligible = _complete_history_tickers(close, set(current_eligible), prior_dates)
        for ticker in eligible:
            current = float(target_price.loc[ticker])
            prior = close.loc[ticker, prior_dates].astype(float)
            prior_high, prior_low = float(prior.max()), float(prior.min())
            change_pct = (current / float(prior.iloc[-1]) - 1.0) * 100.0
            if _breaks_range(current, prior.tolist(), side="high"):
                rows.append({"ticker": ticker, "company_name": ticker_names.get(ticker, ticker), "close_adjusted_idr": current,
                             "prior_range_high_idr": prior_high, "prior_range_low_idr": prior_low, "change_from_prior_close_pct": change_pct})
        highs = rows
        lows: list[dict[str, Any]] = []
        for ticker in eligible:
            current = float(target_price.loc[ticker])
            prior = close.loc[ticker, prior_dates].astype(float)
            prior_high, prior_low = float(prior.max()), float(prior.min())
            change_pct = (current / float(prior.iloc[-1]) - 1.0) * 100.0
            if _breaks_range(current, prior.tolist(), side="low"):
                lows.append({"ticker": ticker, "company_name": ticker_names.get(ticker, ticker), "close_adjusted_idr": current,
                             "prior_range_high_idr": prior_high, "prior_range_low_idr": prior_low, "change_from_prior_close_pct": change_pct})
        historical_high_lows[horizon] = {
            "eligible_count": len(eligible), "eligible_scope": "Selected-session traded stocks with complete adjusted-close observations for every benchmark session in the prior window",
            "prior_sessions": len(prior_dates), "start": prior_dates[0] if prior_dates else None, "end": prior_dates[-1] if prior_dates else None,
            "new_high_count": len(highs), "new_low_count": len(lows),
            "new_highs": sorted(highs, key=lambda row: (-row["change_from_prior_close_pct"], row["ticker"])),
            "new_lows": sorted(lows, key=lambda row: (row["change_from_prior_close_pct"], row["ticker"])),
            "tie_rule": "Strict break only; equal closes do not qualify.",
        }

    daily_flow = sorted(foreign.get("daily", []), key=lambda row: row["as_of"])
    at_or_before = [row for row in daily_flow if row["as_of"] <= as_of]
    current_flow = next((row for row in at_or_before if row["as_of"] == as_of), None)
    prior_flow = [row for row in at_or_before if row["as_of"] < as_of][-20:]
    flow_value = current_flow.get("net_foreign_value_idr") if current_flow else None
    flow_direction = "BUYING" if isinstance(flow_value, (int, float)) and flow_value > 0 else "SELLING" if isinstance(flow_value, (int, float)) and flow_value < 0 else "NEUTRAL" if flow_value == 0 else None
    streak = 0
    if flow_direction in {"BUYING", "SELLING"}:
        for row in reversed(at_or_before):
            value = row.get("net_foreign_value_idr")
            direction = "BUYING" if isinstance(value, (int, float)) and value > 0 else "SELLING" if isinstance(value, (int, float)) and value < 0 else "NEUTRAL"
            if direction != flow_direction:
                break
            streak += 1

    flow_context = {
        "provider": "IDX official daily statistics",
        "scope": foreign.get("scope"),
        "unit": "IDR",
        "as_of": as_of,
        "daily_net_idr": flow_value,
        "preceding_20_session_average_absolute_net_idr": (
            sum(abs(row["net_foreign_value_idr"]) for row in prior_flow) / 20
            if len(prior_flow) == 20 and all(isinstance(row.get("net_foreign_value_idr"), (int, float)) for row in prior_flow) else None
        ),
        "preceding_20_session_count": len(prior_flow),
        "direction": flow_direction,
        "consecutive_sessions": streak,
        "daily_series_start": at_or_before[0]["as_of"] if at_or_before else None,
        "daily_series_count": len(at_or_before),
    }

    payload = {
        "schema_version": "market-breadth-v1",
        "as_of": as_of,
        "official_daily": {
            "scope": market["breadth"]["scope"],
            "breadth": {
                "advancers": len(advancers), "unchanged": len(unchanged), "decliners": len(decliners),
                "net_advances": len(advancers) - len(decliners),
                "advancers_to_decliners_ratio": len(advancers) / len(decliners) if decliners else None,
                "advancing_pct_of_moving_stocks": len(advancers) / (len(advancers) + len(decliners)) * 100 if len(advancers) + len(decliners) else None,
                "moving_stock_count": len(advancers) + len(decliners), "traded_count": len(moving),
            },
            "constituents_by_direction": directional["constituents"],
            "traded_value": {
                "unit": "IDR", "denominator_idr": total_value, "coverage_count": value_rows_count,
                "advancing_idr": category_values["advancing"], "unchanged_idr": category_values["unchanged"], "declining_idr": category_values["declining"],
                "advancing_pct": value_shares["advancing"], "unchanged_pct": value_shares["unchanged"], "declining_pct": value_shares["declining"],
                "denominator": "Sum of official Stock Summary value for selected-session traded stocks with a comparable close and reported value.",
            },
            "activity": {
                "turnover_idr": total_value, "volume_shares": sum_field(traded, "volume_shares") if volume_complete else None,
                "volume_lots": sum_field(traded, "volume_shares") / 100 if volume_complete else None,
                "frequency_trades": sum_field(traded, "frequency_trades") if frequency_complete else None,
                "traded_stock_count": len(traded), "volume_coverage_count": sum(isinstance(row.get("volume_shares"), (int, float)) for row in traded),
                "frequency_coverage_count": sum(isinstance(row.get("frequency_trades"), (int, float)) for row in traded),
                "units": {"turnover": "IDR", "volume_shares": "shares", "volume_lots": "lots (100 shares)", "frequency": "trades"},
                "market_scope_totals": {
                    "provider": "IDX official daily statistics", "scope": current_market_totals["scope"],
                    "turnover_idr": current_market_totals["turnover_idr"], "volume_shares": current_market_totals["volume_shares"],
                    "volume_lots": current_market_totals["volume_shares"] / 100, "frequency_trades": current_market_totals["frequency_trades"],
                    "preceding_20_session_average_turnover_idr": average_turnover,
                    "current_to_average_turnover_multiple": current_market_totals["turnover_idr"] / average_turnover if average_turnover > 0 else None,
                    "preceding_sessions": len(prior_market_totals), "daily_totals": official_market_totals,
                    "precision": current_market_totals["published_units"],
                },
            },
            "market_foreign_flow": flow_context,
        },
        "historical_price_breadth": {
            "basis": "Adjusted-close daily advances among a fixed selected-release signal-eligible cohort with complete observations for each benchmark session in the displayed window.",
            "start": analysis_sessions[0], "end": analysis_sessions[-1], "cohort_count": len(fixed_tickers),
            "cohort_tickers": fixed_tickers, "cohort_sha256": _hash_json(fixed_tickers),
            "sessions": history,
        },
        "new_highs_lows": {
            "price_basis": "Adjusted close; raw close remains in the public price vintage for reference.",
            "selected_session_traded_only": True, "items": historical_high_lows,
        },
        "sources": {
            "market_release_sha256": _sha(market_path), "stock_summary_sha256": _sha(stock_summary_path),
            "foreign_history_sha256": _sha(foreign_path), "adjusted_price_panel_sha256": _sha(prices_path),
            "ihsg_panel_sha256": _sha(benchmark_path),
        },
        "methodology": [
            "Official daily breadth and trading totals use selected-session IDX Stock Summary values.",
            "Historical price breadth is a separate fixed-cohort calculation and is not the official daily market-wide count.",
            "New highs and lows compare the selected-session adjusted close with the complete prior session or 52-calendar-week range; ties do not count.",
            "Foreign flow uses the selected release's official IDX daily statistics sample; the 20-session average uses the 20 preceding observed sessions and excludes the selected session.",
        ],
        "coverage": {
            "official_traded_count": len(traded), "fixed_price_cohort_count": len(fixed_tickers),
            "analysis_benchmark_sessions": len(analysis_sessions), "excluded_signal_eligible_incomplete_history": len(signal_tickers - set(fixed_tickers)),
            "limits": ([f"The validated price vintage starts {available_price_start}, after the requested {requested_history_start}; 52-calendar-week new-high/low counts are omitted until the older price history is acquired."] if available_price_start > requested_history_start else []),
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("market", "foreign", "stock-summary", "prices", "benchmark", "statistics-pdf-dir", "out"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(market_path=args.market, foreign_path=args.foreign, stock_summary_path=args.stock_summary,
                       prices_path=args.prices, benchmark_path=args.benchmark, statistics_pdf_dir=args.statistics_pdf_dir, out=args.out)
        print(json.dumps({"schema_version": result["schema_version"], "as_of": result["as_of"],
                          "cohort_count": result["historical_price_breadth"]["cohort_count"],
                          "new_highs_lows": {key: {"eligible": row["eligible_count"], "highs": row["new_high_count"], "lows": row["new_low_count"]}
                                             for key, row in result["new_highs_lows"]["items"].items()}}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"MARKET_BREADTH_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
