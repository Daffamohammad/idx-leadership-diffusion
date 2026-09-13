"""Provider request ledger for credit auditing.

Records every remote request with parameters, timing, cache status, and
estimated/actual credit cost. For public providers `estimated_credit_cost`
is 0; Sectors can fill `actual_credit_cost` when known.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..utils import data_root, get_logger, log_event

_log = get_logger(__name__)


# Defense-in-depth: the ledger stores only a hash of request parameters, but
# the free-form ``error`` string comes from provider transports. Scrub
# credential-shaped material and bound its length so a fail-open caller
# cannot persist a secret to the JSONL audit file.
_RE_LEDGER_KEY_VALUE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?[^\s'\",;}\]]+"
)
_RE_LEDGER_JSON_VALUE = re.compile(
    r'(?i)("(?:api[_-]?key|token|secret|password|authorization)"\s*:\s*")[^"]+(")'
)
_RE_LEDGER_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/=]+")
_MAX_ERROR_CHARS = 500


def _scrub_error(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    text = _RE_LEDGER_BEARER.sub("Bearer ***", text)
    text = _RE_LEDGER_JSON_VALUE.sub(r"\1***\2", text)
    text = _RE_LEDGER_KEY_VALUE.sub(lambda m: m.group(1) + "=***", text)
    return text[:_MAX_ERROR_CHARS]


def _validate_ledger_path(path: Path) -> Path:
    text = str(path)
    if not text or text == "." or "\x00" in text:
        raise ValueError(f"Invalid ledger path: {text!r}")
    if path.name in ("", ".", ".."):
        raise ValueError(f"Invalid ledger path filename: {text!r}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Ledger path is not a file: {text!r}")
    return path


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
    # Conservative client-side reservation. This can include retry attempts
    # even when the provider's documented endpoint estimate is lower or
    # unavailable; it is kept separate so the audit never presents a reserve
    # as an observed account debit.
    budget_reserved_credit_cost: float = 0.0
    actual_credit_cost: Optional[float] = None
    error: Optional[str] = None


class RequestLedger:
    """Append-only ledger; flushed to JSONL on demand. Thread-safe."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._entries: list[LedgerEntry] = []
        self._lock = threading.Lock()
        raw = path or (data_root() / "raw" / "request_ledger.jsonl")
        self.path = _validate_ledger_path(Path(raw))

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
        budget_reserved_credit_cost: float = 0.0,
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
            budget_reserved_credit_cost=budget_reserved_credit_cost,
            actual_credit_cost=actual_credit_cost,
            error=_scrub_error(error),
        )
        with self._lock:
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
        with self._lock:
            return list(self._entries)

    def flush(self) -> None:
        # Drain under the lock so concurrent flushers can never snapshot
        # overlapping batches (which would duplicate entries on disk).
        with self._lock:
            pending = list(self._entries)
            self._entries.clear()
            target = _validate_ledger_path(self.path)
        if not pending:
            return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as f:
                for e in pending:
                    d = asdict(e)
                    d["timestamp_iso"] = datetime.fromtimestamp(
                        e.timestamp, tz=timezone.utc
                    ).isoformat()
                    f.write(json.dumps(d, default=str) + "\n")
        except OSError:
            with self._lock:
                self._entries[0:0] = pending
            raise

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()
