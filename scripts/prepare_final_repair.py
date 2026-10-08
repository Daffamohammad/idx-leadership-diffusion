"""Stage and reproduce the final repair entirely from saved, hash-bound inputs."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import stat

from idx_leadership.data.releases import calculate_release_id, canonical_json_bytes, validate_manifest_file
from scripts.build_sectors_analysis import build as build_core
from scripts.build_submission_analysis import build as build_context
from scripts.business_groups import reconcile

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path):
    return json.loads(path.read_text())


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def reproduce(manifest_path: Path, out: Path) -> dict:
    manifest = read(manifest_path)
    release = validate_manifest_file(manifest_path, candidate=any("candidate_path" in row for row in manifest["source_evidence"]))
    root = manifest_path.parent
    out.mkdir(parents=True, exist_ok=True)
    for file_id, destination in (("research_price_input", "prices.csv"), ("research_benchmark_input", "benchmark.csv")):
        payload = read(release.additional_paths[file_id])
        raw = gzip.decompress(base64.b64decode(payload["data"]))
        if digest(raw) != payload["uncompressed_sha256"]:
            raise ValueError("reproduction input content hash differs")
        (out / destination).write_bytes(raw)
    entries = release.additional_paths
    plan_path = out / "selection_plan.json"
    write(plan_path, read(entries["sectors_selection_plan"])["plan"])
    core = out / "sectors_signal_analysis.json"
    build_core(sample_path=entries["sectors_recorded_sample"], selection_market_path=entries["sectors_selection_market"],
               selection_plan_path=plan_path, ytd_baseline_path=entries.get("sectors_ytd_baseline"), out=core)
    context = out / "historical_comparison.json"
    build_context(market_path=release.family_paths["market"], rotation_path=release.family_paths["rotation"],
                  snapshot_path=release.family_paths["snapshot"], prices_path=out / "prices.csv", benchmark_path=out / "benchmark.csv", out=context)
    matches = {name: path.read_bytes() == entries[name].read_bytes() for name, path in (("sectors_signal_analysis", core), ("historical_comparison", context))}
    if not all(matches.values()):
        raise ValueError(f"clean input reproduction differs: {matches}")
    return {"status": "PASS", "release_id": release.release_id, "matches": matches, "provider_calls": 0}


def prepare(*, base: Path, prices: Path, benchmark: Path, previous: Path, destination: Path, source_archive: Path) -> dict:
    verified = validate_manifest_file(base, candidate=False)
    if destination.exists():
        raise ValueError("candidate destination exists; preserve prior candidates")
    old = read(verified.additional_paths["historical_comparison"])
    for path, key in ((prices, "adjusted_price_panel_sha256"), (benchmark, "ihsg_panel_sha256")):
        if digest(path.read_bytes()) != old["sources"][key]:
            raise ValueError(f"research input differs from the validated original panel: {key}")
    shutil.copytree(base.parent, destination, copy_function=shutil.copy2)
    for path in (destination, *destination.rglob("*")):
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    manifest = read(destination / "manifest.json")
    wanted = {row["sha256"] for row in manifest["source_evidence"]}
    found = {}
    for directory in (source_archive, ROOT / "data"):
        for path in sorted(directory.rglob("*")):
            if path.is_file() and not path.is_symlink():
                sha = digest(path.read_bytes())
                if sha in wanted:
                    found.setdefault(sha, path)
    missing = [row["source_id"] for row in manifest["source_evidence"] if row["sha256"] not in found]
    if missing:
        raise ValueError(f"saved source archive is incomplete: {missing}")
    for row in manifest["source_evidence"]:
        target = destination / "evidence" / "original-sources" / row["source_id"] / row["file_name"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(found[row["sha256"]], target)
        row["candidate_path"] = str(target.relative_to(destination))
    families = {key: destination / row["path"] for key, row in manifest["families"].items()}
    market, snapshot, ownership = (read(families[key]) for key in ("market", "snapshot", "ownership"))
    prior = read(previous)
    if len(prior) != ownership["coverage"]["previous_rows"] or any(row["as_of"] != ownership["previous_as_of"] for row in prior):
        raise ValueError("prior register rows do not match their original date and coverage")
    ownership["registers"]["previous_one"] = prior
    ownership["five_previous_as_of"] = ownership["registers"]["five"][0].get("previous_as_of")
    write(families["ownership"], ownership)
    definitions = read(ROOT / "config/market_expansion/business_groups.json")
    view, extra_edges, catalogue = reconcile(definition=definitions, legacy=snapshot["taxonomy_views"]["konglo"], market=market, ownership=ownership)
    catalogue["view"] = view
    catalogue["definition_sha256"] = digest((ROOT / "config/market_expansion/business_groups.json").read_bytes())
    catalogue_path = destination / "evidence/business_group_catalogue.json"
    write(catalogue_path, catalogue)
    existing = market.get("ownership_edges", [])
    edges = list({json.dumps(row, sort_keys=True): row for row in existing + extra_edges}.values())
    market["ownership_edges"] = edges
    write(families["market"], market)
    edges_path = destination / "evidence/market-ownership-edges.json"
    write(edges_path, {"schema_version": "business-group-edges-v1", "as_of": ownership["as_of"], "edges": edges})
    plan_path = destination / "evidence/sectors_selection_plan.json"
    plan_source = ROOT / "data/research/acquisitions/sectors-recorded-sample-20261005/recording_manifest.json"
    write(plan_path, {"schema_version": "selection-plan-source-v1", "as_of": manifest["target_session"],
                      "original_sha256": digest(plan_source.read_bytes()), "plan": read(plan_source)})
    inputs = {}
    for file_id, path, name in (("research_price_input", prices, "prices.json"), ("research_benchmark_input", benchmark, "benchmark.json")):
        target = destination / "evidence/reproduction" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        write(target, {"schema_version": "research-input-gzip-v1", "as_of": manifest["target_session"],
                       "encoding": "gzip-base64", "uncompressed_sha256": digest(path.read_bytes()),
                       "data": base64.b64encode(gzip.compress(path.read_bytes(), mtime=0)).decode()})
        inputs[file_id] = target
    entries = {row["file_id"]: destination / row["path"] for row in manifest["additional_files"]}
    build_core(sample_path=entries["sectors_recorded_sample"], selection_market_path=entries["sectors_selection_market"],
               selection_plan_path=plan_source, ytd_baseline_path=entries.get("sectors_ytd_baseline"), out=entries["sectors_signal_analysis"])
    context = build_context(market_path=families["market"], rotation_path=families["rotation"], snapshot_path=families["snapshot"],
                            prices_path=prices, benchmark_path=benchmark, out=entries["historical_comparison"])
    added = {**inputs, "business_group_catalogue": catalogue_path, "business_group_edges": edges_path, "sectors_selection_plan": plan_path}
    for file_id, path in added.items():
        manifest["additional_files"].append({"file_id": file_id, "family": "snapshot", "path": str(path.relative_to(destination)),
            "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size,
            "schema": read(path)["schema_version"], "observation_date": read(path)["as_of"]})
    for row in [*manifest["families"].values(), *manifest["additional_files"]]:
        raw = (destination / row["path"]).read_bytes()
        row.update(sha256=digest(raw), bytes=len(raw))
    manifest["additional_files"].sort(key=lambda row: row["file_id"])
    hashes = manifest["validation"]["input_hashes"]
    hashes["families"] = {key: row["sha256"] for key, row in manifest["families"].items()}
    hashes["additional_files"] = {row["file_id"]: row["sha256"] for row in manifest["additional_files"]}
    manifest["analytical_contracts"]["research_reading_contract_sha256"] = digest(b"per-horizon fixed replay cohorts; coordinate phase; 5d-60d leadership; integer diffusion; actual-20d concentration; v2")
    manifest["validation"]["contract_fingerprints"] = dict(manifest["analytical_contracts"])
    manifest["release_id"] = ""
    manifest["release_id"] = calculate_release_id(manifest)
    (destination / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")
    candidate = validate_manifest_file(destination / "manifest.json", candidate=True)
    return {"status": "PASS", "release_id": candidate.release_id, "manifest_sha256": candidate.manifest_sha256,
            "taxonomy_counts": {key: value["group_count"] for key, value in context["taxonomies"].items()},
            "reference_group_count": len(catalogue["reference_groups"]), "previous_ownership_rows": len(prior), "provider_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-manifest", type=Path)
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--previous-ownership", type=Path)
    parser.add_argument("--source-archive", type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--reproduce", type=Path)
    args = parser.parse_args()
    report = reproduce(args.reproduce, args.destination) if args.reproduce else prepare(base=args.base_manifest, prices=args.prices,
                benchmark=args.benchmark, previous=args.previous_ownership, destination=args.destination, source_archive=args.source_archive)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
