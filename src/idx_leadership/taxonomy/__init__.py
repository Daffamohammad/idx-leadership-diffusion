"""Taxonomy backend — reusable across sector, Konglo, and Themes views.

Provides:

* :class:`Taxonomy` and :class:`TaxonomyMembership` dataclasses (models).
* :class:`TaxonomyRegistry` — versioned registration, validation, and lookup.
* :func:`aggregate_taxonomy` — equal-weight group returns, IHSG-relative
  20D/60D performance, current breadth, leadership, diffusion, and
  map coordinates.

All outputs are deterministic and source-back-traceable. No numeric value is
estimated from qualitative sources.
"""

from .models import (
    MembershipType,
    Taxonomy,
    TaxonomyKind,
    TaxonomyMembership,
    TaxonomySourceKind,
)
from .registry import TaxonomyRegistry, load_registry_from_yaml
from .aggregation import (
    TaxonomyAggregate,
    aggregate_taxonomy,
    build_taxonomy_payload,
)

__all__ = [
    "MembershipType",
    "Taxonomy",
    "TaxonomyAggregate",
    "TaxonomyKind",
    "TaxonomyMembership",
    "TaxonomyRegistry",
    "TaxonomySourceKind",
    "aggregate_taxonomy",
    "build_taxonomy_payload",
    "load_registry_from_yaml",
]