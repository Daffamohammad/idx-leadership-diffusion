"""Build a source-gated, chart-only rotation asset.

Run with --help. All paths in the source ledger are relative to --source-root.
Outputs are separate from historical snapshots. Publication is handled only by
the complete five-family release publisher. No network requests are made.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from idx_leadership.data.rotation_replay import KINDS, endpoints_from_snapshot, replay, validate_asset
from idx_leadership.providers.public import YFinanceProvider
from idx_leadership.providers.idx_statistics import write_json_atomic
from scripts.validate_public_panel import _check_panel_integrity


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified_acquisition_records(ledger: dict, source_root: Path, paths: dict[str, Path]) -> dict[str, dict]:
    sources = ledger.get("sources", {})
    acquisition_ids = [row.get("acquisition_id") for row in sources.values() if row.get("acquisition_id")]
    if not acquisition_ids:
        return {}
    if len(acquisition_ids) != len(set(acquisition_ids)):
        raise ValueError("acquisition IDs must be unique in the rotation source ledger")
    inventory_name = ledger.get("acquisition_inventory")
    if not isinstance(inventory_name, str) or not inventory_name or "\\" in inventory_name:
        raise ValueError("acquisition_inventory path is required for captured source evidence")
    inventory_path = (source_root / inventory_name).resolve(strict=True)
    if not inventory_path.is_relative_to(source_root.resolve()) or not inventory_path.is_file():
        raise ValueError("acquisition inventory path escapes the source root")
    records: dict[str, dict] = {}
    for line_number, line in enumerate(inventory_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"acquisition inventory line {line_number} is invalid JSON") from exc
        acquisition_id = row.get("acquisition_id") if isinstance(row, dict) else None
        if not isinstance(row, dict) or row.get("schema_version") != "idx-acquisition-inventory-v1" or not isinstance(acquisition_id, str) or acquisition_id in records:
            raise ValueError(f"acquisition inventory line {line_number} has an invalid or duplicate ID")
        captured = row.get("captured_file") or {}
        if (
            not isinstance(captured, dict)
            or not isinstance(captured.get("path"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(captured.get("sha256", "")))
            or not isinstance(captured.get("bytes"), int)
            or captured.get("hash_scope") != "captured_file_bytes"
        ):
            raise ValueError(f"acquisition inventory line {line_number} has malformed captured-file metadata")
        try:
            retrieved = datetime.fromisoformat(str(row.get("retrieved_at")).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"acquisition inventory line {line_number} has an invalid retrieval timestamp") from exc
        if retrieved.tzinfo is None:
            raise ValueError(f"acquisition inventory line {line_number} retrieval timestamp has no timezone")
        if retrieved.astimezone(timezone.utc).utcoffset() != retrieved.utcoffset():
            raise ValueError(f"acquisition inventory line {line_number} retrieval timestamp is not UTC")
        for field in ("observation_start", "observation_end", "available_on"):
            value = row.get(field)
            if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError(f"acquisition inventory line {line_number} has an invalid {field}")
        if row["observation_start"] > row["observation_end"]:
            raise ValueError(f"acquisition inventory line {line_number} has a reversed observation range")
        if row.get("availability_basis") == "capture_upper_bound":
            if row.get("available_on") != retrieved.date().isoformat():
                raise ValueError("capture availability bound differs from its actual retrieval date")
        elif row.get("availability_basis") == "published_on":
            published = row.get("publication_date")
            if not isinstance(published, str) or date.fromisoformat(published).isoformat() != published or not row.get("publication_evidence") or row.get("available_on") != published:
                raise ValueError("published availability is not bound to dated publication evidence")
        else:
            raise ValueError(f"acquisition inventory line {line_number} has an unsupported availability basis")
        records[acquisition_id] = row

    by_source_id: dict[str, dict] = {}
    for source_id, source in sources.items():
        acquisition_id = source.get("acquisition_id")
        if not acquisition_id:
            continue
        record = records.get(acquisition_id)
        if record is None:
            raise ValueError(f"acquisition inventory lacks ledger source {source_id}")
        captured = record["captured_file"]
        captured_path = (source_root / captured["path"]).resolve(strict=True)
        if (
            not captured_path.is_relative_to(source_root.resolve())
            or captured_path != paths[source_id]
            or sha(captured_path) != captured["sha256"]
            or captured_path.stat().st_size != captured["bytes"]
            or source.get("sha256") != captured["sha256"]
        ):
            raise ValueError(f"acquisition record does not bind the exact ledger source bytes: {source_id}")
        observed = source.get("observed_on")
        if observed and not (record.get("observation_start") <= observed <= record.get("observation_end")):
            raise ValueError(f"acquisition record does not cover the source observation date: {source_id}")
        if source.get("available_on") != record.get("available_on") or source.get("published_on") != record.get("publication_date"):
            raise ValueError(f"rotation source dates differ from its acquisition record: {source_id}")
        by_source_id[source_id] = record
    return by_source_id


def load_ledger(path: Path, source_root: Path) -> tuple[dict, list, dict]:
    ledger = json.loads(path.read_text())
    if ledger["schema_version"] != "rotation-source-ledger-v1":
        raise ValueError("rotation ledger schema mismatch")
    sources = ledger["sources"]
    paths = {}
    for key, source in sources.items():
        target = (source_root / source["path"]).resolve()
        if not target.is_relative_to(source_root.resolve()) or sha(target) != source["sha256"]:
            raise ValueError(f"rotation source hash/path mismatch: {key}")
        paths[key] = target
        for field in ("observed_on", "published_on", "available_on"):
            value = source.get(field)
            if value is not None and date.fromisoformat(value).isoformat() != value:
                raise ValueError(f"invalid source date: {key}/{field}")
        if not source.get("observed_on"):
            raise ValueError(f"source observation date required: {key}")
        if source.get("available_on") and (not source.get("publication_evidence")
                or (not source.get("published_on") and source.get("publication_basis") != "capture_upper_bound")
                or (source.get("published_on") and source["published_on"] > source["available_on"])):
            raise ValueError(f"unproven source availability: {key}")
    acquisition_records = _verified_acquisition_records(ledger, source_root, paths)
    for key, source in sources.items():
        if source.get("publication_basis") != "capture_upper_bound":
            continue
        evidence_id = source.get("capture_source_id", key)
        if evidence_id in acquisition_records:
            stamp = acquisition_records[evidence_id]["retrieved_at"]
            capture_date = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date().isoformat()
        else:
            if key in {"konglo_membership", "ownership_evidence"} or source.get("taxonomy_kind") == "KONGLO":
                raise ValueError("Konglo availability requires a hash-bound acquisition inventory record")
            captured = json.loads(paths[evidence_id].read_text())["listing_registry"]
            stamp = captured["listing_source"]["captured_at"][:8]
            capture_date = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
            date.fromisoformat(capture_date)
        if not source.get("available_on") or source["available_on"] < capture_date:
            raise ValueError("rotation availability predates its capture evidence")
        if key != evidence_id and source.get("derivation") == "exact_captured_subindustry":
            captured_payload = json.loads(paths[evidence_id].read_text())
            captured = captured_payload.get("listing_registry")
            if not isinstance(captured, dict) or not isinstance(captured.get("records"), list):
                raise ValueError("captured classification source has no complete listing registry")
            memberships = yaml.safe_load(paths[key].read_text())["memberships"]
            expected = {(r["ticker"], "ACTIVITY_" + re.sub(r"[^A-Z0-9]+", "_", r["taxonomy"]["subindustry"].upper()).strip("_"))
                        for r in captured["records"] if r["taxonomy"].get("subindustry")}
            actual = {(r["ticker"], r["taxonomy_group_id"]) for r in memberships if r.get("membership_type") != "EXCLUDED"}
            if actual != expected or len(actual) != len(memberships):
                raise ValueError("theme membership differs from captured subindustry evidence")
        elif key != evidence_id and (key == "konglo_membership" or source.get("taxonomy_kind") == "KONGLO"):
            capture_source = sources.get(evidence_id, {})
            if (
                source.get("derivation") != "ownership_register_threshold_v1"
                or source.get("derivation_input_sha256") != capture_source.get("sha256")
                or evidence_id not in acquisition_records
            ):
                raise ValueError("Konglo membership is not bound to its captured ownership register and derivation")
        elif key != evidence_id:
            raise ValueError("unsupported captured-source derivation")
    universes = copy.deepcopy(ledger["universes"])
    taxonomies = copy.deepcopy(ledger["taxonomies"])
    for versions in [universes, *taxonomies.values()]:
        effective_dates = [v["effective_from"] for v in versions]
        if len(set(effective_dates)) != len(effective_dates):
            raise ValueError("ambiguous rotation version dates")
        for v in versions:
            date.fromisoformat(v["effective_from"])
            if v.get("effective_to") and date.fromisoformat(v["effective_to"]) < date.fromisoformat(v["effective_from"]):
                raise ValueError("reversed version interval")
            if not v["source_ids"] or v["config_source_id"] not in v["source_ids"]:
                raise ValueError("rotation version must bind its configuration source")
            if any(k not in sources for k in v["source_ids"]):
                raise ValueError("unknown rotation source")
    for v in universes:
        config_path = paths[v["config_source_id"]]
        if v.get("format") == "captured_registry":
            captured = json.loads(config_path.read_text())
            registry = captured["listing_registry"]
            if registry.get("full_accessible_universe_listed") is not True:
                raise ValueError("rotation registry is incomplete")
            v["records"] = [dict(ticker=r["ticker"], vendor_ticker=r["ticker"], source="sectors",
                sector=r["taxonomy"].get("sector"), subsector=r["taxonomy"].get("subsector"),
                industry=r["taxonomy"].get("industry"), subindustry=r["taxonomy"].get("subindustry"),
                group_id=r["group_id"], listing_board=r["listing_board"], active=r["active"],
                source_as_of=r["source_as_of"]) for r in registry["records"]]
        else:
            provider = YFinanceProvider(universe_path=config_path)
            v["records"] = [r.model_dump(mode="json") for r in provider.get_security_master()]
        # Never permit provider's default board/classification to fill evidence.
        if any(not r.get("listing_board") or not r.get("sector") for r in v["records"]):
            raise ValueError("dated universe is missing explicit board/classification evidence")
    for kind in KINDS:
        for v in taxonomies.get(kind, []):
            config = yaml.safe_load(paths[v["config_source_id"]].read_text())
            groups = {}
            if v.get("format") == "captured_registry":
                for row in config["listing_registry"]["records"]:
                    groups.setdefault(row["group_id"], []).append(row["ticker"])
            elif kind == "SECTOR":
                for row in config["universe"]:
                    groups.setdefault(row["sectors"], []).append(row["ticker"])
            else:
                if config["taxonomy_kind"] != kind:
                    raise ValueError("taxonomy kind mismatch")
                for row in config["memberships"]:
                    if row.get("membership_type") != "EXCLUDED":
                        groups.setdefault(row["taxonomy_group_id"], []).append(row["ticker"])
            v["groups"] = groups
    return sources, universes, taxonomies


def build(*, ledger_path: Path, source_root: Path, panel: Path, validation: Path,
          snapshot_path: Path, snapshot_provenance: Path, start: str, end: str) -> dict:
    sources, universes, taxonomies = load_ledger(ledger_path, source_root)
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot["as_of"] != end or not snapshot.get("complete"):
        raise ValueError("rotation endpoint must be the complete dated snapshot")
    prices = pd.read_csv(panel / "prices.csv", parse_dates=["date"])
    benchmark = pd.read_csv(panel / "benchmark.csv", parse_dates=["date"])
    prices["date"] = prices["date"].dt.date
    benchmark["date"] = benchmark["date"].dt.date
    manifest = json.loads((panel / "source_manifest.json").read_text())
    report = json.loads(validation.read_text())
    integrity = _check_panel_integrity(prices, benchmark, manifest, panel)
    if report["status"] != "PASS" or integrity["status"] != "PASS" or report["checks"]["panel_integrity"] != integrity:
        raise ValueError("rotation panel validation missing, failed or stale")
    panel_files = {name: sha(panel / name) for name in ("prices.csv", "benchmark.csv")}
    if json.loads(snapshot_provenance.read_text())["panel_files"] != panel_files:
        raise ValueError("rotation panel differs from endpoint snapshot provenance")
    sessions = sorted(s for value in benchmark["date"] if start <= (s := value.isoformat()) <= end)
    diagnostics = manifest.get("diagnostics", {})
    gaps = {r["ticker"] if isinstance(r, dict) else r for key in ("failed_symbols", "quarantined_symbols") for r in diagnostics.get(key, [])}
    result = replay(prices=prices, benchmark=benchmark, sessions=sessions, sources=sources,
                    universes=universes, taxonomies=taxonomies, endpoints=endpoints_from_snapshot(snapshot),
                    snapshot_id=snapshot["snapshot_id"], as_of=end, gaps=gaps)
    result["provenance"] = dict(ledger_sha256=sha(ledger_path), snapshot_sha256=sha(snapshot_path),
        panel_files=panel_files, snapshot_provenance_sha256=sha(snapshot_provenance),
        validation_sha256=sha(validation), quarantined_or_failed=sorted(gaps))
    result["coverage"] = {kind: dict(groups=len(groups), daily=sum(g["daily_available"] for g in groups.values()),
                                      weekly=sum(g["weekly_available"] for g in groups.values()),
                                      observations=sum(len(s["points"]) for g in groups.values() for s in g["segments"]))
                          for kind, groups in result["taxonomies"].items()}
    validate_asset(result, endpoints_from_snapshot(snapshot))
    expected_cohort = snapshot["manifest"]["entries"][0]["eligible_ticker_set_hash"]
    if any(s["points"][-1]["universe_eligible_ticker_set_hash"] != expected_cohort
           for groups in result["taxonomies"].values() for g in groups.values()
           for s in g["segments"] if s["sessions"][-1] == end):
        raise ValueError("rotation endpoint eligibility differs from current snapshot")
    return result


def publish(payload: dict, public_root: Path) -> None:
    """Refuse the former independent rotation-index publication path."""
    raise ValueError(
        "per-family rotation publication is disabled; assemble a complete "
        "five-family candidate and activate it with scripts.publish_release"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("ledger", "source-root", "panel", "validation", "snapshot", "snapshot-provenance", "out"):
        p.add_argument("--" + name, required=True, type=Path)
    p.add_argument("--start", default="2026-09-01")
    p.add_argument("--end", default="2026-10-02")
    p.add_argument("--publish-root", type=Path)
    args = p.parse_args()
    try:
        payload = build(ledger_path=args.ledger, source_root=args.source_root, panel=args.panel,
                        validation=args.validation, snapshot_path=args.snapshot, snapshot_provenance=args.snapshot_provenance,
                        start=args.start, end=args.end)
        # Refuse before replacing either a prior report or served index.
        json.dumps(payload, allow_nan=False)
        if args.publish_root:
            publish(payload, args.publish_root)
        write_json_atomic(args.out, payload)
        print(json.dumps(payload["coverage"]))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ROTATION_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
