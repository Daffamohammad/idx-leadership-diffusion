"""Group aggregation module.

Combines per-security features, breadth, and concentration into a
GroupSnapshot. Ranking is performed here as the last step.
"""
from .groups import (
    build_group_snapshots,
    rank_groups,
    aggregate_history,
)

__all__ = [
    "build_group_snapshots",
    "rank_groups",
    "aggregate_history",
]
