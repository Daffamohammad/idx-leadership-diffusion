"""Export a snapshot directory as a single JSON file for the React UI.

CLI:
    python -m scripts.export_snapshot_json --snapshot-id snap_2026-08-20
    python -m scripts.export_snapshot_json --latest

The output is written to app/web/public/snapshots/<id>.json so the Vite dev
server can serve it as a static asset (GET /snapshots/<id>.json).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from idx_leadership.data.snapshots import SnapshotReader, validate_snapshot_id
from idx_leadership.data.comparability import check_snapshot_compatibility
from idx_leadership.utils import project_root, get_logger

_log = get_logger(__name__)

PUBLIC_DIR = project_root() / "app" / "web" / "public" / "snapshots"


def _records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    """DataFrame -> list[dict] with NaN->None and ISO date strings."""
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    encoded = out.to_json(orient="records", date_format="iso")
    return json.loads(encoded) if encoded is not None else []


def _sanitize_audit(audit: Any) -> Any:
    """Strip machine-specific absolute paths from audit sidecars.

    Shipped web assets must never embed the builder's local filesystem
    layout (e.g. ledger_path). Only the ledger filename is preserved.
    """
    if isinstance(audit, dict):
        cleaned: dict[str, Any] = {}
        for key, value in audit.items():
            if key == "ledger_path" and isinstance(value, str):
                cleaned[key] = value.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            else:
                cleaned[key] = _sanitize_audit(value)
        return cleaned
    if isinstance(audit, list):
        return [_sanitize_audit(item) for item in audit]
    return audit


def _normalize_first_party_idx_urls(value: Any) -> Any:
    """Normalize only the exact legacy IDX URL prefix in an export payload.

    This is intentionally a literal prefix replacement. It does not rewrite
    localhost URLs, other domains, or IDX-like domains with a different host.
    Containers are copied so callers do not mutate the snapshot data loaded
    from disk.
    """
    legacy_prefix = "http://www.idx.co.id/"
    secure_prefix = "https://www.idx.co.id/"
    if isinstance(value, dict):
        return {
            key: _normalize_first_party_idx_urls(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_first_party_idx_urls(item) for item in value]
    if isinstance(value, str):
        return value.replace(legacy_prefix, secure_prefix)
    return value


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


_PRICE_AUX_COLUMNS = ("open", "high", "low", "close", "volume")


def _select_price_columns(prices: pd.DataFrame, price_column: str) -> pd.DataFrame:
    """Copy the price columns while tolerating older snapshot schemas."""
    columns = ["ticker", "date", price_column]
    columns.extend(
        column
        for column in _PRICE_AUX_COLUMNS
        if column not in columns and column in prices.columns
    )
    work = prices[columns].copy()
    for column in _PRICE_AUX_COLUMNS:
        if column not in work.columns:
            work[column] = pd.NA
    return work


def _rounded_optional(value: Any) -> float | None:
    number = _finite_number(value)
    return round(number, 6) if number is not None else None


def _build_group_price_history(
    prices: pd.DataFrame | None,
    benchmark: pd.DataFrame | None,
    security_master: list[dict[str, Any]] | None,
    manifest_entry: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Build a descriptive, rebased group-price series for the web chart.

    This is presentation data only.  It is deliberately separate from the
    analytical feature table: each ticker is rebased to its first valid price
    in the persisted window, then the equal-weight mean is reported by group.
    No chart value is fed back into leadership, breadth, or diffusion logic.
    """
    if prices is None or prices.empty or not security_master:
        return {}
    required = {"ticker", "date"}
    if not required.issubset(prices.columns):
        return {}

    basis = str(manifest_entry.get("price_basis") or "").lower()
    price_column = "adjusted_close" if basis == "adjusted_close" else "close"
    if price_column not in prices.columns:
        alternate = "close" if price_column == "adjusted_close" else "adjusted_close"
        if alternate not in prices.columns:
            return {}
        price_column = alternate

    ticker_to_group = {
        str(row.get("ticker")): str(row.get("group_id"))
        for row in security_master
        if isinstance(row, dict)
        and row.get("ticker")
        and row.get("group_id")
    }
    if not ticker_to_group:
        return {}

    work = _select_price_columns(prices, price_column)
    work["ticker"] = work["ticker"].astype(str)
    work["group_id"] = work["ticker"].map(ticker_to_group)
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["value"] = pd.to_numeric(work[price_column], errors="coerce")
    for column in _PRICE_AUX_COLUMNS:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=["group_id", "date", "value"])
    work = work[work["value"] > 0]
    if work.empty:
        return {}
    work = work.sort_values(["ticker", "date"]).drop_duplicates(
        subset=["ticker", "date"], keep="last"
    )
    first_values = work.groupby("ticker")["value"].transform("first")
    work["rebased"] = work["value"] / first_values * 100.0
    for column in ("open", "high", "low", "close"):
        work[f"rebased_{column}"] = work[column] / first_values * 100.0
    aggregate_spec: dict[str, tuple[str, str | Any]] = {
        "value": ("rebased", "mean"),
        "open": ("rebased_open", "mean"),
        "high": ("rebased_high", "mean"),
        "low": ("rebased_low", "mean"),
        "close": ("rebased_close", "mean"),
        "volume": ("volume", lambda values: values.sum(min_count=1)),
    }
    grouped = work.groupby(["group_id", "date"], as_index=False).agg(**aggregate_spec)

    benchmark_series: pd.DataFrame | None = None
    if benchmark is not None and not benchmark.empty and "date" in benchmark.columns:
        benchmark_column = "close" if "close" in benchmark.columns else None
        if benchmark_column:
            benchmark_series = benchmark[["date", benchmark_column]].copy()
            benchmark_series["date"] = pd.to_datetime(
                benchmark_series["date"], errors="coerce"
            )
            benchmark_series["value"] = pd.to_numeric(
                benchmark_series[benchmark_column], errors="coerce"
            )
            benchmark_series = benchmark_series.dropna(subset=["date", "value"])
            benchmark_series = benchmark_series[benchmark_series["value"] > 0]
            if not benchmark_series.empty:
                benchmark_series = benchmark_series.sort_values("date").drop_duplicates(
                    subset=["date"], keep="last"
                )
                benchmark_series["benchmark"] = (
                    benchmark_series["value"]
                    / benchmark_series["value"].iloc[0]
                    * 100.0
                )

    benchmark_lookup = (
        benchmark_series.set_index("date")["benchmark"].to_dict()
        if benchmark_series is not None and not benchmark_series.empty
        else {}
    )
    output: dict[str, list[dict[str, Any]]] = {}
    for group_id, rows in grouped.groupby("group_id"):
        points: list[dict[str, Any]] = []
        for row in rows.sort_values("date").itertuples(index=False):
            value = _finite_number(row.value)
            if value is None:
                continue
            points.append(
                {
                    "date": row.date.date().isoformat(),
                    "value": round(value, 6),
                    "benchmark": (
                        round(float(benchmark_lookup[row.date]), 6)
                        if row.date in benchmark_lookup
                        and _finite_number(benchmark_lookup[row.date]) is not None
                        else None
                    ),
                    "open": _rounded_optional(getattr(row, "open", None)),
                    "high": _rounded_optional(getattr(row, "high", None)),
                    "low": _rounded_optional(getattr(row, "low", None)),
                    "close": _rounded_optional(getattr(row, "close", None)),
                    "volume": _rounded_optional(getattr(row, "volume", None)),
                }
            )
        if points:
            output[str(group_id)] = points
    return output


def _build_ticker_price_history(
    prices: pd.DataFrame | None,
    benchmark: pd.DataFrame | None,
    manifest_entry: dict[str, Any],
    allowed_tickers: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build real per-ticker chart series from persisted snapshot prices.

    Security and benchmark values are independently rebased to 100 on the
    ticker's first date with a matching benchmark observation. These points
    are descriptive chart data and never feed the signal pipeline.
    """
    if prices is None or prices.empty or benchmark is None or benchmark.empty:
        return {}
    if not {"ticker", "date"}.issubset(prices.columns):
        return {}
    if not {"date", "close"}.issubset(benchmark.columns):
        return {}

    basis = str(manifest_entry.get("price_basis") or "").lower()
    price_column = "adjusted_close" if basis == "adjusted_close" else "close"
    if price_column not in prices.columns:
        return {}

    benchmark_frame = benchmark[["date", "close"]].copy()
    benchmark_frame["date"] = pd.to_datetime(
        benchmark_frame["date"], errors="coerce"
    )
    benchmark_frame["benchmark_close"] = pd.to_numeric(
        benchmark_frame["close"], errors="coerce"
    )
    benchmark_frame = benchmark_frame.dropna(subset=["date", "benchmark_close"])
    benchmark_frame = benchmark_frame[benchmark_frame["benchmark_close"] > 0]
    benchmark_frame = benchmark_frame.sort_values("date").drop_duplicates(
        subset=["date"], keep="last"
    )[["date", "benchmark_close"]]
    if benchmark_frame.empty:
        return {}

    work = _select_price_columns(prices, price_column)
    work["ticker"] = work["ticker"].astype(str).str.upper()
    if allowed_tickers is not None:
        work = work[work["ticker"].isin(allowed_tickers)]
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["security_close"] = pd.to_numeric(work[price_column], errors="coerce")
    for column in _PRICE_AUX_COLUMNS:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=["ticker", "date", "security_close"])
    work = work[work["security_close"] > 0]
    work = work.sort_values(["ticker", "date"]).drop_duplicates(
        subset=["ticker", "date"], keep="last"
    )

    output: dict[str, list[dict[str, Any]]] = {}
    for ticker, ticker_frame in work.groupby("ticker", sort=True):
        aligned = ticker_frame.merge(benchmark_frame, on="date", how="inner")
        if aligned.empty:
            continue
        security_base = _finite_number(aligned["security_close"].iloc[0])
        benchmark_base = _finite_number(aligned["benchmark_close"].iloc[0])
        if security_base is None or benchmark_base is None:
            continue
        for column in ("open", "high", "low", "close"):
            aligned[f"rebased_{column}"] = aligned[column] / security_base * 100.0
        points = [
            {
                "date": row.date.date().isoformat(),
                "value": round(float(row.security_close) / security_base * 100.0, 6),
                "benchmark": round(
                    float(row.benchmark_close) / benchmark_base * 100.0, 6
                ),
                "open": _rounded_optional(getattr(row, "rebased_open", None)),
                "high": _rounded_optional(getattr(row, "rebased_high", None)),
                "low": _rounded_optional(getattr(row, "rebased_low", None)),
                "close": _rounded_optional(getattr(row, "rebased_close", None)),
                "volume": _rounded_optional(getattr(row, "volume", None)),
            }
            for row in aligned.itertuples(index=False)
        ]
        if points:
            output[str(ticker)] = points
    return output


def _build_breadth_history(
    reader: SnapshotReader,
    snapshot_id: str,
    current_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build history only from persisted absolute group observations.

    A transition's ``breadth_delta`` is a difference, not a level.  It cannot
    be converted into an absolute breadth value without the prior level, so
    transitions are deliberately not used as a history source here.
    """
    current_entries = (current_snapshot.get("manifest") or {}).get("entries") or []
    if not current_entries or not isinstance(current_entries[0], dict):
        return []
    current_entry = current_entries[0]
    current_as_of = _iso_date(current_entry.get("as_of"))
    if current_as_of is None:
        return []

    points: dict[tuple[str, str], dict[str, Any]] = {}
    for snapshot_path in reader.list_snapshots():
        if snapshot_path.name == snapshot_id:
            loaded = current_snapshot
        else:
            try:
                loaded = reader.load(snapshot_path.name)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue

        entries = (loaded.get("manifest") or {}).get("entries") or []
        if not entries or not isinstance(entries[0], dict):
            continue
        entry = entries[0]
        as_of = _iso_date(entry.get("as_of"))
        if as_of is None or as_of > current_as_of:
            continue
        if snapshot_path.name != snapshot_id:
            if as_of >= current_as_of:
                continue
            if not check_snapshot_compatibility(current_entry, entry).comparable:
                continue

        for row in _records(loaded.get("groups")):
            group_id = row.get("group_id")
            breadth = _finite_number(row.get("breadth_outperforming"))
            if not isinstance(group_id, str) or not group_id or breadth is None:
                continue
            if not 0 <= breadth <= 100:
                continue
            points[(group_id, as_of)] = {
                "group_id": group_id,
                "as_of": as_of,
                "breadth": breadth,
                "group_excess_return_20d": _finite_number(
                    row.get("group_excess_return_20d")
                ),
            }

    counts: dict[str, int] = {}
    for point in points.values():
        counts[point["group_id"]] = counts.get(point["group_id"], 0) + 1
    return sorted(
        (
            point
            for point in points.values()
            if counts.get(point["group_id"], 0) >= 2
        ),
        key=lambda point: (point["group_id"], point["as_of"]),
    )


def _build_rotation_history(
    reader: SnapshotReader,
    snapshot_id: str,
    current_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build real dated rotation axes from compatible persisted observations.

    Mirrors ``_build_breadth_history``: only contract-compatible snapshots at
    or before the current as-of contribute, and every emitted point carries
    the values the rotation contract actually uses -- YTD excess (relative
    strength) and 20D/60D excess (momentum). Points without a YTD excess are
    omitted rather than interpolated, so a trail can never be drawn through a
    value the pipeline did not compute.
    """
    current_entries = (current_snapshot.get("manifest") or {}).get("entries") or []
    if not current_entries or not isinstance(current_entries[0], dict):
        return []
    current_entry = current_entries[0]
    current_as_of = _iso_date(current_entry.get("as_of"))
    if current_as_of is None:
        return []

    points: dict[tuple[str, str], dict[str, Any]] = {}
    for snapshot_path in reader.list_snapshots():
        if snapshot_path.name == snapshot_id:
            loaded = current_snapshot
        else:
            try:
                loaded = reader.load(snapshot_path.name)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue

        entries = (loaded.get("manifest") or {}).get("entries") or []
        if not entries or not isinstance(entries[0], dict):
            continue
        entry = entries[0]
        as_of = _iso_date(entry.get("as_of"))
        if as_of is None or as_of > current_as_of:
            continue
        if snapshot_path.name != snapshot_id:
            if as_of >= current_as_of:
                continue
            if not check_snapshot_compatibility(current_entry, entry).comparable:
                continue

        for row in _records(loaded.get("groups")):
            group_id = row.get("group_id")
            if not isinstance(group_id, str) or not group_id:
                continue
            ytd = _finite_number(row.get("group_excess_return_ytd"))
            excess_20d = _finite_number(row.get("group_excess_return_20d"))
            excess_60d = _finite_number(row.get("group_excess_return_60d"))
            # The YTD axis is mandatory: a trail without it would plot a
            # position the rotation contract never computed.
            if ytd is None:
                continue
            momentum = (
                excess_20d - excess_60d
                if excess_20d is not None and excess_60d is not None
                else None
            )
            points[(group_id, as_of)] = {
                "group_id": group_id,
                "as_of": as_of,
                "group_excess_return_ytd": ytd,
                "ytd_start_date": row.get("ytd_start_date"),
                "group_excess_return_20d": excess_20d,
                "group_excess_return_60d": excess_60d,
                "relative_momentum": momentum,
            }

    counts: dict[str, int] = {}
    for point in points.values():
        counts[point["group_id"]] = counts.get(point["group_id"], 0) + 1
    return sorted(
        (
            point
            for point in points.values()
            if counts.get(point["group_id"], 0) >= 3
        ),
        key=lambda point: (point["group_id"], point["as_of"]),
    )


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _build_daily_rotation_history(
    reader: SnapshotReader,
    snapshot_id: str,
    current_snapshot: dict[str, Any],
    history_root: Path,
) -> dict[str, Any]:
    """Read a separate daily replay without changing the comparison baseline.

    Every benchmark session in the replay window must have complete, compatible
    group observations from the same panel. Missing days, stale inputs or a
    divergent endpoint refuse export before the served payload is touched.
    """
    provenance = _load_optional_json(reader.root / snapshot_id / "panel_provenance.json")
    panel_files = (provenance or {}).get("panel_files", {})
    if not isinstance(panel_files, dict) or not all(
        isinstance(panel_files.get(name), str) and len(panel_files[name]) == 64
        for name in ("prices.csv", "benchmark.csv")
    ):
        raise ValueError("daily rotation requires current snapshot panel provenance")
    entry = current_snapshot["manifest"]["entries"][0]
    as_of = _iso_date(entry.get("as_of"))
    if as_of is None or not history_root.is_dir():
        raise ValueError("daily rotation requires a dated snapshot and an existing history root")
    daily_reader = SnapshotReader(root=history_root)
    daily_snapshots: dict[str, str] = {}
    endpoint_groups = None
    for path in daily_reader.list_snapshots():
        loaded = daily_reader.load(path.name)
        entries = (loaded.get("manifest") or {}).get("entries") or []
        candidate = entries[0] if entries else {}
        session = _iso_date(candidate.get("as_of"))
        if session is None:
            raise ValueError(f"daily rotation snapshot {path.name} has no valid date")
        if session > as_of:
            continue
        if not loaded.get("complete") or not check_snapshot_compatibility(entry, candidate).comparable:
            raise ValueError(f"daily rotation snapshot {path.name} is incomplete or incomparable")
        source = _load_optional_json(path / "panel_provenance.json") or {}
        if source.get("panel_files") != panel_files:
            raise ValueError(f"daily rotation snapshot {path.name} has different panel provenance")
        if session in daily_snapshots:
            raise ValueError(f"daily rotation has duplicate session {session}")
        daily_snapshots[session] = path.name
        if session == as_of:
            endpoint_groups = loaded["groups"]

    if not daily_snapshots or endpoint_groups is None:
        raise ValueError("daily rotation must reach the current snapshot date")
    benchmark_dates = sorted({
        session for value in current_snapshot["benchmark"]["date"]
        if (session := _iso_date(value)) is not None
    })
    sessions = [session for session in benchmark_dates if min(daily_snapshots) <= session <= as_of]
    if len(sessions) < 3 or set(sessions) != set(daily_snapshots):
        raise ValueError("daily rotation must cover every benchmark session in its window")

    points = _build_rotation_history(daily_reader, snapshot_id, current_snapshot)
    axes = ("group_excess_return_ytd", "group_excess_return_20d", "group_excess_return_60d")
    current_groups = _records(current_snapshot["groups"])
    endpoint = {row["group_id"]: row for row in _records(endpoint_groups)}
    # Do not let a replay with different current prices/membership draw a trail
    # into a position that differs from the published current group row.
    for row in current_groups:
        other = endpoint.get(row["group_id"], {})
        if any(_finite_number(row.get(axis)) != _finite_number(other.get(axis)) for axis in axes):
            raise ValueError(f"daily rotation endpoint differs for {row['group_id']}")
    expected_groups = {
        row["group_id"] for row in current_groups
        if all(_finite_number(row.get(axis)) is not None for axis in axes)
    }
    expected = {(group, session) for group in expected_groups for session in sessions}
    actual = {
        (point["group_id"], point["as_of"]) for point in points
        if all(_finite_number(point.get(axis)) is not None for axis in axes)
    }
    if not expected or actual != expected:
        raise ValueError("daily rotation has missing group observations or return axes")
    return {
        "sessions": sessions,
        "points": points,
        "panel_files": panel_files,
        "snapshot_ids": [daily_snapshots[session] for session in sessions],
        "source": "COMPATIBLE_PUBLIC_SNAPSHOTS",
    }


def _load_yaml_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _taxonomy_memberships(path: Path) -> list[dict[str, Any]]:
    """Read explicit config memberships without inferring new relationships."""
    document = _load_yaml_optional(path)
    rows: list[dict[str, Any]] = []
    direct = document.get("memberships")
    if isinstance(direct, list):
        rows.extend(item for item in direct if isinstance(item, dict))
    nested = document.get("taxonomies")
    if isinstance(nested, list):
        for taxonomy in nested:
            if not isinstance(taxonomy, dict):
                continue
            memberships = taxonomy.get("memberships")
            if isinstance(memberships, list):
                rows.extend(item for item in memberships if isinstance(item, dict))
    return rows


def _membership_map(path: Path) -> dict[str, list[dict[str, Any]]]:
    mapped: dict[str, list[dict[str, Any]]] = {}
    for row in _taxonomy_memberships(path):
        ticker = str(row.get("ticker") or "").strip().upper()
        group_id = str(row.get("taxonomy_group_id") or "").strip()
        if not ticker or not group_id:
            continue
        mapped.setdefault(ticker, []).append(
            {
                "taxonomy_group_id": group_id,
                "taxonomy_group_name": str(row.get("taxonomy_group_name") or group_id),
                "confidence": _finite_number(row.get("confidence")) or 1.0,
                "source": str(row.get("source") or "config taxonomy membership"),
                "source_as_of": _iso_date(row.get("source_as_of")),
            }
        )
    return mapped


def _read_listed_universe_rows(snapshot_dir: Path) -> list[dict[str, Any]]:
    path = snapshot_dir / "listed_universe.csv"
    if not path.is_file():
        return []
    try:
        return _records(pd.read_csv(path))
    except (OSError, UnicodeError, ValueError, pd.errors.ParserError):
        return []


def _read_analysis_tickers(snapshot_dir: Path) -> set[str]:
    path = snapshot_dir / "universe.csv"
    if not path.exists():
        return set()
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError):
        return set()
    if "ticker" not in frame.columns:
        return set()
    return {
        str(value).strip().upper()
        for value in frame["ticker"].dropna().tolist()
        if str(value).strip()
    }


def _read_cached_full_listing(
    *,
    as_of: Any,
    minimum_rows: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reuse a prior validated live capture without spending provider credits."""
    cutoff = _iso_date(as_of)
    if not cutoff:
        return [], {}
    root = project_root() / "data" / "raw" / "sectors_validation"
    reports = sorted(root.glob(f"{cutoff}_*/validation_report.json"), reverse=True)
    for report_path in reports:
        report = _load_optional_json(report_path)
        if not report or report.get("status") not in {"PASS", "REVIEW_REQUIRED"}:
            continue
        taxonomy_check = report.get("checks", {}).get("taxonomy", {})
        if taxonomy_check.get("status") != "PASS":
            continue
        try:
            expected = int(taxonomy_check.get("structured_query_complete_rows") or taxonomy_check.get("rows") or 0)
        except (TypeError, ValueError):
            expected = 0
        if expected < minimum_rows:
            continue
        fixture_dir = report_path.parent / "sanitized_fixtures"
        rows: list[dict[str, Any]] = []
        for path in sorted(fixture_dir.glob("companies_taxonomy_page_*.json")):
            loaded = _load_optional_json(path) or {}
            for item in (loaded.get("payload", {}) if isinstance(loaded, dict) else {}).get("results", []):
                if not isinstance(item, dict):
                    continue
                query_values = item.get("query_values")
                if not isinstance(query_values, dict):
                    continue
                ticker = str(item.get("symbol") or "").strip().upper()
                if not ticker:
                    continue
                sector = query_values.get("sector")
                rows.append(
                    {
                        "ticker": ticker,
                        "company_name": item.get("company_name") or ticker,
                        "exchange": "IDX",
                        "sector": sector,
                        "subsector": query_values.get("sub_sector"),
                        "industry": query_values.get("industry"),
                        "subindustry": query_values.get("sub_industry"),
                        "group_id": sector,
                        "listing_board": query_values.get("listing_board"),
                        "active": True,
                        "common_equity_status": "UNVERIFIED_COMPANY_LISTING",
                        "source": "sectors_validation_fixture",
                        "source_as_of": cutoff,
                    }
                )
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            unique.setdefault(str(row["ticker"]), row)
        if len(unique) < expected or len(unique) < minimum_rows:
            continue
        relative_report = report_path.relative_to(project_root())
        return list(unique.values()), {
            "kind": "CACHED_VALIDATED_LIVE_CAPTURE",
            "validation_report": str(relative_report),
            "validation_status": report.get("status"),
            "taxonomy_rows": len(unique),
            "captured_at": report_path.parent.name.rsplit("_", 1)[-1],
            "provider_mode": report.get("provider_mode"),
        }
    return [], {}


def _build_listing_registry(
    *,
    snapshot_dir: Path,
    security_master: Any,
    coverage: Any,
    features: pd.DataFrame | None,
    manifest_entry: dict[str, Any],
) -> dict[str, Any]:
    """Expose one complete listing/taxonomy contract to the web UI.

    The registry distinguishes rows persisted by the snapshot from the
    provider's discovered count. A page-capped legacy bundle therefore
    remains visibly incomplete instead of being promoted to a full listing.
    """
    listed_rows = _read_listed_universe_rows(snapshot_dir)
    has_listing_sidecar = bool(listed_rows)
    if not listed_rows and isinstance(security_master, list):
        listed_rows = [row for row in security_master if isinstance(row, dict)]
    coverage_map = coverage if isinstance(coverage, dict) else {}
    try:
        discovered_target = int(coverage_map.get("discovered_count") or len(listed_rows))
    except (TypeError, ValueError):
        discovered_target = len(listed_rows)
    listing_source: dict[str, Any] = {
        "kind": "SNAPSHOT_SECURITY_MASTER",
        "provider_mode": manifest_entry.get("provider_mode"),
    }
    cached_rows, cached_source = _read_cached_full_listing(
        as_of=manifest_entry.get("as_of"),
        minimum_rows=max(1, discovered_target),
    )
    if cached_rows and len(listed_rows) < discovered_target:
        listed_rows = cached_rows
        listing_source = cached_source
    analysis_tickers = _read_analysis_tickers(snapshot_dir)
    feature_tickers: set[str] = set()
    if features is not None and not features.empty and "ticker" in features.columns:
        feature_tickers = {
            str(value).strip().upper()
            for value in features["ticker"].dropna().tolist()
            if str(value).strip()
        }

    konglo_map = _membership_map(project_root() / "config" / "konglo.yaml")
    theme_map = _membership_map(project_root() / "config" / "themes.yaml")
    by_ticker: dict[str, dict[str, Any]] = {}
    duplicate_tickers = 0
    records: list[dict[str, Any]] = []
    for raw in listed_rows:
        ticker = str(raw.get("ticker") or raw.get("symbol") or "").strip().upper()
        if not ticker:
            continue
        if ticker in by_ticker:
            duplicate_tickers += 1
            continue
        taxonomy = {
            key: raw.get(key)
            for key in ("sector", "subsector", "industry", "subindustry")
        }
        taxonomy_complete = all(
            value is not None and str(value).strip() not in {"", "nan", "None"}
            for value in taxonomy.values()
        )
        try:
            history_requested = int(coverage_map.get("history_requested_securities") or 0)
        except (TypeError, ValueError):
            history_requested = 0
        legacy_requested = (
            not has_listing_sidecar
            and not analysis_tickers
            and history_requested >= len(listed_rows)
            and len(listed_rows) > 0
        )
        analysis_requested = bool(
            raw.get("analysis_requested", legacy_requested or ticker in analysis_tickers or ticker in feature_tickers)
        )
        analysis_status = str(raw.get("analysis_status") or "").strip()
        if not analysis_status:
            analysis_status = (
                "OBSERVED_FEATURES"
                if ticker in feature_tickers
                else "REQUESTED_NO_FEATURES"
                if analysis_requested
                else "NOT_REQUESTED"
            )
        row = {
            "ticker": ticker,
            "company_name": raw.get("company_name") or ticker,
            "exchange": raw.get("exchange") or "IDX",
            "listing_board": raw.get("listing_board"),
            "listing_status": raw.get("listing_status"),
            "active": raw.get("active") is not False,
            "common_equity_status": raw.get("common_equity_status"),
            "market_cap": _finite_number(raw.get("market_cap")),
            "taxonomy": taxonomy,
            "taxonomy_status": "COMPLETE" if taxonomy_complete else "MISSING_CLASSIFICATION",
            "group_id": raw.get("group_id") or raw.get("sector"),
            "analysis_requested": analysis_requested,
            "analysis_status": analysis_status,
            "konglo_memberships": konglo_map.get(ticker, []),
            "theme_memberships": theme_map.get(ticker, []),
            "source": raw.get("source") or manifest_entry.get("provider"),
            "source_as_of": _iso_date(raw.get("source_as_of") or raw.get("last_trade_date")),
        }
        by_ticker[ticker] = row
        records.append(row)

    discovered_count = coverage_map.get("discovered_count")
    try:
        discovered = max(len(records), int(discovered_count))
    except (TypeError, ValueError):
        discovered = len(records)
    persisted_count = len(records)
    full_listing = (
        coverage_map.get("full_accessible_universe_listed") is True
        and persisted_count >= discovered
    ) or (
        listing_source.get("kind") == "CACHED_VALIDATED_LIVE_CAPTURE"
        and persisted_count >= discovered
    )
    taxonomy_complete_count = sum(row["taxonomy_status"] == "COMPLETE" for row in records)
    mapped_konglo = sum(bool(row["konglo_memberships"]) for row in records)
    mapped_themes = sum(bool(row["theme_memberships"]) for row in records)
    analysis_requested_count = sum(bool(row["analysis_requested"]) for row in records)
    return {
        "schema_version": "listing-registry-v1",
        "status": "READY" if full_listing else "PARTIAL",
        "provider_mode": manifest_entry.get("provider_mode"),
        "as_of": _iso_date(manifest_entry.get("as_of")),
        "scope_label": "Full accessible listing" if full_listing else "Persisted listing",
        "listing_source": listing_source,
        "full_accessible_universe_listed": full_listing,
        "discovered_count": discovered,
        "persisted_count": persisted_count,
        "listed_count": persisted_count,
        "duplicate_ticker_count": duplicate_tickers,
        "analysis_requested_count": analysis_requested_count,
        "observed_feature_count": len(feature_tickers),
        "taxonomy_complete_count": taxonomy_complete_count,
        "taxonomy_coverage_pct": round(taxonomy_complete_count / max(1, persisted_count) * 100.0, 2),
        "konglo_mapped_count": mapped_konglo,
        "theme_mapped_count": mapped_themes,
        "membership_sources": {
            "sector": "provider security master",
            "konglo": "config/konglo.yaml",
            "themes": "config/themes.yaml",
        },
        "integrity": {
            "unique_ticker_count": len(records),
            "duplicate_ticker_count": duplicate_tickers,
            "records_match_persisted_count": len(records) == persisted_count,
            "discovered_rows_without_persisted_record": max(0, discovered - persisted_count),
        },
        "records": records,
    }


def _enrich_with_taxonomy_views(
    payload: dict[str, Any],
    *,
    snapshot_id: str,
    manifest_entry: dict[str, Any],
) -> None:
    """Attach only taxonomy views built for this exact snapshot contract."""
    taxonomy_dir = (
        project_root() / "data" / "derived" / "taxonomy_views" / snapshot_id
    )
    snapshot_as_of = _iso_date(payload.get("as_of"))
    provider_mode = str(manifest_entry.get("provider_mode") or "")
    price_basis = str(manifest_entry.get("price_basis") or "")
    views: dict[str, Any] = {}
    if taxonomy_dir.exists():
        for view_path in sorted(taxonomy_dir.glob("*.json")):
            loaded = _load_optional_json(view_path)
            if not loaded or "taxonomy_id" not in loaded:
                continue
            contract_matches = (
                loaded.get("source_snapshot_id") == snapshot_id
                and _iso_date(loaded.get("as_of")) == snapshot_as_of
                and str(loaded.get("snapshot_provider_mode") or "")
                == provider_mode
                and str(loaded.get("source_snapshot_price_basis") or "")
                == price_basis
            )
            if contract_matches:
                views[str(loaded["taxonomy_id"])] = loaded

    sector_view = _build_sector_view_from_groups(
        payload.get("groups", []),
        snapshot_id=snapshot_id,
        manifest_entry=manifest_entry,
        as_of=snapshot_as_of,
        comparability=payload.get("comparability") or {},
    )
    if sector_view is not None:
        registry = payload.get("listing_registry")
        memberships: list[dict[str, Any]] = []
        if isinstance(registry, dict):
            for record in registry.get("records", []):
                if not isinstance(record, dict) or not record.get("group_id"):
                    continue
                group_id = str(record["group_id"])
                memberships.append(
                    {
                        "ticker": str(record.get("ticker") or ""),
                        "taxonomy_group_id": group_id,
                        "taxonomy_group_name": str(
                            (record.get("taxonomy") or {}).get("sector") or group_id
                        ),
                        "membership_type": "PRIMARY",
                        "confidence": 1.0,
                        "source": "provider security master",
                        "source_as_of": record.get("source_as_of"),
                    }
                )
        sector_view["memberships"] = memberships
        views["sector"] = sector_view
    payload["taxonomy_views"] = views


def _build_sector_view_from_groups(
    groups: list[dict[str, Any]],
    *,
    snapshot_id: str,
    manifest_entry: dict[str, Any],
    as_of: str | None,
    comparability: dict[str, Any],
) -> dict[str, Any] | None:
    if not groups:
        return None
    provider_mode = str(manifest_entry.get("provider_mode") or "UNAVAILABLE")
    is_sectors = provider_mode == "SECTORS_LIVE"
    aggregate: list[dict[str, Any]] = []
    for row in groups:
        constituent_count = int(row.get("constituent_count") or 0)
        eligible_count = int(row.get("eligible_count") or 0)
        coverage_pct = _finite_number(row.get("coverage_pct"))
        if coverage_pct is None:
            coverage_pct = (
                100.0 * eligible_count / constituent_count
                if constituent_count
                else 0.0
            )
        breadth = _finite_number(row.get("breadth_outperforming"))
        breadth_delta = _finite_number(row.get("breadth_delta"))
        excess_20d = _finite_number(row.get("group_excess_return_20d"))
        excess_60d = _finite_number(row.get("group_excess_return_60d"))
        group_ytd = _finite_number(row.get("group_return_ytd"))
        excess_ytd = _finite_number(row.get("group_excess_return_ytd"))
        benchmark_ytd = _finite_number(row.get("benchmark_return_ytd"))
        ytd_start_date = _iso_date(row.get("ytd_start_date"))
        leadership = str(row.get("leadership_state") or "UNCONFIRMED")
        diffusion = str(row.get("diffusion_state") or "UNCONFIRMED")
        if breadth is None or excess_20d is None:
            data_quality = "DATA_GAP"
        elif (
            coverage_pct < 100.0
            or leadership == "UNCONFIRMED"
            or diffusion == "UNCONFIRMED"
        ):
            data_quality = "READY_WITH_GAPS"
        else:
            data_quality = "READY"
        top3 = _finite_number(row.get("top3_contribution_share"))
        aggregate.append(
            {
                "taxonomy_group_id": str(row.get("group_id") or ""),
                "taxonomy_group_name": str(row.get("group_name") or row.get("group_id") or ""),
                "constituent_count": constituent_count,
                "eligible_constituent_count": eligible_count,
                "coverage_pct": round(coverage_pct, 2),
                "equal_weight_return_20d": _finite_number(
                    row.get("group_return_equal_weight")
                ),
                "equal_weight_return_60d": None,
                "equal_weight_return_ytd": group_ytd,
                "excess_return_20d": excess_20d,
                "excess_return_60d": excess_60d,
                "excess_return_ytd": excess_ytd,
                "benchmark_return_20d": None,
                "benchmark_return_60d": None,
                "benchmark_return_ytd": benchmark_ytd,
                "ytd_start_date": ytd_start_date,
                "ytd_eligible_constituent_count": int(
                    row.get("ytd_eligible_count") or 0
                ),
                "breadth_outperforming": breadth,
                "prev_breadth_outperforming": (
                    breadth - breadth_delta
                    if breadth is not None and breadth_delta is not None
                    else None
                ),
                "breadth_delta": breadth_delta,
                "leadership_state": leadership,
                "diffusion_state": diffusion,
                "concentration_top3": top3 * 100.0 if top3 is not None else None,
                "map_x": excess_20d,
                "map_y": breadth,
                "off_scale": bool(
                    excess_20d is not None
                    and (excess_20d < -15.0 or excess_20d > 15.0)
                ),
                "data_quality": data_quality,
                "prototype": not is_sectors,
                "membership_kind_breakdown": {},
                "sample_foreign_flow_idr": None,
                "sample_foreign_flow_direction": None,
            }
        )
    return {
        "schema_version": "taxonomy-view-v1",
        "taxonomy_id": "sector",
        "taxonomy_name": (
            "Sector (Sectors persisted snapshot)"
            if is_sectors
            else "Sector (public prototype snapshot)"
        ),
        "taxonomy_version": str(
            manifest_entry.get("taxonomy_version") or "UNAVAILABLE"
        ),
        "taxonomy_kind": "SECTOR",
        "source_kind": "THIRD_PARTY" if is_sectors else "PROTOTYPE_CONFIG",
        "source_as_of": as_of,
        "membership_policy": "PRIMARY_ONLY",
        "provider_mode": provider_mode,
        "snapshot_provider_mode": provider_mode,
        "taxonomy_definition_provider_mode": provider_mode,
        "source_snapshot_id": snapshot_id,
        "source_snapshot_price_basis": manifest_entry.get("price_basis"),
        "previous_snapshot_id": comparability.get("selected_previous"),
        "comparability": comparability,
        "point_in_time_eligible": True,
        "benchmark_id": "^JKSE",
        "as_of": as_of,
        "calculation": {
            "source": "PERSISTED_GROUP_SNAPSHOT",
            "front_end_recompute": False,
        },
        "calculation_coverage": {
            "group_count": len(aggregate),
            "plottable_group_count": sum(
                row["map_x"] is not None and row["map_y"] is not None
                for row in aggregate
            ),
            "eligible_constituent_count": sum(
                row["eligible_constituent_count"] for row in aggregate
            ),
            "constituent_count": sum(row["constituent_count"] for row in aggregate),
        },
        "groups": aggregate,
    }


def _enrich_with_foreign_flow(
    payload: dict[str, Any], *, manifest_entry: dict[str, Any]
) -> None:
    """Attach bounded flow context only when its full window is known."""
    project = project_root()
    foreign_path = project / "data" / "derived" / "foreign_flow_sample.json"
    loaded = _load_optional_json(foreign_path)
    snapshot_as_of = _iso_date(payload.get("as_of"))
    source_max = _iso_date((loaded or {}).get("as_of", {}).get("max"))
    if loaded is None or snapshot_as_of is None or source_max is None or source_max > snapshot_as_of:
        payload["foreign_flow_sample"] = {
            "schema_version": "foreign-flow-sample-v2",
            "status": "UNAVAILABLE",
            "provider_mode": "PUBLIC_PROTOTYPE",
            "quantitative_use": False,
            "market_observations": [],
            "company_observations": [],
            "daily_market_totals": [],
            "daily_company_samples": [],
            "group_summaries": [],
            "breadth_observed": {
                "market_positive_day_count": 0,
                "market_negative_day_count": 0,
                "sample_positive_day_count": 0,
                "sample_negative_day_count": 0,
                "last_sample_direction": "UNCONFIRMED",
                "last_market_direction": "UNCONFIRMED",
                "market_sample_aligned": False,
            },
            "signal_eligibility": {
                "signal_eligible": False,
                "coverage_gate_met": False,
            },
            "context_compatibility": {
                "role": "DESCRIPTIVE_CONTEXT_ONLY",
                "snapshot_as_of": snapshot_as_of,
                "reason": "complete source window is later than this snapshot",
            },
        }
        return
    scoped = copy.deepcopy(loaded)
    signal = scoped.setdefault("signal_eligibility", {})
    signal["full_universe_coverage_met"] = False
    signal["coverage_gate_met"] = False
    signal["signal_eligible"] = False
    source_mode = str(scoped.get("provider_mode") or "PUBLIC_PROTOTYPE")
    snapshot_mode = str(manifest_entry.get("provider_mode") or "UNAVAILABLE")
    scoped["context_compatibility"] = {
        "role": "DESCRIPTIVE_CONTEXT_ONLY",
        "snapshot_as_of": snapshot_as_of,
        "snapshot_provider_mode": snapshot_mode,
        "source_provider_mode": source_mode,
        "cross_provider_context": source_mode != snapshot_mode,
        "used_in_leadership_or_diffusion": False,
    }
    payload["foreign_flow_sample"] = scoped


def _enrich_with_official_market_context(
    payload: dict[str, Any], *, manifest_entry: dict[str, Any]
) -> None:
    """Attach the bounded LlamaCloud/OJK market context at its time cutoff."""
    path = project_root() / "data" / "derived" / "official_market_context.json"
    loaded = _load_optional_json(path)
    snapshot_as_of = _iso_date(payload.get("as_of"))
    period_end = _iso_date((loaded or {}).get("period_end"))
    if loaded is None or snapshot_as_of is None or period_end is None or period_end > snapshot_as_of:
        payload["official_market_context"] = None
        return
    scoped = copy.deepcopy(loaded)
    compatibility = scoped.setdefault("context_compatibility", {})
    compatibility.update(
        {
            "role": "DESCRIPTIVE_MARKET_CONTEXT",
            "snapshot_as_of": snapshot_as_of,
            "snapshot_provider_mode": manifest_entry.get("provider_mode"),
            "used_in_leadership_or_diffusion": False,
            "publication_cutoff_enforced": True,
        }
    )
    payload["official_market_context"] = scoped


def _enrich_with_research_events(
    payload: dict[str, Any], *, manifest_entry: dict[str, Any]
) -> None:
    """Attach only events published by the snapshot's as-of cutoff."""
    project = project_root()
    events_path = project / "data" / "derived" / "research_events.json"
    loaded = _load_optional_json(events_path)
    if loaded is None:
        payload["research_events"] = {
            "schema_version": "research-events-v1",
            "provider_mode": "PUBLIC_PROTOTYPE",
            "events": [],
            "sources": [],
        }
        return
    snapshot_as_of = _iso_date(payload.get("as_of"))
    scoped = copy.deepcopy(loaded)
    events = [
        event
        for event in scoped.get("events", [])
        if isinstance(event, dict)
        and snapshot_as_of is not None
        and _iso_date(event.get("published_at")) is not None
        and _iso_date(event.get("published_at")) <= snapshot_as_of
    ]
    source_urls = {event.get("source_url") for event in events}
    scoped["events"] = events
    scoped["event_count"] = len(events)
    scoped["sources"] = [
        source
        for source in scoped.get("sources", [])
        if isinstance(source, dict) and source.get("source_url") in source_urls
    ]
    scoped["as_of"] = snapshot_as_of
    scoped["context_compatibility"] = {
        "role": "DESCRIPTIVE_CONTEXT_ONLY",
        "snapshot_provider_mode": manifest_entry.get("provider_mode"),
        "used_in_leadership_or_diffusion": False,
        "publication_cutoff_enforced": True,
    }
    payload["research_events"] = scoped


def export(
    snapshot_id: str,
    out_path: Path,
    *,
    snapshot_root: Path | None = None,
    rotation_history_root: Path | None = None,
) -> dict[str, Any]:
    validate_snapshot_id(snapshot_id)
    reader = SnapshotReader(root=snapshot_root)
    snap = reader.load(snapshot_id)
    manifest_entries = (snap.get("manifest") or {}).get("entries") or []
    entry = manifest_entries[0] if manifest_entries else {}
    as_of = entry.get("as_of")
    # The pipeline only selects a previous snapshot when provider mode,
    # methodology versions, and chronology are compatible. Mirror that
    # decision here instead of treating the directory's previous entry as a
    # valid transition baseline.
    previous_id = (snap.get("comparability") or {}).get("selected_previous")

    payload: dict[str, Any] = {
        "schema_version": "web-snapshot-v1",
        "snapshot_id": snapshot_id,
        "as_of": as_of,
        "previous_snapshot_id": previous_id,
        "manifest": snap.get("manifest"),
        "quality": snap.get("quality"),
        "coverage": snap.get("coverage"),
        "data_warnings": snap.get("data_warnings"),
        "provider_provenance": snap.get("provider_provenance"),
        "methodology_sensitivity": snap.get("methodology_sensitivity"),
        "tavily_context": snap.get("tavily_context"),
        "you_context": snap.get("you_context"),
        "api_credit_audit": _sanitize_audit(snap.get("api_credit_audit")),
        "security_master_diagnostics": snap.get("security_master_diagnostics"),
        "history_diagnostics": snap.get("history_diagnostics"),
        "endpoints": snap.get("endpoints"),
        "comparability": snap.get("comparability"),
        "groups": _records(snap["groups"]),
        "transitions": _records(snap["transitions"]),
        "features": _records(snap["features"]),
        "constituents": [],  # snapshot writer does not yet emit per-group constituents
        "group_price_history": _build_group_price_history(
            snap.get("prices"),
            snap.get("benchmark"),
            snap.get("security_master"),
            entry,
        ),
        "ticker_price_history": _build_ticker_price_history(
            snap.get("prices"),
            snap.get("benchmark"),
            entry,
            {
                str(ticker).upper()
                for ticker in (
                    snap.get("features", pd.DataFrame()).get("ticker", pd.Series())
                ).dropna()
            },
        ),
        "breadth_history": _build_breadth_history(reader, snapshot_id, snap),
        "rotation_history": _build_rotation_history(reader, snapshot_id, snap),
        "security_master": snap.get("security_master"),
        "listing_registry": _build_listing_registry(
            snapshot_dir=reader.root / snapshot_id,
            security_master=snap.get("security_master"),
            coverage=snap.get("coverage"),
            features=snap.get("features"),
            manifest_entry=entry,
        ),
        "change_digest": snap.get("change_digest"),
        "evidence": snap.get("evidence"),
        "complete": snap.get("complete"),
    }
    if rotation_history_root is not None:
        payload["rotation_daily_history"] = _build_daily_rotation_history(
            reader, snapshot_id, snap, rotation_history_root
        )
    _enrich_with_taxonomy_views(
        payload,
        snapshot_id=snapshot_id,
        manifest_entry=entry,
    )
    _enrich_with_foreign_flow(payload, manifest_entry=entry)
    _enrich_with_official_market_context(payload, manifest_entry=entry)
    _enrich_with_research_events(payload, manifest_entry=entry)
    payload = _normalize_first_party_idx_urls(payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        out_path,
        json.dumps(payload, indent=2, default=str),
    )
    return {
        "snapshot_id": snapshot_id,
        "out_path": str(out_path),
        "groups": len(payload["groups"]),
        "transitions": len(payload["transitions"]),
        "features": len(payload["features"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="export_snapshot_json")
    parser.add_argument("--snapshot-id", default=None, help="Snapshot id (e.g. snap_2026-08-20).")
    parser.add_argument("--latest", action="store_true", help="Use the latest snapshot.")
    parser.add_argument("--out", default=None, help="Override output path.")
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing --out outside app/web/public/snapshots/.",
    )
    parser.add_argument(
        "--snapshot-root",
        default=None,
        help="Read snapshots from an alternate root (useful for isolated harnesses).",
    )
    parser.add_argument(
        "--rotation-history-root",
        default=None,
        help="Separate daily replay root; complete sessions and matching panel provenance required.",
    )
    args = parser.parse_args()

    if not args.snapshot_id and not args.latest:
        args.latest = True
    reader = SnapshotReader(root=Path(args.snapshot_root) if args.snapshot_root else None)
    if args.latest:
        snaps = sorted(
            reader.list_snapshots(),
            key=lambda path: (_snapshot_as_of(reader, path), path.name),
        )
        if not snaps:
            print("no snapshots found", file=__import__("sys").stderr)
            return 1
        sid = snaps[-1].name
    else:
        sid = args.snapshot_id
    out_path = Path(args.out) if args.out else PUBLIC_DIR / f"{sid}.json"
    if args.out and not args.allow_outside_root:
        try:
            out_path.resolve().relative_to(PUBLIC_DIR.resolve())
        except ValueError:
            print(
                f"refusing --out outside {PUBLIC_DIR} without --allow-outside-root",
                file=__import__("sys").stderr,
            )
            return 2
    try:
        info = export(
            sid,
            out_path,
            snapshot_root=Path(args.snapshot_root) if args.snapshot_root else None,
            rotation_history_root=Path(args.rotation_history_root) if args.rotation_history_root else None,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"export refused: {exc}", file=__import__("sys").stderr)
        return 2
    print(json.dumps(info, indent=2))
    return 0


def _snapshot_as_of(reader: SnapshotReader, snapshot_dir: Path) -> str:
    """Return the snapshot's calendar date for chronological selection."""
    manifest_path = snapshot_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
        if manifest:
            entries = manifest.get("entries") or []
            entry = entries[0] if entries else {}
            as_of = str(entry.get("as_of") or entry.get("snapshot_date") or "")
            if as_of:
                return as_of
    # Fall back to the directory mtime for legacy harnesses that do not
    # ship a manifest (e.g. yfinance_harness replay).
    try:
        return snapshot_dir.stat().st_mtime.__format__.replace(".", "")
    except OSError:
        return ""


def _atomic_write_text(path: Path, value: str) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(value)
            tmp.flush()
            os.fsync(tmp.fileno())
        Path(tmp_name).replace(path)
    finally:
        try:
            Path(tmp_name).unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
