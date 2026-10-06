"""Build an offline, explicit-session five-family release candidate.

The source plan pins exact inputs and a sequence of existing offline tools.
All declared outputs must stay under the caller's staging directory; this
command never switches the served active pointer.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from idx_leadership.data.releases import (
    RELEASE_MANIFEST_SCHEMA,
    RELEASE_VALIDATOR_CONTRACT,
    REQUIRED_FAMILIES,
    _read_active_pointer,
    _payload_matches_observation_date,
    canonical_json_bytes,
    calculate_release_id,
    validate_manifest_file,
)
from idx_leadership.utils.config import project_root


SOURCE_PLAN_SCHEMA = "idx-release-source-plan-v1"
FAMILY_SCHEMAS = {
    "snapshot": "web-snapshot-v1",
    "market": "market-workspace-v1",
    "ownership": "idx-ownership-v1",
    "foreign": "idx-foreign-history-v1",
    "rotation": "rotation-history-v1",
}
SAFE_STAGES = {
    "scripts.prepare_market_universe",
    "scripts.export_ownership",
    "scripts.prepare_market_catalogs",
    "scripts.validate_public_panel",
    "scripts.build_snapshot_chain",
    "scripts.build_taxonomy_views",
    "scripts.export_market_workspace",
    "scripts.export_foreign_history",
    "scripts.build_rotation_replay",
    "scripts.export_snapshot_json",
}
FORBIDDEN_FLAGS = {
    "--latest", "--force-rebuild", "--publish-root", "--publish",
    "--allow-credit-spend", "--max-estimated-credits", "--live",
}
OUTPUT_FLAGS = {
    "--universe-out", "--daily-out", "--out-dir", "--edges-out", "--out",
    "--snapshots-root", "--report", "--receipt-out",
}
REQUIRED_STAGE_FLAGS = {
    "scripts.prepare_market_universe": {"--stock-summary", "--classification-bundle", "--as-of", "--universe-out", "--daily-out"},
    "scripts.export_ownership": {"--current", "--previous", "--five", "--out"},
    "scripts.prepare_market_catalogs": {"--universe", "--ownership", "--rules", "--out-dir", "--edges-out"},
    "scripts.validate_public_panel": {"--panel-dir", "--target-session", "--composite-workbook", "--stock-summary", "--daily-statistics-pdf", "--out"},
    "scripts.build_snapshot_chain": {"--panel-dir", "--asofs", "--snapshots-root", "--report"},
    "scripts.build_taxonomy_views": {"--snapshot-id", "--snapshot-root", "--out-dir"},
    "scripts.export_market_workspace": {"--daily", "--panel-dir", "--validation", "--snapshot-dir", "--edges", "--universe", "--out"},
    "scripts.export_foreign_history": {"--pdf-root", "--source-list", "--benchmark", "--out"},
    "scripts.build_rotation_replay": {"--ledger", "--source-root", "--panel", "--validation", "--snapshot", "--snapshot-provenance", "--out"},
    "scripts.export_snapshot_json": {"--snapshot-id", "--snapshot-root", "--out"},
}


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path, label: str) -> Any:
    def no_constant(value: str) -> None:
        raise ValueError(f"{label} contains nonfinite JSON value {value}")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"{label} contains duplicate JSON key {key}")
            value[key] = item
        return value

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=no_constant, object_pairs_hook=unique)


def _strict_date(raw: Any, label: str) -> str:
    if not isinstance(raw, str) or date.fromisoformat(raw).isoformat() != raw:
        raise ValueError(f"{label} must use strict YYYY-MM-DD form")
    return raw


def _within(path: Path, root: Path, label: str) -> Path:
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} must stay inside the staging directory")
    return resolved


def _source_path(raw: Any, *, root: Path, label: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError(f"{label} must be an explicit local file path")
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file")
    return resolved


def _expand(raw: str, context: dict[str, str]) -> str:
    pattern = re.compile(r"\{([a-z_]+(?::[A-Za-z0-9._-]+)?)\}")
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise ValueError(f"source plan uses unknown placeholder {{{key}}}")
        return context[key]
    return pattern.sub(replace, raw)


def _run_stages(plan: dict[str, Any], out_dir: Path, target: str, project: Path) -> list[dict[str, Any]]:
    stages = plan.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("source plan must provide ordered offline stages")
    context = {"out_dir": str(out_dir.resolve()), "project_root": str(project), "target_session": target}
    for source in plan.get("source_evidence", []):
        if isinstance(source, dict) and isinstance(source.get("source_id"), str) and isinstance(source.get("path"), str):
            raw_path = Path(_expand(source["path"], context))
            if not raw_path.is_absolute():
                raw_path = project / raw_path
            if raw_path.is_file():
                context[f"source:{source['source_id']}"] = str(raw_path.resolve())

    results = []
    validation_ran = False
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict) or set(stage) != {"name", "module", "args", "outputs"}:
            raise ValueError(f"stage {index} must contain name, module, args and outputs")
        name, module = stage["name"], stage["module"]
        if not isinstance(name, str) or not name or not isinstance(module, str) or module not in SAFE_STAGES:
            raise ValueError(f"stage {index} is unnamed or uses an unsupported tool")
        if not isinstance(stage["args"], list) or any(not isinstance(value, str) for value in stage["args"]):
            raise ValueError(f"stage {name} args must be a string list")
        args = [_expand(value, context) for value in stage["args"]]
        if any(arg.split("=", 1)[0] in FORBIDDEN_FLAGS for arg in args):
            raise ValueError(f"stage {name} contains a publication, live, latest or credit-spend flag")
        flags = {arg.split("=", 1)[0] for arg in args if arg.startswith("--")}
        missing = REQUIRED_STAGE_FLAGS[module] - flags
        if missing:
            raise ValueError(f"stage {name} is missing explicit arguments: {', '.join(sorted(missing))}")
        if module == "scripts.validate_public_panel" and "--no-publish-fixture" not in args:
            args.append("--no-publish-fixture")
        if module == "scripts.validate_public_panel":
            validation_ran = True
            target_value = next((args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--target-session"), None)
            if target_value != target:
                raise ValueError(f"stage {name} target session must match {target}")
            if "--receipt-out" not in args and not any(arg.startswith("--receipt-out=") for arg in args):
                args.extend(["--receipt-out", str(out_dir / "run-receipts" / f"{name}.json")])
        if module == "scripts.export_snapshot_json" and "--allow-outside-root" not in args:
            args.append("--allow-outside-root")

        for offset, arg in enumerate(args):
            flag = arg.split("=", 1)[0]
            if flag in OUTPUT_FLAGS:
                if "=" not in arg and offset + 1 >= len(args):
                    raise ValueError(f"stage {name} output flag {flag} has no value")
                value = arg.partition("=")[2] if "=" in arg else args[offset + 1]
                _within(Path(value), out_dir, f"stage {name} output {flag}")
        expected = stage["outputs"]
        if not isinstance(expected, list) or not expected:
            raise ValueError(f"stage {name} must declare its expected outputs")
        expected_paths = [_within(Path(_expand(value, context)), out_dir, f"stage {name} output") for value in expected]
        completed = subprocess.run([sys.executable, "-m", module, *args], cwd=project, capture_output=True, text=True)
        output_hashes = {}
        for output in expected_paths:
            if not output.is_file():
                raise ValueError(f"stage {name} did not produce required output {output.relative_to(out_dir)}")
            output_hashes[output.relative_to(out_dir).as_posix()] = _sha256(output.read_bytes())
        result = {"name": name, "module": module, "exit_code": completed.returncode, "outputs": output_hashes}
        results.append(result)
        if completed.returncode:
            detail = (completed.stderr or completed.stdout)[-3000:]
            raise ValueError(f"stage {name} failed ({completed.returncode}): {detail.strip()}")
    if not validation_ran:
        raise ValueError("source plan must run scripts.validate_public_panel for the explicit target session")
    return results


def _copy_verified(source: Path, destination: Path, expected_hash: str) -> tuple[int, str]:
    raw = source.read_bytes()
    digest = _sha256(raw)
    if digest != expected_hash:
        raise ValueError(f"input changed or has a stale SHA-256: {source.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return len(raw), digest


def _build_candidate(plan: dict[str, Any], out_dir: Path, project: Path, target: str, stages: list[dict[str, Any]]) -> tuple[Path, dict[str, Any]]:
    path_context = {
        "out_dir": str(out_dir.resolve()),
        "project_root": str(project.resolve()),
        "target_session": target,
    }
    families_input = plan.get("families")
    if not isinstance(families_input, dict) or set(families_input) != set(REQUIRED_FAMILIES):
        raise ValueError("source plan must pin exactly all five family artifacts")
    families: dict[str, dict[str, Any]] = {}
    payloads = {}
    for family in REQUIRED_FAMILIES:
        item = families_input[family]
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "observation_date"}:
            raise ValueError(f"source plan family {family} needs path, sha256 and observation_date")
        source_name = item["path"]
        if not isinstance(source_name, str):
            raise ValueError(f"source plan {family} path must be a string")
        source_path = _source_path(_expand(source_name, path_context), root=project, label=f"{family} family")
        expected_date = _strict_date(item["observation_date"], f"{family}.observation_date")
        raw = source_path.read_bytes()
        if _sha256(raw) != item["sha256"]:
            raise ValueError(f"source plan {family} SHA-256 is stale")
        payload = _json(source_path, f"{family} family")
        if not isinstance(payload, dict) or payload.get("schema_version") != FAMILY_SCHEMAS[family] or payload.get("as_of") != expected_date:
            raise ValueError(f"source plan {family} schema or observation date mismatch")
        if family in {"snapshot", "market", "foreign", "rotation"} and expected_date != target:
            raise ValueError(f"{family} family does not reach explicit target session {target}")
        destination = out_dir / "candidate" / "assets" / f"{family}.json"
        size, digest = _copy_verified(source_path, destination, item["sha256"])
        entry = {"path": f"assets/{family}.json", "sha256": digest, "bytes": size,
                 "schema": FAMILY_SCHEMAS[family], "observation_date": expected_date}
        families[family] = entry
        payloads[family] = payload

    additional_files = []
    for item in plan.get("additional_files", []):
        if not isinstance(item, dict) or set(item) != {"file_id", "path", "sha256", "schema", "observation_date"}:
            raise ValueError("additional files need file_id, path, sha256, schema and observation_date")
        file_id = item["file_id"]
        if not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", file_id):
            raise ValueError("additional file ID is invalid")
        source_name = item["path"]
        if not isinstance(source_name, str):
            raise ValueError(f"additional file {file_id} path must be a string")
        source_path = _source_path(_expand(source_name, path_context), root=project, label=f"additional file {file_id}")
        payload = _json(source_path, f"additional file {file_id}")
        observed = _strict_date(item["observation_date"], f"additional file {file_id} observation date")
        if payload.get("schema_version") != item["schema"] or not _payload_matches_observation_date(payload, observed):
            raise ValueError(f"additional file {file_id} schema or date mismatch")
        destination = out_dir / "candidate" / "assets" / "context" / f"{file_id}.json"
        size, digest = _copy_verified(source_path, destination, item["sha256"])
        additional_files.append({"file_id": file_id, "family": "snapshot", "path": f"assets/context/{file_id}.json",
                                 "sha256": digest, "bytes": size, "schema": item["schema"], "observation_date": observed})

    source_evidence = []
    source_ids = set()
    for index, item in enumerate(plan.get("source_evidence", [])):
        if not isinstance(item, dict) or "path" not in item or "candidate_path" in item:
            raise ValueError(f"source evidence {index} needs an input path and must not set candidate_path")
        source_id = item.get("source_id")
        if not isinstance(source_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", source_id) or source_id in source_ids:
            raise ValueError("source evidence IDs must be unique and filename-safe")
        source_ids.add(source_id)
        expected_hash = item.get("sha256")
        source_name = item["path"]
        if not isinstance(source_name, str):
            raise ValueError(f"source evidence {source_id} path must be a string")
        source_path = _source_path(_expand(source_name, path_context), root=project, label=f"source evidence {source_id}")
        evidence_path = out_dir / "candidate" / "evidence" / f"{source_id}{source_path.suffix.lower()}"
        size, digest = _copy_verified(source_path, evidence_path, expected_hash)
        metadata = {key: value for key, value in item.items() if key not in {"path", "sha256"}}
        metadata.update({"source_id": source_id, "sha256": digest, "candidate_path": evidence_path.relative_to(out_dir / "candidate").as_posix()})
        source_evidence.append(metadata)
    source_evidence.sort(key=lambda row: row["source_id"])

    if not isinstance(plan.get("snapshot_identity"), dict) or not isinstance(plan.get("analytical_contracts"), dict):
        raise ValueError("source plan must pin snapshot_identity and analytical_contracts")
    panel_rows = [row for row in source_evidence if row.get("role") == "market_panel_validation"]
    if len(panel_rows) != 1:
        raise ValueError("source inventory must contain exactly one market_panel_validation report")
    report_row = panel_rows[0]
    panel_report_path = out_dir / "candidate" / report_row["candidate_path"]
    panel_report = _json(panel_report_path, "public-panel validation report")
    if panel_report.get("status") != "PASS" or panel_report.get("validator_contract") != "public-panel-validation-v2":
        raise ValueError("public-panel validation report is not a current PASS")

    input_hashes = {
        "families": {name: families[name]["sha256"] for name in sorted(families)},
        "additional_files": {row["file_id"]: row["sha256"] for row in sorted(additional_files, key=lambda entry: entry["file_id"])},
        "source_evidence": {row["source_id"]: row["sha256"] for row in source_evidence},
    }
    validation = {
        "package_status": "PASS",
        "analytical_status": "COVERAGE_REPORTED_IN_FAMILY_ASSETS",
        "validator_contract": RELEASE_VALIDATOR_CONTRACT,
        "contract_fingerprints": plan["analytical_contracts"],
        "input_hashes": input_hashes,
        "evidence_reports": {
            "market_panel": {
                "status": "PASS", "sha256": report_row["sha256"],
                "contract": panel_report["validator_contract"], "input_hashes": panel_report["input_hashes"],
            }
        },
    }
    manifest = {
        "schema_version": RELEASE_MANIFEST_SCHEMA,
        "release_id": "",
        "target_session": target,
        "snapshot_identity": plan["snapshot_identity"],
        "analytical_contracts": plan["analytical_contracts"],
        "validation": validation,
        "source_evidence": source_evidence,
        "families": families,
        "additional_files": sorted(additional_files, key=lambda row: row["file_id"]),
    }
    manifest["release_id"] = calculate_release_id(manifest)
    candidate_root = out_dir / "candidate"
    manifest_path = candidate_root / "manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    verified = validate_manifest_file(manifest_path, candidate=True)
    releases_root = project / "app" / "web" / "public" / "releases"
    _, active, _ = _read_active_pointer(releases_root)
    expected_active = active.release_id if active else "none"
    report = {
        "schema_version": "idx-release-refresh-report-v1",
        "requested_calendar_date": plan.get("requested_calendar_date"),
        "target_session": target,
        "target_session_proof": {"market_benchmark_latest": max(row["date"] for row in payloads["market"].get("benchmark", []))},
        "stages": stages,
        "sources": [{key: row.get(key) for key in ("source_id", "role", "file_name", "sha256", "observation_date", "published_on", "available_on", "retrieved_at")} for row in source_evidence],
        "family_hashes": {name: families[name]["sha256"] for name in REQUIRED_FAMILIES},
        "coverage": {
            "market": payloads["market"].get("coverage"),
            "ownership": payloads["ownership"].get("coverage"),
            "foreign": {"start": payloads["foreign"].get("start"), "sessions": len(payloads["foreign"].get("daily", []))},
            "rotation": payloads["rotation"].get("coverage"),
        },
        "package_validity": "PASS",
        "analytical_readiness": validation["analytical_status"],
        "publication_readiness": "CANDIDATE_READY",
        "release_id": verified.release_id,
        "manifest_sha256": verified.manifest_sha256,
        "publication_command": f".venv/bin/python -m scripts.publish_release --candidate <candidate-manifest-path> --expect-active {expected_active}",
        "manifest_path": "candidate/manifest.json",
        "blocking_reasons": [],
    }
    return manifest_path, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-session", required=True)
    parser.add_argument("--sources", required=True, type=Path, help="hash-pinned idx-release-source-plan-v1 JSON")
    parser.add_argument("--out-dir", required=True, type=Path, help="new staging directory outside served and historical roots")
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()
    project = project_root().resolve()
    write_root: Path | None = None
    report: dict[str, Any] = {"schema_version": "idx-release-refresh-report-v1", "target_session": args.target_session,
                              "publication_readiness": "BLOCKED", "blocking_reasons": []}
    try:
        target = _strict_date(args.target_session, "--target-session")
        temporary_roots = {Path(tempfile.gettempdir()).resolve(), Path("/private/tmp").resolve()}
        project_staging = project / "data" / "staging"
        if not out_dir.is_relative_to(project_staging) and not any(out_dir.is_relative_to(root) for root in temporary_roots):
            raise ValueError("staging directory must be under data/staging or the system temporary directory")
        forbidden_roots = [project / "app" / "web" / "public", project / "data" / "snapshots", project / "tests" / "fixtures"]
        if any(out_dir == root or out_dir.is_relative_to(root) for root in forbidden_roots):
            raise ValueError("staging directory overlaps served files, canonical history or tracked fixtures")
        if out_dir.exists() and any(out_dir.iterdir()):
            raise ValueError("staging directory must be new or empty; existing outputs are never overwritten")
        out_dir.mkdir(parents=True, exist_ok=True)
        write_root = out_dir
        plan_path = _source_path(str(args.sources), root=project, label="source plan")
        plan = _json(plan_path, "source plan")
        if not isinstance(plan, dict) or plan.get("schema_version") != SOURCE_PLAN_SCHEMA:
            raise ValueError(f"source plan schema must be {SOURCE_PLAN_SCHEMA}")
        if _strict_date(plan.get("target_session"), "source plan target_session") != target:
            raise ValueError("source plan target session differs from the required CLI target")
        if plan.get("requested_calendar_date") is not None:
            _strict_date(plan["requested_calendar_date"], "requested_calendar_date")
        stages = _run_stages(plan, out_dir, target, project)
        manifest_path, report = _build_candidate(plan, out_dir, project, target, stages)
        report["requested_calendar_date"] = plan.get("requested_calendar_date")
        status = 0
    except Exception as exc:
        report.setdefault("blocking_reasons", []).append(str(exc))
        report["package_validity"] = "BLOCKED"
        report["publication_readiness"] = "BLOCKED"
        status = 1
    if write_root is None:
        write_root = Path(tempfile.mkdtemp(prefix="idx-release-refresh-blocked-"))
    report_path = write_root / "refresh-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    summary_path = write_root / "refresh-report.md"
    summary_path.write_text(
        "# Release refresh report\n\n"
        f"- Target session: {report.get('target_session')}\n"
        f"- Package validity: {report.get('package_validity', 'BLOCKED')}\n"
        f"- Publication readiness: {report.get('publication_readiness')}\n"
        f"- Release ID: {report.get('release_id', 'none')}\n\n"
        + ("\n".join(f"- Blocked: {reason}" for reason in report.get("blocking_reasons", [])) or "Candidate is ready for review.\n"),
        encoding="utf-8",
    )
    receipt = {
        "schema_version": "idx-release-refresh-receipt-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_plan": str(args.sources.resolve()),
        "staging_directory": str(write_root),
        "publication_command": report.get("publication_command"),
    }
    (write_root / "run-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"publication_readiness": report["publication_readiness"],
                      "release_id": report.get("release_id"), "report": str(report_path),
                      "manifest": report.get("manifest_path"), "blocking_reasons": report.get("blocking_reasons", [])}, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
