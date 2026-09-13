"""Snapshot writer with atomic semantics.

A snapshot bundles:
  - one normalized price parquet (long format)
  - one normalized benchmark parquet
  - one normalized security master csv
  - one feature snapshot parquet
  - one group snapshot parquet
  - one transitions parquet
  - one manifest.json

Files are written atomically per file (tmp + rename). The COMPLETE
sentinel is written by the pipeline after all sidecars, so writer-level
output alone loads with complete=false. SnapshotReader.load reports the
flag; pre-sentinel bundles remain loadable for back-compat. The on-disk
layout is stable and versioned.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import pandas as pd

from ..models import (
    GroupSnapshot,
    ManifestEntry,
    PriceBasis,
    ProviderName,
    ProviderMode,
    SecurityFeatureSnapshot,
    SecurityMasterEntry,
    SnapshotManifest,
    TransitionEvent,
)
from ..utils import data_root, get_logger, project_root

_log = get_logger(__name__)


SNAPSHOT_VERSION = "snapshot-v2"

_SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Intra-process mutual exclusion for SnapshotWriter.write. Class-level shared
# lock so concurrent threads in the same process serialize bundle writes even
# when they use distinct SnapshotWriter instances pointing at the same root.
_WRITE_LOCK = threading.Lock()

_LOCK_FILENAME = ".snapshot_write.lock"


@contextlib.contextmanager
def _interprocess_lock(root: Path) -> Iterator[None]:
    """Hold an exclusive inter-process lock for the snapshot root.

    Uses POSIX ``fcntl.flock`` on a root-level lock file. Falls back
    gracefully (no inter-process exclusion, intra-process threading lock
    still applies) when ``fcntl`` is unavailable or the lock file cannot be
    created — e.g. Windows, read-only filesystems. Never leaks credentials;
    the lock file contains no payload.
    """

    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        yield
        return
    lock_path = root / _LOCK_FILENAME
    try:
        import fcntl  # POSIX only; ImportError on Windows is expected
    except ImportError:
        yield
        return
    try:
        handle = open(lock_path, "a+b")
    except OSError:
        yield
        return
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except OSError:
            # Graceful fallback: proceed without inter-process exclusion.
            yield
            return
        try:
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        try:
            handle.close()
        except OSError:
            pass


def validate_snapshot_id(snapshot_id: str) -> str:
    """Reject path-escape / absolute snapshot ids before joining to root."""
    if not snapshot_id or not _SNAPSHOT_ID_RE.match(snapshot_id):
        raise ValueError(
            f"Invalid snapshot_id={snapshot_id!r}; must match ^[A-Za-z0-9_-]+$"
        )
    return snapshot_id


class SnapshotWriter:
    """Write a complete snapshot bundle to disk atomically.

    Concurrency contract (single-writer boundary):

    * One writer at a time per snapshot root. ``write`` serializes callers
      in this process via a shared threading lock and across processes via a
      POSIX ``fcntl`` exclusive lock on ``<root>/.snapshot_write.lock``
      (graceful no-op fallback where ``fcntl`` is unavailable).
    * There is deliberately no background scheduler or async worker; all
      scheduled refreshes must go through this single-writer entry point one
      run at a time. Concurrent schedulers must acquire the same root lock
      (i.e. run sequentially) rather than writing concurrently.
    * Readers never take the lock; they are tolerant of in-progress bundles
      (missing ``COMPLETE`` sentinel, ``*.tmp`` leftovers ignored, optional
      JSON sidecars defaulted). Atomic ``tmp + rename`` per file guarantees a
      reader sees either the old or the new file, never a torn write.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or (data_root() / "snapshots")
        self.root.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        snapshot_id: str,
        as_of: date,
        provider: ProviderName,
        provider_mode: ProviderMode | None = None,
        price_basis: PriceBasis | str | None = None,
        universe_version: str,
        taxonomy_version: str,
        eligibility_version: str = "eligibility-v1",
        method_version: str,
        feature_version: str,
        leadership_version: str = "leadership-v1",
        diffusion_version: str = "diffusion-v1",
        concentration_version: str = "concentration-v1",
        schema_version: str = "schemas-v1",
        coverage_status,
        coverage_pct: float,
        prices: pd.DataFrame,
        benchmark: pd.DataFrame,
        security_master: list[SecurityMasterEntry],
        features: pd.DataFrame,
        groups: pd.DataFrame,
        transitions: pd.DataFrame,
        notes: Optional[str] = None,
        eligible_ticker_set_hash: Optional[str] = None,
        eligible_ticker_count: int = 0,
        raw_ticker_count: int = 0,
    ) -> Path:
        validate_snapshot_id(snapshot_id)
        with _WRITE_LOCK:
            with _interprocess_lock(self.root):
                return self._write_locked(
                    snapshot_id=snapshot_id,
                    as_of=as_of,
                    provider=provider,
                    provider_mode=provider_mode,
                    price_basis=price_basis,
                    universe_version=universe_version,
                    taxonomy_version=taxonomy_version,
                    eligibility_version=eligibility_version,
                    method_version=method_version,
                    feature_version=feature_version,
                    leadership_version=leadership_version,
                    diffusion_version=diffusion_version,
                    concentration_version=concentration_version,
                    schema_version=schema_version,
                    coverage_status=coverage_status,
                    coverage_pct=coverage_pct,
                    prices=prices,
                    benchmark=benchmark,
                    security_master=security_master,
                    features=features,
                    groups=groups,
                    transitions=transitions,
                    notes=notes,
                    eligible_ticker_set_hash=eligible_ticker_set_hash,
                    eligible_ticker_count=eligible_ticker_count,
                    raw_ticker_count=raw_ticker_count,
                )

    def _write_locked(
        self,
        *,
        snapshot_id: str,
        as_of: date,
        provider: ProviderName,
        provider_mode: ProviderMode | None = None,
        price_basis: PriceBasis | str | None = None,
        universe_version: str,
        taxonomy_version: str,
        eligibility_version: str = "eligibility-v1",
        method_version: str,
        feature_version: str,
        leadership_version: str = "leadership-v1",
        diffusion_version: str = "diffusion-v1",
        concentration_version: str = "concentration-v1",
        schema_version: str = "schemas-v1",
        coverage_status,
        coverage_pct: float,
        prices: pd.DataFrame,
        benchmark: pd.DataFrame,
        security_master: list[SecurityMasterEntry],
        features: pd.DataFrame,
        groups: pd.DataFrame,
        transitions: pd.DataFrame,
        notes: Optional[str] = None,
        eligible_ticker_set_hash: Optional[str] = None,
        eligible_ticker_count: int = 0,
        raw_ticker_count: int = 0,
    ) -> Path:
        target = self.root / snapshot_id
        target.mkdir(parents=True, exist_ok=True)

        # Atomic per-file write.
        _atomic_to_csv(prices, target / "prices.csv")
        _atomic_to_csv(benchmark, target / "benchmark.csv")
        _atomic_to_parquet(prices, target / "prices.parquet")
        _atomic_to_parquet(benchmark, target / "benchmark.parquet")
        _atomic_to_parquet(features, target / "features.parquet")
        _atomic_to_parquet(groups, target / "groups.parquet")
        _atomic_to_parquet(transitions, target / "transitions.parquet")

        _atomic_write_text(
            target / "security_master.json",
            json.dumps(
                [sm.model_dump(mode="json") for sm in security_master],
                indent=2,
                default=str,
                ensure_ascii=False,
            ),
        )

        market_date = _latest_date(prices)
        benchmark_date = _latest_date(benchmark)
        resolved_mode = provider_mode or _default_provider_mode(provider)

        manifest = SnapshotManifest(
            snapshot_count=1,
            first_date=as_of,
            latest_date=as_of,
            provider=provider,
            provider_mode=resolved_mode,
            price_basis=price_basis,
            universe_version=universe_version,
            taxonomy_version=taxonomy_version,
            eligibility_version=eligibility_version,
            method_version=method_version,
            feature_version=feature_version,
            leadership_version=leadership_version,
            diffusion_version=diffusion_version,
            concentration_version=concentration_version,
            schema_version=schema_version,
            snapshot_version=SNAPSHOT_VERSION,
            entries=[
                ManifestEntry(
                    snapshot_id=snapshot_id,
                    snapshot_date=as_of,
                    as_of=as_of,
                    provider=provider,
                    provider_mode=resolved_mode,
                    price_basis=price_basis,
                    market_date=market_date,
                    benchmark_date=benchmark_date,
                    universe_version=universe_version,
                    taxonomy_version=taxonomy_version,
                    eligibility_version=eligibility_version,
                    method_version=method_version,
                    feature_version=feature_version,
                    leadership_version=leadership_version,
                    diffusion_version=diffusion_version,
                    concentration_version=concentration_version,
                    schema_version=schema_version,
                    snapshot_version=SNAPSHOT_VERSION,
                    coverage_status=coverage_status,
                    coverage_pct=coverage_pct,
                    created_at=date.today(),
                    notes=notes,
                    eligible_ticker_set_hash=eligible_ticker_set_hash,
                    eligible_ticker_count=eligible_ticker_count,
                    raw_ticker_count=raw_ticker_count,
                )
            ],
            notes=[],
        )
        _atomic_write_text(target / "manifest.json", manifest.model_dump_json(indent=2))
        _log.info("snapshot_written id=%s as_of=%s dir=%s", snapshot_id, as_of, target)
        return target


class SnapshotReader:
    """Read snapshot bundles and aggregate them into a manifest."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or (data_root() / "snapshots")
        self.root.mkdir(parents=True, exist_ok=True)

    def list_snapshots(self) -> list[Path]:
        return sorted(
            [
                p
                for p in self.root.iterdir()
                if p.is_dir() and (p / "manifest.json").exists()
            ]
        )

    def load(self, snapshot_id: str) -> dict[str, Any]:
        validate_snapshot_id(snapshot_id)
        d = self.root / snapshot_id
        if not d.exists():
            raise FileNotFoundError(d)
        # COMPLETE is written last by SnapshotWriter.write. Pre-sentinel
        # bundles remain loadable for back-compat; consumers must check the
        # flag instead of assuming bundle integrity from manifest presence.
        # Readers never take the write lock (single-writer boundary); atomic
        # tmp+rename per file plus tolerant JSON/parquet reads keep concurrent
        # reads safe: *.tmp leftovers are ignored and a torn manifest/master
        # read is retried once before surfacing.
        complete = (d / "COMPLETE").exists()
        prices = _read_any(d / "prices")
        benchmark = _read_any(d / "benchmark")
        features = _read_any(d / "features")
        groups = _read_any(d / "groups")
        transitions = _read_any(d / "transitions")
        master = _read_json_required(d / "security_master.json")
        manifest = _read_json_required(d / "manifest.json")
        return {
            "complete": complete,
            "prices": prices,
            "benchmark": benchmark,
            "features": features,
            "groups": groups,
            "transitions": transitions,
            "security_master": master,
            "manifest": manifest,
            "change_digest": _read_json_optional(d / "change_digest.json", {}),
            "quality": _read_json_optional(d / "quality.json", {}),
            "coverage": _read_json_optional(d / "coverage.json", {}),
            "data_warnings": _read_json_optional(d / "data_warnings.json", {}),
            "provider_provenance": _read_json_optional(d / "provider_provenance.json", {}),
            "methodology_sensitivity": _read_json_optional(
                d / "methodology_sensitivity.json", {}
            ),
            "api_credit_audit": _read_json_optional(d / "api_credit_audit.json", {}),
            "tavily_context": _read_json_optional(d / "tavily_context.json", {}),
            "you_context": _read_json_optional(d / "you_context.json", {}),
            "security_master_diagnostics": _read_json_optional(
                d / "security_master_diagnostics.json", {}
            ),
            "history_diagnostics": _read_json_optional(
                d / "history_diagnostics.json", {}
            ),
            "evidence": _read_json_optional(d / "evidence.json", []),
            "market_read": _read_json_optional(d / "market_read.json", {}),
            "story_mode": _read_json_optional(d / "story_mode.json", {}),
            "comparability": _read_json_optional(d / "comparability.json", {}),
            "endpoints": _read_json_optional(d / "endpoints.json", []),
        }

    def aggregate_manifest(self) -> SnapshotManifest:
        entries: list[ManifestEntry] = []
        for p in self.list_snapshots():
            try:
                m = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            e = m.get("entries", [])
            if e:
                entries.append(ManifestEntry(**e[0]))
        if not entries:
            return SnapshotManifest(
                snapshot_count=0,
                first_date=None,
                latest_date=None,
                provider=ProviderName.YFINANCE,
                universe_version="prototype-v1",
                taxonomy_version="prototype-v1",
                method_version="methodology-v1",
                feature_version="features-v1",
                entries=[],
                notes=["no snapshots yet"],
            )
        entries.sort(key=lambda x: x.as_of)
        first = entries[0].as_of
        last = entries[-1].as_of
        return SnapshotManifest(
            snapshot_count=len(entries),
            first_date=first,
            latest_date=last,
            provider=entries[-1].provider,
            provider_mode=entries[-1].provider_mode,
            price_basis=entries[-1].price_basis,
            universe_version=entries[-1].universe_version,
            taxonomy_version=entries[-1].taxonomy_version,
            eligibility_version=entries[-1].eligibility_version,
            method_version=entries[-1].method_version,
            feature_version=entries[-1].feature_version,
            leadership_version=entries[-1].leadership_version,
            diffusion_version=entries[-1].diffusion_version,
            concentration_version=entries[-1].concentration_version,
            schema_version=entries[-1].schema_version,
            snapshot_version=entries[-1].snapshot_version,
            entries=entries,
            notes=[],
        )


def _atomic_to_csv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def _atomic_write_text(path: Path, value: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value, encoding="utf-8")
    tmp.replace(path)


def _latest_date(df: pd.DataFrame) -> date | None:
    if df is None or df.empty or "date" not in df.columns:
        return None
    values = pd.to_datetime(df["date"], errors="coerce").dropna()
    if values.empty:
        return None
    return values.max().date()


def _default_provider_mode(provider: ProviderName) -> ProviderMode:
    if provider == ProviderName.SECTORS:
        return ProviderMode.SECTORS_LIVE
    if provider == ProviderName.FIXTURE:
        return ProviderMode.DEMO_FIXTURE
    return ProviderMode.PUBLIC_PROTOTYPE


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    if df.empty:
        # Write a valid (schema-preserving) empty parquet so external
        # parquet readers never see a 0-byte stub. _read_any prefers
        # parquet and falls back to CSV only when absent.
        df.to_parquet(tmp, index=False)
        tmp.replace(path)
        return
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def _read_any(stem: Path) -> pd.DataFrame:
    par = stem.with_suffix(".parquet")
    if par.exists() and par.stat().st_size > 0:
        try:
            return pd.read_parquet(par)
        except (OSError, ValueError):
            # Tolerate a concurrent writer mid-rename: fall back to CSV or
            # empty rather than crashing the read path.
            pass
    csv = stem.with_suffix(".csv")
    if csv.exists():
        try:
            return pd.read_csv(csv)
        except (OSError, ValueError, pd.errors.ParserError):
            return pd.DataFrame()
    return pd.DataFrame()


def _read_json_required(path: Path) -> Any:
    """Read a required bundle file tolerantly across a concurrent rename.

    Atomic tmp+rename means a reader normally sees the old or the new file.
    On filesystems where the rename window is visible, retry once after a
    short sleep before surfacing the error.
    """

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        time.sleep(0.05)
        return json.loads(path.read_text(encoding="utf-8"))


def _read_json_optional(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Retry once for a concurrent atomic rename, then fall back to the
        # default so optional sidecars never break the read path.
        try:
            time.sleep(0.02)
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default
