"""Create a successor release with frozen Sectors lineage and analysis assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Any

from idx_leadership.data.releases import (
    calculate_release_id,
    canonical_json_bytes,
    validate_manifest_file,
)
try:
    from scripts.build_sectors_analysis import HORIZONS, MINIMUM_CONTRIBUTORS, SCHEMA, build
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from build_sectors_analysis import HORIZONS, MINIMUM_CONTRIBUTORS, SCHEMA, build


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _link_or_copy(source: str, destination: str) -> str:
    try:
        os.link(source, destination)
        return destination
    except OSError:
        shutil.copy2(source, destination)
        return destination


def _copy_candidate(base: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"successor candidate destination already exists: {destination}")
    shutil.copytree(base, destination, copy_function=_link_or_copy)
    for path in (destination, *destination.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)


def _entry(*, file_id: str, relative_path: str, raw: bytes, schema: str, observation_date: str) -> dict[str, Any]:
    return {
        "file_id": file_id,
        "family": "snapshot",
        "path": relative_path,
        "sha256": _sha(raw),
        "bytes": len(raw),
        "schema": schema,
        "observation_date": observation_date,
    }


def extend(
    *,
    base_manifest_path: Path,
    out_dir: Path,
    run_dir: Path,
    selection_market_path: Path,
    ytd_baseline_path: Path | None = None,
) -> dict[str, Any]:
    base_manifest_path = base_manifest_path.resolve(strict=True)
    base = validate_manifest_file(base_manifest_path, candidate=True)
    run_dir = run_dir.resolve(strict=True)
    selection_market_path = selection_market_path.resolve(strict=True)
    receipt = json.loads((run_dir / "run_receipt.json").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "recording_manifest.json").read_text(encoding="utf-8"))
    raw_sample = (run_dir / "sectors_recorded_sample.json").read_bytes()
    source_sample = json.loads(raw_sample)
    if receipt.get("status") != "ACQUISITIONS_VALIDATED":
        raise ValueError("the original Sectors recording is not validated")
    if receipt.get("run_id") != plan.get("run_id") or receipt.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError("the Sectors recording receipt does not match its frozen plan")
    if receipt.get("sample_sha256") != _sha(raw_sample):
        raise ValueError("the original recorded sample hash differs from its persistent receipt")
    inherited_budget = receipt.get("request_budget") or {}
    if (inherited_budget.get("max_requests") != 450 or inherited_budget.get("max_credits") != 450
            or inherited_budget.get("requests_reserved", 451) > 450
            or inherited_budget.get("credits_reserved", 451) > 450):
        raise ValueError("the original recording exceeded its historical 450-call/credit ceiling")

    market_raw = selection_market_path.read_bytes()
    market = json.loads(market_raw)
    market_hash = _sha(market_raw)
    if market_hash != plan.get("market_release_source", {}).get("sha256"):
        raise ValueError("frozen selection-market bytes do not match the original plan")
    if market_hash != source_sample.get("sources", {}).get("market_release_source_sha256"):
        raise ValueError("original sample does not point to the supplied frozen selection-market source")

    destination = Path(out_dir).resolve()
    _copy_candidate(base.root, destination)
    candidate_manifest = destination / "manifest.json"
    manifest = json.loads(candidate_manifest.read_text(encoding="utf-8"))
    existing_entries = {row["file_id"]: row for row in manifest.get("additional_files", [])}
    if "sectors_recorded_sample" not in existing_entries:
        raise ValueError("base release must already contain the verified Sectors recorded sample")
    sample_entry = existing_entries["sectors_recorded_sample"]
    sample_path = destination / sample_entry["path"]
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    if (sample.get("sources", {}).get("market_release_source_sha256") != market_hash
            or sample.get("selection", {}).get("membership_release_id") != plan.get("selection_release_id")):
        raise ValueError("base release sample does not match the original recording lineage")
    source_roster = {(row["ticker"], row["sector"]) for row in source_sample["stocks"]}
    package_roster = {(row["ticker"], row["sector"]) for row in sample["stocks"]}
    if source_roster != package_roster:
        raise ValueError("base release sample membership differs from the original acquisition")

    selection_relative = "assets/context/sectors_selection_market.json"
    existing_selection = existing_entries.get("sectors_selection_market")
    if existing_selection and existing_selection["sha256"] != market_hash:
        raise ValueError("base release binds another frozen selection-market source")
    if existing_selection:
        selection_relative = existing_selection["path"]
    selection_destination = destination / selection_relative
    _atomic_write(selection_destination, market_raw)
    selection_entry = _entry(
        file_id="sectors_selection_market",
        relative_path=selection_relative,
        raw=market_raw,
        schema="market-workspace-v1",
        observation_date=str(market["as_of"]),
    )
    entries = [selection_entry]

    existing_ytd = existing_entries.get("sectors_ytd_baseline")
    ytd_relative = existing_ytd["path"] if existing_ytd else None
    if ytd_baseline_path is not None:
        ytd_raw = ytd_baseline_path.resolve(strict=True).read_bytes()
        ytd_payload = json.loads(ytd_raw)
        if ytd_payload.get("schema_version") != "sectors-ytd-baseline-v1" or ytd_payload.get("as_of") != sample["as_of"]:
            raise ValueError("YTD baseline asset schema or sample end date is invalid")
        ytd_relative = "assets/context/sectors_ytd_baseline.json"
        _atomic_write(destination / ytd_relative, ytd_raw)
        entries.append(_entry(file_id="sectors_ytd_baseline", relative_path=ytd_relative, raw=ytd_raw,
                              schema="sectors-ytd-baseline-v1", observation_date=sample["as_of"]))
    elif existing_ytd:
        ytd_relative = existing_ytd["path"]
        entries.append(existing_ytd)

    existing_analysis = existing_entries.get("sectors_signal_analysis")
    analysis_relative = (existing_analysis["path"] if existing_analysis
                         else "assets/context/sectors_signal_analysis.json")
    with tempfile.TemporaryDirectory(prefix="sectors-analysis-build-") as temporary:
        analysis_work_path = Path(temporary) / "sectors_signal_analysis.json"
        analysis_result = build(
            sample_path=sample_path,
            selection_market_path=selection_destination,
            selection_plan_path=run_dir / "recording_manifest.json",
            ytd_baseline_path=(destination / ytd_relative) if ytd_relative else None,
            out=analysis_work_path,
        )
        analysis_raw = analysis_work_path.read_bytes()
    _atomic_write(destination / analysis_relative, analysis_raw)
    entries.append(_entry(file_id="sectors_signal_analysis", relative_path=analysis_relative,
                          raw=analysis_raw, schema=SCHEMA, observation_date=sample["as_of"]))
    manifest["additional_files"] = [
        row for row in manifest["additional_files"]
        if row["file_id"] not in {"sectors_selection_market", "sectors_ytd_baseline", "sectors_signal_analysis"}
    ]
    manifest["additional_files"].extend(entries)
    manifest["additional_files"].sort(key=lambda row: row["file_id"])

    analysis_contract = {
        "schema": SCHEMA,
        "horizons_sessions": HORIZONS,
        "minimum_contributors": MINIMUM_CONTRIBUTORS,
        "price_basis": "raw Sectors daily close",
        "benchmark": "native Sectors IHSG close",
        "comparison": "paired-date intersection of valid members from the fixed 66-name sample",
        "actions": sorted({"split", "rights_issue", "bonus", "dividend", "other mechanical price changes"}),
    }
    manifest["analytical_contracts"]["sectors_signal_analysis"] = _sha(canonical_json_bytes(analysis_contract))
    manifest["analytical_contracts"]["sectors_selection_market"] = market_hash
    manifest["validation"]["contract_fingerprints"] = manifest["analytical_contracts"]
    manifest["validation"]["input_hashes"]["additional_files"] = {
        row["file_id"]: row["sha256"] for row in manifest["additional_files"]
    }
    manifest["validation"]["analytical_status"] = "SECTORS_SIGNAL_ANALYSIS_PASS"
    manifest["release_id"] = ""
    manifest["release_id"] = calculate_release_id(manifest)
    _atomic_write(candidate_manifest, canonical_json_bytes(manifest) + b"\n")
    verified = validate_manifest_file(candidate_manifest, candidate=True)
    return {
        "status": "PASS",
        "parent_release_id": base.release_id,
        "release_id": verified.release_id,
        "manifest_sha256": verified.manifest_sha256,
        "recorded_sample_sha256": sample_entry["sha256"],
        "selection_market_sha256": market_hash,
        "analysis_sha256": _sha(analysis_raw),
        "analysis_bytes": len(analysis_raw),
        "ytd_baseline_sha256": next((row["sha256"] for row in entries if row["file_id"] == "sectors_ytd_baseline"), None),
        "analysis_summary": analysis_result,
        "candidate_manifest": str(candidate_manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-candidate-manifest", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--selection-market", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--ytd-baseline", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(extend(base_manifest_path=args.base_candidate_manifest,
                                run_dir=args.run_dir,
                                selection_market_path=args.selection_market,
                                out_dir=args.out_dir,
                                ytd_baseline_path=args.ytd_baseline), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SECTORS_RELEASE_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
