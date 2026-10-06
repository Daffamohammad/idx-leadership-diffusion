"""Validate, publish, and roll back immutable five-family frontend releases.

Candidate manifests live beside their candidate assets. Published manifests
live at releases/<release-id>/manifest.json and are selected only through
releases/active.json. The active pointer is the only mutable publication
record.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any, Iterator, Mapping

from idx_leadership.data.rotation_replay import endpoints_from_snapshot, validate_asset
from idx_leadership.providers.idx_flow_history import validate_continuity


RELEASE_MANIFEST_SCHEMA = "idx-release-manifest-v1"
ACTIVE_POINTER_SCHEMA = "idx-active-release-v1"
RELEASE_VALIDATOR_CONTRACT = "idx-release-validator-v1"
PUBLIC_PANEL_VALIDATION_CONTRACT = "public-panel-validation-v2"
REQUIRED_FAMILIES = ("snapshot", "market", "ownership", "foreign", "rotation")
SUPPORTED_FAMILY_SCHEMAS = {
    "snapshot": {"web-snapshot-v1"},
    "market": {"market-workspace-v1"},
    "ownership": {"idx-ownership-v1"},
    "foreign": {"idx-foreign-history-v1"},
    "rotation": {"rotation-history-v1"},
}
_HEX = frozenset("0123456789abcdef")
_MANIFEST_KEYS = {
    "schema_version",
    "release_id",
    "target_session",
    "snapshot_identity",
    "analytical_contracts",
    "validation",
    "source_evidence",
    "families",
    "additional_files",
}
_ENTRY_KEYS = {"path", "sha256", "bytes", "schema", "observation_date"}
_ADDITIONAL_FILE_KEYS = _ENTRY_KEYS | {"file_id", "family"}
_SNAPSHOT_IDENTITY_KEYS = {"snapshot_id", "provider", "provider_mode", "price_basis"}
_VALIDATION_KEYS = {
    "package_status",
    "analytical_status",
    "validator_contract",
    "contract_fingerprints",
    "input_hashes",
    "evidence_reports",
}
_INPUT_HASH_KEYS = {"families", "additional_files", "source_evidence"}
_RESERVED_BASENAMES = {
    "active.json",
    "index.json",
    "manifest.json",
    "latest.json",
    "idx_daily_statistics_latest.json",
}


@dataclass(frozen=True)
class VerifiedRelease:
    """A release manifest and all package files whose bytes it verifies."""

    manifest: dict[str, Any]
    root: Path
    manifest_path: Path
    manifest_bytes: bytes
    manifest_sha256: str
    family_paths: dict[str, Path]
    additional_paths: dict[str, Path]

    @property
    def release_id(self) -> str:
        return str(self.manifest["release_id"])


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically and reject nonfinite numbers."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not canonical finite JSON: {exc}") from exc


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON number is not allowed: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _parse_json(raw: bytes, label: str) -> Any:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} is not valid finite JSON: {exc}") from exc
    _assert_finite_json(value, label)
    return value


def _assert_finite_json(value: Any, label: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} contains a nonfinite number")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite_json(item, f"{label}[{index}]")
    elif isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(f"{label} contains a non-string object key")
        for key, item in value.items():
            _assert_finite_json(item, f"{label}.{key}")


def _strict_date(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label} must use strict YYYY-MM-DD form")
    return value


def _payload_matches_observation_date(payload: Mapping[str, Any], expected: str) -> bool:
    """Match an exact date or the final date of a bounded as_of range."""
    observed = payload.get("as_of")
    if isinstance(observed, str):
        try:
            return _strict_date(observed, "additional file as_of") == expected
        except ValueError:
            return False
    if not isinstance(observed, dict) or set(observed) != {"min", "max"}:
        return False
    try:
        start = _strict_date(observed["min"], "additional file as_of.min")
        end = _strict_date(observed["max"], "additional file as_of.max")
    except ValueError:
        return False
    return start <= end and end == expected


def _valid_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _HEX for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _valid_release_id(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 68
        or not value.startswith("rel-")
        or any(character not in _HEX for character in value[4:])
    ):
        raise ValueError(f"{label} is not a canonical release ID")
    return value


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_package_file(root: Path, raw_path: Any, label: str) -> tuple[str, Path]:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        raise ValueError(f"{label} path must be a relative POSIX path")
    relative = PurePosixPath(raw_path)
    if (
        relative.is_absolute()
        or relative.as_posix() != raw_path
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or ":" in relative.parts[0]
        or relative.name.lower() in _RESERVED_BASENAMES
        or relative.name.lower().endswith("_latest.json")
    ):
        raise ValueError(f"{label} path is unsafe or names a mutable alias: {raw_path!r}")

    root = root.resolve()
    path = root.joinpath(*relative.parts)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"{label} path contains a symlink: {raw_path!r}")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError(f"{label} path escapes its package: {raw_path!r}")
    if not resolved.is_file():
        raise ValueError(f"{label} path is not a regular file: {raw_path!r}")
    return raw_path, resolved


def _check_entry_shape(entry: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(entry, dict) or set(entry) != keys:
        raise ValueError(f"{label} must contain exactly {sorted(keys)}")
    if not isinstance(entry["schema"], str) or not entry["schema"]:
        raise ValueError(f"{label}.schema is required")
    if isinstance(entry["bytes"], bool) or not isinstance(entry["bytes"], int) or entry["bytes"] <= 0:
        raise ValueError(f"{label}.bytes must be a positive integer")
    _valid_sha256(entry["sha256"], f"{label}.sha256")
    _strict_date(entry["observation_date"], f"{label}.observation_date")
    return entry


def _entry_payload(
    entry: Mapping[str, Any],
    path: Path,
    label: str,
) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if len(raw) != entry["bytes"]:
        raise ValueError(f"{label} byte count mismatch")
    if _sha256_bytes(raw) != entry["sha256"]:
        raise ValueError(f"{label} SHA-256 mismatch")
    payload = _parse_json(raw, label)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return payload, raw


def _resolve_evidence_file(root: Path, raw_path: Any, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"{label} path is required for staged evidence")
    if "\\" in raw_path:
        raise ValueError(f"{label} path must not use backslashes")
    supplied = Path(raw_path)
    if supplied.is_absolute():
        resolved = supplied.resolve(strict=True)
    else:
        relative = PurePosixPath(raw_path)
        if (
            relative.as_posix() != raw_path
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise ValueError(f"{label} relative path is unsafe")
        candidate = root.resolve().joinpath(*relative.parts)
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root.resolve()):
            raise ValueError(f"{label} relative path escapes the candidate")
    if not resolved.is_file():
        raise ValueError(f"{label} path is not a regular evidence file")
    return resolved


def _source_records(manifest: Mapping[str, Any], *, candidate: bool) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    raw_sources = manifest.get("source_evidence")
    if not isinstance(raw_sources, list):
        raise ValueError("source_evidence must be a list")
    source_ids: set[str] = set()
    source_paths: dict[str, Path] = {}
    sources: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_sources):
        label = f"source_evidence[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{label} must be an object")
        source_id = raw.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip() or source_id in source_ids:
            raise ValueError(f"{label}.source_id must be unique and nonempty")
        source_ids.add(source_id)
        _valid_sha256(raw.get("sha256"), f"{label}.sha256")
        _assert_finite_json(raw, label)
        for key in ("observation_date", "observed_on", "published_on", "available_on", "publication_date"):
            if raw.get(key) is not None:
                _strict_date(raw[key], f"{label}.{key}")
        for key in ("retrieved_at", "captured_at", "published_at"):
            if raw.get(key) is not None:
                stamp = raw[key]
                if not isinstance(stamp, str):
                    raise ValueError(f"{label}.{key} must be an ISO timestamp")
                try:
                    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"{label}.{key} must be an ISO timestamp") from exc
                if parsed.tzinfo is None:
                    raise ValueError(f"{label}.{key} must include a timezone")
        source = dict(raw)
        candidate_path = source.pop("candidate_path", None)
        if candidate:
            source_path = _resolve_evidence_file(
                Path(manifest["_candidate_root"]),
                candidate_path,
                f"{label}.candidate_path",
            )
            if _sha256_bytes(source_path.read_bytes()) != raw["sha256"]:
                raise ValueError(f"{label} evidence file SHA-256 mismatch")
            source_paths[source_id] = source_path
        elif candidate_path is not None:
            raise ValueError(f"{label}.candidate_path is only valid in a staged candidate")
        sources.append(source)
    return sources, source_paths


def _normalised_sources(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for raw in manifest["source_evidence"]:
        source = dict(raw)
        source.pop("candidate_path", None)
        result.append(source)
    return sorted(result, key=lambda row: row["source_id"])


def _file_identity(entry: Mapping[str, Any], *, file_id: str | None = None, family: str | None = None) -> dict[str, Any]:
    result = {
        "path": entry["path"],
        "sha256": entry["sha256"],
        "bytes": entry["bytes"],
        "schema": entry["schema"],
        "observation_date": entry["observation_date"],
    }
    if file_id is not None:
        result["file_id"] = file_id
    if family is not None:
        result["family"] = family
    return result


def _release_identity_material(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target_session": manifest["target_session"],
        "snapshot_identity": manifest["snapshot_identity"],
        "analytical_contracts": manifest["analytical_contracts"],
        "source_evidence": _normalised_sources(manifest),
        "validation": manifest["validation"],
        "families": {
            family: _file_identity(manifest["families"][family])
            for family in sorted(REQUIRED_FAMILIES)
        },
        "additional_files": [
            _file_identity(row, file_id=row["file_id"], family=row["family"])
            for row in sorted(manifest.get("additional_files", []), key=lambda row: row["file_id"])
        ],
    }


def calculate_release_id(manifest: Mapping[str, Any]) -> str:
    """Calculate release identity without including the release directory prefix."""
    return f"rel-{_sha256_bytes(canonical_json_bytes(_release_identity_material(manifest)))}"


def _validate_input_hashes(manifest: Mapping[str, Any]) -> None:
    validation = manifest["validation"]
    if not isinstance(validation, dict) or set(validation) != _VALIDATION_KEYS:
        raise ValueError(f"validation must contain exactly {sorted(_VALIDATION_KEYS)}")
    if validation["package_status"] != "PASS":
        raise ValueError("package validation verdict is not PASS")
    if not isinstance(validation["analytical_status"], str) or not validation["analytical_status"]:
        raise ValueError("validation.analytical_status is required")
    if validation["validator_contract"] != RELEASE_VALIDATOR_CONTRACT:
        raise ValueError("unsupported release validator contract")
    if validation["contract_fingerprints"] != manifest["analytical_contracts"]:
        raise ValueError("validation report analytical contract fingerprints are stale")
    reports = validation["evidence_reports"]
    if not isinstance(reports, dict) or "market_panel" not in reports:
        raise ValueError("validation.evidence_reports must include market_panel")
    for report_id, report in reports.items():
        if not isinstance(report_id, str) or not report_id:
            raise ValueError("validation evidence report IDs must be nonempty strings")
        if not isinstance(report, dict) or set(report) != {"status", "sha256", "contract", "input_hashes"}:
            raise ValueError(f"validation evidence report {report_id} is malformed")
        if report["status"] != "PASS":
            raise ValueError(f"validation evidence report {report_id} is not PASS")
        _valid_sha256(report["sha256"], f"validation evidence report {report_id}.sha256")
        if not isinstance(report["contract"], str) or not report["contract"]:
            raise ValueError(f"validation evidence report {report_id} has no contract")
        if not isinstance(report["input_hashes"], dict):
            raise ValueError(f"validation evidence report {report_id} has no input hashes")

    expected = {
        "families": {
            key: manifest["families"][key]["sha256"] for key in sorted(REQUIRED_FAMILIES)
        },
        "additional_files": {
            row["file_id"]: row["sha256"]
            for row in sorted(manifest.get("additional_files", []), key=lambda row: row["file_id"])
        },
        "source_evidence": {
            row["source_id"]: row["sha256"] for row in _normalised_sources(manifest)
        },
    }
    input_hashes = validation["input_hashes"]
    if not isinstance(input_hashes, dict) or set(input_hashes) != _INPUT_HASH_KEYS:
        raise ValueError("validation.input_hashes has an invalid shape")
    if input_hashes != expected:
        raise ValueError("validation report input hashes do not match this candidate")


def _validate_panel_validation_report(
    report_path: Path,
    *,
    report_sha256: str,
    target_session: str,
    market: Mapping[str, Any],
    input_hashes: Mapping[str, Any],
) -> None:
    raw = report_path.read_bytes()
    if _sha256_bytes(raw) != report_sha256:
        raise ValueError("panel validation report SHA-256 mismatch")
    report = _parse_json(raw, "panel validation report")
    if not isinstance(report, dict) or report.get("status") != "PASS":
        raise ValueError("panel validation report is missing PASS")
    if report.get("kind") != "PUBLIC_PANEL_VALIDATION":
        raise ValueError("panel validation report has an unsupported kind")
    if (
        report.get("validator_contract") != PUBLIC_PANEL_VALIDATION_CONTRACT
        or report.get("input_hashes") != input_hashes
    ):
        raise ValueError("panel validation report contract or input hashes are stale")
    panel_window = report.get("panel_window")
    if not isinstance(panel_window, dict) or panel_window.get("end") != target_session:
        raise ValueError("panel validation report does not reach the target session")

    checks = report.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("panel validation report has no checks")
    panel_integrity = checks.get("panel_integrity", {})
    if (
        panel_integrity.get("status") != "PASS"
        or panel_integrity.get("panel_file_hashes_verified") is not True
        or panel_integrity.get("latest_session") != target_session
    ):
        raise ValueError("panel validation report is stale or failed panel integrity")
    for name in (
        "benchmark_vs_official_workbook",
        "benchmark_vs_daily_statistics_pdfs",
        "stocks_vs_official_stock_summary",
        "coverage_reconciliation",
    ):
        if checks.get(name, {}).get("status") != "PASS":
            raise ValueError(f"panel validation report lacks mandatory PASS: {name}")

    official = checks["stocks_vs_official_stock_summary"]
    market_summary = market.get("sources", {}).get("stock_summary", {})
    if (
        official.get("official_date") != target_session
        or official.get("official_date_matches_panel") is not True
        or official.get("source") != market_summary.get("file")
    ):
        raise ValueError("panel validation report does not bind the exact official stock-summary input")
    composite = checks["benchmark_vs_official_workbook"]
    if composite.get("source") != input_hashes["official_sources"]["composite_workbook"]["file_name"]:
        raise ValueError("panel validation report does not bind the exact composite workbook")


def _source_records_by_role(manifest: Mapping[str, Any], role: str) -> list[dict[str, Any]]:
    return [
        row for row in _normalised_sources(manifest)
        if row.get("role") == role
    ]


def _single_source_record(
    manifest: Mapping[str, Any],
    role: str,
    file_name: str,
) -> dict[str, Any]:
    rows = _source_records_by_role(manifest, role)
    if len(rows) != 1 or rows[0].get("file_name") != file_name:
        raise ValueError(f"source inventory does not bind exactly one {role} file named {file_name}")
    return rows[0]


def _validate_panel_report_bindings(
    manifest: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    source_paths: Mapping[str, Path],
    candidate: bool,
) -> dict[str, Any]:
    report = manifest["validation"]["evidence_reports"]["market_panel"]
    if report["contract"] != PUBLIC_PANEL_VALIDATION_CONTRACT:
        raise ValueError("unsupported public-panel validation contract")
    panel_source = market.get("sources", {}).get("validated_panel") or {}
    if report["sha256"] != panel_source.get("validation_sha256"):
        raise ValueError("market validation hash differs from its bound validation report")
    input_hashes = report["input_hashes"]
    if (
        not isinstance(input_hashes, dict)
        or set(input_hashes) != {"validator_contract", "panel_files", "official_sources"}
        or input_hashes["validator_contract"] != PUBLIC_PANEL_VALIDATION_CONTRACT
    ):
        raise ValueError("panel validation report input inventory is malformed")

    panel_files = input_hashes["panel_files"]
    if not isinstance(panel_files, dict) or set(panel_files) != {
        "prices.csv",
        "benchmark.csv",
        "source_manifest.json",
    }:
        raise ValueError("panel validation report must hash both panel files and source manifest")
    if {
        name: panel_files[name] for name in ("prices.csv", "benchmark.csv")
    } != panel_source.get("files"):
        raise ValueError("panel validation report hashes differ from the market workspace")
    for file_name, role in (
        ("prices.csv", "market_panel_prices"),
        ("benchmark.csv", "market_panel_benchmark"),
        ("source_manifest.json", "market_panel_manifest"),
    ):
        digest = _valid_sha256(panel_files[file_name], f"panel validation input {file_name}")
        source = _single_source_record(manifest, role, file_name)
        if source["sha256"] != digest:
            raise ValueError(f"panel validation input hash differs from source inventory: {file_name}")
        if candidate and file_name == "source_manifest.json":
            source_path = source_paths.get(source["source_id"])
            if source_path is None:
                raise ValueError("panel source manifest was not verified")
            source_manifest = _parse_json(source_path.read_bytes(), "panel source manifest")
            recorded_files = source_manifest.get("files") or {}
            for panel_file in ("prices.csv", "benchmark.csv"):
                recorded_sha = (recorded_files.get(panel_file) or {}).get("sha256")
                if recorded_sha != panel_files[panel_file]:
                    raise ValueError(f"panel source manifest hash mismatch: {panel_file}")

    official = input_hashes["official_sources"]
    if not isinstance(official, dict) or set(official) != {
        "composite_workbook",
        "stock_summary",
        "daily_statistics_pdfs",
    }:
        raise ValueError("panel validation official-source inventory is malformed")
    for key, role in (
        ("composite_workbook", "official_composite_workbook"),
        ("stock_summary", "official_stock_summary"),
    ):
        record = official[key]
        if not isinstance(record, dict) or set(record) != {"file_name", "sha256"}:
            raise ValueError(f"panel validation input {key} is malformed")
        _valid_sha256(record["sha256"], f"panel validation input {key}.sha256")
        source = _single_source_record(manifest, role, record["file_name"])
        if source["sha256"] != record["sha256"]:
            raise ValueError(f"panel validation official-source hash mismatch: {key}")
    market_summary = market.get("sources", {}).get("stock_summary") or {}
    if official["stock_summary"] != {
        "file_name": market_summary.get("file"),
        "sha256": market_summary.get("sha256"),
    }:
        raise ValueError("panel validation report does not match market stock-summary provenance")

    daily_pdfs = official["daily_statistics_pdfs"]
    if not isinstance(daily_pdfs, dict) or not daily_pdfs:
        raise ValueError("panel validation report has no dated daily-statistics PDF hashes")
    source_pdfs = _source_records_by_role(manifest, "official_daily_statistics_pdf")
    evidence_pdfs = {
        row.get("file_name"): row["sha256"]
        for row in source_pdfs
    }
    for file_name, digest in daily_pdfs.items():
        if not isinstance(file_name, str) or not file_name:
            raise ValueError("daily-statistics PDF filename is required")
        _valid_sha256(digest, f"daily-statistics PDF {file_name}.sha256")
    if evidence_pdfs != daily_pdfs:
        raise ValueError("panel validation daily-statistics PDF hashes differ from source inventory")

    return report


def _validate_release_semantics(
    manifest: Mapping[str, Any],
    payloads: Mapping[str, dict[str, Any]],
    source_paths: Mapping[str, Path],
    *,
    candidate: bool,
) -> None:
    target = manifest["target_session"]
    identity = manifest["snapshot_identity"]
    snapshot = payloads["snapshot"]
    market = payloads["market"]
    ownership = payloads["ownership"]
    foreign = payloads["foreign"]
    rotation = payloads["rotation"]
    snapshot_id = identity["snapshot_id"]
    snapshot_entry = ((snapshot.get("manifest") or {}).get("entries") or [{}])[0]

    for family in ("snapshot", "market", "foreign", "rotation"):
        payload = payloads[family]
        if payload.get("as_of") != target:
            raise ValueError(f"{family} observation does not reach target session {target}")
        if manifest["families"][family]["observation_date"] != target:
            raise ValueError(f"{family} manifest observation date differs from target session")

    if snapshot.get("schema_version") != "web-snapshot-v1" or snapshot.get("snapshot_id") != snapshot_id:
        raise ValueError("snapshot family identity or schema mismatch")
    if snapshot.get("complete") is not True:
        raise ValueError("snapshot family is incomplete")
    if (
        snapshot_entry.get("snapshot_id") != snapshot_id
        or snapshot_entry.get("as_of") != target
        or snapshot_entry.get("provider") != identity["provider"]
        or snapshot_entry.get("provider_mode") != identity["provider_mode"]
        or snapshot_entry.get("price_basis") != identity["price_basis"]
    ):
        raise ValueError("snapshot manifest entry differs from release snapshot identity")

    if (
        market.get("schema_version") != "market-workspace-v1"
        or market.get("snapshot_id") != snapshot_id
        or market.get("as_of") != target
    ):
        raise ValueError("market family identity or schema mismatch")
    benchmark = market.get("benchmark")
    if not isinstance(benchmark, list) or not benchmark:
        raise ValueError("market family has no benchmark sessions")
    benchmark_dates = [_strict_date(row.get("date"), "market benchmark date") for row in benchmark]
    if benchmark_dates != sorted(set(benchmark_dates)) or benchmark_dates[-1] != target:
        raise ValueError("market benchmark sessions do not uniquely reach the target")
    for row in benchmark:
        close = row.get("close")
        if isinstance(close, bool) or not isinstance(close, (int, float)) or not math.isfinite(close) or close <= 0:
            raise ValueError("market benchmark contains an invalid close")

    records = market.get("records")
    if not isinstance(records, list):
        raise ValueError("market family records must be a list")
    if any(not isinstance(row, dict) for row in records):
        raise ValueError("market family records must contain objects")
    tickers = [row.get("ticker") for row in records]
    if any(not isinstance(ticker, str) or not ticker for ticker in tickers) or len(tickers) != len(set(tickers)):
        raise ValueError("market records contain missing or duplicate tickers")
    eligible = sorted(
        row["ticker"] for row in records if row.get("signal_eligible") is True
    )
    if len(eligible) != len(set(eligible)):
        raise ValueError("market eligible cohort contains missing or duplicate tickers")
    expected_cohort = hashlib.sha256(json.dumps(eligible).encode("utf-8")).hexdigest()[:16]
    if snapshot_entry.get("eligible_ticker_set_hash") != expected_cohort:
        raise ValueError("market eligible cohort differs from snapshot manifest")

    taxonomy_views = snapshot.get("taxonomy_views")
    if not isinstance(taxonomy_views, dict):
        raise ValueError("snapshot taxonomy views are missing")
    found_kinds: set[str] = set()
    for view in taxonomy_views.values():
        if not isinstance(view, dict):
            raise ValueError("snapshot taxonomy view must be an object")
        kind = view.get("taxonomy_kind")
        if kind not in {"SECTOR", "KONGLO", "THEMES"}:
            continue
        found_kinds.add(kind)
        if (
            view.get("source_snapshot_id") != snapshot_id
            or view.get("as_of") != target
            or view.get("provider_mode") != identity["provider_mode"]
        ):
            raise ValueError("taxonomy view is not bound to the selected snapshot")
        calculation = view.get("calculation") or {}
        cohort = calculation.get("eligible_ticker_set_hash")
        if kind in {"KONGLO", "THEMES"} and cohort != expected_cohort:
            raise ValueError("taxonomy view eligible cohort differs from market family")
    if not {"KONGLO", "THEMES"}.issubset(found_kinds):
        raise ValueError("snapshot must include both Konglo and Themes taxonomy views")

    if ownership.get("schema_version") != "idx-ownership-v1":
        raise ValueError("ownership family schema mismatch")
    ownership_date = _strict_date(ownership.get("as_of"), "ownership as_of")
    five_date = _strict_date(ownership.get("five_as_of"), "ownership five_as_of")
    previous_date = _strict_date(ownership.get("previous_as_of"), "ownership previous_as_of")
    if ownership_date > target or five_date > target or previous_date >= ownership_date:
        raise ValueError("ownership register chronology is incompatible with target session")
    registers = ownership.get("registers")
    if not isinstance(registers, dict) or not registers.get("one") or not registers.get("five"):
        raise ValueError("ownership family has an empty register")
    for register_key, expected_date in (("one", ownership_date), ("five", five_date)):
        rows = registers[register_key]
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or row.get("as_of") != expected_date for row in rows
        ):
            raise ValueError(f"ownership {register_key} register row date mismatch")
    ownership_edges = market.get("ownership_edges") or []
    if not isinstance(ownership_edges, list):
        raise ValueError("market ownership_edges must be a list")
    for edge in ownership_edges:
        if not isinstance(edge, dict):
            raise ValueError("market ownership edge must be an object")
        edge_date = edge.get("as_of")
        if edge_date is not None and _strict_date(edge_date, "ownership edge as_of") > target:
            raise ValueError("market ownership edge contains future evidence")
        control_source = edge.get("control_source")
        if control_source and not isinstance(control_source, dict):
            raise ValueError("ownership edge control_source must be an object")
        if control_source and control_source.get("as_of"):
            if _strict_date(control_source["as_of"], "ownership control source as_of") > target:
                raise ValueError("market ownership edge contains future evidence")

    if (
        foreign.get("schema_version") != "idx-foreign-history-v1"
        or foreign.get("as_of") != target
        or not (foreign.get("validation") or {}).get("session_continuity")
        or not (foreign.get("validation") or {}).get("ytd_continuity")
    ):
        raise ValueError("foreign family is not validated through the target session")
    daily = foreign.get("daily")
    if not isinstance(daily, list) or not daily:
        raise ValueError("foreign history does not reach the target session")
    if not isinstance(daily[-1], dict) or daily[-1].get("as_of") != target:
        raise ValueError("foreign history does not reach the target session")
    for index, row in enumerate(daily):
        if not isinstance(row, dict):
            raise ValueError("foreign daily history must contain objects")
        _strict_date(row.get("as_of"), f"foreign daily[{index}].as_of")
        for key in ("net_foreign_value_idr", "ytd_net_foreign_value_idr"):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"foreign daily[{index}].{key} must be finite")
    validate_continuity(daily, benchmark_dates)

    if (
        rotation.get("schema_version") != "rotation-history-v1"
        or rotation.get("snapshot_id") != snapshot_id
        or rotation.get("as_of") != target
    ):
        raise ValueError("rotation family identity or schema mismatch")
    snapshot_sha256 = manifest["families"]["snapshot"]["sha256"]
    provenance = rotation.get("provenance") or {}
    if provenance.get("snapshot_sha256") != snapshot_sha256:
        raise ValueError("rotation endpoint snapshot hash is stale")
    rotation_sessions = rotation.get("sessions")
    if not isinstance(rotation_sessions, list):
        raise ValueError("rotation sessions must be a list")
    for index, session in enumerate(rotation_sessions):
        _strict_date(session, f"rotation sessions[{index}]")
    validate_asset(rotation, endpoints_from_snapshot(snapshot))
    for groups in rotation.get("taxonomies", {}).values():
        for group in groups.values():
            for segment in group.get("segments", []):
                if segment.get("sessions") and segment["sessions"][-1] == target:
                    for point in segment.get("points", []):
                        if point.get("as_of") == target and point.get("universe_eligible_ticker_set_hash") != expected_cohort:
                            raise ValueError("rotation endpoint eligible cohort differs from snapshot")

    evidence_hashes = {row["sha256"] for row in _normalised_sources(manifest)}
    market_sources = market.get("sources") or {}
    panel_source = market_sources.get("validated_panel") or {}
    if not isinstance(panel_source, dict):
        raise ValueError("market family has no validated-panel source record")
    panel_hashes = panel_source.get("files") or {}
    rotation_panel_hashes = provenance.get("panel_files") or {}
    if (
        not isinstance(panel_hashes, dict)
        or not panel_hashes
        or panel_hashes != rotation_panel_hashes
    ):
        raise ValueError("market and rotation panel source hashes differ")
    for name, digest in panel_hashes.items():
        _valid_sha256(digest, f"validated panel {name}")
        if digest not in evidence_hashes:
            raise ValueError(f"validated panel source hash is absent from source inventory: {name}")

    validation_sha = _valid_sha256(
        panel_source.get("validation_sha256"),
        "market validated-panel validation_sha256",
    )
    report_matches = [
        row for row in _normalised_sources(manifest)
        if row["sha256"] == validation_sha and row.get("role") == "market_panel_validation"
    ]
    if len(report_matches) != 1:
        raise ValueError("market validation report hash is absent or ambiguous in source inventory")
    report_binding = _validate_panel_report_bindings(
        manifest,
        market,
        source_paths=source_paths,
        candidate=candidate,
    )
    if candidate:
        report_source = next(
            raw for raw in manifest["source_evidence"]
            if raw["source_id"] == report_matches[0]["source_id"]
        )
        if not report_source.get("candidate_path"):
            raise ValueError("staged candidate must include the exact panel validation report")
        report_path = source_paths.get(report_source["source_id"])
        if report_path is None:
            raise ValueError("panel validation report was not verified")
        _validate_panel_validation_report(
            report_path,
            report_sha256=validation_sha,
            target_session=target,
            market=market,
            input_hashes=report_binding["input_hashes"],
        )
    if validation_sha not in evidence_hashes:
        raise ValueError("market validation report hash is absent from source inventory")

    official_summary = market_sources.get("stock_summary") or {}
    classification = market_sources.get("classification") or {}
    for label, source in (("official stock summary", official_summary), ("classification", classification)):
        digest = _valid_sha256(source.get("sha256"), f"{label} SHA-256")
        if digest not in evidence_hashes:
            raise ValueError(f"{label} hash is absent from source inventory")

    for index, source in enumerate(ownership.get("sources") or []):
        if isinstance(source, dict) and source.get("sha256"):
            digest = _valid_sha256(source["sha256"], f"ownership source {index} SHA-256")
            if digest not in evidence_hashes:
                raise ValueError(f"ownership source hash is absent from source inventory: {index}")

    for name in ("ledger_sha256", "snapshot_provenance_sha256", "validation_sha256"):
        digest = _valid_sha256(provenance.get(name), f"rotation provenance {name}")
        if digest not in evidence_hashes:
            raise ValueError(f"rotation provenance hash is absent from source inventory: {name}")
    for name, digest in (provenance.get("panel_files") or {}).items():
        if digest not in evidence_hashes:
            raise ValueError(f"rotation panel provenance hash is absent from source inventory: {name}")

    if manifest["families"]["ownership"]["observation_date"] != ownership_date:
        raise ValueError("ownership manifest observation date differs from its register date")
    if manifest["families"]["foreign"]["observation_date"] != target:
        raise ValueError("foreign manifest observation date differs from target session")
    if manifest["families"]["rotation"]["observation_date"] != target:
        raise ValueError("rotation manifest observation date differs from target session")


def validate_manifest_file(
    manifest_path: str | Path,
    *,
    candidate: bool = True,
    expected_release_id: str | None = None,
    expected_manifest_sha256: str | None = None,
) -> VerifiedRelease:
    """Validate a candidate or finalized package and every referenced asset."""
    path = Path(manifest_path)
    if path.is_symlink() or not path.is_file() or path.name != "manifest.json":
        raise ValueError("release manifest must be a regular manifest.json file")
    root = path.parent.resolve()
    raw_manifest = path.read_bytes()
    manifest = _parse_json(raw_manifest, "release manifest")
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_KEYS:
        raise ValueError(f"release manifest must contain exactly {sorted(_MANIFEST_KEYS)}")
    if manifest["schema_version"] != RELEASE_MANIFEST_SCHEMA:
        raise ValueError("unsupported release manifest schema")
    manifest["_candidate_root"] = str(root)
    _strict_date(manifest.get("target_session"), "target_session")
    identity = manifest.get("snapshot_identity")
    if not isinstance(identity, dict) or set(identity) != _SNAPSHOT_IDENTITY_KEYS:
        raise ValueError(f"snapshot_identity must contain exactly {sorted(_SNAPSHOT_IDENTITY_KEYS)}")
    if any(not isinstance(value, str) or not value.strip() for value in identity.values()):
        raise ValueError("snapshot_identity values must be nonempty strings")

    contracts = manifest.get("analytical_contracts")
    if not isinstance(contracts, dict) or not contracts:
        raise ValueError("analytical_contracts must be a nonempty fingerprint map")
    for name, digest in contracts.items():
        if not isinstance(name, str) or not name:
            raise ValueError("analytical contract names must be nonempty strings")
        _valid_sha256(digest, f"analytical_contracts.{name}")

    source_rows, source_paths = _source_records(manifest, candidate=candidate)
    if not candidate and any("candidate_path" in row for row in manifest["source_evidence"]):
        raise ValueError("published source inventory contains candidate-only paths")
    if source_rows != _normalised_sources(manifest):
        raise ValueError("source evidence must be sorted by source_id")

    raw_families = manifest.get("families")
    if not isinstance(raw_families, dict) or set(raw_families) != set(REQUIRED_FAMILIES):
        raise ValueError(f"release must contain all five families: {', '.join(REQUIRED_FAMILIES)}")
    additional = manifest.get("additional_files")
    if not isinstance(additional, list):
        raise ValueError("additional_files must be a list")
    paths: dict[str, str] = {}
    family_paths: dict[str, Path] = {}
    additional_paths: dict[str, Path] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for family in REQUIRED_FAMILIES:
        entry = _check_entry_shape(raw_families[family], f"families.{family}", _ENTRY_KEYS)
        if entry["schema"] not in SUPPORTED_FAMILY_SCHEMAS[family]:
            raise ValueError(f"unsupported {family} schema: {entry['schema']}")
        raw_path, file_path = _safe_package_file(root, entry["path"], f"families.{family}")
        if raw_path in paths:
            raise ValueError("release package references the same path more than once")
        paths[raw_path] = family
        family_paths[family] = file_path
        payload, _ = _entry_payload(entry, file_path, family)
        if payload.get("schema_version") != entry["schema"]:
            raise ValueError(f"{family} file schema differs from manifest")
        payloads[family] = payload

    seen_file_ids: set[str] = set()
    for index, raw_entry in enumerate(additional):
        entry = _check_entry_shape(raw_entry, f"additional_files[{index}]", _ADDITIONAL_FILE_KEYS)
        file_id = entry["file_id"]
        if not isinstance(file_id, str) or not file_id.strip() or file_id in seen_file_ids:
            raise ValueError(f"additional_files[{index}].file_id must be unique and nonempty")
        seen_file_ids.add(file_id)
        if entry["family"] != "snapshot":
            raise ValueError("additional release files must belong to the snapshot family")
        raw_path, file_path = _safe_package_file(root, entry["path"], f"additional_files[{index}]")
        if raw_path in paths:
            raise ValueError("release package references the same path more than once")
        paths[raw_path] = f"additional_files.{file_id}"
        additional_paths[file_id] = file_path
        payload, _ = _entry_payload(entry, file_path, f"additional file {file_id}")
        if payload.get("schema_version") != entry["schema"]:
            raise ValueError(f"additional file schema differs from manifest: {file_id}")
        if not _payload_matches_observation_date(payload, entry["observation_date"]):
            raise ValueError(f"additional file observation date differs from manifest: {file_id}")

    path_names = sorted(paths)
    for index, name in enumerate(path_names):
        if any(other.startswith(name + "/") for other in path_names[index + 1:]):
            raise ValueError("release package file paths overlap")

    if not _normalised_sources(manifest):
        raise ValueError("release source-evidence inventory is empty")
    _validate_input_hashes(manifest)
    try:
        _validate_release_semantics(
            manifest,
            payloads,
            source_paths,
            candidate=candidate,
        )
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise ValueError(f"release family contract is malformed: {exc}") from exc

    calculated_id = calculate_release_id(manifest)
    if manifest.get("release_id") != calculated_id:
        raise ValueError("release_id does not match the canonical package inventory")
    if expected_release_id is not None and calculated_id != expected_release_id:
        raise ValueError("release manifest directory and release_id differ")

    canonical_manifest = dict(manifest)
    canonical_manifest.pop("_candidate_root", None)
    for row in canonical_manifest["source_evidence"]:
        row.pop("candidate_path", None)
    canonical_bytes = canonical_json_bytes(canonical_manifest) + b"\n"
    manifest_bytes = raw_manifest if candidate else canonical_bytes
    if not candidate and raw_manifest != canonical_bytes:
        raise ValueError("published release manifest is not canonical")
    manifest_hash = _sha256_bytes(manifest_bytes)
    if expected_manifest_sha256 is not None and manifest_hash != expected_manifest_sha256:
        raise ValueError("active pointer manifest SHA-256 mismatch")
    return VerifiedRelease(
        manifest=canonical_manifest,
        root=root,
        manifest_path=path.resolve(),
        manifest_bytes=manifest_bytes,
        manifest_sha256=manifest_hash,
        family_paths=family_paths,
        additional_paths=additional_paths,
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _copy_candidate_file(source: Path, destination: Path, entry: Mapping[str, Any]) -> None:
    """Copy one already verified candidate file with exclusive creation."""
    raw = source.read_bytes()
    if len(raw) != entry["bytes"] or _sha256_bytes(raw) != entry["sha256"]:
        raise ValueError(f"candidate changed while staging: {entry['path']}")
    _write_exclusive(destination, raw)
    copied = destination.read_bytes()
    if len(copied) != entry["bytes"] or _sha256_bytes(copied) != entry["sha256"]:
        raise ValueError(f"staged release asset failed verification: {entry['path']}")


@contextmanager
def _writer_lock(releases_root: Path) -> Iterator[None]:
    lock_id = hashlib.sha256(str(releases_root.resolve()).encode("utf-8")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"idx-release-publisher-{lock_id}.lock"
    if lock_path.is_symlink():
        raise ValueError("publication lock path may not be a symlink")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "rb+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        # fdopen owns and closes the descriptor after the with block.
        pass


def _release_ref(release: VerifiedRelease) -> dict[str, str]:
    return {
        "release_id": release.release_id,
        "manifest_path": f"{release.release_id}/manifest.json",
        "manifest_sha256": release.manifest_sha256,
    }


def _resolve_pointer_ref(releases_root: Path, raw: Any, label: str) -> VerifiedRelease:
    if not isinstance(raw, dict) or set(raw) != {"release_id", "manifest_path", "manifest_sha256"}:
        raise ValueError(f"active pointer {label} reference is malformed")
    release_id = _valid_release_id(raw["release_id"], f"active pointer {label} release_id")
    release_dir = releases_root / release_id
    if release_dir.is_symlink():
        raise ValueError(f"active pointer {label} release directory may not be a symlink")
    expected_path = f"{release_id}/manifest.json"
    if raw["manifest_path"] != expected_path:
        raise ValueError(f"active pointer {label} manifest path is not canonical")
    manifest_path = releases_root / expected_path
    if manifest_path.is_symlink():
        raise ValueError(f"active pointer {label} manifest may not be a symlink")
    return validate_manifest_file(
        manifest_path,
        candidate=False,
        expected_release_id=release_id,
        expected_manifest_sha256=_valid_sha256(raw["manifest_sha256"], f"active pointer {label} manifest_sha256"),
    )


def _read_active_pointer(releases_root: Path) -> tuple[dict[str, Any] | None, VerifiedRelease | None, VerifiedRelease | None]:
    pointer_path = releases_root / "active.json"
    if pointer_path.is_symlink():
        raise ValueError("active pointer may not be a symlink")
    if not pointer_path.exists():
        return None, None, None
    if pointer_path.is_symlink() or not pointer_path.is_file():
        raise ValueError("active pointer must be a regular file")
    pointer = _parse_json(pointer_path.read_bytes(), "active pointer")
    if (
        not isinstance(pointer, dict)
        or set(pointer) != {"schema_version", "active", "previous"}
        or pointer.get("schema_version") != ACTIVE_POINTER_SCHEMA
    ):
        raise ValueError("active pointer schema mismatch")
    active = _resolve_pointer_ref(releases_root, pointer["active"], "active")
    previous = None
    if pointer["previous"] is not None:
        previous = _resolve_pointer_ref(releases_root, pointer["previous"], "previous")
        if previous.release_id == active.release_id:
            raise ValueError("active and previous releases must differ")
    return pointer, active, previous


def _compare_expected_active(active: VerifiedRelease | None, expected: str | None) -> None:
    actual = active.release_id if active else None
    if actual != expected:
        expected_text = expected if expected is not None else "none"
        actual_text = actual if actual is not None else "none"
        raise ValueError(f"stale active release: expected {expected_text}, found {actual_text}")


def _copy_release_to_incoming(candidate: VerifiedRelease, incoming: Path) -> VerifiedRelease:
    for family in REQUIRED_FAMILIES:
        entry = candidate.manifest["families"][family]
        destination = incoming.joinpath(*PurePosixPath(entry["path"]).parts)
        _copy_candidate_file(candidate.family_paths[family], destination, entry)
    for entry in candidate.manifest.get("additional_files", []):
        file_id = entry["file_id"]
        destination = incoming.joinpath(*PurePosixPath(entry["path"]).parts)
        _copy_candidate_file(candidate.additional_paths[file_id], destination, entry)
    manifest_raw = canonical_json_bytes(candidate.manifest) + b"\n"
    _write_exclusive(incoming / "manifest.json", manifest_raw)

    verified = validate_manifest_file(
        incoming / "manifest.json",
        candidate=False,
        expected_release_id=candidate.release_id,
    )
    if verified.manifest_bytes != manifest_raw:
        raise ValueError("finalized release manifest changed during staging")
    return verified


def _freeze_release(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir():
            os.chmod(path, 0o555)
        else:
            os.chmod(path, 0o444)
    os.chmod(root, 0o555)
    for directory in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda item: len(item.parts), reverse=True):
        _fsync_directory(directory)
    _fsync_directory(root)


def _make_writable_and_remove(root: Path) -> None:
    if not root.exists():
        return
    for path in [*root.rglob("*"), root]:
        try:
            os.chmod(path, 0o755 if path.is_dir() else 0o644)
        except OSError:
            pass
    shutil.rmtree(root, ignore_errors=True)


def _atomic_pointer_write(releases_root: Path, pointer: dict[str, Any]) -> None:
    raw = canonical_json_bytes(pointer) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".active-", suffix=".tmp", dir=releases_root)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, releases_root / "active.json")
        _fsync_directory(releases_root)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _verify_existing_package(
    release_dir: Path,
    candidate: VerifiedRelease,
) -> VerifiedRelease:
    if release_dir.is_symlink() or not release_dir.is_dir():
        raise ValueError("immutable release path exists but is not a directory")
    existing = validate_manifest_file(
        release_dir / "manifest.json",
        candidate=False,
        expected_release_id=candidate.release_id,
    )
    desired_manifest = canonical_json_bytes(candidate.manifest) + b"\n"
    if existing.manifest_bytes != desired_manifest:
        raise ValueError("immutable release ID collision: manifest bytes differ")
    for family in REQUIRED_FAMILIES:
        entry = candidate.manifest["families"][family]
        existing_path = existing.root.joinpath(*PurePosixPath(entry["path"]).parts)
        if existing_path.read_bytes() != candidate.family_paths[family].read_bytes():
            raise ValueError(f"immutable release ID collision: {family} bytes differ")
    for entry in candidate.manifest.get("additional_files", []):
        existing_path = existing.root.joinpath(*PurePosixPath(entry["path"]).parts)
        if existing_path.read_bytes() != candidate.additional_paths[entry["file_id"]].read_bytes():
            raise ValueError(f"immutable release ID collision: {entry['file_id']} bytes differ")
    return existing


def activate_candidate(
    candidate_manifest_path: str | Path,
    public_root: str | Path,
    *,
    expected_active_release_id: str | None,
) -> dict[str, Any]:
    """Verify a staged five-family candidate and atomically select it."""
    candidate = validate_manifest_file(candidate_manifest_path, candidate=True)
    releases_root = Path(public_root).resolve() / "releases"
    if releases_root.is_symlink():
        raise ValueError("releases directory may not be a symlink")
    releases_root.mkdir(parents=True, exist_ok=True)

    with _writer_lock(releases_root):
        current_pointer, current_active, _ = _read_active_pointer(releases_root)
        _compare_expected_active(current_active, expected_active_release_id)
        final_dir = releases_root / candidate.release_id
        if final_dir.is_symlink() or final_dir.exists():
            finalized = _verify_existing_package(final_dir, candidate)
        else:
            incoming = Path(tempfile.mkdtemp(prefix=".incoming-", dir=releases_root))
            try:
                finalized = _copy_release_to_incoming(candidate, incoming)
                _freeze_release(incoming)
                os.rename(incoming, final_dir)
                _fsync_directory(releases_root)
            except Exception:
                _make_writable_and_remove(incoming)
                raise

        if current_active and current_active.release_id == finalized.release_id:
            # Re-selecting the active immutable package is a verified no-op.
            return current_pointer or {}
        pointer = {
            "schema_version": ACTIVE_POINTER_SCHEMA,
            "active": _release_ref(finalized),
            "previous": _release_ref(current_active) if current_active else None,
        }
        _atomic_pointer_write(releases_root, pointer)
        return pointer


def rollback_to_previous(
    previous_manifest_path: str | Path,
    public_root: str | Path,
    *,
    expected_active_release_id: str | None,
) -> dict[str, Any]:
    """Reverify the retained previous package and switch only active.json."""
    releases_root = Path(public_root).resolve() / "releases"
    if not releases_root.is_dir() or releases_root.is_symlink():
        raise ValueError("no release directory is available for rollback")
    with _writer_lock(releases_root):
        _, current_active, previous = _read_active_pointer(releases_root)
        if current_active is None:
            raise ValueError("no active release is available for rollback")
        _compare_expected_active(current_active, expected_active_release_id)
        if previous is None:
            raise ValueError("active pointer has no verified previous release")

        requested = Path(previous_manifest_path)
        if requested.is_symlink() or not requested.is_file():
            raise ValueError("rollback manifest must be a regular retained manifest")
        if requested.resolve() != previous.manifest_path:
            raise ValueError("rollback may select only the pointer's verified previous release")
        verified_previous = validate_manifest_file(
            requested,
            candidate=False,
            expected_release_id=previous.release_id,
            expected_manifest_sha256=previous.manifest_sha256,
        )
        pointer = {
            "schema_version": ACTIVE_POINTER_SCHEMA,
            "active": _release_ref(verified_previous),
            "previous": _release_ref(current_active),
        }
        _atomic_pointer_write(releases_root, pointer)
        return pointer
