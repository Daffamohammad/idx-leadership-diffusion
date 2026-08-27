"""Observation-count persistence for leadership and diffusion states.

Persistence is deliberately a count, not a weighted score. Counts include the
current observation: a newly observed state has persistence ``1``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from ..models import DiffusionState, GroupSnapshot


@dataclass
class PersistenceMetrics:
    leadership_persistence_snapshots: int = 1
    leadership_persistence_first_seen: Optional[date] = None
    diffusion_persistence_snapshots: int = 1
    diffusion_persistence_first_seen: Optional[date] = None
    broadening_persistence_snapshots: int = 0
    narrowing_persistence_snapshots: int = 0


def compute_persistence(
    group_id: str,
    current: GroupSnapshot,
    history: Iterable[GroupSnapshot],
) -> PersistenceMetrics:
    """Count consecutive observations in the current state.

    History may contain other groups, duplicate dates, or future observations;
    those rows are ignored. This keeps the helper safe for whole-panel history
    inputs and preserves the no-look-ahead boundary at ``current.snapshot_date``.
    """

    if current.group_id != group_id:
        raise ValueError(
            f"current snapshot group_id={current.group_id!r} does not match {group_id!r}"
        )

    prior_by_date: dict[date, GroupSnapshot] = {}
    for previous in history:
        if previous.group_id != group_id:
            continue
        if previous.snapshot_date >= current.snapshot_date:
            continue
        prior_by_date[previous.snapshot_date] = previous
    prior = [prior_by_date[key] for key in sorted(prior_by_date)]

    leadership_count, leadership_first_seen = _state_run(
        current_state=_state_value(current.leadership_state),
        current_date=current.snapshot_date,
        history_states=[
            (snapshot.snapshot_date, _state_value(snapshot.leadership_state))
            for snapshot in prior
        ],
    )
    current_diffusion = _diffusion_family(current)
    diffusion_count, diffusion_first_seen = _state_run(
        current_state=current_diffusion,
        current_date=current.snapshot_date,
        history_states=[
            (snapshot.snapshot_date, _diffusion_family(snapshot))
            for snapshot in prior
        ],
    )

    broadening_count = diffusion_count if current_diffusion == "BROADENING" else 0
    narrowing_count = diffusion_count if current_diffusion == "NARROWING" else 0
    return PersistenceMetrics(
        leadership_persistence_snapshots=leadership_count,
        leadership_persistence_first_seen=leadership_first_seen,
        diffusion_persistence_snapshots=diffusion_count,
        diffusion_persistence_first_seen=diffusion_first_seen,
        broadening_persistence_snapshots=broadening_count,
        narrowing_persistence_snapshots=narrowing_count,
    )


def _state_run(
    *,
    current_state: str,
    current_date: date,
    history_states: list[tuple[date, str]],
) -> tuple[int, date]:
    count = 1
    first_seen = current_date
    for snapshot_date, state in reversed(history_states):
        if state != current_state:
            break
        count += 1
        first_seen = snapshot_date
    return count, first_seen


def _state_value(state: object) -> str:
    value = getattr(state, "value", state)
    return str(value)


def _diffusion_family(snapshot: GroupSnapshot) -> str:
    state = snapshot.diffusion_state_v2 or snapshot.diffusion_state
    value = _state_value(state)
    if value.startswith("BROADENING"):
        return DiffusionState.BROADENING.value
    if value.startswith("NARROWING"):
        return DiffusionState.NARROWING.value
    if value == DiffusionState.STABLE.value:
        return value
    return DiffusionState.UNCONFIRMED.value
