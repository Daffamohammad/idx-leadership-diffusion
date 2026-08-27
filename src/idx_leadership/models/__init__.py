"""Canonical schemas for the IDX Leadership Diffusion analytical pipeline.

These Pydantic models define the contract between the data layer and the
analytical layer. They are deliberately strict at the boundaries and
permissive in internal computations.
"""
from .enums import (
    LeadershipState,
    DiffusionState,
    DiffusionStateV2,
    MaterialityLabel,
    EligibilityStatus,
    DataQualityStatus,
    PriceBasis,
    ProviderName,
    ProviderMode,
)
from .security_master import SecurityMasterEntry
from .price_observation import PriceObservation
from .benchmark_observation import BenchmarkObservation
from .security_feature_snapshot import SecurityFeatureSnapshot
from .group_snapshot import GroupSnapshot, ConcentrationMetrics
from .transition_event import TransitionEvent
from .evidence import (
    ConcentrationEvidence,
    ConfirmationEvidence,
    ContradictionRecord,
    DataGap,
    DataGapCategory,
    DataGapStatus,
    DiffusionEvidence,
    EvidenceRecord,
    GroupEvidence,
    InvalidationCondition,
    LeadershipEvidence,
    PerformanceEvidence,
)
from .fundamental import FundamentalConfirmation
from .flow import FlowConfirmation
from .manifest import SnapshotManifest, ManifestEntry

__all__ = [
    "LeadershipState",
    "DiffusionState",
    "DiffusionStateV2",
    "MaterialityLabel",
    "EligibilityStatus",
    "DataQualityStatus",
    "PriceBasis",
    "ProviderName",
    "ProviderMode",
    "SecurityMasterEntry",
    "PriceObservation",
    "BenchmarkObservation",
    "SecurityFeatureSnapshot",
    "GroupSnapshot",
    "ConcentrationMetrics",
    "TransitionEvent",
    "EvidenceRecord",
    "GroupEvidence",
    "LeadershipEvidence",
    "DiffusionEvidence",
    "ConcentrationEvidence",
    "PerformanceEvidence",
    "ConfirmationEvidence",
    "ContradictionRecord",
    "DataGap",
    "DataGapCategory",
    "DataGapStatus",
    "InvalidationCondition",
    "FundamentalConfirmation",
    "FlowConfirmation",
    "SnapshotManifest",
    "ManifestEntry",
]
