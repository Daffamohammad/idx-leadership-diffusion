"""Dataclasses for taxonomies and their memberships."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Mapping


class TaxonomyKind(str, Enum):
    SECTOR = "SECTOR"
    KONGLO = "KONGLO"
    THEMES = "THEMES"


class MembershipType(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    EXCLUDED = "EXCLUDED"


class TaxonomySourceKind(str, Enum):
    PROTOTYPE_CONFIG = "PROTOTYPE_CONFIG"
    ANALYST_DEFINED = "ANALYST_DEFINED"
    PRIMARY_INDEX = "PRIMARY_INDEX"
    THIRD_PARTY = "THIRD_PARTY"


@dataclass(frozen=True)
class TaxonomyMembership:
    """A single ticker→group membership in a taxonomy."""

    ticker: str
    taxonomy_group_id: str
    taxonomy_group_name: str
    membership_type: MembershipType = MembershipType.PRIMARY
    confidence: float = 1.0
    source: str = ""
    source_as_of: date | None = None
    relationship: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "taxonomy_group_id": self.taxonomy_group_id,
            "taxonomy_group_name": self.taxonomy_group_name,
            "membership_type": self.membership_type.value,
            "confidence": round(float(self.confidence), 4),
            "source": self.source,
            "source_as_of": self.source_as_of.isoformat() if self.source_as_of else None,
            **({"relationship": self.relationship} if self.relationship else {}),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TaxonomyMembership":
        membership_type = MembershipType(
            str(payload.get("membership_type", "PRIMARY")).upper()
        )
        confidence_raw = payload.get("confidence", 1.0)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 1.0
        source_as_of_raw = payload.get("source_as_of")
        source_as_of: date | None = None
        if source_as_of_raw:
            try:
                source_as_of = date.fromisoformat(str(source_as_of_raw))
            except ValueError:
                source_as_of = None
        return cls(
            ticker=str(payload.get("ticker", "")).strip().upper(),
            taxonomy_group_id=str(payload.get("taxonomy_group_id", "")).strip(),
            taxonomy_group_name=str(payload.get("taxonomy_group_name", "")).strip(),
            membership_type=membership_type,
            confidence=confidence,
            source=str(payload.get("source", "") or ""),
            source_as_of=source_as_of,
            relationship=str(payload["relationship"]) if payload.get("relationship") else None,
        )


@dataclass(frozen=True)
class Taxonomy:
    """A versioned taxonomy definition."""

    taxonomy_id: str
    taxonomy_name: str
    taxonomy_version: str
    taxonomy_kind: TaxonomyKind
    source_kind: TaxonomySourceKind
    source_as_of: date | None
    membership_policy: str
    provider_mode: str
    memberships: tuple[TaxonomyMembership, ...] = field(default_factory=tuple)

    def groups(self) -> list[str]:
        seen: list[str] = []
        for m in self.memberships:
            if m.membership_type == MembershipType.EXCLUDED:
                continue
            if m.taxonomy_group_id and m.taxonomy_group_id not in seen:
                seen.append(m.taxonomy_group_id)
        return seen

    def members_of(self, taxonomy_group_id: str) -> list[TaxonomyMembership]:
        return [
            m
            for m in self.memberships
            if m.membership_type != MembershipType.EXCLUDED
            and m.taxonomy_group_id == taxonomy_group_id
        ]

    def primary_tickers(self) -> list[str]:
        seen: list[str] = []
        for m in self.memberships:
            if m.membership_type == MembershipType.PRIMARY and m.ticker not in seen:
                seen.append(m.ticker)
        return seen

    def to_dict(self) -> dict[str, Any]:
        return {
            "taxonomy_id": self.taxonomy_id,
            "taxonomy_name": self.taxonomy_name,
            "taxonomy_version": self.taxonomy_version,
            "taxonomy_kind": self.taxonomy_kind.value,
            "source_kind": self.source_kind.value,
            "source_as_of": self.source_as_of.isoformat() if self.source_as_of else None,
            "membership_policy": self.membership_policy,
            "provider_mode": self.provider_mode,
            "coverage": self._coverage_payload(),
            "memberships": [m.to_dict() for m in self.memberships],
        }

    def _coverage_payload(self) -> dict[str, Any]:
        included = [
            m for m in self.memberships if m.membership_type != MembershipType.EXCLUDED
        ]
        unique_tickers = {m.ticker for m in included}
        unique_groups = {m.taxonomy_group_id for m in included}
        return {
            "ticker_count": len(unique_tickers),
            "group_count": len(unique_groups),
            "membership_count": len(self.memberships),
            "excluded_count": sum(
                1 for m in self.memberships if m.membership_type == MembershipType.EXCLUDED
            ),
            "prototype": self.source_kind != TaxonomySourceKind.PRIMARY_INDEX,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Taxonomy":
        source_as_of_raw = payload.get("source_as_of")
        source_as_of: date | None = None
        if source_as_of_raw:
            try:
                source_as_of = date.fromisoformat(str(source_as_of_raw))
            except ValueError:
                source_as_of = None
        memberships = tuple(
            TaxonomyMembership.from_dict(m)
            for m in payload.get("memberships", [])
            if isinstance(m, Mapping)
        )
        return cls(
            taxonomy_id=str(payload.get("taxonomy_id", "")).strip(),
            taxonomy_name=str(payload.get("taxonomy_name", "")).strip(),
            taxonomy_version=str(payload.get("taxonomy_version", "prototype-v1")).strip()
            or "prototype-v1",
            taxonomy_kind=TaxonomyKind(str(payload.get("taxonomy_kind", "SECTOR")).upper()),
            source_kind=TaxonomySourceKind(
                str(payload.get("source_kind", "PROTOTYPE_CONFIG")).upper()
            ),
            source_as_of=source_as_of,
            membership_policy=str(payload.get("membership_policy", "PRIMARY_ONLY") or "PRIMARY_ONLY"),
            provider_mode=str(payload.get("provider_mode", "PUBLIC_PROTOTYPE") or "PUBLIC_PROTOTYPE"),
            memberships=memberships,
        )