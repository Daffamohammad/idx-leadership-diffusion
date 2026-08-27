"""Signal engines: diffusion, leadership, transitions, change digest."""
from .diffusion import classify_diffusion
from .diffusion_v2 import (
    DiffusionStateV2,
    classify_diffusion_v2,
    constituent_floor,
    to_v1_state,
)
from .leadership import classify_leadership
from .transitions import (
    build_transition_events,
    compute_transition,
    transition_label,
)
from .change_digest import build_change_digest

__all__ = [
    "classify_diffusion",
    "classify_diffusion_v2",
    "DiffusionStateV2",
    "constituent_floor",
    "to_v1_state",
    "classify_leadership",
    "compute_transition",
    "build_transition_events",
    "transition_label",
    "build_change_digest",
]
