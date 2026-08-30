"""Provider abstraction and concrete implementations.

The application/analytics layer MUST NOT import any provider directly.
It consumes the `MarketDataProvider` interface and the capability
protocols under `capabilities.py` only.
"""
from .base import MarketDataProvider
from .capabilities import (
    BenchmarkProvider,
    CapabilityNotSupported,
    CapabilitySet,
    EventProvider,
    FlowProvider,
    FreeFloatProvider,
    PriceCrossSectionProvider,
    PriceHistoryProvider,
    SecurityMasterProvider,
    TaxonomyProvider,
)
from .factory import build_provider_from_config, parse_provider_mode
from .ledger import RequestLedger
from .tavily_client import TavilyClient, TavilyError, TavilyResponse
from .you_client import YouClient, YouError, YouResponse
from .idx_statistics import (
    IDXStatisticsError,
    build_monthly_investor_url,
    fetch_idx_html,
    parse_idx_monthly_investor_html,
    parse_idx_statistics_listing_html,
)

__all__ = [
    "MarketDataProvider",
    "BenchmarkProvider",
    "CapabilityNotSupported",
    "CapabilitySet",
    "EventProvider",
    "FlowProvider",
    "FreeFloatProvider",
    "PriceCrossSectionProvider",
    "PriceHistoryProvider",
    "SecurityMasterProvider",
    "TaxonomyProvider",
    "RequestLedger",
    "TavilyClient",
    "YouClient",
    "TavilyError",
    "YouError",
    "TavilyResponse",
    "YouResponse",
    "IDXStatisticsError",
    "build_monthly_investor_url",
    "fetch_idx_html",
    "parse_idx_monthly_investor_html",
    "parse_idx_statistics_listing_html",
    "build_provider_from_config",
    "parse_provider_mode",
]
