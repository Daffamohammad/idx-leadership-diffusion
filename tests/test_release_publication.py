from __future__ import annotations

import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

from idx_leadership.data.releases import (
    ACTIVE_POINTER_SCHEMA,
    RELEASE_MANIFEST_SCHEMA,
    RELEASE_VALIDATOR_CONTRACT,
    PUBLIC_PANEL_VALIDATION_CONTRACT,
    activate_candidate,
    calculate_release_id,
    canonical_json_bytes,
    rollback_to_previous,
    validate_manifest_file,
)
from idx_leadership.data.rotation_replay import METHOD
from scripts.validate_public_panel import _validation_input_hashes
from scripts.refresh_release import _build_candidate


TARGET = "2026-10-02"
PREVIOUS_SESSION = "2026-10-01"
COHORT_HASH = hashlib.sha256(json.dumps(["AAA.JK"]).encode()).hexdigest()[:16]
CONTRACT_HASH = hashlib.sha256(b"test-methodology-v1").hexdigest()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(payload: dict) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _source_digest(label: str, version: str) -> str:
    return _sha(_source_bytes(label, version))


def _source_bytes(label: str, version: str) -> bytes:
    return f"{label}:{version}".encode()


def test_panel_validation_inventory_hashes_every_panel_and_official_input(tmp_path):
    panel = tmp_path / "panel"
    official = tmp_path / "official"
    panel.mkdir()
    official.mkdir()
    panel_files = {
        name: f"panel:{name}".encode()
        for name in ("prices.csv", "benchmark.csv", "source_manifest.json")
    }
    official_files = {
        name: f"official:{name}".encode()
        for name in ("composite.xlsx", "summary.xlsx", "ds_20261002.pdf")
    }
    for name, raw in panel_files.items():
        (panel / name).write_bytes(raw)
    for name, raw in official_files.items():
        (official / name).write_bytes(raw)

    inventory = _validation_input_hashes(
        panel_dir=panel,
        workbook_path=official / "composite.xlsx",
        summary_path=official / "summary.xlsx",
        daily_statistics_pdfs=[official / "ds_20261002.pdf"],
    )

    assert inventory["validator_contract"] == PUBLIC_PANEL_VALIDATION_CONTRACT
    assert inventory["panel_files"] == {
        name: _sha(raw) for name, raw in panel_files.items()
    }
    assert inventory["official_sources"]["composite_workbook"] == {
        "file_name": "composite.xlsx",
        "sha256": _sha(official_files["composite.xlsx"]),
    }
    assert inventory["official_sources"]["stock_summary"] == {
        "file_name": "summary.xlsx",
        "sha256": _sha(official_files["summary.xlsx"]),
    }
    assert inventory["official_sources"]["daily_statistics_pdfs"] == {
        "ds_20261002.pdf": _sha(official_files["ds_20261002.pdf"])
    }


def build_candidate(root: Path, version: str = "one") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "evidence").mkdir()
    snapshot_id = f"snap_test_{TARGET}_{version}"
    panel_hashes = {
        "prices.csv": _source_digest("prices", version),
        "benchmark.csv": _source_digest("benchmark", version),
    }
    panel_manifest = {
        "files": {
            name: {"sha256": digest} for name, digest in panel_hashes.items()
        }
    }
    panel_manifest_raw = _json_bytes(panel_manifest)
    panel_manifest_hash = _sha(panel_manifest_raw)
    (root / "evidence" / "panel-source-manifest.json").write_bytes(panel_manifest_raw)
    stock_summary_hash = _source_digest("stock-summary", version)
    composite_hash = _source_digest("composite-workbook", version)
    daily_pdf_hash = _source_digest("daily-statistics-pdf", version)
    classification_hash = _source_digest("classification", version)
    ownership_source_hash = _source_digest("ownership-source", version)
    ledger_hash = _source_digest("rotation-ledger", version)
    snapshot_provenance_hash = _source_digest("snapshot-provenance", version)
    rotation_validation_hash = _source_digest("rotation-validation", version)

    report = {
        "kind": "PUBLIC_PANEL_VALIDATION",
        "validator_contract": PUBLIC_PANEL_VALIDATION_CONTRACT,
        "input_hashes": {
            "validator_contract": PUBLIC_PANEL_VALIDATION_CONTRACT,
            "panel_files": {
                **panel_hashes,
                "source_manifest.json": panel_manifest_hash,
            },
            "official_sources": {
                "composite_workbook": {
                    "file_name": "composite.xlsx",
                    "sha256": composite_hash,
                },
                "stock_summary": {
                    "file_name": "stock-summary.xlsx",
                    "sha256": stock_summary_hash,
                },
                "daily_statistics_pdfs": {"ds_20261002.pdf": daily_pdf_hash},
            },
        },
        "panel_window": {"start": PREVIOUS_SESSION, "end": TARGET},
        "status": "PASS",
        "checks": {
            "panel_integrity": {
                "status": "PASS",
                "panel_file_hashes_verified": True,
                "latest_session": TARGET,
            },
            "benchmark_vs_official_workbook": {
                "status": "PASS",
                "source": "composite.xlsx",
            },
            "benchmark_vs_daily_statistics_pdfs": {
                "status": "PASS",
                "source": "idx_daily_statistics/ds_*.pdf",
            },
            "stocks_vs_official_stock_summary": {
                "status": "PASS",
                "official_date": TARGET,
                "official_date_matches_panel": True,
                "source": "stock-summary.xlsx",
            },
            "coverage_reconciliation": {"status": "PASS"},
        },
    }
    report_path = root / "evidence" / "panel-validation.json"
    report_raw = _json_bytes(report)
    report_path.write_bytes(report_raw)
    report_hash = _sha(report_raw)

    snapshot = {
        "schema_version": "web-snapshot-v1",
        "snapshot_id": snapshot_id,
        "as_of": TARGET,
        "complete": True,
        "manifest": {
            "provider": "yfinance",
            "provider_mode": "PUBLIC_PROTOTYPE",
            "price_basis": "adjusted_close",
            "entries": [{
                "snapshot_id": snapshot_id,
                "as_of": TARGET,
                "provider": "yfinance",
                "provider_mode": "PUBLIC_PROTOTYPE",
                "price_basis": "adjusted_close",
                "eligible_ticker_set_hash": COHORT_HASH,
            }],
        },
        "groups": [{"group_id": "TEST", "group_name": "Test"}],
        "taxonomy_views": {
            key: {
                "taxonomy_kind": kind,
                "source_snapshot_id": snapshot_id,
                "as_of": TARGET,
                "provider_mode": "PUBLIC_PROTOTYPE",
                "calculation": {"eligible_ticker_set_hash": COHORT_HASH},
                "groups": [],
            }
            for key, kind in (("konglo", "KONGLO"), ("themes", "THEMES"))
        },
    }
    snapshot_raw = _json_bytes(snapshot)
    snapshot_hash = _sha(snapshot_raw)

    market = {
        "schema_version": "market-workspace-v1",
        "snapshot_id": snapshot_id,
        "as_of": TARGET,
        "records": [{"ticker": "AAA.JK", "signal_eligible": True}],
        "benchmark": [
            {"date": PREVIOUS_SESSION, "close": 1000.0},
            {"date": TARGET, "close": 1001.0},
        ],
        "ownership_edges": [],
        "sources": {
            "stock_summary": {
                "file": "stock-summary.xlsx",
                "sha256": stock_summary_hash,
                "as_of": TARGET,
            },
            "classification": {
                "snapshot_id": "classification-test",
                "sha256": classification_hash,
                "as_of": PREVIOUS_SESSION,
            },
            "validated_panel": {
                "files": panel_hashes,
                "validation_sha256": report_hash,
            },
        },
    }
    ownership = {
        "schema_version": "idx-ownership-v1",
        "as_of": "2026-09-30",
        "previous_as_of": "2026-08-31",
        "five_as_of": "2026-10-01",
        "registers": {
            "one": [{"as_of": "2026-09-30", "ticker": "AAA.JK"}],
            "five": [{"as_of": "2026-10-01", "ticker": "AAA.JK"}],
        },
        "sources": [{"sha256": ownership_source_hash}],
    }
    foreign = {
        "schema_version": "idx-foreign-history-v1",
        "as_of": TARGET,
        "validation": {"session_continuity": True, "ytd_continuity": True},
        "daily": [
            {
                "as_of": PREVIOUS_SESSION,
                "net_foreign_value_idr": 10,
                "ytd_net_foreign_value_idr": 90,
            },
            {
                "as_of": TARGET,
                "net_foreign_value_idr": -5,
                "ytd_net_foreign_value_idr": 85,
            },
        ],
    }

    payloads = {
        "snapshot": snapshot,
        "market": market,
        "ownership": ownership,
        "foreign": foreign,
    }
    family_entries = {}
    family_hashes = {}
    for family, payload in payloads.items():
        raw = snapshot_raw if family == "snapshot" else _json_bytes(payload)
        path = root / f"{family}.json"
        path.write_bytes(raw)
        digest = _sha(raw)
        family_hashes[family] = digest
        family_entries[family] = {
            "path": path.name,
            "sha256": digest,
            "bytes": len(raw),
            "schema": payload["schema_version"],
            "observation_date": ownership["as_of"] if family == "ownership" else TARGET,
        }

    rotation = {
        "schema_version": "rotation-history-v1",
        "method": METHOD,
        "snapshot_id": snapshot_id,
        "as_of": TARGET,
        "sessions": [PREVIOUS_SESSION, TARGET],
        "sources": {},
        "taxonomies": {
            "SECTOR": {
                "TEST": {
                    "group_id": "TEST",
                    "name": "Test",
                    "segments": [],
                    "gaps": [],
                    "current_segment_id": None,
                    "daily_available": False,
                    "weekly_available": False,
                }
            },
            "KONGLO": {},
            "THEMES": {},
        },
        "provenance": {
            "ledger_sha256": ledger_hash,
            "snapshot_sha256": snapshot_hash,
            "panel_files": panel_hashes,
            "snapshot_provenance_sha256": snapshot_provenance_hash,
            "validation_sha256": report_hash,
        },
    }
    rotation_raw = _json_bytes(rotation)
    rotation_path = root / "rotation.json"
    rotation_path.write_bytes(rotation_raw)
    family_entries["rotation"] = {
        "path": rotation_path.name,
        "sha256": _sha(rotation_raw),
        "bytes": len(rotation_raw),
        "schema": rotation["schema_version"],
        "observation_date": TARGET,
    }
    family_hashes["rotation"] = _sha(rotation_raw)

    source_specs = [
        ("classification", "classification", classification_hash, None, None),
        ("market_panel_benchmark", "benchmark", panel_hashes["benchmark.csv"], "market_panel_benchmark", "benchmark.csv"),
        ("market_panel_manifest", None, panel_manifest_hash, "market_panel_manifest", "source_manifest.json"),
        ("market_panel_prices", "prices", panel_hashes["prices.csv"], "market_panel_prices", "prices.csv"),
        ("market_panel_validation", None, report_hash, "market_panel_validation", None),
        ("official_composite", "composite-workbook", composite_hash, "official_composite_workbook", "composite.xlsx"),
        ("official_daily_pdf", "daily-statistics-pdf", daily_pdf_hash, "official_daily_statistics_pdf", "ds_20261002.pdf"),
        ("official_stock_summary", "stock-summary", stock_summary_hash, "official_stock_summary", "stock-summary.xlsx"),
        ("ownership_source", "ownership-source", ownership_source_hash, None, None),
        ("rotation_ledger", "rotation-ledger", ledger_hash, None, None),
        ("rotation_validation", "rotation-validation", rotation_validation_hash, None, None),
        ("snapshot_provenance", "snapshot-provenance", snapshot_provenance_hash, None, None),
    ]
    source_evidence = []
    for source_id, label, digest, role, file_name in source_specs:
        if source_id == "market_panel_validation":
            candidate_path = "evidence/panel-validation.json"
        elif source_id == "market_panel_manifest":
            candidate_path = "evidence/panel-source-manifest.json"
        else:
            raw = _source_bytes(label, version)
            assert _sha(raw) == digest
            evidence_path = root / "evidence" / f"{source_id}.bin"
            evidence_path.write_bytes(raw)
            candidate_path = evidence_path.relative_to(root).as_posix()
        row = {
            "source_id": source_id,
            "sha256": digest,
            "candidate_path": candidate_path,
        }
        if role:
            row["role"] = role
        if file_name:
            row["file_name"] = file_name
        source_evidence.append(row)
    source_evidence.sort(key=lambda row: row["source_id"])
    manifest = {
        "schema_version": RELEASE_MANIFEST_SCHEMA,
        "release_id": "",
        "target_session": TARGET,
        "snapshot_identity": {
            "snapshot_id": snapshot_id,
            "provider": "yfinance",
            "provider_mode": "PUBLIC_PROTOTYPE",
            "price_basis": "adjusted_close",
        },
        "analytical_contracts": {"methodology": CONTRACT_HASH},
        "validation": {
            "package_status": "PASS",
            "analytical_status": "PARTIAL",
            "validator_contract": RELEASE_VALIDATOR_CONTRACT,
            "contract_fingerprints": {"methodology": CONTRACT_HASH},
            "evidence_reports": {
                "market_panel": {
                    "status": "PASS",
                    "sha256": report_hash,
                    "contract": PUBLIC_PANEL_VALIDATION_CONTRACT,
                    "input_hashes": report["input_hashes"],
                }
            },
            "input_hashes": {
                "families": family_hashes,
                "additional_files": {},
                "source_evidence": {
                    row["source_id"]: row["sha256"] for row in source_evidence
                },
            },
        },
        "source_evidence": source_evidence,
        "families": family_entries,
        "additional_files": [],
    }
    manifest["release_id"] = calculate_release_id(manifest)
    manifest_path = root / "manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))
    return manifest_path


def add_additional_file(
    manifest_path: Path,
    *,
    file_id: str,
    payload: dict,
    observation_date: str,
) -> None:
    manifest = json.loads(manifest_path.read_text())
    relative_path = f"assets/context/{file_id}.json"
    asset_path = manifest_path.parent / relative_path
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    raw = _json_bytes(payload)
    asset_path.write_bytes(raw)
    digest = _sha(raw)
    manifest["additional_files"] = [{
        "file_id": file_id,
        "family": "snapshot",
        "path": relative_path,
        "sha256": digest,
        "bytes": len(raw),
        "schema": payload["schema_version"],
        "observation_date": observation_date,
    }]
    manifest["validation"]["input_hashes"]["additional_files"] = {file_id: digest}
    manifest["release_id"] = calculate_release_id(manifest)
    manifest_path.write_bytes(_json_bytes(manifest))


def _pointer(public_root: Path) -> dict:
    return json.loads((public_root / "releases" / "active.json").read_text())


def _assert_pointer_release_valid(public_root: Path, pointer: dict, which: str = "active") -> None:
    reference = pointer[which]
    manifest_path = public_root / "releases" / reference["manifest_path"]
    release = validate_manifest_file(
        manifest_path,
        candidate=False,
        expected_release_id=reference["release_id"],
        expected_manifest_sha256=reference["manifest_sha256"],
    )
    assert release.release_id == reference["release_id"]


def test_candidate_activation_publishes_all_five_immutable_families(tmp_path):
    candidate = build_candidate(tmp_path / "candidate")
    public = tmp_path / "public"

    pointer = activate_candidate(candidate, public, expected_active_release_id=None)

    assert pointer["schema_version"] == ACTIVE_POINTER_SCHEMA
    assert pointer["previous"] is None
    assert set(validate_manifest_file(
        public / "releases" / pointer["active"]["manifest_path"],
        candidate=False,
    ).manifest["families"]) == {"snapshot", "market", "ownership", "foreign", "rotation"}
    _assert_pointer_release_valid(public, pointer)
    package = public / "releases" / pointer["active"]["release_id"]
    assert (package / "manifest.json").stat().st_mode & 0o222 == 0
    assert all((package / f"{family}.json").stat().st_mode & 0o222 == 0 for family in (
        "snapshot", "market", "ownership", "foreign", "rotation"
    ))


def test_release_accepts_and_publishes_bounded_context_date_range(tmp_path):
    candidate = build_candidate(tmp_path / "candidate")
    payload = {
        "schema_version": "idx-investor-trading-v1",
        "as_of": {"min": "2026-07-01", "max": "2026-07-31"},
        "daily": [],
    }
    add_additional_file(
        candidate,
        file_id="idx_investor_release",
        payload=payload,
        observation_date="2026-07-31",
    )

    verified = validate_manifest_file(candidate, candidate=True)
    assert verified.additional_paths["idx_investor_release"].is_file()

    pointer = activate_candidate(candidate, tmp_path / "public", expected_active_release_id=None)
    package = tmp_path / "public" / "releases" / pointer["active"]["release_id"]
    published = package / "assets/context/idx_investor_release.json"
    assert json.loads(published.read_text())["as_of"] == {"min": "2026-07-01", "max": "2026-07-31"}


def test_release_rejects_invalid_context_date_range(tmp_path):
    candidate = build_candidate(tmp_path / "candidate")
    add_additional_file(
        candidate,
        file_id="idx_investor_release",
        payload={
            "schema_version": "idx-investor-trading-v1",
            "as_of": {"min": "2026-08-01", "max": "2026-07-31"},
        },
        observation_date="2026-07-31",
    )

    with pytest.raises(ValueError, match="additional file observation date differs"):
        validate_manifest_file(candidate, candidate=True)


def test_refresh_candidate_assembler_revalidates_staged_source_bytes(tmp_path):
    source_manifest_path = build_candidate(tmp_path / "source")
    source_root = source_manifest_path.parent
    source_manifest = validate_manifest_file(source_manifest_path, candidate=True).manifest
    staged_source_rows = json.loads(source_manifest_path.read_text())["source_evidence"]
    panel_report_row = next(row for row in staged_source_rows if row.get("role") == "market_panel_validation")
    panel_report_path = source_root / panel_report_row["candidate_path"]
    staged = tmp_path / "staged"
    staged.mkdir()
    family_sources = staged / "source"
    family_sources.mkdir()
    family_paths = {}
    for family, entry in source_manifest["families"].items():
        source_path = source_root / entry["path"]
        staged_path = family_sources / f"{family}.json"
        staged_path.write_bytes(source_path.read_bytes())
        family_paths[family] = {
            "path": f"{{out_dir}}/source/{family}.json",
            "sha256": entry["sha256"],
            "observation_date": entry["observation_date"],
        }
    staged_report = staged / "source-evidence" / "panel-validation.json"
    staged_report.parent.mkdir()
    staged_report.write_bytes(panel_report_path.read_bytes())
    plan = {
        "target_session": TARGET,
        "snapshot_identity": source_manifest["snapshot_identity"],
        "analytical_contracts": source_manifest["analytical_contracts"],
        "families": family_paths,
        "additional_files": [],
        "source_evidence": [
            {
                **{key: value for key, value in row.items() if key != "candidate_path"},
                "path": (
                    "{out_dir}/source-evidence/panel-validation.json"
                    if row.get("role") == "market_panel_validation"
                    else str(source_root / row["candidate_path"])
                ),
            }
            for row in staged_source_rows
        ],
    }
    manifest_path, report = _build_candidate(plan, staged, tmp_path, TARGET, [])
    validated = validate_manifest_file(manifest_path, candidate=True)
    assert validated.release_id == report["release_id"]
    assert report["package_validity"] == "PASS"
    assert report["publication_readiness"] == "CANDIDATE_READY"
    assert not (tmp_path / "app" / "web" / "public" / "releases" / "active.json").exists()


def test_refresh_release_cli_writes_candidate_without_activating(tmp_path, monkeypatch):
    from scripts import refresh_release

    source_manifest_path = build_candidate(tmp_path / "source")
    source_root = source_manifest_path.parent
    source_doc = json.loads(source_manifest_path.read_text())
    source_manifest = validate_manifest_file(source_manifest_path, candidate=True).manifest
    panel_report_source = next(
        row for row in source_doc["source_evidence"]
        if row.get("role") == "market_panel_validation"
    )
    panel_report_path = source_root / panel_report_source["candidate_path"]
    staging = tmp_path / "staging"
    validation_output = staging / "reports" / "panel-validation.json"
    source_plan = {
        "schema_version": "idx-release-source-plan-v1",
        "target_session": TARGET,
        "snapshot_identity": source_manifest["snapshot_identity"],
        "analytical_contracts": source_manifest["analytical_contracts"],
        "stages": [{
            "name": "panel-validation",
            "module": "scripts.validate_public_panel",
            "args": [
                "--panel-dir", str(staging / "inputs" / "panel"),
                "--target-session", TARGET,
                "--composite-workbook", str(panel_report_path),
                "--stock-summary", str(panel_report_path),
                "--daily-statistics-pdf", str(panel_report_path),
                "--out", "{out_dir}/reports/panel-validation.json",
            ],
            "outputs": ["{out_dir}/reports/panel-validation.json"],
        }],
        "families": {
            family: {
                "path": str(source_root / entry["path"]),
                "sha256": entry["sha256"],
                "observation_date": entry["observation_date"],
            }
            for family, entry in source_manifest["families"].items()
        },
        "additional_files": [],
        "source_evidence": [
            {
                **{key: value for key, value in row.items() if key != "candidate_path"},
                "path": (
                    "{out_dir}/reports/panel-validation.json"
                    if row.get("role") == "market_panel_validation"
                    else str(source_root / row["candidate_path"])
                ),
            }
            for row in source_doc["source_evidence"]
        ],
    }
    plan_path = tmp_path / "source-plan.json"
    plan_path.write_text(json.dumps(source_plan))

    def fake_run(command, *, cwd, capture_output, text):
        args = command[3:]
        output_path = Path(args[args.index("--out") + 1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(panel_report_path.read_bytes())
        receipt_path = Path(args[args.index("--receipt-out") + 1])
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text("{}\n")
        return SimpleNamespace(returncode=0, stdout="PASS", stderr="")

    monkeypatch.setattr(refresh_release.subprocess, "run", fake_run)
    monkeypatch.setattr("sys.argv", [
        "refresh_release",
        "--target-session", TARGET,
        "--sources", str(plan_path),
        "--out-dir", str(staging),
    ])
    active_pointer = Path(__file__).parents[1] / "app" / "web" / "public" / "releases" / "active.json"
    active_before = active_pointer.read_bytes() if active_pointer.exists() else None

    assert refresh_release.main() == 0

    report = json.loads((staging / "refresh-report.json").read_text())
    candidate = validate_manifest_file(staging / "candidate" / "manifest.json", candidate=True)
    assert report["publication_readiness"] == "CANDIDATE_READY"
    assert report["target_session"] == TARGET
    assert report["release_id"] == candidate.release_id
    assert set(report["family_hashes"]) == {"snapshot", "market", "ownership", "foreign", "rotation"}
    active_after = active_pointer.read_bytes() if active_pointer.exists() else None
    assert active_after == active_before


def test_release_id_is_stable_across_staging_roots_for_identical_inputs(tmp_path):
    first = build_candidate(tmp_path / "candidate-a", "same")
    second = build_candidate(tmp_path / "candidate-b", "same")
    first_manifest = json.loads(first.read_text())
    second_manifest = json.loads(second.read_text())

    assert first_manifest["release_id"] == second_manifest["release_id"]


def test_failed_asset_copy_keeps_active_pointer_and_referenced_bytes_unchanged(tmp_path, monkeypatch):
    public = tmp_path / "public"
    first = build_candidate(tmp_path / "candidate-one", "one")
    second = build_candidate(tmp_path / "candidate-two", "two")
    first_pointer = activate_candidate(first, public, expected_active_release_id=None)
    pointer_bytes = (public / "releases" / "active.json").read_bytes()
    active_dir = public / "releases" / first_pointer["active"]["release_id"]
    before = {
        path.relative_to(active_dir).as_posix(): _sha(path.read_bytes())
        for path in active_dir.rglob("*")
        if path.is_file()
    }

    from idx_leadership.data import releases

    original_copy = releases._copy_candidate_file

    def interrupt(source, destination, entry):
        if entry["path"] == "ownership.json":
            raise OSError("injected interruption during asset copy")
        return original_copy(source, destination, entry)

    monkeypatch.setattr(releases, "_copy_candidate_file", interrupt)
    with pytest.raises(OSError, match="injected interruption"):
        activate_candidate(
            second,
            public,
            expected_active_release_id=first_pointer["active"]["release_id"],
        )

    assert (public / "releases" / "active.json").read_bytes() == pointer_bytes
    _assert_pointer_release_valid(public, _pointer(public))
    after = {
        path.relative_to(active_dir).as_posix(): _sha(path.read_bytes())
        for path in active_dir.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not list((public / "releases").glob(".incoming-*"))


def test_interruption_before_pointer_replace_leaves_old_release_selected(tmp_path, monkeypatch):
    public = tmp_path / "public"
    first = build_candidate(tmp_path / "candidate-one", "one")
    second = build_candidate(tmp_path / "candidate-two", "two")
    first_pointer = activate_candidate(first, public, expected_active_release_id=None)
    pointer_path = public / "releases" / "active.json"
    old_pointer = pointer_path.read_bytes()

    from idx_leadership.data import releases

    def fail_before_replace(*_args, **_kwargs):
        raise OSError("injected interruption before active pointer replacement")

    monkeypatch.setattr(releases, "_atomic_pointer_write", fail_before_replace)
    with pytest.raises(OSError, match="before active pointer"):
        activate_candidate(
            second,
            public,
            expected_active_release_id=first_pointer["active"]["release_id"],
        )

    assert pointer_path.read_bytes() == old_pointer
    _assert_pointer_release_valid(public, _pointer(public))


def test_interruption_after_pointer_replace_selects_a_complete_release(tmp_path, monkeypatch):
    public = tmp_path / "public"
    first = build_candidate(tmp_path / "candidate-one", "one")
    second = build_candidate(tmp_path / "candidate-two", "two")
    first_pointer = activate_candidate(first, public, expected_active_release_id=None)

    from idx_leadership.data import releases

    original_write = releases._atomic_pointer_write

    def replace_then_interrupt(root, pointer):
        original_write(root, pointer)
        raise OSError("injected interruption after active pointer replacement")

    monkeypatch.setattr(releases, "_atomic_pointer_write", replace_then_interrupt)
    with pytest.raises(OSError, match="after active pointer"):
        activate_candidate(
            second,
            public,
            expected_active_release_id=first_pointer["active"]["release_id"],
        )

    pointer = _pointer(public)
    assert pointer["previous"]["release_id"] == first_pointer["active"]["release_id"]
    _assert_pointer_release_valid(public, pointer)
    _assert_pointer_release_valid(public, pointer, "previous")


def test_rollback_reverifies_previous_package_and_changes_only_pointer(tmp_path):
    public = tmp_path / "public"
    first = build_candidate(tmp_path / "candidate-one", "one")
    second = build_candidate(tmp_path / "candidate-two", "two")
    first_pointer = activate_candidate(first, public, expected_active_release_id=None)
    first_id = first_pointer["active"]["release_id"]
    first_dir = public / "releases" / first_id
    first_before = {
        path.relative_to(first_dir).as_posix(): _sha(path.read_bytes())
        for path in first_dir.rglob("*")
        if path.is_file()
    }
    second_pointer = activate_candidate(second, public, expected_active_release_id=first_id)
    second_id = second_pointer["active"]["release_id"]
    pointer_path = public / "releases" / "active.json"
    before_pointer_write = pointer_path.read_bytes()

    pointer = rollback_to_previous(
        first_dir / "manifest.json",
        public,
        expected_active_release_id=second_id,
    )

    assert pointer["active"]["release_id"] == first_id
    assert pointer["previous"]["release_id"] == second_id
    assert pointer_path.read_bytes() != before_pointer_write
    _assert_pointer_release_valid(public, pointer)
    _assert_pointer_release_valid(public, pointer, "previous")
    first_after = {
        path.relative_to(first_dir).as_posix(): _sha(path.read_bytes())
        for path in first_dir.rglob("*")
        if path.is_file()
    }
    assert first_after == first_before


def test_stale_expected_active_and_stale_validation_report_are_refused(tmp_path):
    public = tmp_path / "public"
    first = build_candidate(tmp_path / "candidate-one", "one")
    second = build_candidate(tmp_path / "candidate-two", "two")
    first_pointer = activate_candidate(first, public, expected_active_release_id=None)
    pointer_path = public / "releases" / "active.json"
    before = pointer_path.read_bytes()
    with pytest.raises(ValueError, match="stale active release"):
        activate_candidate(second, public, expected_active_release_id=None)
    assert pointer_path.read_bytes() == before

    second_root = second.parent
    report_path = second_root / "evidence" / "panel-validation.json"
    report_path.write_bytes(b'{"status":"PASS"}\n')
    with pytest.raises(ValueError, match="evidence file SHA-256 mismatch"):
        activate_candidate(
            second,
            public,
            expected_active_release_id=first_pointer["active"]["release_id"],
        )
    assert pointer_path.read_bytes() == before
    assert not (public / "releases" / json.loads(second.read_text())["release_id"]).exists()


def test_concurrent_publishers_with_same_expected_pointer_allow_one_activation(tmp_path):
    public = tmp_path / "public"
    candidates = [
        build_candidate(tmp_path / "candidate-one", "one"),
        build_candidate(tmp_path / "candidate-two", "two"),
    ]
    barrier = Barrier(2)

    def publish(candidate):
        barrier.wait(timeout=10)
        try:
            pointer = activate_candidate(
                candidate,
                public,
                expected_active_release_id=None,
            )
        except ValueError as exc:
            return "refused", str(exc)
        return "published", pointer["active"]["release_id"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(publish, candidates))

    published = [value for status, value in outcomes if status == "published"]
    refused = [value for status, value in outcomes if status == "refused"]
    assert len(published) == 1
    assert len(refused) == 1
    assert "stale active release" in refused[0]
    pointer = _pointer(public)
    assert pointer["active"]["release_id"] == published[0]
    assert pointer["previous"] is None
    _assert_pointer_release_valid(public, pointer)


def test_candidate_rejects_unverified_hash_only_source_evidence(tmp_path):
    candidate = build_candidate(tmp_path / "candidate")
    manifest = json.loads(candidate.read_text())
    manifest["source_evidence"][0].pop("candidate_path")
    manifest["release_id"] = calculate_release_id(manifest)
    candidate.write_bytes(_json_bytes(manifest))

    with pytest.raises(ValueError, match="path is required for staged evidence"):
        validate_manifest_file(candidate)


def test_stale_validation_report_inputs_are_refused_even_when_report_hash_matches(tmp_path):
    candidate = build_candidate(tmp_path / "candidate")
    manifest = json.loads(candidate.read_text())
    report_path = candidate.parent / "evidence" / "panel-validation.json"
    report = json.loads(report_path.read_text())
    report["input_hashes"]["panel_files"]["prices.csv"] = "0" * 64
    report_raw = _json_bytes(report)
    report_path.write_bytes(report_raw)
    report_hash = _sha(report_raw)

    market_path = candidate.parent / manifest["families"]["market"]["path"]
    market = json.loads(market_path.read_text())
    market["sources"]["validated_panel"]["validation_sha256"] = report_hash
    market_raw = _json_bytes(market)
    market_path.write_bytes(market_raw)
    market_hash = _sha(market_raw)
    manifest["families"]["market"]["sha256"] = market_hash
    manifest["families"]["market"]["bytes"] = len(market_raw)

    validation_report = manifest["validation"]["evidence_reports"]["market_panel"]
    validation_report["sha256"] = report_hash
    validation_report["input_hashes"] = report["input_hashes"]
    manifest["validation"]["input_hashes"]["families"]["market"] = market_hash
    source_report = next(
        row for row in manifest["source_evidence"]
        if row["source_id"] == "market_panel_validation"
    )
    source_report["sha256"] = report_hash
    manifest["validation"]["input_hashes"]["source_evidence"]["market_panel_validation"] = report_hash
    manifest["release_id"] = calculate_release_id(manifest)
    candidate.write_bytes(_json_bytes(manifest))

    with pytest.raises(ValueError, match="panel validation report hashes differ from the market workspace"):
        validate_manifest_file(candidate)


def test_stale_rotation_snapshot_hash_is_refused_before_activation(tmp_path):
    candidate = build_candidate(tmp_path / "candidate")
    manifest = json.loads(candidate.read_text())
    rotation_path = candidate.parent / manifest["families"]["rotation"]["path"]
    rotation = json.loads(rotation_path.read_text())
    rotation["provenance"]["snapshot_sha256"] = "0" * 64
    rotation_raw = _json_bytes(rotation)
    rotation_path.write_bytes(rotation_raw)
    rotation_entry = manifest["families"]["rotation"]
    rotation_entry["sha256"] = _sha(rotation_raw)
    rotation_entry["bytes"] = len(rotation_raw)
    manifest["validation"]["input_hashes"]["families"]["rotation"] = _sha(rotation_raw)
    manifest["release_id"] = calculate_release_id(manifest)
    candidate.write_bytes(_json_bytes(manifest))

    public = tmp_path / "public"
    with pytest.raises(ValueError, match="rotation endpoint snapshot hash is stale"):
        activate_candidate(candidate, public, expected_active_release_id=None)
    assert not (public / "releases" / "active.json").exists()


def test_tampered_previous_package_blocks_rollback_without_changing_active_pointer(tmp_path):
    public = tmp_path / "public"
    first = build_candidate(tmp_path / "candidate-one", "one")
    second = build_candidate(tmp_path / "candidate-two", "two")
    activate_candidate(first, public, expected_active_release_id=None)
    second_pointer = activate_candidate(
        second,
        public,
        expected_active_release_id=json.loads(first.read_text())["release_id"],
    )
    pointer_path = public / "releases" / "active.json"
    pointer_before = pointer_path.read_bytes()
    previous_id = second_pointer["previous"]["release_id"]
    previous_dir = public / "releases" / previous_id
    tampered = previous_dir / "market.json"
    tampered.chmod(0o644)
    tampered.write_bytes(tampered.read_bytes() + b" ")

    with pytest.raises(ValueError, match="mismatch"):
        rollback_to_previous(
            previous_dir / "manifest.json",
            public,
            expected_active_release_id=second_pointer["active"]["release_id"],
        )
    assert pointer_path.read_bytes() == pointer_before
    _assert_pointer_release_valid(public, _pointer(public))


def test_release_manifest_rejects_nonfinite_json_and_mutable_alias_paths(tmp_path):
    candidate = build_candidate(tmp_path / "candidate")
    manifest = json.loads(candidate.read_text())
    manifest["families"]["market"]["path"] = "market/index.json"
    manifest["release_id"] = calculate_release_id(manifest)
    candidate.write_bytes(_json_bytes(manifest))
    with pytest.raises(ValueError, match="mutable alias"):
        validate_manifest_file(candidate)

    candidate = build_candidate(tmp_path / "candidate-nan")
    raw = candidate.read_bytes().replace(b'"PARTIAL"', b'"PARTIAL","unused":NaN')
    candidate.write_bytes(raw)
    with pytest.raises(ValueError, match="nonfinite JSON"):
        validate_manifest_file(candidate)


@pytest.mark.parametrize("defect", ["missing", "empty", "wrong_schema"])
def test_invalid_family_asset_cannot_replace_the_active_release(tmp_path, defect):
    public = tmp_path / "public"
    active_candidate = build_candidate(tmp_path / "active", "active")
    active_pointer = activate_candidate(active_candidate, public, expected_active_release_id=None)
    candidate = build_candidate(tmp_path / "candidate", "invalid")
    pointer_path = public / "releases" / "active.json"
    pointer_before = pointer_path.read_bytes()
    manifest = json.loads(candidate.read_text())
    entry = manifest["families"]["market"]
    asset_path = candidate.parent / entry["path"]

    if defect == "missing":
        asset_path.unlink()
    elif defect == "empty":
        asset_path.write_bytes(b"")
    else:
        market = json.loads(asset_path.read_text())
        market["schema_version"] = "unsupported-market-schema-v1"
        raw = _json_bytes(market)
        asset_path.write_bytes(raw)
        entry["bytes"] = len(raw)
        entry["sha256"] = _sha(raw)
        manifest["validation"]["input_hashes"]["families"]["market"] = entry["sha256"]
        manifest["release_id"] = calculate_release_id(manifest)
        candidate.write_bytes(_json_bytes(manifest))

    with pytest.raises((OSError, ValueError)):
        activate_candidate(
            candidate,
            public,
            expected_active_release_id=active_pointer["active"]["release_id"],
        )

    assert pointer_path.read_bytes() == pointer_before
    _assert_pointer_release_valid(public, _pointer(public))
    rejected_id = json.loads(candidate.read_text())["release_id"]
    assert not (public / "releases" / rejected_id).exists()
