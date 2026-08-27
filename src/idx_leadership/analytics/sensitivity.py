"""Offline leadership-horizon and diffusion group-size sensitivity harnesses.

The diagnostics compare stability, agreement, coverage, churn, and duration.
They deliberately do not calculate or optimize against future returns.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from ..features.relative_strength import compute_benchmark_returns
from ..features.returns import compute_returns
from ..models import LeadershipState
from ..signals.diffusion import classify_diffusion
from ..signals.diffusion_v2 import (
    DiffusionStateV2,
    classify_diffusion_v2,
    constituent_floor,
)
from ..signals.leadership import classify_leadership
from .turnover import LEADERSHIP_STATE_ORDER, analyze_dimension_turnover


@dataclass(frozen=True)
class HorizonVariant:
    label: str
    short: int
    primary: int
    long: int

    def role_horizons(self) -> dict[str, int]:
        return {"short": self.short, "primary": self.primary, "long": self.long}


HORIZON_VARIANTS: tuple[HorizonVariant, ...] = (
    HorizonVariant("5/20/60", short=5, primary=20, long=60),
    HorizonVariant("10/20/60", short=10, primary=20, long=60),
    HorizonVariant("10/40", short=10, primary=40, long=40),
    HorizonVariant("20/60", short=20, primary=20, long=60),
)

GROUP_SIZES: tuple[int, ...] = (3, 4, 5, 7, 10, 20, 40)


@dataclass
class MethodologySensitivityReport:
    baseline_variant: str
    horizon_summary: list[dict[str, Any]]
    group_size_summary: list[dict[str, Any]]
    recommended_minimum_group_size: int
    recommendation_basis: str
    forward_returns_used: bool = False
    live_sectors_validated: bool = False
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            "# Offline Methodology Sensitivity",
            "",
            "Forward returns used: **NO**",
            "Live Sectors validated: **NO**",
            "",
            "## Leadership horizon sensitivity",
            "",
            "| Variant | Agreement vs baseline | Rank correlation | Transition rate | Median duration | Coverage |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in self.horizon_summary:
            lines.append(
                "| {variant} | {agreement} | {rank_corr} | {transition} | "
                "{duration} | {coverage} |".format(
                    variant=row["variant"],
                    agreement=_fmt_pct(row.get("state_agreement"), ratio=True),
                    rank_corr=_fmt_number(row.get("mean_rank_correlation")),
                    transition=_fmt_pct(row.get("transition_rate"), ratio=True),
                    duration=_fmt_number(row.get("median_state_duration")),
                    coverage=_fmt_pct(row.get("coverage"), ratio=True),
                )
            )
        lines.extend(
            [
                "",
                "## Diffusion group-size sensitivity",
                "",
                "| Group size | One-name step | Required count | Baseline/candidate agreement (10pp) |",
                "| ---: | ---: | ---: | ---: |",
            ]
        )
        threshold_rows = [
            row for row in self.group_size_summary if row["threshold_pp"] == 10.0
        ]
        for row in threshold_rows:
            lines.append(
                f"| {row['group_size']} | {row['one_constituent_step_pp']:.2f}pp | "
                f"{row['minimum_changed_constituents']} | "
                f"{_fmt_pct(row['classification_agreement'], ratio=True)} |"
            )
        lines.extend(
            [
                "",
                f"Synthetic minimum-group-size candidate: **{self.recommended_minimum_group_size}**.",
                "",
                self.recommendation_basis,
            ]
        )
        if self.limitations:
            lines.extend(["", "## Limitations", ""])
            lines.extend(f"- {limitation}" for limitation in self.limitations)
        return "\n".join(lines).rstrip() + "\n"


def build_horizon_state_histories(
    *,
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    taxonomy: pd.DataFrame,
    variants: Sequence[HorizonVariant] = HORIZON_VARIANTS,
    as_of_dates: Iterable[object] | None = None,
    min_constituents: int = 4,
    min_coverage_pct: float = 60.0,
    acceleration_threshold_pp: float = 1.0,
) -> dict[str, pd.DataFrame]:
    """Build as-of leadership histories for constrained horizon variants.

    Every return calculation is truncated at its row's ``snapshot_date``.
    Adding future prices therefore cannot change prior rows.
    """

    _require_columns(prices, {"ticker", "date", "adjusted_close"}, "prices")
    _require_columns(benchmark, {"date", "close"}, "benchmark")
    _require_columns(taxonomy, {"ticker", "group_id"}, "taxonomy")
    if min_constituents < 1:
        raise ValueError("min_constituents must be at least 1")
    if not 0 <= min_coverage_pct <= 100:
        raise ValueError("min_coverage_pct must be between 0 and 100")

    price_frame = prices.copy()
    benchmark_frame = benchmark.copy()
    taxonomy_frame = (
        taxonomy[["ticker", "group_id"]]
        .dropna(subset=["ticker", "group_id"])
        .drop_duplicates("ticker", keep="last")
    )
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.date
    benchmark_frame["date"] = pd.to_datetime(
        benchmark_frame["date"], errors="coerce"
    ).dt.date
    if as_of_dates is None:
        common_dates = sorted(
            set(price_frame["date"].dropna()).intersection(
                benchmark_frame["date"].dropna()
            )
        )
        maximum_horizon = max(
            max(variant.short, variant.primary, variant.long)
            for variant in variants
        )
        dates = common_dates[maximum_horizon:]
    else:
        dates = sorted(
            {
                pd.Timestamp(value).date()
                for value in as_of_dates
                if not pd.isna(value)
            }
        )

    histories: dict[str, pd.DataFrame] = {}
    for variant in variants:
        rows: list[dict[str, Any]] = []
        horizons = variant.role_horizons()
        for snapshot_date in dates:
            security_returns = compute_returns(
                price_frame,
                horizons=horizons,
                as_of=snapshot_date,
            )
            benchmark_returns = compute_benchmark_returns(
                benchmark_frame,
                horizons=horizons,
                as_of=snapshot_date,
            )
            panel = taxonomy_frame.merge(security_returns, on="ticker", how="left")
            for role in ("short", "primary", "long"):
                benchmark_return = benchmark_returns.get(f"return_{role}")
                security_return = pd.to_numeric(
                    panel.get(f"return_{role}"), errors="coerce"
                )
                if benchmark_return is None or pd.isna(benchmark_return):
                    panel[f"excess_return_{role}"] = np.nan
                else:
                    panel[f"excess_return_{role}"] = (
                        security_return - float(benchmark_return)
                    )

            snapshot_rows: list[dict[str, Any]] = []
            for group_id, group in panel.groupby("group_id", sort=True):
                total_count = int(group["ticker"].nunique())
                primary_values = group["excess_return_primary"].dropna()
                eligible_count = int(len(primary_values))
                coverage = eligible_count / total_count if total_count else 0.0
                eligible = (
                    total_count >= min_constituents
                    and coverage * 100.0 >= min_coverage_pct
                )
                short_excess = _mean_or_none(group["excess_return_short"])
                primary_excess = _mean_or_none(group["excess_return_primary"])
                long_excess = _mean_or_none(group["excess_return_long"])
                state = classify_leadership(
                    excess_return_20d=primary_excess,
                    excess_return_5d=short_excess,
                    excess_return_60d=long_excess,
                    acceleration_threshold_pp=acceleration_threshold_pp,
                    eligible=eligible,
                )
                outperforming_count = int((primary_values > 0).sum())
                breadth = (
                    (outperforming_count / eligible_count) * 100.0
                    if eligible_count
                    else None
                )
                snapshot_rows.append(
                    {
                        "snapshot_date": snapshot_date,
                        "group_id": str(group_id),
                        "leadership_state": state.value,
                        "short_excess": short_excess,
                        "primary_excess": primary_excess,
                        "long_excess": long_excess,
                        "leadership_rank": None,
                        "constituent_count": total_count,
                        "eligible_count": eligible_count,
                        "coverage": coverage,
                        "breadth_outperforming": breadth,
                    }
                )
            eligible_rows = [
                row
                for row in snapshot_rows
                if row["leadership_state"] != LeadershipState.UNCONFIRMED.value
                and row["primary_excess"] is not None
            ]
            eligible_rows.sort(
                key=lambda row: (-float(row["primary_excess"]), row["group_id"])
            )
            for rank, row in enumerate(eligible_rows, start=1):
                row["leadership_rank"] = rank
            rows.extend(snapshot_rows)

        history = pd.DataFrame(rows)
        if not history.empty:
            history = history.sort_values(["group_id", "snapshot_date"])
            history["breadth_delta"] = history.groupby("group_id")[
                "breadth_outperforming"
            ].diff()
            history["diffusion_state"] = history.apply(
                lambda row: classify_diffusion(
                    breadth_delta_pp=(
                        None if pd.isna(row["breadth_delta"]) else row["breadth_delta"]
                    ),
                    eligible=row["leadership_state"]
                    != LeadershipState.UNCONFIRMED.value,
                ).value,
                axis=1,
            )
            history = history.sort_values(["snapshot_date", "group_id"]).reset_index(
                drop=True
            )
        histories[variant.label] = history
    return histories


def evaluate_horizon_sensitivity(
    histories: dict[str, pd.DataFrame],
    *,
    baseline_variant: str = "5/20/60",
) -> pd.DataFrame:
    """Compare state/rank stability across precomputed horizon histories."""

    if baseline_variant not in histories:
        raise ValueError(f"missing baseline variant: {baseline_variant}")
    baseline = histories[baseline_variant]
    _require_history_columns(baseline)
    summary: list[dict[str, Any]] = []
    for variant, history in histories.items():
        _require_history_columns(history)
        comparison = baseline[
            ["snapshot_date", "group_id", "leadership_state", "leadership_rank"]
        ].merge(
            history[
                ["snapshot_date", "group_id", "leadership_state", "leadership_rank"]
            ],
            on=["snapshot_date", "group_id"],
            how="inner",
            suffixes=("_baseline", "_variant"),
        )
        comparable_states = int(len(comparison))
        state_agreement = (
            float(
                (
                    comparison["leadership_state_baseline"]
                    == comparison["leadership_state_variant"]
                ).mean()
            )
            if comparable_states
            else None
        )
        confirmed = comparison[
            (comparison["leadership_state_baseline"] != "UNCONFIRMED")
            & (comparison["leadership_state_variant"] != "UNCONFIRMED")
        ]
        confirmed_agreement = (
            float(
                (
                    confirmed["leadership_state_baseline"]
                    == confirmed["leadership_state_variant"]
                ).mean()
            )
            if not confirmed.empty
            else None
        )
        rank_correlations: list[float] = []
        for _, date_rows in comparison.groupby("snapshot_date"):
            ranked = date_rows.dropna(
                subset=["leadership_rank_baseline", "leadership_rank_variant"]
            )
            if (
                len(ranked) >= 2
                and ranked["leadership_rank_baseline"].nunique() >= 2
                and ranked["leadership_rank_variant"].nunique() >= 2
            ):
                # Spearman is Pearson correlation over ordinal ranks. Compute
                # it directly so the offline harness does not require scipy.
                baseline_ranks = ranked["leadership_rank_baseline"].rank(
                    method="average"
                )
                variant_ranks = ranked["leadership_rank_variant"].rank(
                    method="average"
                )
                correlation = baseline_ranks.corr(variant_ranks)
                if correlation is not None and np.isfinite(correlation):
                    rank_correlations.append(float(correlation))
        turnover = analyze_dimension_turnover(
            history,
            state_col="leadership_state",
            state_order=LEADERSHIP_STATE_ORDER,
            dimension="leadership",
        )
        coverage = (
            float((history["leadership_state"] != "UNCONFIRMED").mean())
            if not history.empty
            else None
        )
        summary.append(
            {
                "variant": variant,
                "short_horizon": _variant_lookup(variant).short,
                "primary_horizon": _variant_lookup(variant).primary,
                "long_horizon": _variant_lookup(variant).long,
                "observations": int(len(history)),
                "comparable_state_observations": comparable_states,
                "state_agreement": _round_optional(state_agreement),
                "confirmed_state_agreement": _round_optional(confirmed_agreement),
                "mean_rank_correlation": _round_optional(
                    float(np.mean(rank_correlations)) if rank_correlations else None
                ),
                "rank_correlation_dates": len(rank_correlations),
                "transition_rate": _round_optional(
                    (turnover.change_pct / 100.0)
                    if turnover.change_pct is not None
                    else None
                ),
                "median_state_duration": turnover.median_state_duration,
                "mean_state_duration": turnover.mean_state_duration,
                "coverage": _round_optional(coverage),
                "flags": ";".join(turnover.flags),
            }
        )
    return pd.DataFrame(summary)


def build_group_size_sensitivity(
    *,
    group_sizes: Sequence[int] = GROUP_SIZES,
    thresholds_pp: Sequence[float] = (5.0, 10.0, 15.0, 20.0),
    minimum_constituents: int = 2,
    constituent_fraction: float = 0.10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare raw percentage-point and count-confirmed diffusion rules."""

    scenarios: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for group_size in group_sizes:
        if group_size < 1:
            raise ValueError("group sizes must be positive")
        previous_count = group_size // 2
        previous_breadth = previous_count / group_size * 100.0
        required_count = constituent_floor(
            group_size,
            fraction=constituent_fraction,
            minimum=minimum_constituents,
        )
        for threshold in thresholds_pp:
            if threshold <= 0:
                raise ValueError("thresholds_pp must be positive")
            threshold_rows: list[dict[str, Any]] = []
            for current_count in range(group_size + 1):
                current_breadth = current_count / group_size * 100.0
                delta_count = current_count - previous_count
                delta_pp = current_breadth - previous_breadth
                baseline = classify_diffusion(
                    breadth_delta_pp=delta_pp,
                    broadening_threshold_pp=float(threshold),
                    narrowing_threshold_pp=-float(threshold),
                ).value
                candidate_v2 = classify_diffusion_v2(
                    breadth_current=current_breadth,
                    breadth_previous=previous_breadth,
                    group_size=group_size,
                    broadening_threshold_pp=float(threshold),
                    narrowing_threshold_pp=-float(threshold),
                    fraction=constituent_fraction,
                    minimum_constituents=minimum_constituents,
                )
                candidate = _conservative_diffusion_state(candidate_v2)
                row = {
                    "group_size": group_size,
                    "threshold_pp": float(threshold),
                    "previous_participating_count": previous_count,
                    "current_participating_count": current_count,
                    "net_changed_constituents": delta_count,
                    "breadth_previous": round(previous_breadth, 6),
                    "breadth_current": round(current_breadth, 6),
                    "breadth_delta_pp": round(delta_pp, 6),
                    "minimum_changed_constituents": required_count,
                    "baseline_state": baseline,
                    "candidate_detail_state": candidate_v2.value,
                    "candidate_state": candidate,
                    "agree": baseline == candidate,
                }
                scenarios.append(row)
                threshold_rows.append(row)
            broadening_firm = [
                row["net_changed_constituents"]
                for row in threshold_rows
                if row["candidate_state"] == "BROADENING"
            ]
            narrowing_firm = [
                abs(row["net_changed_constituents"])
                for row in threshold_rows
                if row["candidate_state"] == "NARROWING"
            ]
            summary.append(
                {
                    "group_size": group_size,
                    "threshold_pp": float(threshold),
                    "one_constituent_step_pp": round(100.0 / group_size, 6),
                    "minimum_changed_constituents": required_count,
                    "candidate_broadening_min_changes": (
                        min(broadening_firm) if broadening_firm else None
                    ),
                    "candidate_narrowing_min_changes": (
                        min(narrowing_firm) if narrowing_firm else None
                    ),
                    "classification_agreement": round(
                        sum(row["agree"] for row in threshold_rows)
                        / len(threshold_rows),
                        6,
                    ),
                    "fragile_scenario_count": sum(
                        "FRAGILE" in row["candidate_detail_state"]
                        for row in threshold_rows
                    ),
                }
            )
    return pd.DataFrame(scenarios), pd.DataFrame(summary)


def recommend_minimum_group_size(
    *,
    maximum_one_constituent_step_pp: float = 25.0,
    minimum_changed_constituents: int = 2,
) -> tuple[int, str]:
    """Return a transparent synthetic candidate, not a live IDX estimate."""

    if maximum_one_constituent_step_pp <= 0:
        raise ValueError("maximum_one_constituent_step_pp must be positive")
    candidate = max(
        math.ceil(100.0 / maximum_one_constituent_step_pp),
        minimum_changed_constituents + 1,
    )
    basis = (
        "Synthetic rule: keep a single constituent at or below "
        f"{maximum_one_constituent_step_pp:g} percentage points and require at "
        f"least {minimum_changed_constituents} changed constituents for a firm "
        "diffusion state. This is an offline minimum, not live IDX validation."
    )
    return candidate, basis


def build_methodology_sensitivity_report(
    histories: dict[str, pd.DataFrame],
    *,
    baseline_variant: str = "5/20/60",
) -> tuple[MethodologySensitivityReport, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    horizon_summary = evaluate_horizon_sensitivity(
        histories, baseline_variant=baseline_variant
    )
    group_scenarios, group_summary = build_group_size_sensitivity()
    recommendation, basis = recommend_minimum_group_size()
    report = MethodologySensitivityReport(
        baseline_variant=baseline_variant,
        horizon_summary=horizon_summary.to_dict("records"),
        group_size_summary=group_summary.to_dict("records"),
        recommended_minimum_group_size=recommendation,
        recommendation_basis=basis,
        limitations=[
            "Prototype/fixture history is short and is not live Sectors validation.",
            "Agreement, churn, duration, coverage, and rank stability are diagnostic; no variant is selected using forward returns.",
            "Synthetic group-size results isolate mechanical denominator behavior and do not estimate live IDX liquidity or taxonomy quality.",
        ],
    )
    return report, horizon_summary, group_summary, group_scenarios


def write_methodology_sensitivity_outputs(
    report: MethodologySensitivityReport,
    *,
    histories: dict[str, pd.DataFrame],
    horizon_summary: pd.DataFrame,
    group_size_summary: pd.DataFrame,
    group_size_scenarios: pd.DataFrame,
    output_dir: Path | str,
    prefix: str = "methodology_sensitivity",
) -> dict[str, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": destination / f"{prefix}.json",
        "markdown": destination / f"{prefix}.md",
        "horizon_summary_csv": destination / f"{prefix}_horizons.csv",
        "horizon_observations_csv": destination / f"{prefix}_horizon_observations.csv",
        "group_size_summary_csv": destination / f"{prefix}_group_sizes.csv",
        "group_size_scenarios_csv": destination
        / f"{prefix}_group_size_scenarios.csv",
    }
    paths["json"].write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    paths["markdown"].write_text(report.to_markdown(), encoding="utf-8")
    horizon_summary.to_csv(paths["horizon_summary_csv"], index=False)
    observations = pd.concat(
        [history.assign(variant=variant) for variant, history in histories.items()],
        ignore_index=True,
    )
    observations.to_csv(paths["horizon_observations_csv"], index=False)
    group_size_summary.to_csv(paths["group_size_summary_csv"], index=False)
    group_size_scenarios.to_csv(paths["group_size_scenarios_csv"], index=False)
    return paths


def _conservative_diffusion_state(state: DiffusionStateV2) -> str:
    if state == DiffusionStateV2.BROADENING_FIRM:
        return "BROADENING"
    if state == DiffusionStateV2.NARROWING_FIRM:
        return "NARROWING"
    if state == DiffusionStateV2.UNCONFIRMED:
        return "UNCONFIRMED"
    return "STABLE"


def _variant_lookup(label: str) -> HorizonVariant:
    try:
        return next(variant for variant in HORIZON_VARIANTS if variant.label == label)
    except StopIteration as exc:
        raise ValueError(f"unknown constrained horizon variant: {label}") from exc


def _mean_or_none(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return float(numeric.dropna().mean()) if numeric.notna().any() else None


def _require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} missing required columns: {', '.join(sorted(missing))}")


def _require_history_columns(history: pd.DataFrame) -> None:
    _require_columns(
        history,
        {"snapshot_date", "group_id", "leadership_state", "leadership_rank"},
        "horizon history",
    )


def _round_optional(value: float | None) -> float | None:
    return round(float(value), 6) if value is not None and np.isfinite(value) else None


def _fmt_pct(value: object, *, ratio: bool) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    number = float(value) * (100.0 if ratio else 1.0)
    return f"{number:.2f}%"


def _fmt_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"
