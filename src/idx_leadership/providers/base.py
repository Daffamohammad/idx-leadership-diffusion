"""Provider base + market-data composition.

`MarketDataProvider` is the **combined** interface the engine depends
on. It declares the core methods the snapshot pipeline always needs
(security master, price history, benchmark, taxonomy). Capability
protocols (`SecurityMasterProvider`, `PriceHistoryProvider`, …) are
separate mixins that providers compose in their concrete class — see
`YFinanceProvider`, `FixtureProvider`, and `SectorsProvider`.

Keeping the base provider class ABC-free here avoids MRO conflicts
between `ABC` and the capability protocols.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

import pandas as pd

from ..models import (
    BenchmarkObservation,
    PriceObservation,
    ProviderName,
    ProviderMode,
    SecurityMasterEntry,
)
from .ledger import RequestLedger


class MarketDataProvider:
    """The base provider interface for the core snapshot pipeline.

    Concrete providers inherit from this class AND from the relevant
    capability protocols in `capabilities.py`.
    """

    name: str = "abstract"
    mode: ProviderMode = ProviderMode.PUBLIC_PROTOTYPE

    def __init__(self, ledger: Optional[RequestLedger] = None) -> None:
        self.ledger = ledger or RequestLedger()

    # Core methods the engine relies on. Subclasses must override.

    def get_security_master(self) -> list[SecurityMasterEntry]:
        raise NotImplementedError

    def get_price_history(
        self, tickers: list[str], *, start: date, end: date
    ) -> pd.DataFrame:
        raise NotImplementedError

    def get_benchmark_history(
        self, benchmark_id: str, *, start: date, end: date
    ) -> pd.DataFrame:
        raise NotImplementedError

    def get_group_taxonomy(self) -> pd.DataFrame:
        raise NotImplementedError
