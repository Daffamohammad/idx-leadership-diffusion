"""Calculate a bounded, source-backed foreign-flow sample.

This script reads a CSV of normalised foreign-flow observations and emits
a single JSON envelope used by the web frontend. The CSV format requires
columns:

    as_of,scope,ticker,market_scope,net_value_idr,buy_value_idr,
    sell_value_idr,source_url,source_published_at,source_kind,
    source_name,source_locator,quantitative_use

``scope`` is either ``market`` (one observation per day+market_scope)
or ``company`` (top-buy / top-sell list rows). The calculator refuses to
treat a top-list company row as a market-wide observation.

The emitted envelope separates:

* ``MARKET_TOTAL`` — observed market-wide net flow (one row per
  as_of+market_scope).
* ``TOP_LIST_SAMPLE`` — company rows from the published top lists.
* ``GROUP_SAMPLE`` — sample flow aggregated by sector group, only when
  the ticker maps to a known sector.

Synthetic test fixtures are exported under the ``SYNTHETIC_TEST_ONLY``
label and never reach the public web payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

SCHEMA_VERSION = "foreign-flow-sample-v2"
ROUNDING_TOLERANCE_IDR = 10_000_000_000
DEFAULT_INPUT = Path("data/fixtures/foreign_flow_sample.csv")
DEFAULT_SECURITY_MASTER = Path("config/universe.yaml")
DEFAULT_OUTPUT = Path("data/derived/foreign_flow_sample.json")

REQUIRED_COLUMNS = (
    "as_of",
    "scope",
    "ticker",
    "market_scope",
    "net_value_idr",
    "buy_value_idr",
    "sell_value_idr",
    "source_url",
    "source_published_at",
    "source_kind",
    "source_name",
    "source_locator",
    "quantitative_use",
)
NUMERIC_COLUMNS = ("net_value_idr", "buy_value_idr", "sell_value_idr")
ALLOWED_SCOPES = {"market", "company", "synthetic_test_only"}
ALLOWED_MARKET_SCOPES = {"regular", "reported_market", "negotiated"}


class ForeignFlowInputError(ValueError):
    """Raised when the normalized sample violates its contract."""


@dataclass
class ForeignFlowSchema:
    schema_version: str
    provider_mode: str
    status: str
    as_of: dict[str, str]
    coverage: dict[str, Any]
    market_observations: list[dict[str, Any]]
    company_observations: list[dict[str, Any]]
    daily_market_totals: list[dict[str, Any]]
    daily_company_samples: list[dict[str, Any]]
    group_summaries: list[dict[str, Any]]
    rolling_sample_flow: list[dict[str, Any]]
    breadth_observed: dict[str, Any]
    signal_eligibility: dict[str, Any]
    synthetic_test_only: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    source_discovery: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


def _normalise_ticker(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    return text if text.endswith(".JK") else f"{text}.JK"


def _parse_bool(value: Any, *, column: str, row_number: int) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no", ""}:
        return False
    raise ForeignFlowInputError(
        f"row {row_number}: column {column!r} must be a boolean, got {value!r}"
    )


def _normalise_integer_column(frame: pd.DataFrame, column: str) -> None:
    """Coerce a numeric column to ``Float64`` (nullable).

    Empty / NA cells are accepted (they become ``<NA>`` and surface as
    ``null`` in JSON). Non-numeric text is still rejected so the data
    contract is preserved.
    """
    raw = frame[column].astype("string").str.strip()
    raw = raw.replace({"": pd.NA, "<NA>": pd.NA, "nan": pd.NA})
    parsed = pd.to_numeric(raw, errors="coerce")
    bad_mask = raw.notna() & parsed.isna()
    if bad_mask.any():
        first = int(bad_mask[bad_mask].index[0]) + 2
        raise ForeignFlowInputError(
            f"row {first}: column {column!r} has non-numeric value"
        )
    frame[column] = parsed.astype("Float64")


def _normalise_input(path: Path) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError) as exc:
        raise ForeignFlowInputError(f"could not read input CSV: {exc}") from exc
    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    if missing:
        raise ForeignFlowInputError(
            f"input CSV missing required columns: {', '.join(missing)}"
        )
    for col in REQUIRED_COLUMNS:
        if col == "as_of":
            parsed = pd.to_datetime(frame["as_of"], errors="coerce")
            if parsed.isna().any():
                bad = parsed[parsed.isna()].index.tolist()
                first = bad[0] + 2 if bad else None
                raise ForeignFlowInputError(
                    f"row {first}: as_of must be ISO date"
                )
            frame["as_of"] = parsed.dt.strftime("%Y-%m-%d")
        elif col in NUMERIC_COLUMNS:
            _normalise_integer_column(frame, col)
        elif col in {"scope", "market_scope"}:
            frame[col] = frame[col].astype("string").str.strip().str.lower()
        elif col == "ticker":
            frame["ticker"] = frame["ticker"].astype("string").str.strip().str.upper()
        else:
            frame[col] = frame[col].astype("string").str.strip()

    bad_scope = frame[~frame["scope"].isin(ALLOWED_SCOPES)]
    if not bad_scope.empty:
        raise ForeignFlowInputError(
            f"row {int(bad_scope.index[0]) + 2}: scope must be one of {sorted(ALLOWED_SCOPES)}"
        )
    bad_market = frame[~frame["market_scope"].isin(ALLOWED_MARKET_SCOPES)]
    if not bad_market.empty:
        raise ForeignFlowInputError(
            f"row {int(bad_market.index[0]) + 2}: market_scope must be one of {sorted(ALLOWED_MARKET_SCOPES)}"
        )
    frame["quantitative_use"] = [
        _parse_bool(value, column="quantitative_use", row_number=int(idx) + 2)
        for idx, value in frame["quantitative_use"].items()
    ]
    frame["ticker"] = [
        _normalise_ticker(t) if scope == "company" else None
        for t, scope in zip(frame["ticker"], frame["scope"])
    ]
    duplicate_key = ["as_of", "scope", "ticker", "market_scope", "source_url"]
    if bool(frame.duplicated(duplicate_key).any()):
        row_number = int(frame.index[frame.duplicated(duplicate_key)][0]) + 2
        raise ForeignFlowInputError(f"row {row_number}: duplicate source observation")
    market = frame[frame["scope"].isin({"market", "synthetic_test_only"})]
    if bool(market.duplicated(["as_of", "market_scope"]).any()):
        raise ForeignFlowInputError(
            "at most one market observation is allowed per as_of and market_scope; "
            "add a source reconciliation step before combining reports"
        )
    company = frame[frame["scope"] == "company"]
    if (company["ticker"].isna()).any():
        bad = company[company["ticker"].isna()].index
        raise ForeignFlowInputError(
            f"row {int(bad[0]) + 2}: company rows require a ticker"
        )
    # Company rows are top-list samples; they must remain net-only. Buy/sell
    # components would imply component-level inference we explicitly forbid.
    bad_components = company[
        company["buy_value_idr"].notna() | company["sell_value_idr"].notna()
    ]
    if not bad_components.empty:
        row_number = int(bad_components.index[0]) + 2
        raise ForeignFlowInputError(
            f"row {row_number}: company sample rows must remain net-only"
        )
    return frame


def _load_security_master(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml

            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ForeignFlowInputError(
                f"could not read prototype universe {path}: {exc}"
            ) from exc
        rows = payload.get("universe", []) if isinstance(payload, Mapping) else []
        mapping: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            ticker = _normalise_ticker(row.get("ticker"))
            group_id = str(row.get("sectors") or row.get("group_id") or "").strip()
            if ticker and group_id and ticker not in mapping:
                mapping[ticker] = group_id
        return mapping
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForeignFlowInputError(f"could not read security master {path}: {exc}") from exc
    rows: Any = payload
    if isinstance(payload, Mapping):
        rows = payload.get("security_master", [])
    if not isinstance(rows, list):
        raise ForeignFlowInputError("security master must be a JSON array or payload block")
    mapping: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = _normalise_ticker(row.get("ticker"))
        group_id = str(row.get("group_id") or "").strip()
        if ticker and group_id and ticker not in mapping:
            mapping[ticker] = group_id
    return mapping


def _as_int(value: Any) -> int | None:
    if value is None or value is pd.NA or pd.isna(value):
        return None
    return int(value)


def _as_optional_text(value: Any) -> str | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value)
    return text or None


def _direction(value: int | None) -> str:
    if value is None:
        return "UNCONFIRMED"
    if value > 0:
        return "NET_BUY"
    if value < 0:
        return "NET_SELL"
    return "FLAT"


def _reconciliation(row: pd.Series) -> tuple[str, int | None]:
    if row["scope"] not in {"market", "synthetic_test_only"}:
        return "NET_REPORTED_ONLY", None
    buy = _as_int(row["buy_value_idr"])
    sell = _as_int(row["sell_value_idr"])
    net = _as_int(row["net_value_idr"])
    if buy is None or sell is None or net is None:
        return "NET_REPORTED_ONLY", None
    delta = net - (buy - sell)
    if delta == 0:
        return "RECONCILED", delta
    if abs(delta) <= ROUNDING_TOLERANCE_IDR:
        return "ROUNDING_VARIANCE", delta
    return "INCONSISTENT", delta


def _row_output(
    row: pd.Series,
    *,
    taxonomy_version: str = "prototype-v1",
) -> dict[str, Any]:
    status, delta = _reconciliation(row)
    return {
        "as_of": str(row["as_of"]),
        "scope": str(row["scope"]),
        "ticker": _as_optional_text(row.get("ticker")),
        "group_id": _as_optional_text(row.get("group_id")),
        "taxonomy_version": taxonomy_version,
        "mapping_status": _as_optional_text(row.get("mapping_status")) or "NOT_APPLICABLE",
        "market_scope": str(row["market_scope"]),
        "net_value_idr": _as_int(row["net_value_idr"]),
        "buy_value_idr": _as_int(row["buy_value_idr"]),
        "sell_value_idr": _as_int(row["sell_value_idr"]),
        "direction": _direction(_as_int(row["net_value_idr"])),
        "reconciliation_status": status,
        "reconciliation_delta_idr": delta,
        "source_url": str(row["source_url"]),
        "source_published_at": str(row["source_published_at"]),
        "source_kind": str(row["source_kind"]),
        "source_name": str(row["source_name"]),
        "source_locator": str(row["source_locator"]),
        "quantitative_use": bool(row["quantitative_use"]),
    }


def _source_provenance(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for url, source in frame.groupby("source_url", sort=True):
        first = source.iloc[0]
        rows.append(
            {
                "source_url": str(url),
                "source_name": str(first["source_name"]),
                "source_kind": str(first["source_kind"]),
                "source_published_at": str(first["source_published_at"]),
                "source_locators": sorted(source["source_locator"].unique().tolist()),
                "observed_rows": int(len(source)),
                "quantitative_use": True,
                "numeric_role": "reported_net_and_market_components",
            }
        )
    return rows


def _group_summaries(
    company: pd.DataFrame, taxonomy_version: str = "prototype-v1"
) -> list[dict[str, Any]]:
    mapped = company[company["group_id"].notna()].copy()
    if mapped.empty:
        return []
    grouped = (
        mapped.groupby(["as_of", "group_id"], sort=True, as_index=False)
        .agg(
            net_value_idr=("net_value_idr", "sum"),
            observed_company_count=("ticker", "nunique"),
            positive_company_count=(
                "net_value_idr",
                lambda values: int((values > 0).sum()),
            ),
            negative_company_count=(
                "net_value_idr",
                lambda values: int((values < 0).sum()),
            ),
        )
    )
    output: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        net = int(row["net_value_idr"])
        output.append(
            {
                "as_of": str(row["as_of"]),
                "group_id": str(row["group_id"]),
                "taxonomy_version": taxonomy_version,
                "net_value_idr": net,
                "direction": _direction(net),
                "observed_company_count": int(row["observed_company_count"]),
                "positive_company_count": int(row["positive_company_count"]),
                "negative_company_count": int(row["negative_company_count"]),
                "mapping_status": "MAPPED_SAMPLE_ONLY",
                "scope": "GROUP_SAMPLE",
            }
        )
    return output


def _daily_company_sample(
    company: pd.DataFrame, taxonomy_version: str = "prototype-v1"
) -> list[dict[str, Any]]:
    if company.empty:
        return []
    grouped = (
        company.groupby("as_of", sort=True, as_index=False)
        .agg(
            sample_net_value_idr=("net_value_idr", "sum"),
            observed_company_count=("ticker", "nunique"),
            mapped_company_count=("group_id", lambda values: int(values.notna().sum())),
            positive_company_count=(
                "net_value_idr",
                lambda values: int((values > 0).sum()),
            ),
            negative_company_count=(
                "net_value_idr",
                lambda values: int((values < 0).sum()),
            ),
        )
    )
    output: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        net = int(row["sample_net_value_idr"])
        output.append(
            {
                "as_of": str(row["as_of"]),
                "scope": "TOP_LIST_SAMPLE",
                "taxonomy_version": taxonomy_version,
                "sample_net_value_idr": net,
                "direction": _direction(net),
                "observed_company_count": int(row["observed_company_count"]),
                "mapped_company_count": int(row["mapped_company_count"]),
                "positive_company_count": int(row["positive_company_count"]),
                "negative_company_count": int(row["negative_company_count"]),
                "coverage_scope": "top-list-sample_not_full_market",
            }
        )
    return output


def _daily_market_totals(market: pd.DataFrame, taxonomy_version: str) -> list[dict[str, Any]]:
    if market.empty:
        return []
    grouped = (
        market.groupby("as_of", sort=True, as_index=False)
        .agg(net_value_idr=("net_value_idr", "sum"))
    )
    output: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        net = int(row["net_value_idr"])
        output.append(
            {
                "as_of": str(row["as_of"]),
                "scope": "MARKET_TOTAL",
                "taxonomy_version": taxonomy_version,
                "net_value_idr": net,
                "direction": _direction(net),
                "coverage_scope": "reported_market_total_only",
            }
        )
    return output


def _rolling_sample_flow(daily_samples: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Compute the rolling sum of sample flow across the most-recent three dates."""
    rolling: list[dict[str, Any]] = []
    values = sorted(
        (entry for entry in daily_samples if entry.get("sample_net_value_idr") is not None),
        key=lambda entry: entry["as_of"],
    )
    for index in range(len(values)):
        window = values[max(0, index - 2) : index + 1]
        net = sum(int(item["sample_net_value_idr"]) for item in window)
        rolling.append(
            {
                "as_of": values[index]["as_of"],
                "rolling_3d_sample_net_value_idr": net,
                "window_size": len(window),
                "direction": _direction(net),
            }
        )
    return rolling


def _breadth_observed(
    daily_samples: Sequence[Mapping[str, Any]],
    market_totals: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Observed breadth: positive vs negative sample days and market vs sample divergence."""
    sample_positive = sum(
        1 for entry in daily_samples if (entry.get("sample_net_value_idr") or 0) > 0
    )
    sample_negative = sum(
        1 for entry in daily_samples if (entry.get("sample_net_value_idr") or 0) < 0
    )
    market_positive = sum(1 for entry in market_totals if (entry.get("net_value_idr") or 0) > 0)
    market_negative = sum(1 for entry in market_totals if (entry.get("net_value_idr") or 0) < 0)
    last_sample = daily_samples[-1] if daily_samples else None
    last_market = market_totals[-1] if market_totals else None
    sample_direction = last_sample["direction"] if last_sample else "UNCONFIRMED"
    market_direction = last_market["direction"] if last_market else "UNCONFIRMED"
    return {
        "sample_positive_day_count": sample_positive,
        "sample_negative_day_count": sample_negative,
        "market_positive_day_count": market_positive,
        "market_negative_day_count": market_negative,
        "last_sample_direction": sample_direction,
        "last_market_direction": market_direction,
        "market_sample_aligned": sample_direction == market_direction
        and sample_direction in {"NET_BUY", "NET_SELL"},
    }


def _signal_eligibility(
    frame: pd.DataFrame,
    market_count: int,
    company_count: int,
    mapped_pct: float,
    breadth: Mapping[str, Any],
    missing_dates: Sequence[str],
    stale_dates: Sequence[str],
) -> dict[str, Any]:
    """Compute the explicit signal eligibility gate.

    Published top-buy/top-sell lists are intentionally bounded samples. They
    can pass data-volume and mapping diagnostics but can never satisfy the
    full-universe feed requirement needed for a confirmation signal.
    """
    market_days = frame.loc[frame["scope"] == "market", "as_of"].nunique()
    sample_diagnostics_met = (
        market_days >= 5
        and company_count >= 30
        and mapped_pct >= 80.0
    )
    full_universe_coverage_met = False
    coverage_met = sample_diagnostics_met and full_universe_coverage_met
    return {
        "market_day_count": int(market_days),
        "company_observation_count": int(company_count),
        "mapped_company_observation_pct": mapped_pct,
        "market_days_meets_threshold": market_days >= 5,
        "company_rows_meets_threshold": company_count >= 30,
        "mapped_pct_meets_threshold": mapped_pct >= 80.0,
        "sample_diagnostics_met": sample_diagnostics_met,
        "full_universe_coverage_met": full_universe_coverage_met,
        "coverage_gate_met": coverage_met,
        "missing_dates": list(missing_dates),
        "stale_dates": list(stale_dates),
        "regime_diversity": (
            breadth.get("market_positive_day_count", 0) >= 1
            and breadth.get("market_negative_day_count", 0) >= 1
        ),
        "signal_eligible": coverage_met,
    }


def calculate_foreign_flow_sample(
    input_path: Path,
    *,
    security_master_path: Path | None = DEFAULT_SECURITY_MASTER,
    taxonomy_version: str = "prototype-v1",
    expected_dates: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return a validated, deterministic calculation envelope."""
    frame = _normalise_input(input_path)
    group_mapping = _load_security_master(security_master_path)
    company_mask = frame["scope"] == "company"
    frame["group_id"] = frame["ticker"].map(group_mapping)
    frame["mapping_status"] = [
        "NOT_APPLICABLE"
        if scope in {"market", "synthetic_test_only"}
        else "MAPPED"
        if pd.notna(group_id)
        else "UNMAPPED"
        for scope, group_id in zip(frame["scope"], frame["group_id"])
    ]

    market = frame[frame["scope"] == "market"].copy()
    company = frame[company_mask].copy()
    synthetic = frame[frame["scope"] == "synthetic_test_only"].copy()

    market_rows = [_row_output(row, taxonomy_version=taxonomy_version) for _, row in market.iterrows()]
    company_rows = [_row_output(row, taxonomy_version=taxonomy_version) for _, row in company.iterrows()]
    synthetic_rows = [
        _row_output(row, taxonomy_version=taxonomy_version) for _, row in synthetic.iterrows()
    ]
    mapped_company_rows = company[company["group_id"].notna()]
    unique_tickers = set(company["ticker"].dropna().tolist())
    mapped_tickers = set(mapped_company_rows["ticker"].dropna().tolist())
    unmapped_tickers = sorted(unique_tickers - mapped_tickers)
    reconciliation_counts = {
        str(key): int(value)
        for key, value in frame.apply(_reconciliation, axis=1)
        .map(lambda item: item[0])
        .value_counts()
        .sort_index()
        .items()
    }
    mapped_pct = (
        round(100.0 * len(mapped_company_rows) / len(company), 2)
        if len(company)
        else 0.0
    )
    daily_samples = _daily_company_sample(company, taxonomy_version=taxonomy_version)
    daily_markets = _daily_market_totals(market, taxonomy_version=taxonomy_version)
    group_summaries = _group_summaries(company, taxonomy_version=taxonomy_version)
    rolling = _rolling_sample_flow(daily_samples)
    breadth = _breadth_observed(daily_samples, daily_markets)

    expected_set = set(expected_dates or [])
    observed_dates = set(frame["as_of"].unique().tolist())
    missing_dates = sorted(expected_set - observed_dates) if expected_set else []
    stale_dates = sorted(
        as_of
        for as_of, count in (
            frame[frame["scope"] == "company"].groupby("as_of").size().items()
        )
        if count < 5
    )

    status = "READY_WITH_GAPS"
    if mapped_pct == 0:
        status = "DATA_GAP"
    if not market_rows and not synthetic_rows:
        status = "UNAVAILABLE"

    signal = _signal_eligibility(
        frame,
        market_count=len(market),
        company_count=len(company),
        mapped_pct=mapped_pct,
        breadth=breadth,
        missing_dates=missing_dates,
        stale_dates=stale_dates,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "provider_mode": "PUBLIC_PROTOTYPE",
        "status": status,
        "as_of": {
            "min": str(frame["as_of"].min()),
            "max": str(frame["as_of"].max()),
        },
        "quantitative_use": True,
        "scope": "sampled_market_and_company_rows",
        "calculation": {
            "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "rounding_tolerance_idr": ROUNDING_TOLERANCE_IDR,
            "group_mapping_source": (
                str(security_master_path) if security_master_path is not None else None
            ),
            "leadership_integration": "DISABLED_DATA_GAP",
            "sectors_api_called": False,
            "network_requests_made": False,
        },
        "coverage": {
            "market_observation_count": int(len(market)),
            "market_day_count": int(market["as_of"].nunique()),
            "company_observation_count": int(len(company)),
            "unique_company_ticker_count": int(len(unique_tickers)),
            "mapped_company_observation_count": int(len(mapped_company_rows)),
            "mapped_ticker_count": int(len(mapped_tickers)),
            "unmapped_tickers": unmapped_tickers,
            "mapped_company_observation_pct": mapped_pct,
            "coverage_label": "SAMPLE_ONLY_NOT_FULL_UNIVERSE",
            "synthetic_test_rows": int(len(synthetic)),
        },
        "quality": {
            "rows_validated": int(len(frame)),
            "reconciliation_status_counts": reconciliation_counts,
            "reported_net_preserved": True,
            "missing_company_buy_sell_not_inferred": True,
            "missing_dates": missing_dates,
            "stale_dates": stale_dates,
        },
        "market_observations": market_rows,
        "company_observations": company_rows,
        "synthetic_test_only": synthetic_rows,
        "daily_market_totals": daily_markets,
        "daily_company_samples": daily_samples,
        "group_summaries": group_summaries,
        "rolling_sample_flow": rolling,
        "breadth_observed": breadth,
        "signal_eligibility": signal,
        "provenance": _source_provenance(frame),
        "source_discovery": {
            "providers": ["tavily", "you"],
            "numeric_ingestion": "manual_normalized_rows_from_published_reports",
            "first_party_structured_daily_per_ticker_feed_found": False,
            "qualitative_context_used_as_numeric_input": False,
        },
        "limitations": [
            "Company rows are published top-buy/top-sell samples, not the full IDX universe.",
            "A top-list sample is never eligible as a full-universe foreign-flow confirmation signal.",
            "Company rows report net flow only; buy/sell components are intentionally null.",
            "Market buy/sell components are rounded in the source and are not used to overwrite reported net.",
            "Secondary reports are retained as source-backed sample evidence, not as a first-party entitlement claim.",
            "The result does not alter leadership, diffusion, or confirmation classification.",
            "Synthetic rows are excluded from the public web payload and live only in synthetic_test_only.",
        ],
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON next to the destination, then replace it atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="calculate_foreign_flow_sample")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--security-master",
        type=Path,
        default=DEFAULT_SECURITY_MASTER,
        help="Persisted JSON security master used only for group mapping.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--no-security-master",
        action="store_true",
        help="Skip group mapping and report all company rows as unmapped.",
    )
    parser.add_argument(
        "--taxonomy-version",
        default="prototype-v1",
        help="Taxonomy version label for downstream mapping.",
    )
    parser.add_argument(
        "--expected-dates",
        nargs="*",
        default=None,
        help="Optional list of expected as_of dates; missing dates are surfaced.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    security_master = None if args.no_security_master else args.security_master
    try:
        result = calculate_foreign_flow_sample(
            args.input,
            security_master_path=security_master,
            taxonomy_version=args.taxonomy_version,
            expected_dates=args.expected_dates,
        )
        write_json_atomic(args.output, result)
    except (ForeignFlowInputError, OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(args.output),
                "market_days": result["coverage"]["market_day_count"],
                "company_rows": result["coverage"]["company_observation_count"],
                "mapped_company_rows": result["coverage"][
                    "mapped_company_observation_count"
                ],
                "signal_eligible": result["signal_eligibility"]["signal_eligible"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
