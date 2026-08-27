"""Snapshot writer with atomic semantics.

A snapshot bundles:
  - one normalized price parquet (long format)
  - one normalized benchmark parquet
  - one normalized security master csv
  - one feature snapshot parquet
  - one group snapshot parquet
  - one transitions parquet
  - one manifest.json

Files are written via a temp-dir + rename for atomicity. The on-disk
layout is stable and versioned.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..models import (
    GroupSnapshot,
    ManifestEntry,
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


class SnapshotWriter:
    """Write a complete snapshot bundle to disk atomically."""

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
        d = self.root / snapshot_id
        if not d.exists():
            raise FileNotFoundError(d)
        prices = _read_any(d / "prices")
        benchmark = _read_any(d / "benchmark")
        features = _read_any(d / "features")
        groups = _read_any(d / "groups")
        transitions = _read_any(d / "transitions")
        master = json.loads((d / "security_master.json").read_text(encoding="utf-8"))
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        return {
            "prices": prices,
            "benchmark": benchmark,
            "features": features,
            "groups": groups,
            "transitions": transitions,
            "security_master": master,
            "manifest": manifest,
            "change_digest": _read_json_optional(d / "change_digest.json", {}),
            "quality": _read_json_optional(d / "quality.json", {}),
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
    if df.empty:
        # Write an empty parquet by using a stub
        path.write_bytes(b"")
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def _read_any(stem: Path) -> pd.DataFrame:
    par = stem.with_suffix(".parquet")
    if par.exists() and par.stat().st_size > 0:
        return pd.read_parquet(par)
    csv = stem.with_suffix(".csv")
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def _read_json_optional(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
