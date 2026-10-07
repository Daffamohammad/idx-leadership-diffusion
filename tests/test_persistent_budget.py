import json
import threading

import pytest

from idx_leadership.providers.persistent_budget import PersistentRequestBudget
from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.utils.errors import CreditBudgetExceeded


def test_persistent_budget_survives_restart_and_blocks_before_request(tmp_path):
    path = tmp_path / "budget.json"
    budget = PersistentRequestBudget.create(
        path, run_id="sample-1", plan_sha256="a" * 64, max_requests=3, max_credits=3,
    )
    budget.reserve("/v2/daily/BBCA.JK/", 1)
    budget.reserve("/v2/index-daily/ihsg/", 1)

    resumed = PersistentRequestBudget(path, run_id="sample-1", plan_sha256="a" * 64)
    resumed.reserve("/v2/foreign-flow/IHSG/", 1)
    with pytest.raises(CreditBudgetExceeded, match="request ceiling"):
        resumed.reserve("/v2/daily/BBRI.JK/", 1)

    assert resumed.snapshot() == {
        "requests_reserved": 3,
        "credits_reserved": 3.0,
        "max_requests": 3,
        "max_credits": 3.0,
    }


def test_persistent_budget_serializes_concurrent_requests(tmp_path):
    path = tmp_path / "budget.json"
    budget = PersistentRequestBudget.create(
        path, run_id="sample-2", plan_sha256="b" * 64, max_requests=8, max_credits=8,
    )
    failures = []

    def reserve(index):
        try:
            budget.reserve(f"/v2/daily/S{index:03d}.JK/", 1)
        except Exception as exc:  # pragma: no cover - assertion reports unexpected errors
            failures.append(exc)

    threads = [threading.Thread(target=reserve, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    assert budget.snapshot()["requests_reserved"] == 8
    assert budget.snapshot()["credits_reserved"] == 8


def test_persistent_budget_rejects_different_manifest(tmp_path):
    path = tmp_path / "budget.json"
    PersistentRequestBudget.create(
        path, run_id="sample-3", plan_sha256="c" * 64, max_requests=2, max_credits=2,
    )
    resumed = PersistentRequestBudget(path, run_id="sample-3", plan_sha256="d" * 64)
    with pytest.raises(CreditBudgetExceeded, match="does not match"):
        resumed.reserve("/v2/daily/BBCA.JK/", 1)


def test_successor_budget_carries_prior_reservations_and_rejects_attempt_501(tmp_path):
    source = tmp_path / "source.json"
    source_budget = PersistentRequestBudget.create(
        source, run_id="sample-parent", plan_sha256="e" * 64, max_requests=450, max_credits=450,
    )
    for index in range(433):
        source_budget.reserve(f"/v2/daily/S{index:03d}.JK/", 1)
    source_bytes = source.read_bytes()
    source_state = json.loads(source_bytes)

    successor_path = tmp_path / "successor.json"
    successor = PersistentRequestBudget.create(
        successor_path,
        run_id="sample-successor",
        plan_sha256="f" * 64,
        max_requests=500,
        max_credits=500,
        initial_reservations=source_state["reservations"],
        inherited_budget={"run_id": "sample-parent", "budget_sha256": "a" * 64},
    )
    assert successor.snapshot()["requests_reserved"] == 433
    assert successor.snapshot()["credits_reserved"] == 433

    # The duplicate endpoint represents a retry and still reserves a new
    # request before transport.
    successor.reserve("/v2/daily/S000.JK/", 1)
    resumed = PersistentRequestBudget(successor_path, run_id="sample-successor", plan_sha256="f" * 64)
    for index in range(66):
        resumed.reserve(f"/v2/daily/N{index:03d}.JK/", 1)
    assert resumed.snapshot()["requests_reserved"] == 500
    with pytest.raises(CreditBudgetExceeded, match="request ceiling"):
        resumed.reserve("/v2/daily/attempt-501.JK/", 1)
    assert resumed.snapshot()["credits_reserved"] == 500
    assert source.read_bytes() == source_bytes


def test_mocked_client_retry_reserves_each_attempt_before_transport(tmp_path):
    budget = PersistentRequestBudget.create(
        tmp_path / "retry-budget.json", run_id="retry-run", plan_sha256="1" * 64,
        max_requests=2, max_credits=2,
    )
    attempts = []

    def transport(method, url, params, headers):
        attempts.append(url)
        return (429, {"error": "retry"}) if len(attempts) == 1 else (200, {"results": []})

    client = SectorsClient(
        api_key="test-only", transport=transport, allow_live=True, force_refresh=True,
        max_retries=1, backoff_seconds=0, max_estimated_credits=2, max_http_requests=2,
        budget_reserver=budget.reserve,
    )
    response = client.get("/v2/index-daily/ihsg/", {"start": "2025-12-15", "end": "2025-12-31"})

    assert response.status == 200
    assert len(attempts) == 2
    assert budget.snapshot()["requests_reserved"] == 2
    assert budget.snapshot()["credits_reserved"] == 2
    assert [row["sequence"] for row in json.loads((tmp_path / "retry-budget.json").read_text())["reservations"]] == [1, 2]
