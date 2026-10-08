"""Offline, horizon-specific group readings on observed benchmark sessions."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import pandas as pd

from idx_leadership.signals.diffusion_v2 import classify_diffusion_v2
from idx_leadership.signals.leadership import classify_leadership


def phase(x: float | None, y: float | None) -> str:
    if x is None or y is None or not math.isfinite(x) or not math.isfinite(y):
        return "UNAVAILABLE"
    return ("LEADING" if x >= 0 else "IMPROVING") if y >= 0 else ("WEAKENING" if x >= 0 else "LAGGING")


def group_readings(members: list[str], prices: pd.DataFrame, benchmark: pd.Series,
                   dates: list[str], weekly_dates: list[str], eligible: set[str]) -> dict[str, Any]:
    sessions = sorted(benchmark.index.astype(str))
    positions = {day: i for i, day in enumerate(sessions)}
    prior_year = [day for day in sessions if day[:4] < dates[-1][:4]]
    baseline = prior_year[-1] if prior_year else None
    starts = {day: {**{f"{n}d": sessions[positions[day] - n] if positions[day] >= n else None for n in (5, 20, 60)}, "ytd": baseline} for day in dates}
    cohorts: dict[str, list[str]] = {}
    for horizon in ("5d", "20d", "60d", "ytd"):
        required = sorted({endpoint for day in dates for endpoint in (day, starts[day][horizon]) if endpoint})
        if any(starts[day][horizon] is None for day in dates):
            cohorts[horizon] = []
            continue
        panel = prices.reindex(index=members, columns=required)
        valid = panel.notna().all(axis=1) & panel.gt(0).all(axis=1) & panel.lt(float("inf")).all(axis=1)
        cohorts[horizon] = sorted(ticker for ticker in valid[valid].index if ticker in eligible)
    cohorts["map"] = sorted(set(cohorts["20d"]) & set(cohorts["60d"]))
    cohorts["ytd_map"] = sorted(set(cohorts["map"]) & set(cohorts["ytd"]))
    cohorts["leadership"] = sorted(set(cohorts["map"]) & set(cohorts["5d"]))

    def readings(day: str, horizon: str, names: list[str]) -> pd.Series:
        start = starts[day][horizon]
        if not names or not start:
            return pd.Series(dtype=float)
        return (prices.loc[names, day] / prices.loc[names, start] - 1) * 100

    def excess(day: str, horizon: str, names: list[str]) -> pd.Series:
        raw = readings(day, horizon, names)
        start = starts[day][horizon]
        return raw - (float(benchmark[day]) / float(benchmark[start]) - 1) * 100 if start else raw

    def mean(values: pd.Series) -> float | None:
        value = float(values.mean()) if not values.empty else None
        return value if value is not None and math.isfinite(value) else None

    points = []
    for day in dates:
        ex = {h: mean(excess(day, h, cohorts[h])) for h in ("5d", "20d", "60d", "ytd")}
        map20 = mean(excess(day, "20d", cohorts["map"]))
        map60 = mean(excess(day, "60d", cohorts["map"]))
        momentum = map20 - map60 if map20 is not None and map60 is not None else None
        ytd20 = mean(excess(day, "20d", cohorts["ytd_map"]))
        ytd60 = mean(excess(day, "60d", cohorts["ytd_map"]))
        ytdx = mean(excess(day, "ytd", cohorts["ytd_map"]))
        ytdy = ytd20 - ytd60 if ytd20 is not None and ytd60 is not None else None
        lead = {h: mean(excess(day, h, cohorts["leadership"])) for h in ("5d", "20d", "60d")}
        signed = readings(day, "20d", cohorts["20d"])
        raw = signed.abs().sort_values(ascending=False)
        gross = float(raw.sum())
        n = len(cohorts["20d"])
        count = int((excess(day, "20d", cohorts["20d"]) > 0).sum()) if n else None
        points.append({
            "as_of": day, **{f"excess_return_{h}": v for h, v in ex.items()},
            "relative_momentum": momentum, "map_x_60d": map60,
            "map_x_ytd": ytdx, "map_y_ytd": ytdy,
            "map_contributors": len(cohorts["map"]), "ytd_map_contributors": len(cohorts["ytd_map"]),
            "contributor_counts": {h: len(names) for h, names in cohorts.items()},
            "breadth_count": count, "breadth_denominator": n,
            "breadth_pct": 100 * count / n if count is not None and n else None,
            "leadership": classify_leadership(excess_return_20d=lead["20d"], excess_return_5d=lead["5d"], excess_return_60d=lead["60d"], eligible=len(cohorts["leadership"]) >= 5).value,
            "leadership_basis": lead,
            "concentration_top3_pct": 100 * float(raw.head(3).sum()) / gross if gross > 0 and n >= 3 else None,
            "concentration_detail": [{"ticker": ticker, "return_pct": float(signed[ticker]),
                                      "absolute_share_pct": 100 * float(value) / gross if gross else None}
                                     for ticker, value in raw.items()],
            "rotation_phase": phase(map60, momentum),
            "rotation_phase_ytd": phase(ytdx, ytdy),
            "coverage_pct": 100 * n / len(members) if members else 0,
        })

    def cadence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output = []
        for current in rows:
            point = dict(current)
            previous = output[-1] if output else None
            n = point["breadth_denominator"]
            delta = point["breadth_count"] - previous["breadth_count"] if previous and point["breadth_count"] is not None and previous["breadth_count"] is not None else None
            state = classify_diffusion_v2(breadth_current=point["breadth_pct"], breadth_previous=previous["breadth_pct"] if previous else None, group_size=n, eligible=n >= 5 and delta is not None, breadth_change_count=delta).value
            point.update(breadth_change_count=delta, breadth_change_pp=100 * delta / n if delta is not None and n else None, diffusion_v2=state, diffusion=state.removesuffix("_FIRM").removesuffix("_FRAGILE"), concentration_change_pp=point["concentration_top3_pct"] - previous["concentration_top3_pct"] if previous and point["concentration_top3_pct"] is not None and previous["concentration_top3_pct"] is not None else None, leadership_transition=f"{previous['leadership']} -> {point['leadership']}" if previous and previous["leadership"] != point["leadership"] else None, diffusion_transition=f"{previous['diffusion_v2']} -> {state}" if previous and previous["diffusion_v2"] != state else None, material_shift=None)
            if previous:
                reasons = []
                if point["breadth_change_pp"] is not None and abs(point["breadth_change_pp"]) >= 10:
                    reasons.append(f"breadth {point['breadth_change_pp']:+.1f}pp")
                if point["excess_return_20d"] is not None and previous["excess_return_20d"] is not None:
                    change = point["excess_return_20d"] - previous["excess_return_20d"]
                    if abs(change) >= 1.5:
                        reasons.append(f"20D excess {change:+.2f}pp")
                point["material_shift"] = "; ".join(reasons) or None
            output.append(point)
        return output

    weekly = cadence([point for point in points if point["as_of"] in weekly_dates])
    persistence = 0
    for point in reversed(weekly):
        if point["leadership"] != weekly[-1]["leadership"]:
            break
        persistence += 1
    coverage = {}
    for h in ("5d", "20d", "60d", "ytd"):
        required = sorted({endpoint for day in dates for endpoint in (day, starts[day][h]) if endpoint})
        coverage[h] = {}
        for ticker in members:
            if ticker in cohorts[h]:
                continue
            if ticker not in eligible:
                reason = "Outside the dated price-eligible universe"
            elif any(starts[day][h] is None for day in dates):
                reason = "Observed prior-year benchmark baseline is missing" if h == "ytd" else "Insufficient observed benchmark sessions"
            else:
                missing = [day for day in required if ticker not in prices.index or day not in prices.columns or pd.isna(prices.loc[ticker, day]) or not math.isfinite(float(prices.loc[ticker, day])) or float(prices.loc[ticker, day]) <= 0]
                reason = f"No positive matched close on {missing[0]} ({len(missing)} missing endpoints); excluded from fixed replay cohort" if missing else "No matched reading"
            coverage[h][ticker] = reason
    names = cohorts["20d"]
    return {"daily": cadence(points), "weekly": weekly,
            "cohorts": cohorts, "cohort": {"contributors": names, "count": len(names), "sha256": hashlib.sha256(json.dumps(names, separators=(",", ":")).encode()).hexdigest()},
            "coverage_reasons": {ticker: "; ".join(f"{h.upper()}: {reasons[ticker]}" for h, reasons in coverage.items() if ticker in reasons) for ticker in members if any(ticker in reasons for reasons in coverage.values())},
            "coverage_by_horizon": coverage,
            "persistence": {"current_leadership_weeks": persistence, "observations": len(weekly)}}
