import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from idx_leadership.data.releases import canonical_json_bytes
from scripts.prepare_sectors_ytd_baseline import preflight, prepare_successor
from scripts.record_sectors_ytd_baseline import _previous_attempts


SECTORS = (
    "Basic Materials", "Consumer Cyclicals", "Consumer Non-Cyclicals", "Energy",
    "Financials", "Healthcare", "Industrials", "Infrastructures",
    "Properties & Real Estate", "Technology", "Transportation & Logistic",
)


def _inputs(tmp_path, monkeypatch):
    run = tmp_path / "original"
    run.mkdir()
    market = tmp_path / "selection-market.json"
    market_raw = b'{"schema_version":"market-workspace-v1","as_of":"2026-10-02"}\n'
    market.write_bytes(market_raw)
    digest = hashlib.sha256(market_raw).hexdigest()
    plan = {
        "schema_version": "sectors-recording-plan-v1",
        "run_id": "parent-run",
        "market_release_source": {"sha256": digest},
    }
    plan["plan_sha256"] = hashlib.sha256(canonical_json_bytes({k: v for k, v in plan.items() if k != "run_id"})).hexdigest()
    plan_path = run / "recording_manifest.json"
    plan_path.write_bytes(canonical_json_bytes(plan) + b"\n")
    stocks = []
    for sector_index, sector in enumerate(SECTORS):
        for index in range(6):
            action = {"dividend": [{"ex_date": "2026-01-02"}]} if len(stocks) < 42 else {}
            stocks.append({
                "ticker": f"S{sector_index:02d}{index:02d}.JK", "sector": sector,
                "corporate_actions": {"response": {"corporate_actions": action}},
            })
    sample = {
        "schema_version": "sectors-recorded-sample-v1",
        "as_of": "2026-10-02",
        "sources": {"market_release_source_sha256": digest},
        "stocks": stocks,
    }
    sample_path = run / "sectors_recorded_sample.json"
    sample_path.write_bytes(canonical_json_bytes(sample) + b"\n")
    reservations = [
        {"sequence": index, "endpoint": f"/v2/daily/S{index:03d}.JK/", "estimated_credits": 1.0}
        for index in range(1, 434)
    ]
    budget = {
        "schema_version": "sectors-recording-budget-v1", "run_id": "parent-run",
        "plan_sha256": plan["plan_sha256"], "max_requests": 450, "max_credits": 450,
        "requests_reserved": 433, "credits_reserved": 433.0, "reservations": reservations,
    }
    budget_path = run / "request_budget.json"
    budget_path.write_bytes(canonical_json_bytes(budget) + b"\n")
    ledger_path = run / "request_ledger.jsonl"
    ledger_path.write_bytes(b'{"status":"ok"}\n')
    receipt = {
        "status": "ACQUISITIONS_VALIDATED", "run_id": "parent-run",
        "plan_sha256": plan["plan_sha256"],
        "sample_sha256": hashlib.sha256(sample_path.read_bytes()).hexdigest(),
        "request_budget": {"max_requests": 450, "max_credits": 450,
                           "requests_reserved": 433, "credits_reserved": 433.0},
    }
    receipt_path = run / "run_receipt.json"
    receipt_path.write_bytes(canonical_json_bytes(receipt) + b"\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    import scripts.prepare_sectors_ytd_baseline as preparation
    monkeypatch.setattr(preparation, "validate_manifest_file", lambda *_args, **_kwargs: SimpleNamespace(
        manifest={"target_session": "2026-10-02"}, release_id="rel-" + "a" * 64,
    ))
    originals = {path.name: path.read_bytes() for path in [plan_path, sample_path, budget_path, ledger_path, receipt_path]}
    return run, manifest, market, originals


def test_ytd_preflight_is_read_only_and_reserves_room_for_retries(tmp_path, monkeypatch):
    run, manifest, market, originals = _inputs(tmp_path, monkeypatch)
    report = preflight(original_run_dir=run, base_release_manifest=manifest, selection_market_path=market)

    assert report["status"] == "PREFLIGHT_PASS"
    assert report["read_only"] is True
    assert report["transport_initialized"] is False
    assert report["calls_made"] == 0
    assert report["planned_requests"]["native_ihsg_baseline"] == 1
    assert report["planned_requests"]["eligible_stock_baselines"] == 24
    assert report["planned_total_requests"] == 458
    assert report["remaining_request_reserve_for_retries"] == 42
    assert {path.name: path.read_bytes() for path in [
        run / "recording_manifest.json", run / "sectors_recorded_sample.json",
        run / "request_budget.json", run / "request_ledger.jsonl", run / "run_receipt.json",
    ]} == originals


def test_ytd_preflight_accepts_published_release_manifest(tmp_path, monkeypatch):
    run, manifest, market, _ = _inputs(tmp_path, monkeypatch)
    import scripts.prepare_sectors_ytd_baseline as preparation
    calls = []

    def validate(path, *, candidate):
        calls.append(candidate)
        if candidate:
            raise ValueError("published source inventory has no staged candidate paths")
        return SimpleNamespace(manifest={"target_session": "2026-10-02"}, release_id="rel-" + "b" * 64)

    monkeypatch.setattr(preparation, "validate_manifest_file", validate)
    report = preflight(original_run_dir=run, base_release_manifest=manifest, selection_market_path=market)

    assert report["status"] == "PREFLIGHT_PASS"
    assert calls == [True, False]


def test_successor_plan_seeds_all_reservations_without_touching_original(tmp_path, monkeypatch):
    run, manifest, market, originals = _inputs(tmp_path, monkeypatch)
    out = tmp_path / "successor"
    result = prepare_successor(original_run_dir=run, base_release_manifest=manifest,
                               selection_market_path=market, out_dir=out)
    successor_plan = json.loads((out / "recording_manifest.json").read_text())

    assert result["status"] == "SUCCESSOR_PLAN_READY"
    assert successor_plan["maximum_requests"] == 500
    assert successor_plan["maximum_estimated_credits"] == 500
    assert successor_plan["retry_reserve_requests"] == 42
    assert result["successor_budget"]["requests_reserved"] == 433
    assert result["successor_budget"]["credits_reserved"] == 433
    assert (out / "parent_request_ledger.jsonl").read_bytes() == originals["request_ledger.jsonl"]
    assert {path.name: path.read_bytes() for path in [
        run / "recording_manifest.json", run / "sectors_recorded_sample.json",
        run / "request_budget.json", run / "request_ledger.jsonl", run / "run_receipt.json",
    ]} == originals


def test_resumed_ytd_run_preserves_prior_failed_attempts(tmp_path):
    path = tmp_path / "run_receipt.json"
    attempts = [{"kind": "native_ihsg_baseline", "status": "FAILED_AFTER_RETRIES",
                 "error": "network unavailable"}]
    path.write_text(json.dumps({
        "schema_version": "sectors-ytd-baseline-receipt-v1",
        "run_id": "successor-run", "plan_sha256": "plan-hash", "attempts": attempts,
    }))

    assert _previous_attempts(path, run_id="successor-run", plan_sha256="plan-hash") == attempts
