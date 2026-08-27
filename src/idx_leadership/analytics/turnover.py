"""Reusable state-churn diagnostics for historical group snapshots.

The harness treats leadership and diffusion independently and reports explicit
denominators for changes and reversals. It does not use forward returns or
modify classification rules.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Sequence

import pandas as pd

from ..models import DiffusionState, LeadershipState


LEADERSHIP_STATE_ORDER = tuple(state.value for state in LeadershipState)
DIFFUSION_STATE_ORDER = tuple(state.value for state in DiffusionState)


@dataclass
class DimensionTurnover:
    dimension: str
    states: list[str]
    observation_count: int
    group_count: int
    comparable_pairs: int
    change_count: int
    change_pct: float | None
    one_period_reversal_candidates: int
    one_period_reversal_count: int
    one_period_reversal_rate: float | None
    two_period_reversal_candidates: int
    two_period_reversal_count: int
    two_period_reversal_rate: float | None
    state_run_count: int
    median_state_duration: float | None
    mean_state_duration: float | None
    min_state_duration: int | None
    max_state_duration: int | None
    transition_counts: dict[str, dict[str, int]]
    transition_rates: dict[str, dict[str, float]]
    per_group: list[dict[str, Any]] = field(default_factory=list)
    per_period: list[dict[str, Any]] = field(default_factory=list)
    duration_runs: list[dict[str, Any]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TurnoverReport:
    observation_count: int
    group_count: int
    snapshot_count: int
    first_snapshot: str | None
    last_snapshot: str | None
    leadership: DimensionTurnover
    diffusion: DimensionTurnover
    analysis_mode: str = "OFFLINE"
    live_sectors_validated: bool = False
    definitions: dict[str, str] = field(
        default_factory=lambda: {
            "change_pct": "changed adjacent observations / comparable adjacent observations",
            "one_period_reversal": "A-B-A exact reversal after one observation in B",
            "two_period_reversal": "A-B-B-A exact reversal after two observations in B",
            "state_duration": "consecutive observed snapshots in one state",
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            "# State Turnover Audit",
            "",
            f"Snapshots: **{self.snapshot_count}** "
            f"({self.first_snapshot or 'n/a'} to {self.last_snapshot or 'n/a'})  ",
            f"Groups: **{self.group_count}**  ",
            f"Observations: **{self.observation_count}**",
            f"Live Sectors validated: **{'YES' if self.live_sectors_validated else 'NO'}**",
            "",
            "## Definitions",
            "",
        ]
        for key, value in self.definitions.items():
            lines.append(f"- `{key}`: {value}.")
        for result in (self.leadership, self.diffusion):
            lines.extend(_dimension_markdown(result))
        return "\n".join(lines).rstrip() + "\n"


def analyze_state_turnover(
    history: pd.DataFrame | Iterable[dict[str, Any]],
    *,
    date_col: str = "snapshot_date",
    group_col: str = "group_id",
    leadership_col: str = "leadership_state",
    diffusion_col: str = "diffusion_state",
) -> TurnoverReport:
    """Analyze leadership and diffusion churn from a long history panel."""

    frame = _normalize_history(
        history,
        date_col=date_col,
        group_col=group_col,
        state_cols=(leadership_col, diffusion_col),
    )
    leadership = analyze_dimension_turnover(
        frame,
        state_col=leadership_col,
        state_order=LEADERSHIP_STATE_ORDER,
        date_col=date_col,
        group_col=group_col,
        dimension="leadership",
        normalized=True,
    )
    diffusion = analyze_dimension_turnover(
        frame,
        state_col=diffusion_col,
        state_order=DIFFUSION_STATE_ORDER,
        date_col=date_col,
        group_col=group_col,
        dimension="diffusion",
        normalized=True,
    )
    dates = sorted(frame[date_col].dropna().unique())
    return TurnoverReport(
        observation_count=int(len(frame)),
        group_count=int(frame[group_col].nunique()),
        snapshot_count=len(dates),
        first_snapshot=_date_string(dates[0]) if dates else None,
        last_snapshot=_date_string(dates[-1]) if dates else None,
        leadership=leadership,
        diffusion=diffusion,
    )


def analyze_dimension_turnover(
    history: pd.DataFrame | Iterable[dict[str, Any]],
    *,
    state_col: str,
    state_order: Sequence[str],
    date_col: str = "snapshot_date",
    group_col: str = "group_id",
    dimension: str | None = None,
    normalized: bool = False,
) -> DimensionTurnover:
    """Analyze one state dimension; useful for sensitivity harnesses."""

    frame = (
        pd.DataFrame(history).copy()
        if normalized
        else _normalize_history(
            history,
            date_col=date_col,
            group_col=group_col,
            state_cols=(state_col,),
        )
    )
    state_values = [str(value) for value in state_order]
    extras = sorted(set(frame[state_col]).difference(state_values))
    states = state_values + extras
    transition_counts = {
        source: {target: 0 for target in states} for source in states
    }
    comparable_pairs = 0
    change_count = 0
    one_candidates = 0
    one_reversals = 0
    two_candidates = 0
    two_reversals = 0
    duration_runs: list[dict[str, Any]] = []
    per_group: list[dict[str, Any]] = []
    period_counters: dict[str, dict[str, int]] = {}

    for group_id, group_frame in frame.groupby(group_col, sort=True):
        ordered = group_frame.sort_values(date_col).reset_index(drop=True)
        group_states = ordered[state_col].tolist()
        group_dates = ordered[date_col].tolist()
        group_changes = 0
        group_one_candidates = 0
        group_one_reversals = 0
        group_two_candidates = 0
        group_two_reversals = 0

        for index in range(1, len(group_states)):
            source = group_states[index - 1]
            target = group_states[index]
            comparable_pairs += 1
            transition_counts[source][target] += 1
            period_key = _date_string(group_dates[index])
            period = period_counters.setdefault(
                period_key, {"comparable_pairs": 0, "change_count": 0}
            )
            period["comparable_pairs"] += 1
            if source == target:
                continue
            change_count += 1
            group_changes += 1
            period["change_count"] += 1

            if index + 1 < len(group_states):
                one_candidates += 1
                group_one_candidates += 1
                if group_states[index + 1] == source:
                    one_reversals += 1
                    group_one_reversals += 1
            if index + 2 < len(group_states):
                two_candidates += 1
                group_two_candidates += 1
                if (
                    group_states[index + 1] == target
                    and group_states[index + 2] == source
                ):
                    two_reversals += 1
                    group_two_reversals += 1

        runs = _state_runs(
            group_id=str(group_id), states=group_states, dates=group_dates
        )
        duration_runs.extend(runs)
        group_pairs = max(0, len(group_states) - 1)
        per_group.append(
            {
                "group_id": str(group_id),
                "observation_count": len(group_states),
                "comparable_pairs": group_pairs,
                "change_count": group_changes,
                "change_pct": _percentage(group_changes, group_pairs),
                "one_period_reversal_candidates": group_one_candidates,
                "one_period_reversal_count": group_one_reversals,
                "one_period_reversal_rate": _ratio(
                    group_one_reversals, group_one_candidates
                ),
                "two_period_reversal_candidates": group_two_candidates,
                "two_period_reversal_count": group_two_reversals,
                "two_period_reversal_rate": _ratio(
                    group_two_reversals, group_two_candidates
                ),
                "median_state_duration": (
                    float(median(run["duration_observations"] for run in runs))
                    if runs
                    else None
                ),
            }
        )

    transition_rates = {
        source: {
            target: _ratio(count, sum(transition_counts[source].values())) or 0.0
            for target, count in targets.items()
        }
        for source, targets in transition_counts.items()
    }
    per_period = [
        {
            "snapshot_date": snapshot_date,
            **counts,
            "change_pct": _percentage(
                counts["change_count"], counts["comparable_pairs"]
            ),
        }
        for snapshot_date, counts in sorted(period_counters.items())
    ]
    durations = [int(run["duration_observations"]) for run in duration_runs]
    result = DimensionTurnover(
        dimension=dimension or state_col,
        states=states,
        observation_count=int(len(frame)),
        group_count=int(frame[group_col].nunique()),
        comparable_pairs=comparable_pairs,
        change_count=change_count,
        change_pct=_percentage(change_count, comparable_pairs),
        one_period_reversal_candidates=one_candidates,
        one_period_reversal_count=one_reversals,
        one_period_reversal_rate=_ratio(one_reversals, one_candidates),
        two_period_reversal_candidates=two_candidates,
        two_period_reversal_count=two_reversals,
        two_period_reversal_rate=_ratio(two_reversals, two_candidates),
        state_run_count=len(durations),
        median_state_duration=float(median(durations)) if durations else None,
        mean_state_duration=round(float(mean(durations)), 4) if durations else None,
        min_state_duration=min(durations) if durations else None,
        max_state_duration=max(durations) if durations else None,
        transition_counts=transition_counts,
        transition_rates=transition_rates,
        per_group=per_group,
        per_period=per_period,
        duration_runs=duration_runs,
    )
    result.flags = _turnover_flags(result)
    return result


def write_turnover_outputs(
    report: TurnoverReport,
    *,
    output_dir: Path | str,
    prefix: str = "state_turnover",
) -> dict[str, Path]:
    """Write JSON, Markdown, and normalized CSV evidence tables."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": destination / f"{prefix}.json",
        "markdown": destination / f"{prefix}.md",
        "summary_csv": destination / f"{prefix}_summary.csv",
        "transitions_csv": destination / f"{prefix}_transitions.csv",
        "durations_csv": destination / f"{prefix}_durations.csv",
        "per_group_csv": destination / f"{prefix}_per_group.csv",
        "per_period_csv": destination / f"{prefix}_per_period.csv",
    }
    paths["json"].write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    paths["markdown"].write_text(report.to_markdown(), encoding="utf-8")
    pd.DataFrame(
        [_summary_row(report.leadership), _summary_row(report.diffusion)]
    ).to_csv(paths["summary_csv"], index=False)
    pd.DataFrame(
        _transition_rows(report.leadership) + _transition_rows(report.diffusion)
    ).to_csv(paths["transitions_csv"], index=False)
    pd.DataFrame(
        _tag_rows(report.leadership.duration_runs, "leadership")
        + _tag_rows(report.diffusion.duration_runs, "diffusion")
    ).to_csv(paths["durations_csv"], index=False)
    pd.DataFrame(
        _tag_rows(report.leadership.per_group, "leadership")
        + _tag_rows(report.diffusion.per_group, "diffusion")
    ).to_csv(paths["per_group_csv"], index=False)
    pd.DataFrame(
        _tag_rows(report.leadership.per_period, "leadership")
        + _tag_rows(report.diffusion.per_period, "diffusion")
    ).to_csv(paths["per_period_csv"], index=False)
    return paths


def _normalize_history(
    history: pd.DataFrame | Iterable[dict[str, Any]],
    *,
    date_col: str,
    group_col: str,
    state_cols: Sequence[str],
) -> pd.DataFrame:
    frame = pd.DataFrame(history).copy()
    required = {date_col, group_col, *state_cols}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            "history missing required columns: " + ", ".join(sorted(missing))
        )
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame.dropna(subset=[date_col, group_col])
    frame[group_col] = frame[group_col].astype(str)
    for state_col in state_cols:
        frame[state_col] = frame[state_col].map(_state_string)
    frame = (
        frame.sort_values([date_col, group_col], kind="mergesort")
        .drop_duplicates([date_col, group_col], keep="last")
        .reset_index(drop=True)
    )
    return frame


def _state_string(value: object) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return "UNCONFIRMED"
    return str(getattr(value, "value", value))


def _state_runs(
    *, group_id: str, states: list[str], dates: list[pd.Timestamp]
) -> list[dict[str, Any]]:
    if not states:
        return []
    runs: list[dict[str, Any]] = []
    start = 0
    for index in range(1, len(states) + 1):
        if index < len(states) and states[index] == states[start]:
            continue
        runs.append(
            {
                "group_id": group_id,
                "state": states[start],
                "start_snapshot": _date_string(dates[start]),
                "end_snapshot": _date_string(dates[index - 1]),
                "duration_observations": index - start,
                "left_censored": start == 0,
                "right_censored": index == len(states),
            }
        )
        start = index
    return runs


def _turnover_flags(result: DimensionTurnover) -> list[str]:
    flags: list[str] = []
    if result.comparable_pairs >= 10 and (result.change_pct or 0.0) >= 50.0:
        flags.append("HIGH_CHURN_REVIEW")
    if (
        result.one_period_reversal_candidates >= 4
        and (result.one_period_reversal_rate or 0.0) >= 0.25
    ):
        flags.append("EXCESSIVE_ONE_PERIOD_REVERSALS_REVIEW")
    extremes = (
        (("LEADING", "LAGGING"), ("LAGGING", "LEADING"))
        if result.dimension == "leadership"
        else (
            ("BROADENING", "NARROWING"),
            ("NARROWING", "BROADENING"),
        )
    )
    extreme_count = sum(
        result.transition_counts.get(source, {}).get(target, 0)
        for source, target in extremes
    )
    if extreme_count:
        flags.append(f"EXTREME_STATE_JUMPS_REVIEW:{extreme_count}")
    return flags


def _percentage(numerator: int, denominator: int) -> float | None:
    return round((numerator / denominator) * 100.0, 4) if denominator else None


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _date_string(value: object) -> str:
    return pd.Timestamp(value).date().isoformat()


def _summary_row(result: DimensionTurnover) -> dict[str, Any]:
    excluded = {
        "states",
        "transition_counts",
        "transition_rates",
        "per_group",
        "per_period",
        "duration_runs",
    }
    row = {
        key: value
        for key, value in result.to_dict().items()
        if key not in excluded
    }
    row["flags"] = ";".join(result.flags)
    return row


def _transition_rows(result: DimensionTurnover) -> list[dict[str, Any]]:
    return [
        {
            "dimension": result.dimension,
            "from_state": source,
            "to_state": target,
            "count": result.transition_counts[source][target],
            "row_rate": result.transition_rates[source][target],
        }
        for source in result.states
        for target in result.states
    ]


def _tag_rows(rows: list[dict[str, Any]], dimension: str) -> list[dict[str, Any]]:
    return [{"dimension": dimension, **row} for row in rows]


def _dimension_markdown(result: DimensionTurnover) -> list[str]:
    lines = [
        "",
        f"## {result.dimension.title()}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Comparable pairs | {result.comparable_pairs} |",
        f"| State changes | {result.change_count} |",
        f"| Changing state | {_format_pct(result.change_pct)} |",
        f"| 1-period reversals | {result.one_period_reversal_count} / "
        f"{result.one_period_reversal_candidates} "
        f"({_format_ratio(result.one_period_reversal_rate)}) |",
        f"| 2-period reversals | {result.two_period_reversal_count} / "
        f"{result.two_period_reversal_candidates} "
        f"({_format_ratio(result.two_period_reversal_rate)}) |",
        f"| Median state duration | {result.median_state_duration or 'n/a'} observations |",
        f"| Mean state duration | {result.mean_state_duration or 'n/a'} observations |",
        "",
        "### Transition matrix (counts)",
        "",
    ]
    lines.extend(_markdown_matrix(result.states, result.transition_counts))
    if result.flags:
        lines.extend(["", "Flags: " + ", ".join(f"`{flag}`" for flag in result.flags)])
    else:
        lines.extend(["", "Flags: none."])
    return lines


def _markdown_matrix(
    states: list[str], matrix: dict[str, dict[str, int]]
) -> list[str]:
    lines = [
        "| From / To | " + " | ".join(states) + " |",
        "| --- | " + " | ".join("---:" for _ in states) + " |",
    ]
    for source in states:
        lines.append(
            f"| {source} | "
            + " | ".join(str(matrix[source][target]) for target in states)
            + " |"
        )
    return lines


def _format_pct(value: float | None) -> str:
    return f"{value:.2f}%" if value is not None else "n/a"


def _format_ratio(value: float | None) -> str:
    return f"{value * 100:.2f}%" if value is not None else "n/a"
