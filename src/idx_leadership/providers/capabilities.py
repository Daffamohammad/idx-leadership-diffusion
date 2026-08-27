"""Capability-oriented provider interfaces.

A provider composes whichever capabilities it supports. The analytical
engine asks for the capability it needs; if the provider doesn't have
it, a clear `CapabilityNotSupported` error is raised (no silent fallback).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Optional

import pandas as pd


class CapabilityNotSupported(NotImplementedError):
    """The provider does not implement this capability."""


class SecurityMasterProvider(ABC):
    @abstractmethod
    def get_security_master(self) -> list[Any]:
        """Return canonical security master entries (one row per security)."""


class PriceHistoryProvider(ABC):
    @abstractmethod
    def get_price_history(
        self, tickers: list[str], *, start: date, end: date
    ) -> pd.DataFrame:
        """Return long-format price frame; canonical columns required by
        `features/returns.py` and `data/quality.py`."""


class PriceCrossSectionProvider(ABC):
    @abstractmethod
    def get_full_universe_close(self, as_of: date) -> pd.DataFrame:
        """Return the full cross-section for one trading day."""


class BenchmarkProvider(ABC):
    @abstractmethod
    def get_benchmark_history(
        self, benchmark_id: str, *, start: date, end: date
    ) -> pd.DataFrame:
        """Return benchmark price history; canonical columns."""


class TaxonomyProvider(ABC):
    @abstractmethod
    def get_group_taxonomy(self) -> pd.DataFrame:
        """Return a DataFrame mapping `ticker` -> group_id, sector,
        subsector, industry, sub_industry."""


class FreeFloatProvider(ABC):
    @abstractmethod
    def get_free_float(self, as_of: Optional[date] = None) -> pd.DataFrame:
        """Return ticker, free_float (0-1) for the universe."""


class FlowProvider(ABC):
    @abstractmethod
    def get_foreign_flow(
        self, ticker: str, *, start: date, end: date
    ) -> pd.DataFrame:
        """Return per-day net foreign inflow (IDR) for one ticker."""


class FundamentalProvider(ABC):
    @abstractmethod
    def get_company_fundamentals(self, ticker: str) -> dict[str, Any]:
        """Return a structured fundamentals bundle for one ticker."""


class EventProvider(ABC):
    @abstractmethod
    def get_corporate_actions(self, ticker: str) -> dict[str, Any]:
        """Return corporate-action history for one ticker."""

    @abstractmethod
    def get_suspensions(self, *, start: date, end: date) -> pd.DataFrame:
        """Return suspension events in a date window."""


# Convenience marker
class CapabilitySet:
    """Sticky marker of which capability protocols a provider implements."""

    def __init__(self, provider: Any) -> None:
        self.has_security_master = isinstance(provider, SecurityMasterProvider)
        self.has_price_history = isinstance(provider, PriceHistoryProvider)
        self.has_price_cross_section = isinstance(provider, PriceCrossSectionProvider)
        self.has_benchmark = isinstance(provider, BenchmarkProvider)
        self.has_taxonomy = isinstance(provider, TaxonomyProvider)
        self.has_free_float = isinstance(provider, FreeFloatProvider)
        self.has_flow = isinstance(provider, FlowProvider)
        self.has_fundamental = isinstance(provider, FundamentalProvider)
        self.has_event = isinstance(provider, EventProvider)

    def summary(self) -> dict[str, bool]:
        return {
            "security_master": self.has_security_master,
            "price_history": self.has_price_history,
            "price_cross_section": self.has_price_cross_section,
            "benchmark": self.has_benchmark,
            "taxonomy": self.has_taxonomy,
            "free_float": self.has_free_float,
            "flow": self.has_flow,
            "fundamental": self.has_fundamental,
            "event": self.has_event,
        }
