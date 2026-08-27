"""Analytics layer: persistence, contradictions, screen invalidation, data gaps."""
from .persistence import PersistenceMetrics, compute_persistence
from .contradictions import build_contradictions
from .invalidation import build_invalidation_conditions
from .data_gaps import build_data_gaps

__all__ = [
    "PersistenceMetrics",
    "compute_persistence",
    "build_contradictions",
    "build_invalidation_conditions",
    "build_data_gaps",
]
