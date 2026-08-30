"""Custom exceptions used across the package."""
from __future__ import annotations


class IDXError(Exception):
    """Root for project-specific errors."""


class ProviderError(IDXError):
    """A data provider could not complete a request."""


class CreditBudgetExceeded(ProviderError):
    """A paid-provider request was blocked by the configured credit ceiling."""


class NormalizationError(IDXError):
    """A provider response could not be normalized to a canonical schema."""


class DataQualityError(IDXError):
    """Data quality checks failed; downstream consumers should not proceed silently."""


class InsufficientHistoryError(IDXError):
    """Not enough history to compute a return or feature."""


class SnapshotError(IDXError):
    """Snapshot read/write or manifest integrity issue."""


class ConfigurationError(IDXError):
    """A required configuration value is missing or invalid."""
