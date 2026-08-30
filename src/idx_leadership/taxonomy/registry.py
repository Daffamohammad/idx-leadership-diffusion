"""Registry for taxonomies (sector, Konglo, themes).

A registry holds versioned :class:`Taxonomy` definitions keyed by
``taxonomy_id`` and indexed by ``taxonomy_kind``. The registry is
immutable per construction; loading a YAML file returns a new registry.

Public methods:

* :meth:`TaxonomyRegistry.get`
* :meth:`TaxonomyRegistry.by_kind`
* :meth:`TaxonomyRegistry.ticker_groups`
* :meth:`TaxonomyRegistry.latest_of_kind`

Validation:

* Membership ``taxonomy_group_id`` must match a registered group or be
  declared in the YAML itself.
* ``membership_type = EXCLUDED`` always wins — the ticker is removed from
  any aggregation.
* A ticker may appear in multiple groups of the same taxonomy; the
  ``membership_policy`` (``PRIMARY_ONLY`` or ``MULTI``) controls how
  duplicate primary memberships are reported.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from .models import MembershipType, Taxonomy, TaxonomyKind, TaxonomyMembership


class TaxonomyRegistry:
    """Versioned taxonomy registry.

    Holds multiple taxonomies (e.g. sector + Konglo + themes). Lookup is
    O(1) by ``taxonomy_id`` and O(N) by kind.
    """

    def __init__(self, taxonomies: Iterable[Taxonomy]):
        self._taxonomies: dict[str, Taxonomy] = {}
        for taxonomy in taxonomies:
            if not taxonomy.taxonomy_id:
                raise ValueError("Taxonomy must declare a non-empty taxonomy_id")
            if taxonomy.taxonomy_id in self._taxonomies:
                raise ValueError(
                    f"Duplicate taxonomy_id detected: {taxonomy.taxonomy_id!r}"
                )
            self._taxonomies[taxonomy.taxonomy_id] = taxonomy

    @property
    def taxonomies(self) -> tuple[Taxonomy, ...]:
        return tuple(self._taxonomies.values())

    def get(self, taxonomy_id: str) -> Taxonomy | None:
        return self._taxonomies.get(taxonomy_id)

    def by_kind(self, kind: TaxonomyKind) -> list[Taxonomy]:
        return [t for t in self._taxonomies.values() if t.taxonomy_kind == kind]

    def latest_of_kind(self, kind: TaxonomyKind) -> Taxonomy | None:
        candidates = self.by_kind(kind)
        if not candidates:
            return None
        candidates.sort(key=lambda t: t.taxonomy_version, reverse=True)
        return candidates[0]

    def ticker_groups(self, taxonomy_id: str) -> dict[str, list[str]]:
        taxonomy = self.get(taxonomy_id)
        if taxonomy is None:
            return {}
        out: dict[str, list[str]] = defaultdict(list)
        for m in taxonomy.memberships:
            if m.membership_type == MembershipType.EXCLUDED:
                continue
            out[m.ticker].append(m.taxonomy_group_id)
        return dict(out)

    def validate(self) -> list[str]:
        """Return a list of validation warnings (empty when clean)."""
        warnings: list[str] = []
        for taxonomy in self._taxonomies.values():
            seen: set[tuple[str, str]] = set()
            for m in taxonomy.memberships:
                key = (m.ticker, m.taxonomy_group_id)
                if key in seen:
                    warnings.append(
                        f"{taxonomy.taxonomy_id}: duplicate membership for {m.ticker} in {m.taxonomy_group_id}"
                    )
                seen.add(key)
                if not m.taxonomy_group_id:
                    warnings.append(
                        f"{taxonomy.taxonomy_id}: membership for {m.ticker} missing taxonomy_group_id"
                    )
                if not m.ticker.endswith(".JK"):
                    warnings.append(
                        f"{taxonomy.taxonomy_id}: ticker {m.ticker!r} is not IDX-formatted"
                    )
        return warnings


def _coerce_membership(payload: Mapping[str, object]) -> TaxonomyMembership:
    membership_type_raw = payload.get("membership_type", "PRIMARY")
    try:
        membership_type = MembershipType(str(membership_type_raw).upper())
    except ValueError:
        membership_type = MembershipType.PRIMARY
    confidence_raw = payload.get("confidence", 1.0)
    try:
        confidence = float(confidence_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        confidence = 1.0
    source_as_of = payload.get("source_as_of")
    if hasattr(source_as_of, "isoformat"):
        source_as_of = source_as_of.isoformat()  # type: ignore[attr-defined]
    return TaxonomyMembership.from_dict(
        {
            "ticker": payload.get("ticker"),
            "taxonomy_group_id": payload.get("taxonomy_group_id")
            or payload.get("group_id"),
            "taxonomy_group_name": payload.get("taxonomy_group_name")
            or payload.get("group_name"),
            "membership_type": membership_type.value,
            "confidence": confidence,
            "source": payload.get("source", "") or "",
            "source_as_of": source_as_of,
        }
    )


def load_registry_from_yaml(*paths: Path | str) -> TaxonomyRegistry:
    """Load one or more YAML taxonomy files into a single registry.

    Each YAML document must declare at least one taxonomy. Multiple
    taxonomies can live in a single document using ``taxonomies:`` as a
    list, or the document itself can be a single taxonomy mapping.
    """
    taxonomies: list[Taxonomy] = []
    for raw_path in paths:
        path = Path(raw_path)
        with path.open("r", encoding="utf-8") as handle:
            documents = list(yaml.safe_load_all(handle))
        for document in documents:
            if not document:
                continue
            if isinstance(document, Mapping) and "taxonomies" in document:
                documents.extend(document["taxonomies"])
                continue
            if isinstance(document, Mapping):
                taxonomies.append(_build_taxonomy_from_yaml(document))
    return TaxonomyRegistry(taxonomies)


def _build_taxonomy_from_yaml(document: Mapping[str, object]) -> Taxonomy:
    taxonomy_kind_raw = str(document.get("taxonomy_kind", "SECTOR")).upper()
    try:
        taxonomy_kind = TaxonomyKind(taxonomy_kind_raw)
    except ValueError:
        taxonomy_kind = TaxonomyKind.SECTOR
    memberships_raw = document.get("memberships", []) or []
    memberships: list[TaxonomyMembership] = []
    if isinstance(memberships_raw, list):
        for entry in memberships_raw:
            if not isinstance(entry, Mapping):
                continue
            memberships.append(_coerce_membership(entry))
    return Taxonomy.from_dict(
        {
            "taxonomy_id": document.get("taxonomy_id"),
            "taxonomy_name": document.get("taxonomy_name"),
            "taxonomy_version": document.get("taxonomy_version", "prototype-v1"),
            "taxonomy_kind": taxonomy_kind.value,
            "source_kind": document.get("source_kind", "PROTOTYPE_CONFIG"),
            "source_as_of": document.get("source_as_of"),
            "membership_policy": document.get("membership_policy", "PRIMARY_ONLY"),
            "provider_mode": document.get("provider_mode", "PUBLIC_PROTOTYPE"),
            "memberships": [m.to_dict() for m in memberships],
        }
    )