"""Provider request ledger for credit auditing.

Records every remote request with parameters, timing, cache status, and
estimated/actual credit cost. For public providers `estimated_credit_cost`
is 0; Sectors can fill `actual_credit_cost` when known.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from ..utils import data_root, get_logger, log_event

_log = get_logger(__name__)


@dataclass
class LedgerEntry:
    timestamp: float
    provider: str
    endpoint: str
    request_type: str
    parameters_hash: str
    cache_hit: bool
    status: str
    rows_returned: int
    elapsed_ms: float
    estimated_credit_cost: float = 0.0
    actual_credit_cost: Optional[float] = None
    error: Optional[str] = None


class RequestLedger:
    """Append-only ledger; flushed to JSONL on demand."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._entries: list[LedgerEntry] = []
        self.path = path or (data_root() / "raw" / "request_ledger.jsonl")

    @staticmethod
    def hash_params(params: Any) -> str:
        try:
            s = json.dumps(params, sort_keys=True, default=str)
        except (TypeError, ValueError):
            s = repr(params)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

    def record(
        self,
        *,
        provider: str,
        endpoint: str,
        request_type: str,
        parameters: Any,
        cache_hit: bool,
        status: str,
        rows_returned: int,
        elapsed_ms: float,
        estimated_credit_cost: float = 0.0,
        actual_credit_cost: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        entry = LedgerEntry(
            timestamp=time.time(),
            provider=provider,
            endpoint=endpoint,
            request_type=request_type,
            parameters_hash=self.hash_params(parameters),
            cache_hit=cache_hit,
            status=status,
            rows_returned=rows_returned,
            elapsed_ms=elapsed_ms,
            estimated_credit_cost=estimated_credit_cost,
            actual_credit_cost=actual_credit_cost,
            error=error,
        )
        self._entries.append(entry)
        log_event(
            _log,
            "provider_request",
            provider=provider,
            endpoint=endpoint,
            type=request_type,
            cache_hit=cache_hit,
            status=status,
            rows=rows_returned,
            elapsed_ms=round(elapsed_ms, 1),
        )

    def entries(self) -> list[LedgerEntry]:
        return list(self._entries)

    def flush(self) -> None:
        if not self._entries:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            for e in self._entries:
                d = asdict(e)
                d["timestamp_iso"] = date.fromtimestamp(e.timestamp).isoformat()
                f.write(json.dumps(d, default=str) + "\n")
        self._entries.clear()

    def reset(self) -> None:
        self._entries.clear()
