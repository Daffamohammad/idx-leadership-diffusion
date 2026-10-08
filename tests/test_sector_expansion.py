import copy
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from idx_leadership.data.releases import canonical_json_bytes
from idx_leadership.providers.persistent_budget import PersistentRequestBudget
from idx_leadership.utils.errors import CreditBudgetExceeded
from scripts.acquire_sector_expansion import ExpansionRun
from scripts.build_sectors_analysis import build
from scripts.prepare_sector_expansion import SECTORS, freeze_plan
from scripts.verify_sectors_analysis_oracle import verify


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "app/web/public/releases"


def _active_assets():
    pointer = json.loads((RELEASES / "active.json").read_text())
    release_ref = pointer["active"]
    release_dir = RELEASES / release_ref["release_id"]
    manifest_path = release_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    paths = {row["file_id"]: release_dir / row["path"] for row in manifest["additional_files"]}
    sample = json.loads(paths["sectors_recorded_sample"].read_text())
    if len(sample.get("stocks", [])) != 66:
        release_ref = pointer.get("previous")
        if not release_ref:
            raise AssertionError("the 66-stock rollback package is required for expansion tests")
        release_dir = RELEASES / release_ref["release_id"]
        manifest_path = release_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        paths = {row["file_id"]: release_dir / row["path"] for row in manifest["additional_files"]}
        sample = json.loads(paths["sectors_recorded_sample"].read_text())
    assert len(sample.get("stocks", [])) == 66
    return manifest_path, manifest, paths


def _eligible(row, as_of):
    return (
        row.get("signal_eligible") is True
        and row.get("instrument_type") == "LISTED_STOCK"
        and row.get("traded") is True
        and row.get("last_trade_date") == as_of
        and float(row.get("close") or 0) > 0
        and float(row.get("market_cap") or 0) > 0
        and isinstance(row.get("ticker"), str)
        and row["ticker"].endswith(".JK")
    )


def test_expansion_plan_freezes_exact_top_twelve_without_spending(tmp_path):
    base_manifest, manifest, assets = _active_assets()
    run_dir = tmp_path / "expansion"
    report = freeze_plan(base_manifest_path=base_manifest, out_dir=run_dir)
    plan = json.loads((run_dir / "expansion_plan.json").read_text())
    market = json.loads(assets["sectors_selection_market"].read_text())
    sample = json.loads(assets["sectors_recorded_sample"].read_text())
    original = {sector: {row["ticker"] for row in sample["stocks"] if row["sector"] == sector}
                for sector in SECTORS}

    assert report["status"] == "PREFLIGHT_PASS"
    assert report["total_stocks"] == 132
    assert report["daily_dates"] == 21
    assert report["weekly_dates"] == 5
    assert report["planned_credits"] == 198
    assert report["retry_reserve"] == 23
    assert report["hard_ceiling"] == 221
    assert report["budget"]["credits_reserved"] == 0
    assert plan["selection"]["stock_count"] == 132
    assert plan["selection"]["stocks_per_sector"] == 12

    for sector in SECTORS:
        ranked = sorted(
            (row for row in market["records"]
             if _eligible(row, market["as_of"]) and (row.get("taxonomy") or {}).get("sector") == sector),
            key=lambda row: (-float(row["market_cap"]), row["ticker"].upper()),
        )
        expected = [row["ticker"] for row in ranked[:12]]
        assert plan["selections"][sector]["selected"] == expected
        assert set(plan["selections"][sector]["original"]) == original[sector]
        assert plan["selections"][sector]["additions"] == expected[6:12]
    assert len({row["ticker"] for row in plan["selection"]["members"]}) == 132
    assert len(plan["request_plan"]) == 66
    for item in plan["request_plan"].values():
        assert len(item["price_windows"]) == 2
        assert item["corporate_action_check"] is True
    budget = PersistentRequestBudget(run_dir / "request_budget.json", run_id=plan["run_id"], plan_sha256=plan["plan_sha256"])
    assert budget.snapshot() == {"requests_reserved": 0, "credits_reserved": 0.0,
                                 "max_requests": 221, "max_credits": 221.0}


def test_expanded_calculations_keep_ytd_on_original_66_and_match_independent_oracle(tmp_path):
    base_manifest, _manifest, assets = _active_assets()
    run_dir = tmp_path / "expansion"
    freeze_plan(base_manifest_path=base_manifest, out_dir=run_dir)
    plan_path = run_dir / "expansion_plan.json"
    plan = json.loads(plan_path.read_text())
    old_sample = json.loads(assets["sectors_recorded_sample"].read_text())
    market = json.loads(assets["sectors_selection_market"].read_text())
    baseline = assets["sectors_ytd_baseline"]
    old_analysis_path = tmp_path / "old-analysis.json"
    build(sample_path=assets["sectors_recorded_sample"], selection_market_path=assets["sectors_selection_market"],
          ytd_baseline_path=baseline, out=old_analysis_path)
    old_analysis = json.loads(old_analysis_path.read_text())

    original_by_sector = {}
    for row in old_sample["stocks"]:
        original_by_sector.setdefault(row["sector"], []).append(row)
    market_by_ticker = {row["ticker"]: row for row in market["records"]}
    original_tickers = sorted(row["ticker"] for row in old_sample["stocks"])
    expanded = copy.deepcopy(old_sample)
    additions = []
    for sector in SECTORS:
        template = original_by_sector[sector][0]
        for ticker in plan["selections"][sector]["additions"]:
            source = market_by_ticker[ticker]
            prices = [row for row in template["prices"] if row["date"] >= "2026-06-09"]
            stock = {
                **copy.deepcopy(template),
                "ticker": ticker,
                "company_name": source.get("company_name"),
                "prices": prices,
                "corporate_actions": {"response": {"corporate_actions": {}}},
                "foreign_flow": None,
                "history_coverage": {
                    "requested_start": "2026-06-09", "requested_end": old_sample["as_of"],
                    "observed_start": prices[0]["date"] if prices else None,
                    "observed_end": prices[-1]["date"] if prices else None,
                    "window_count": 2, "price_windows": [
                        {"window": ["2026-06-09", "2026-09-07"], "path": f"test/{ticker}/1", "sha256": "a" * 64},
                        {"window": ["2026-09-08", "2026-10-02"], "path": f"test/{ticker}/2", "sha256": "b" * 64},
                    ],
                },
            }
            additions.append(stock)
    expanded["schema_version"] = "sectors-expanded-universe-v1"
    expanded["label"] = "132 stocks across 11 IDX sectors"
    expanded["selection"].update({
        "stock_count": 132,
        "stocks_per_sector": 12,
        "sector_counts": {sector: 12 for sector in SECTORS},
        "ytd_tickers": original_tickers,
        "expansion_plan_sha256": plan["plan_sha256"],
    })
    expanded["stocks"] = [*old_sample["stocks"], *additions]
    old_analysis = json.loads(old_analysis_path.read_text())
    per_stock = {}
    for stock in expanded["stocks"]:
        coverage = stock.get("history_coverage")
        if coverage is None:
            dates = sorted(row["date"] for row in stock["prices"])
            coverage = {
                "requested_start": old_sample["price_history"]["start"],
                "requested_end": old_sample["as_of"],
                "observed_start": dates[0] if dates else None,
                "observed_end": dates[-1] if dates else None,
                "window_count": len(stock.get("price_sources", [])),
                "price_windows": stock.get("price_sources", []),
            }
            stock["history_coverage"] = coverage
        per_stock[stock["ticker"]] = coverage
    expanded["coverage"] = {
        "price_history": {
            "stock_count": 132, "stocks_per_sector": 12,
            "first_replay_date": old_analysis["daily"][0]["date"],
            "first_required_price_date": "2026-06-09", "end_date": old_sample["as_of"],
            "daily_dates": [row["date"] for row in old_analysis["daily"]],
            "weekly_dates": [row["date"] for row in old_analysis["weekly"]],
            "per_stock": per_stock,
        },
        "ytd": {"stock_count": 66, "tickers": original_tickers,
                "baseline_date": "2025-12-30", "end_date": old_sample["as_of"],
                "baseline_asset_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest()},
        "company_flow": {"stock_count": 66, "tickers": original_tickers,
                         "start_date": old_sample["foreign_flow"]["stock_recent_start"],
                         "end_date": old_sample["as_of"]},
    }
    expanded_path = tmp_path / "expanded.json"
    expanded_path.write_bytes(canonical_json_bytes(expanded) + b"\n")
    analysis_path = tmp_path / "expanded-analysis.json"
    build(sample_path=expanded_path, selection_market_path=assets["sectors_selection_market"],
          ytd_baseline_path=baseline, selection_plan_path=plan_path, out=analysis_path)
    analysis = json.loads(analysis_path.read_text())
    oracle = verify(sample_path=expanded_path, analysis_path=analysis_path, ytd_baseline_path=baseline)

    assert analysis["selection"]["stock_count"] == 132
    assert analysis["selection"]["stocks_per_sector"] == 12
    assert len(analysis["daily"]) == 21
    assert len(analysis["weekly"]) == 5
    assert analysis["ytd"] == old_analysis["ytd"]
    assert oracle["status"] == "PASS"
    assert oracle["mismatch_count"] == 0
    assert oracle["counts"]["member_window_values"] == 10_296
    assert oracle["counts"]["ytd_contributor_values"] == 66


def test_expansion_budget_blocks_attempt_222(tmp_path):
    budget = PersistentRequestBudget.create(
        tmp_path / "budget.json", run_id="expansion-test", plan_sha256="c" * 64,
        max_requests=221, max_credits=221,
    )
    for index in range(221):
        budget.reserve(f"/v2/daily/S{index:03d}.JK/", 1)
    with pytest.raises(CreditBudgetExceeded, match="request ceiling reached"):
        budget.reserve("/v2/daily/attempt-222.JK/", 1)
    assert budget.snapshot()["requests_reserved"] == 221
    assert budget.snapshot()["credits_reserved"] == 221


def test_expansion_response_can_resume_after_an_interrupted_attempt(tmp_path):
    base_manifest, _manifest, _assets = _active_assets()
    run_dir = tmp_path / "expansion"
    freeze_plan(base_manifest_path=base_manifest, out_dir=run_dir)
    plan = json.loads((run_dir / "expansion_plan.json").read_text())

    class FakeClient:
        def __init__(self, budget, *, fail):
            self.budget = budget
            self.fail = fail
            self.http_requests_made = 0

        def get(self, endpoint, params, *, use_cache=True):
            self.budget.reserve(endpoint, 1)
            self.http_requests_made += 1
            if self.fail:
                raise RuntimeError("interrupted after reserving this request")
            return SimpleNamespace(payload={"rows": [{"date": "2026-06-09", "close": 100}]},
                                   cache_hit=False, status=200, estimated_credit_cost=1,
                                   request_id="test-request")

    run = ExpansionRun(run_dir, record=False)
    run.client = FakeClient(run.budget, fail=True)
    with pytest.raises(RuntimeError, match="interrupted"):
        run.fetch("prices/TEST/01.json", "/v2/daily/TEST.JK/", {"start": "2026-06-09", "end": "2026-10-02"})
    assert run.budget.snapshot()["requests_reserved"] == 1

    resumed = ExpansionRun(run_dir, record=False)
    resumed.client = FakeClient(resumed.budget, fail=False)
    payload = resumed.fetch("prices/TEST/01.json", "/v2/daily/TEST.JK/", {"start": "2026-06-09", "end": "2026-10-02"})
    assert payload["rows"][0]["close"] == 100
    assert resumed.budget.snapshot()["requests_reserved"] == 2

    restarted = ExpansionRun(run_dir, record=False)
    restarted.client = FakeClient(restarted.budget, fail=True)
    assert restarted.fetch("prices/TEST/01.json", "/v2/daily/TEST.JK/", {"start": "2026-06-09", "end": "2026-10-02"}) == payload
    assert restarted.budget.snapshot()["requests_reserved"] == 2
