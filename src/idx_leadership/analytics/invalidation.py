"""Screen invalidation (D023).

A **screen-state invalidation** is a deterministic statement of the
conditions under which the current leadership state would be
considered *weakened* on the next observation.

This is NOT investment-thesis invalidation. The user reads it as:
"what would make us reconsider this group on the next refresh?"

Output: list of :class:`InvalidationCondition` objects ready to attach
to a :class:`GroupEvidence.invalidation` list.  The contract is frozen
at v1; new conditions require a version bump.
"""
from __future__ import annotations

from typing import Iterable

from ..models import GroupSnapshot, InvalidationCondition


def build_invalidation_conditions(snap: GroupSnapshot) -> list[InvalidationCondition]:
    """Generate the invalidation conditions for one group."""
    out: list[InvalidationCondition] = []

    # 20D excess return sign
    if snap.group_excess_return is not None:
        if snap.group_excess_return > 0:
            out.append(InvalidationCondition(
                metric="weaken_if_20d_excess_turns_negative",
                condition="20D excess return turns negative",
                threshold="excess_20d < 0",
                rationale=(
                    "State may weaken if 20D excess return turns negative on the next refresh."
                ),
            ))
        else:
            out.append(InvalidationCondition(
                metric="strengthen_if_20d_excess_turns_positive",
                condition="20D excess return turns positive",
                threshold="excess_20d > 0",
                rationale=(
                    "State may strengthen if 20D excess return turns positive on the next refresh."
                ),
            ))

    # Breadth floor
    if snap.breadth_outperforming is not None:
        out.append(InvalidationCondition(
            metric="weaken_if_breadth_below_threshold",
            condition="breadth falls below the configured threshold",
            threshold=f"breadth_outperforming < 30% (current {snap.breadth_outperforming:.1f}%)",
            rationale="State may weaken if breadth falls below the configured threshold.",
        ))

    # Diffusion shift
    diffusion_state = snap.diffusion_state_v2 or snap.diffusion_state
    out.append(InvalidationCondition(
        metric="weaken_if_diffusion_shifts",
        condition="diffusion shifts to NARROWING or UNCONFIRMED",
        threshold=f"diffusion != {diffusion_state.value}",
        rationale="State may weaken if diffusion shifts away from its current classification.",
    ))

    # Persistence check
    out.append(InvalidationCondition(
        metric="weaken_if_persistence_broken",
        condition="the consecutive-observation persistence chain is broken",
        threshold="persistence resets to 1",
        rationale="State may weaken if the persistence chain resets to 1 on the next refresh.",
    ))

    return out
