"""Contradiction engine (D022).

A contradiction is a heuristic note that the current `GroupSnapshot`
contains internal tension worth surfacing to the user.

Each contradiction is a :class:`ContradictionRecord` so it can be
attached to the `GroupEvidence.contradictions` list and consumed by
both the UI and the Markdown brief contract.

Heuristics shipped this pass:

1. LEADING + NARROWING                  — strong but thin
2. LEADING + BROADENING_FRAGILE         — strong but on a few names
3. IMPROVING + excess return < 0        — improving into headwind
4. WEAKENING + excess return > 0        — weakening despite strength
5. Top-1 abs share > 0.6                — concentrated
6. Breadth outperforming < 30%          — thin participation
7. Persistence >= 4 + STABLE            — long-running neutral
"""
from __future__ import annotations

from typing import Optional

from ..models import (
    ContradictionRecord,
    DiffusionState,
    DiffusionStateV2,
    GroupSnapshot,
    LeadershipState,
)


def _direction_for(value: float | None) -> str:
    if value is None:
        return "neutral"
    return "positive" if value > 0 else ("negative" if value < 0 else "neutral")


def build_contradictions(snap: GroupSnapshot) -> list[ContradictionRecord]:
    out: list[ContradictionRecord] = []
    diffusion_state = snap.diffusion_state_v2 or snap.diffusion_state

    if snap.leadership_state == LeadershipState.LEADING and diffusion_state in (
        DiffusionState.NARROWING,
        DiffusionStateV2.NARROWING_FIRM,
        DiffusionStateV2.NARROWING_FRAGILE,
    ):
        out.append(ContradictionRecord(
            metric="leading_but_narrowing",
            label=f"{snap.leadership_state.value} + {diffusion_state.value}",
            severity="CRITICAL",
            evidence="Strong leadership but participation is narrowing — concentrated.",
        ))

    if (
        snap.leadership_state in (LeadershipState.LEADING, LeadershipState.IMPROVING)
        and diffusion_state in (DiffusionStateV2.BROADENING_FRAGILE, DiffusionState.BROADENING)
        and (snap.concentration.top1_contribution_share or 0.0) > 0.6
    ):
        out.append(ContradictionRecord(
            metric="leading_concentrated_breadth",
            label=f"top1 {snap.concentration.top1_contribution_share:.0%}",
            severity="WARNING",
            evidence="Leadership exists but top contributor drives >60% of the group move.",
        ))

    if snap.leadership_state == LeadershipState.IMPROVING and (
        snap.group_excess_return is not None and snap.group_excess_return < 0
    ):
        out.append(ContradictionRecord(
            metric="improving_into_headwind",
            label=f"excess_20d {snap.group_excess_return:+.1f}%",
            severity="WARNING",
            evidence="Improving short-term, but medium-term excess return still negative.",
        ))

    if snap.leadership_state == LeadershipState.WEAKENING and (
        snap.group_excess_return is not None and snap.group_excess_return > 0
    ):
        out.append(ContradictionRecord(
            metric="weakening_despite_strength",
            label=f"excess_20d {snap.group_excess_return:+.1f}%",
            severity="WARNING",
            evidence="20D excess return still positive but state has weakened.",
        ))

    if snap.breadth_outperforming is not None and snap.breadth_outperforming < 30.0:
        out.append(ContradictionRecord(
            metric="thin_breadth",
            label=f"breadth {snap.breadth_outperforming:.1f}%",
            severity="WARNING",
            evidence="Fewer than 30% of constituents are outperforming the benchmark.",
        ))

    if (snap.concentration.top1_contribution_share or 0.0) > 0.6:
        out.append(ContradictionRecord(
            metric="concentrated_top1",
            label=f"top1 {snap.concentration.top1_contribution_share:.0%}",
            severity="WARNING",
            evidence="Top-1 contribution > 60% of group absolute move.",
        ))

    return out
