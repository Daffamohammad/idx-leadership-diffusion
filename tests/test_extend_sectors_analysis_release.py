import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from idx_leadership.data.releases import calculate_release_id
from scripts import extend_sectors_analysis_release as extension


ROOT = Path(__file__).resolve().parents[1]


def test_successor_rebuild_replaces_hardlinked_analysis_without_mutating_base(tmp_path, monkeypatch):
    releases = ROOT / "app/web/public/releases"
    pointer = json.loads((releases / "active.json").read_text())
    active = releases / pointer["active"]["release_id"]
    base = tmp_path / "base"
    shutil.copytree(active, base)
    base_manifest_path = base / "manifest.json"
    base_manifest = json.loads(base_manifest_path.read_text())
    sample_entry = next(row for row in base_manifest["additional_files"]
                        if row["file_id"] == "sectors_recorded_sample")
    market_entry = next(row for row in base_manifest["additional_files"]
                        if row["file_id"] == "sectors_selection_market")
    analysis_entry = next(row for row in base_manifest["additional_files"]
                          if row["file_id"] == "sectors_signal_analysis")
    base_analysis_path = base / analysis_entry["path"]
    base_analysis_before = base_analysis_path.read_bytes()
    original_analysis_hash = hashlib.sha256(base_analysis_before).hexdigest()

    sample_raw = (base / sample_entry["path"]).read_bytes()
    sample = json.loads(sample_raw)
    market_raw = (base / market_entry["path"]).read_bytes()
    market = json.loads(market_raw)
    by_sector = {}
    for row in market["records"]:
        sector = (row.get("taxonomy") or {}).get("sector")
        if sector:
            by_sector.setdefault(sector, []).append(row)
    selections = {}
    for sector, rows in by_sector.items():
        eligible = [row for row in rows if row.get("signal_eligible") is True
                    and row.get("instrument_type") == "LISTED_STOCK" and row.get("traded") is True
                    and row.get("last_trade_date") == market["as_of"]
                    and float(row.get("close") or 0) > 0 and float(row.get("market_cap") or 0) > 0]
        ranked = sorted(eligible, key=lambda row: (-float(row["market_cap"]), row["ticker"]))
        selections[sector] = {"selected": [row["ticker"] for row in ranked[:6]]}

    run_dir = tmp_path / "recording"
    run_dir.mkdir()
    (run_dir / "sectors_recorded_sample.json").write_bytes(sample_raw)
    plan = {
        "run_id": "test-run", "plan_sha256": "a" * 64,
        "market_release_source": {"sha256": hashlib.sha256(market_raw).hexdigest()},
        "selection_release_id": sample["selection"]["membership_release_id"],
        "selections": selections,
    }
    (run_dir / "recording_manifest.json").write_text(json.dumps(plan))
    (run_dir / "run_receipt.json").write_text(json.dumps({
        "status": "ACQUISITIONS_VALIDATED", "run_id": plan["run_id"],
        "plan_sha256": plan["plan_sha256"],
        "sample_sha256": hashlib.sha256(sample_raw).hexdigest(),
        "request_budget": {"max_requests": 450, "max_credits": 450,
                           "requests_reserved": 433, "credits_reserved": 433.0},
    }))

    def fake_build(*, out, **_kwargs):
        Path(out).write_bytes(b'{"schema_version":"sectors-signal-analysis-v1"}\n')
        return {"status": "PASS"}

    def fake_validate(path, *, candidate=True, **_kwargs):
        if Path(path).resolve() == base_manifest_path.resolve():
            return SimpleNamespace(manifest=base_manifest, root=base,
                                   release_id=base_manifest["release_id"])
        output_manifest = json.loads(Path(path).read_text())
        return SimpleNamespace(release_id=calculate_release_id(output_manifest),
                               manifest_sha256="b" * 64)

    monkeypatch.setattr(extension, "build", fake_build)
    monkeypatch.setattr(extension, "validate_manifest_file", fake_validate)
    destination = tmp_path / "successor"
    result = extension.extend(base_manifest_path=base_manifest_path, out_dir=destination,
                              run_dir=run_dir, selection_market_path=base / market_entry["path"])

    assert result["status"] == "PASS"
    assert hashlib.sha256(base_analysis_path.read_bytes()).hexdigest() == original_analysis_hash
    assert base_analysis_path.read_bytes() == base_analysis_before
    successor = destination / analysis_entry["path"]
    assert successor.read_bytes() == b'{"schema_version":"sectors-signal-analysis-v1"}\n'
    ids = [row["file_id"] for row in json.loads((destination / "manifest.json").read_text())["additional_files"]]
    assert len(ids) == len(set(ids))
