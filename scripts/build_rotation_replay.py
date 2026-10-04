"""Build and optionally publish a source-gated, chart-only rotation asset.

Run with --help. All paths in the source ledger are relative to --source-root.
Outputs are separate from historical snapshots. No network requests are made.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from idx_leadership.data.rotation_replay import KINDS, endpoints_from_snapshot, replay, validate_asset
from idx_leadership.providers.public import YFinanceProvider
from idx_leadership.providers.idx_statistics import write_json_atomic
from scripts.validate_public_panel import _check_panel_integrity


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    for key, source in sources.items():
        if source.get("publication_basis") != "capture_upper_bound":
            continue
        evidence_id = source.get("capture_source_id", key)
        captured = json.loads(paths[evidence_id].read_text())["listing_registry"]
        stamp = captured["listing_source"]["captured_at"][:8]
        capture_date = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
        date.fromisoformat(capture_date)
        if not source.get("available_on") or source["available_on"] < capture_date:
            raise ValueError("rotation availability predates its capture evidence")
        if key != evidence_id:
            if source.get("derivation") != "exact_captured_subindustry":
                raise ValueError("unsupported captured-source derivation")
            memberships = yaml.safe_load(paths[key].read_text())["memberships"]
            expected = {(r["ticker"], "ACTIVITY_" + re.sub(r"[^A-Z0-9]+", "_", r["taxonomy"]["subindustry"].upper()).strip("_"))
                        for r in captured["records"] if r["taxonomy"].get("subindustry")}
            actual = {(r["ticker"], r["taxonomy_group_id"]) for r in memberships if r.get("membership_type") != "EXCLUDED"}
            if actual != expected or len(actual) != len(memberships):
                raise ValueError("theme membership differs from captured subindustry evidence")
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
    """Immutable content-addressed artifact first; atomic index last."""
    index_path = public_root / "market" / "index.json"
    index = json.loads(index_path.read_text())
    snapshot_path = public_root / "snapshots" / f'{payload["snapshot_id"]}.json'
    if (index["snapshot_id"] != payload["snapshot_id"] or index["as_of"] != payload["as_of"]
            or sha(snapshot_path) != payload["provenance"]["snapshot_sha256"]):
        raise ValueError("rotation publication snapshot mismatch")
    validate_asset(payload, endpoints_from_snapshot(json.loads(snapshot_path.read_text())))
    content = json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n"
    digest = hashlib.sha256(content.encode()).hexdigest()
    name = f'rotation-{payload["as_of"]}-{digest[:16]}.json'
    target = index_path.parent / name
    if target.exists() and sha(target) != digest:
        raise ValueError("immutable rotation asset collision")
    temporary = target.with_suffix(".tmp")
    temporary.write_text(content); temporary.replace(target)
    index["assets"]["rotation"] = dict(path="/market/" + name, sha256=digest, as_of=payload["as_of"], schema_version=payload["schema_version"])
    write_json_atomic(index_path, index)


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
