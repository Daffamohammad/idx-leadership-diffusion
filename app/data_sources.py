"""Read-only data sources for the product UI.

This module only loads artifacts already present on disk.  It never creates a
provider, reads credentials, or performs a network request.  That boundary is
deliberate: opening the UI cannot consume Sectors credits or silently fall
back to another source.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEMO_FIXTURE_PATH = ROOT / "data" / "fixtures" / "demo_market.json"
SNAPSHOT_ROOT = ROOT / "data" / "snapshots"
METHODOLOGY_PATH = ROOT / "config" / "methodology.yaml"


@dataclass(frozen=True)
class SourceOption:
    """One safe, local source exposed in the UI selector."""

    source_id: str
    label: str
    kind: str
    path: Path


def available_sources(snapshot_root: Path = SNAPSHOT_ROOT) -> tuple[SourceOption, ...]:
    """Return deterministic demo + readable local snapshots, newest first."""
    options: list[SourceOption] = [
        SourceOption(
            source_id="demo",
            label="Demo fixture — deterministic story",
            kind="demo",
            path=DEMO_FIXTURE_PATH,
        )
    ]
    if not snapshot_root.exists():
        return tuple(options)

    candidates = sorted(snapshot_root.glob("**/snap_*/manifest.json"), reverse=True)
    for manifest_path in candidates:
        snapshot_dir = manifest_path.parent
        try:
            manifest = _read_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue
        entry = (manifest.get("entries") or [{}])[-1]
        as_of = entry.get("as_of") or manifest.get("latest_date") or snapshot_dir.name
        mode = _safe_mode_hint(manifest, snapshot_dir)
        options.append(
            SourceOption(
                source_id=f"snapshot:{snapshot_dir}",
                label=f"{mode.replace('_', ' ').title()} — {as_of}",
                kind="snapshot",
                path=snapshot_dir,
            )
        )
    return tuple(options)


def load_source(option: SourceOption) -> dict[str, Any]:
    """Load one selected source without invoking a provider."""
    if option.kind == "demo":
        return load_demo_payload(option.path)
    if option.kind == "snapshot":
        return load_snapshot_payload(option.path)
    raise ValueError(f"Unsupported local source kind: {option.kind}")


def load_demo_payload(path: Path = DEMO_FIXTURE_PATH) -> dict[str, Any]:
    payload = _read_json(path)
    payload["methodology_config"] = _read_yaml(METHODOLOGY_PATH)
    payload["source_path"] = str(path)
    return payload


def load_snapshot_payload(snapshot_dir: Path) -> dict[str, Any]:
    """Load a persisted snapshot and compatible local history.

    The payload shape matches the demo fixture closely enough for the pure
    view-model builder.  Optional artifacts are tolerated and represented as
    empty collections; missing core group data remains a visible error.
    """
    snapshot_dir = snapshot_dir.resolve()
    manifest = _read_json(snapshot_dir / "manifest.json")
    groups = _read_table(snapshot_dir / "groups")
    if groups.empty:
        raise ValueError(f"Snapshot has no group rows: {snapshot_dir}")

    sibling_dirs = _snapshot_siblings(snapshot_dir)
    earlier = [path for path in sibling_dirs if path.name < snapshot_dir.name]
    previous_groups: list[dict[str, Any]] = []
    if earlier:
        previous_groups = _records(_read_table(earlier[-1] / "groups"))

    history: list[dict[str, Any]] = []
    for path in [*earlier, snapshot_dir]:
        frame = _read_table(path / "groups")
        if frame.empty:
            continue
        history.extend(_records(frame))

    transitions = _read_table(snapshot_dir / "transitions")
    quality = _read_json_optional(snapshot_dir / "quality.json")
    endpoints = _read_json_optional(snapshot_dir / "endpoints.json", default=[])
    change_digest = _read_json_optional(snapshot_dir / "change_digest.json")
    features = _read_table(snapshot_dir / "features")
    security_master = _read_json_optional(snapshot_dir / "security_master.json", default=[])
    coverage = _read_json_optional(snapshot_dir / "coverage.json")
    data_warnings = _read_json_optional(snapshot_dir / "data_warnings.json")
    provider_provenance = _read_json_optional(snapshot_dir / "provider_provenance.json")
    methodology_sensitivity = _read_json_optional(
        snapshot_dir / "methodology_sensitivity.json"
    )
    tavily_context = _read_json_optional(snapshot_dir / "tavily_context.json")
    api_credit_audit = _read_json_optional(snapshot_dir / "api_credit_audit.json")
    security_master_diagnostics = _read_json_optional(
        snapshot_dir / "security_master_diagnostics.json"
    )
    history_diagnostics = _read_json_optional(
        snapshot_dir / "history_diagnostics.json"
    )

    return {
        "provider_mode": _safe_mode_hint(manifest, snapshot_dir),
        "fixture_label": None,
        "as_of": _manifest_value(manifest, "as_of", "latest_date"),
        "market_date": _max_date(_read_table(snapshot_dir / "prices")),
        "benchmark_date": _max_date(_read_table(snapshot_dir / "benchmark")),
        "manifest": manifest,
        "quality": quality,
        "coverage": coverage,
        "data_warnings": data_warnings,
        "provider_provenance": provider_provenance,
        "methodology_sensitivity": methodology_sensitivity,
        "you_context": _read_json_optional(snapshot_dir / "you_context.json"),
        "api_credit_audit": api_credit_audit,
        "security_master_diagnostics": security_master_diagnostics,
        "history_diagnostics": history_diagnostics,
        "endpoints": endpoints,
        "change_digest": change_digest,
        "groups": _records(groups),
        "previous_groups": previous_groups,
        "history": history,
        "transitions": _records(transitions),
        "constituents": _build_constituents(features, security_master),
        "methodology_config": _read_yaml(METHODOLOGY_PATH),
        "source_path": str(snapshot_dir),
    }


def _safe_mode_hint(manifest: dict[str, Any], snapshot_dir: Path) -> str:
    """Infer a conservative badge; live requires an explicit manifest claim."""
    entry = (manifest.get("entries") or [{}])[-1]
    explicit = manifest.get("provider_mode") or entry.get("provider_mode")
    valid = {"DEMO_FIXTURE", "PUBLIC_PROTOTYPE", "SECTORS_FIXTURE", "SECTORS_LIVE"}
    if explicit in valid:
        return str(explicit)

    provider = str(entry.get("provider") or manifest.get("provider") or "").lower()
    # A provider name alone is not proof that a credentialed call occurred.
    if provider == "sectors" or "sectors" in {part.lower() for part in snapshot_dir.parts}:
        return "SECTORS_FIXTURE"
    return "PUBLIC_PROTOTYPE"


def _snapshot_siblings(snapshot_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in snapshot_dir.parent.glob("snap_*")
        if path.is_dir() and (path / "manifest.json").exists()
    )


def _build_constituents(
    features: pd.DataFrame,
    security_master: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    feature_by_ticker = {
        str(row.get("ticker")): row
        for row in _records(features)
        if row.get("ticker") is not None
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for security in security_master:
        ticker = str(security.get("ticker") or security.get("symbol") or "")
        if not ticker:
            continue
        group_id = str(
            security.get("group_id")
            or security.get("subsector")
            or security.get("sector")
            or "UNMAPPED"
        )
        feature = feature_by_ticker.get(ticker, {})
        excess_20d = _clean_scalar(feature.get("excess_return_20d"))
        grouped.setdefault(group_id, []).append(
            {
                "ticker": ticker,
                "company_name": security.get("company_name") or ticker,
                "excess_return_5d": _clean_scalar(feature.get("excess_return_5d")),
                "excess_return_20d": excess_20d,
                "excess_return_60d": _clean_scalar(feature.get("excess_return_60d")),
                "participating": bool(excess_20d is not None and excess_20d > 0),
            }
        )
    return grouped


def _read_table(stem: Path) -> pd.DataFrame:
    parquet = stem.with_suffix(".parquet")
    csv = stem.with_suffix(".csv")
    if parquet.exists() and parquet.stat().st_size:
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return [
        {key: _clean_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_optional(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {} if default is None else default


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _manifest_value(manifest: dict[str, Any], entry_key: str, root_key: str) -> Any:
    entry = (manifest.get("entries") or [{}])[-1]
    return entry.get(entry_key) or manifest.get(root_key)


def _max_date(frame: pd.DataFrame) -> str | None:
    if frame.empty:
        return None
    for column in ("date", "as_of", "snapshot_date"):
        if column in frame.columns:
            values = pd.to_datetime(frame[column], errors="coerce").dropna()
            if not values.empty:
                return values.max().date().isoformat()
    return None
