"""Local cache for raw provider responses.

Stores raw payloads as parquet (preferred) or json. Reused to avoid
network calls during tests and to give Sectors a way to retain paid
responses.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..utils import data_root, get_logger, project_root

_log = get_logger(__name__)


class RawCache:
    """Filesystem-backed key/value cache with TTL."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or (data_root() / "cache")
        self.root.mkdir(parents=True, exist_ok=True)

    def _key_path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{h[:2]}" / f"{h}.json"

    def get(self, key: str, ttl_seconds: Optional[int] = None) -> Optional[dict]:
        p = self._key_path(key)
        if not p.exists():
            return None
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            _log.warning("cache_read_failed key=%s err=%s", key, e)
            return None
        if ttl_seconds is not None:
            age = time.time() - payload.get("_cached_at", 0)
            if age > ttl_seconds:
                return None
        return payload.get("data")

    def set(self, key: str, data: Any) -> None:
        p = self._key_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"_cached_at": time.time(), "data": data},
                default=str,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        tmp.replace(p)

    def has(self, key: str) -> bool:
        return self._key_path(key).exists()

    def clear(self) -> None:
        for p in self.root.glob("**/*.json"):
            p.unlink()
from .comparability import SnapshotComparability, assess_snapshot_comparability, check_snapshot_compatibility

__all__ = ["SnapshotComparability", "assess_snapshot_comparability", "check_snapshot_compatibility"]
