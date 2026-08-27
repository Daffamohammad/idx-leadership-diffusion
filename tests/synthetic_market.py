"""Deterministic synthetic-market scenarios for methodology regression tests.

The scenarios in this module are not live data and not Sectors API results.
They exist so the leadership, diffusion, concentration, persistence, and
materiality engines can be exercised against well-known boundary inputs
without any provider call.

Each scenario produces a list of :class:`SyntheticGroupObservation` rows
covering several weekly observations. The same scenarios drive the golden
tests in ``tests/test_synthetic_scenarios.py``.

Scenarios
=========

A. Healthy Leadership
    strong excess return; broad participation; low concentration
B. Narrow Leadership
    strong excess return; few leaders; high concentration
C. Early Recovery
    negative medium-term RS; positive short-term RS; breadth improving
D. Deterioration
    positive medium-term RS; negative short-term RS; breadth falling
E. Noisy Micro Group
    3 constituents; one extreme move; one stable
F. Missing Data
    partial coverage; some constituents return ``None``
G. Corporate Action Shock
    single discontinuous price move that resembles extreme leadership
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


@dataclass(frozen=True)
class SyntheticConstituent:
    ticker: str
    return_5d: float | None
    return_20d: float | None
    return_60d: float | None


@dataclass(frozen=True)
class SyntheticGroupObservation:
    """One weekly observation of one group under one scenario."""

    group_id: str
    scenario: str
    snapshot_date: str
    constituents: tuple[SyntheticConstituent, ...]
    benchmark_return_5d: float = 0.0
    benchmark_return_20d: float = 0.0
    benchmark_return_60d: float = 0.0
    # Optional per-observation extras used by scenario G.
    corporate_action_window: bool = False

    def excess(self, horizon: str) -> tuple[float | None, ...]:
        benchmark = {
            "5d": self.benchmark_return_5d,
            "20d": self.benchmark_return_20d,
            "60d": self.benchmark_return_60d,
        }[horizon]
        returns = {
            "5d": [c.return_5d for c in self.constituents],
            "20d": [c.return_20d for c in self.constituents],
            "60d": [c.return_60d for c in self.constituents],
        }[horizon]
        return tuple(
            None if r is None else round(r - benchmark, 4) for r in returns
        )

    def eligible_excess(self, horizon: str) -> list[float]:
        return [value for value in self.excess(horizon) if value is not None]


def _const(
    ticker: str,
    return_5d: float,
    return_20d: float,
    return_60d: float,
) -> SyntheticConstituent:
    return SyntheticConstituent(
        ticker=ticker,
        return_5d=return_5d,
        return_20d=return_20d,
        return_60d=return_60d,
    )


def _healthy_constituents() -> tuple[SyntheticConstituent, ...]:
    # Broadly positive, low dispersion, *accelerating* 5D over 60D so the
    # leadership state is LEADING (acceleration >= 1.0pp).  Returns
    # distributed so a single name is not dominant; absolute concentration
    # top1 should be modest.
    return tuple(
        _const(
            ticker,
            return_5d=4.0 + i * 0.05,
            return_20d=6.0 + i * 0.10,
            return_60d=2.0 + i * 0.05,
        )
        for i, ticker in enumerate(
            ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10")
        )
    )


def _narrow_constituents() -> tuple[SyntheticConstituent, ...]:
    # One dominant name; the rest flat to slightly negative. The headline
    # 20D is strong, the 5D has just turned up vs the 60D so the group is
    # still LEADING, but participation is thin.
    return (
        _const("B1", 12.0, 18.0, 4.0),  # dominant + accelerating
        _const("B2", 0.5, -1.0, -0.5),
        _const("B3", -0.2, 0.5, 0.2),
        _const("B4", 0.1, -0.4, -0.1),
        _const("B5", -0.1, 0.0, 0.0),
        _const("B6", 0.0, 0.3, 0.1),
        _const("B7", 0.0, -0.2, -0.1),
        _const("B8", -0.3, 0.0, 0.0),
    )


def _early_recovery_history() -> list[SyntheticGroupObservation]:
    # Weekly history: medium-term RS is still negative, short-term has
    # just turned positive, breadth expands from 0/6 to 5/6 as the
    # participating names cross back above the benchmark.  The 20D
    # average is still negative, so the leadership state is IMPROVING.
    dates = ("2026-07-10", "2026-07-17", "2026-07-24", "2026-07-31", "2026-08-07", "2026-08-14")
    rows: list[SyntheticGroupObservation] = []
    for index, snapshot_date in enumerate(dates):
        breadth_growth = min(5, index)
        constituents: list[SyntheticConstituent] = []
        for i in range(6):
            if i < breadth_growth:
                # Becoming-participating: short-term strongly positive,
                # 20D crosses zero this week, 60D still negative.
                r5 = 2.0 + index * 0.4
                r20 = -2.0 + index * 0.5
                r60 = -4.0 + index * 0.05
            else:
                # Still-lagging names: mild negative across the board.
                r5 = -0.3
                r20 = -3.0
                r60 = -6.0
            constituents.append(_const(f"C{i+1}", r5, r20, r60))
        rows.append(
            SyntheticGroupObservation(
                group_id="early_recovery",
                scenario="C",
                snapshot_date=snapshot_date,
                constituents=tuple(constituents),
                benchmark_return_5d=0.0,
                benchmark_return_20d=0.0,
                benchmark_return_60d=0.0,
            )
        )
    return rows


def _deterioration_history() -> list[SyntheticGroupObservation]:
    # Positive medium-term RS (the equal-weight 20D excess stays above
    # zero) but the short-horizon has turned negative and breadth has
    # collapsed from 8/8 to 1/8.  The 1pp acceleration threshold is
    # never cleared, so the leadership state is WEAKENING rather than
    # LEADING.
    dates = ("2026-07-10", "2026-07-17", "2026-07-24", "2026-07-31", "2026-08-07", "2026-08-14")
    rows: list[SyntheticGroupObservation] = []
    beat_counts = (8, 7, 6, 4, 2, 1)
    for index, snapshot_date in enumerate(dates):
        constituents: list[SyntheticConstituent] = []
        beat = beat_counts[index]
        for i in range(8):
            if i < beat:
                # Still outperforming at 20D but the 5D has turned
                # negative as the regime rolls over.
                r5 = -1.5 - index * 0.4
                r20 = 8.0 - index * 0.1
                r60 = 9.0 - index * 0.05
            else:
                r5 = -2.0
                r20 = -1.0
                r60 = 0.0
            constituents.append(_const(f"D{i+1}", r5, r20, r60))
        rows.append(
            SyntheticGroupObservation(
                group_id="deterioration",
                scenario="D",
                snapshot_date=snapshot_date,
                constituents=tuple(constituents),
            )
        )
    return rows


def _noisy_micro_history() -> list[SyntheticGroupObservation]:
    return [
        SyntheticGroupObservation(
            group_id="micro",
            scenario="E",
            snapshot_date="2026-08-14",
            constituents=(
                _const("E1", 25.0, 60.0, 30.0),  # one extreme outlier
                _const("E2", 0.5, 1.0, 0.4),
                _const("E3", -0.4, 0.0, 0.1),
            ),
        )
    ]


def _missing_data_observation() -> SyntheticGroupObservation:
    return SyntheticGroupObservation(
        group_id="partial",
        scenario="F",
        snapshot_date="2026-08-14",
        constituents=(
            _const("F1", 2.0, 5.0, 3.0),
            _const("F2", -1.0, -2.0, -0.5),
            _const("F3", None, None, None),  # newly listed
            _const("F4", 1.0, 2.5, 1.0),
            SyntheticConstituent("F5", None, None, None),  # stale
        ),
    )


def _corporate_action_observations() -> list[SyntheticGroupObservation]:
    # Single discontinuous move; resembles a leadership + concentration
    # spike, but the 60D excess has not changed and the corporate-action
    # window flag forces a contradiction.
    return [
        SyntheticGroupObservation(
            group_id="ca_shock",
            scenario="G",
            snapshot_date="2026-08-07",
            constituents=tuple(
                _const(f"G{i+1}", 0.0, 0.0, 0.0) for i in range(6)
            ),
        ),
        SyntheticGroupObservation(
            group_id="ca_shock",
            scenario="G",
            snapshot_date="2026-08-14",
            constituents=tuple(
                _const(f"G{i+1}", 0.0, 0.0, 0.0) for i in range(6)
            ),
            corporate_action_window=True,
        ),
    ]


def healthy_history() -> list[SyntheticGroupObservation]:
    # Three weekly observations.  In the prior week breadth_outperforming
    # is ~50% (5 of 10 names beat the benchmark); in the latest week all
    # 10 names beat the benchmark, so breadth delta is +50pp — well above
    # the ±10pp threshold and the constituent floor.
    def _constituents(beat_count: int) -> tuple[SyntheticConstituent, ...]:
        rows: list[SyntheticConstituent] = []
        for index, ticker in enumerate(
            ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10")
        ):
            if index < beat_count:
                rows.append(
                    _const(
                        ticker,
                        return_5d=4.0 + index * 0.05,
                        return_20d=6.0 + index * 0.10,
                        return_60d=2.0 + index * 0.05,
                    )
                )
            else:
                # Slightly underperform so excess < 0 and outperformance is
                # not counted.
                rows.append(
                    _const(
                        ticker,
                        return_5d=0.0,
                        return_20d=-1.0,
                        return_60d=0.0,
                    )
                )
        return tuple(rows)

    return [
        SyntheticGroupObservation(
            group_id="healthy",
            scenario="A",
            snapshot_date="2026-07-31",
            constituents=_constituents(5),
        ),
        SyntheticGroupObservation(
            group_id="healthy",
            scenario="A",
            snapshot_date="2026-08-07",
            constituents=_constituents(7),
        ),
        SyntheticGroupObservation(
            group_id="healthy",
            scenario="A",
            snapshot_date="2026-08-14",
            constituents=_constituents(10),
        ),
    ]


def narrow_history() -> list[SyntheticGroupObservation]:
    return [
        SyntheticGroupObservation(
            group_id="narrow",
            scenario="B",
            snapshot_date="2026-08-14",
            constituents=_narrow_constituents(),
        )
    ]


def early_recovery_history() -> list[SyntheticGroupObservation]:
    return _early_recovery_history()


def deterioration_history() -> list[SyntheticGroupObservation]:
    return _deterioration_history()


def noisy_micro_history() -> list[SyntheticGroupObservation]:
    return _noisy_micro_history()


def missing_data_observation() -> list[SyntheticGroupObservation]:
    return [_missing_data_observation()]


def corporate_action_history() -> list[SyntheticGroupObservation]:
    return _corporate_action_observations()


def all_scenarios() -> list[SyntheticGroupObservation]:
    return (
        healthy_history()
        + narrow_history()
        + early_recovery_history()
        + deterioration_history()
        + noisy_micro_history()
        + missing_data_observation()
        + corporate_action_history()
    )


@dataclass(frozen=True)
class GoldenLeadership:
    """Expected leadership classification outcome for one observation."""

    state: str  # "LEADING" / "IMPROVING" / "LAGGING" / "WEAKENING" / "UNCONFIRMED"
    note: str = ""


@dataclass(frozen=True)
class GoldenDiffusion:
    """Expected diffusion classification outcome for one observation."""

    state: str  # v2 enum or UNCONFIRMED
    note: str = ""


@dataclass(frozen=True)
class GoldenConcentration:
    """Expected absolute concentration bounds for one observation."""

    top1_lte: float
    hhi_lte: float
    top1_gte: float = 0.0


@dataclass(frozen=True)
class GoldenScenario:
    """Expected analytical outcome for one scenario at one observation."""

    group_id: str
    scenario: str
    snapshot_date: str
    leadership: GoldenLeadership
    diffusion: GoldenDiffusion
    concentration: GoldenConcentration
    contradiction: str | None = None  # an EvidenceRecord.metric or None


# Golden expectations are intentionally coarse (state plus a single
# numeric bound). They are *not* a claim about IDX; they are a regression
# test for the engine's own classifications on deterministic inputs.
GOLDEN = {
    "A": GoldenScenario(
        group_id="healthy",
        scenario="A",
        snapshot_date="2026-08-14",
        leadership=GoldenLeadership("LEADING", "strong + accelerating"),
        diffusion=GoldenDiffusion("BROADENING_FIRM", "+10pp and >=2 names moved"),
        concentration=GoldenConcentration(top1_lte=0.30, hhi_lte=0.20),
    ),
    "B": GoldenScenario(
        group_id="narrow",
        scenario="B",
        snapshot_date="2026-08-14",
        leadership=GoldenLeadership("LEADING", "one name dominates 20D excess"),
        diffusion=GoldenDiffusion("NARROWING_FIRM", "narrowing on absolute loss of breadth"),
        concentration=GoldenConcentration(top1_lte=1.0, hhi_lte=1.0, top1_gte=0.50),
        contradiction="leading_but_narrowing",
    ),
    "C-final": GoldenScenario(
        group_id="early_recovery",
        scenario="C",
        snapshot_date="2026-08-14",
        leadership=GoldenLeadership("IMPROVING", "20D still negative; 5D turning up"),
        diffusion=GoldenDiffusion("BROADENING_FIRM", "breadth moved from 0/6 to 5/6"),
        concentration=GoldenConcentration(top1_lte=0.40, hhi_lte=0.25),
    ),
    "D-final": GoldenScenario(
        group_id="deterioration",
        scenario="D",
        snapshot_date="2026-08-14",
        leadership=GoldenLeadership("WEAKENING", "20D positive but 5D has turned negative"),
        diffusion=GoldenDiffusion("NARROWING_FIRM", "breadth collapses on the latest 5D"),
        concentration=GoldenConcentration(top1_lte=0.30, hhi_lte=0.18),
    ),
    "E": GoldenScenario(
        group_id="micro",
        scenario="E",
        snapshot_date="2026-08-14",
        leadership=GoldenLeadership("LEADING", "20D excess dominated by single name"),
        diffusion=GoldenDiffusion("UNCONFIRMED", "group size < 5 below eligibility floor"),
        concentration=GoldenConcentration(top1_lte=1.0, hhi_lte=1.0, top1_gte=0.80),
        contradiction="leading_but_narrowing",
    ),
    "F": GoldenScenario(
        group_id="partial",
        scenario="F",
        snapshot_date="2026-08-14",
        leadership=GoldenLeadership("LEADING", "3/3 eligible names beat the benchmark"),
        diffusion=GoldenDiffusion("STABLE", "no prior observation; classification neutral"),
        concentration=GoldenConcentration(top1_lte=1.0, hhi_lte=1.0),
    ),
    "G-final": GoldenScenario(
        group_id="ca_shock",
        scenario="G",
        snapshot_date="2026-08-14",
        leadership=GoldenLeadership("UNCONFIRMED", "corporate-action window blocks state classification"),
        diffusion=GoldenDiffusion("UNCONFIRMED", "covered by data gap contract"),
        concentration=GoldenConcentration(top1_lte=1.0, hhi_lte=1.0),
        contradiction="corporate_action_window",
    ),
}


def _avg(values: Iterable[float | None]) -> float:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else 0.0


def obs_5d(cons: Sequence[SyntheticConstituent]) -> list[float | None]:
    return [c.return_5d for c in cons]


def obs_20d(cons: Sequence[SyntheticConstituent]) -> list[float | None]:
    return [c.return_20d for c in cons]


def obs_60d(cons: Sequence[SyntheticConstituent]) -> list[float | None]:
    return [c.return_60d for c in cons]
