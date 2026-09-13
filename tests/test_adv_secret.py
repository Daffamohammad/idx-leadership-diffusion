"""Agent B — adversarial secret-leakage tests (canary keys).

Fail-closed: every test asserts a canary credential value is ABSENT from an
observable surface (rendered log lines, client envelopes, ledger entries and
flushed JSONL files, snapshot sidecars, error strings). All provider work uses
injected fake transports; zero live calls.
"""
from __future__ import annotations

import io
import json
import logging

import pytest

from idx_leadership.data import RawCache
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.tavily_client import TavilyClient
from idx_leadership.providers.you_client import YouClient
from idx_leadership.utils.logging import _redact, get_logger, log_event

CANARY = "CANARY_SK_9f8e7d6c5b4a_adv1"


def _rendered(msg, args=()):
    rec = logging.LogRecord("adv", logging.INFO, "f.py", 1, msg, args, None)
    _redact(rec)
    return rec.getMessage()


def _ok_payload():
    return {
        "results": [
            {"title": "t", "url": "https://idx.co.id/x", "content": "c"}
        ],
        "usage": {},
    }


def _clients(tmp_path, api_key=CANARY):
    cache_t = RawCache(root=tmp_path / "ct")
    cache_y = RawCache(root=tmp_path / "cy")
    ledger_t = RequestLedger(path=tmp_path / "t.jsonl")
    ledger_y = RequestLedger(path=tmp_path / "y.jsonl")
    ok = lambda m, u, p, h: (200, _ok_payload())  # noqa: E731
    tavily = TavilyClient(
        api_key=api_key, allow_live=True, transport=ok,
        cache=cache_t, ledger=ledger_t, backoff_seconds=0.0,
    )
    you = YouClient(
        api_key=api_key, allow_live=True, transport=ok,
        cache=cache_y, ledger=ledger_y, backoff_seconds=0.0,
    )
    return tavily, you


def test_logger_info_redacts_key_value_shapes():
    for msg in (
        f"api_key={CANARY}",
        f"token={CANARY} trailing",
        f"password={CANARY}",
        f"api_key={CANARY}",
    ):
        assert CANARY not in _rendered(msg), msg
    assert CANARY not in _rendered("api_key=%s", (CANARY,))


def test_logger_info_redacts_header_bearer_and_json_shapes():
    assert CANARY not in _rendered(f"Authorization: Bearer {CANARY}")
    assert CANARY not in _rendered(f"X-API-Key: {CANARY}")
    assert CANARY not in _rendered(f"api_key: {CANARY}")
    assert CANARY not in _rendered(json.dumps({"api_key": CANARY}))
    assert CANARY not in _rendered(json.dumps({"token": CANARY}))


def test_log_event_redacts_secret_named_fields():
    logger = get_logger("adv.secret.log_event")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        log_event(logger, "adv_probe", api_key=CANARY, note="hello")
        log_event(logger, "adv_probe", authorization=f"Bearer {CANARY}")
    finally:
        logger.removeHandler(handler)
    assert CANARY not in stream.getvalue()


def test_client_to_dict_contains_no_credential(tmp_path):
    tavily, you = _clients(tmp_path)
    assert CANARY not in json.dumps(tavily.search("probe").to_dict())
    assert CANARY not in json.dumps(you.search("probe").to_dict())
    assert CANARY not in json.dumps(you.research("probe").to_dict())


def test_client_search_context_records_contain_no_credential(tmp_path):
    tavily, you = _clients(tmp_path)
    assert CANARY not in json.dumps(tavily.search_context("probe"))
    assert CANARY not in json.dumps(you.search_context("probe"))


def test_ledger_entry_and_flush_file_contain_no_credential(tmp_path):
    ledger = RequestLedger(path=tmp_path / "ledger.jsonl")
    ledger.record(
        provider="tavily", endpoint="/search", request_type="POST",
        parameters={"query": "probe", "api_key": CANARY},
        cache_hit=False, status="ok", rows_returned=1, elapsed_ms=1.0,
        error=f"boom api_key={CANARY} Bearer {CANARY}",
    )
    for entry in ledger.entries():
        assert CANARY not in json.dumps(entry.__dict__, default=str)
    ledger.flush()
    assert CANARY not in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")


def test_error_paths_redact_credential(tmp_path):
    def bad_transport(method, url, params, headers):
        return 400, {"error": f"bad request {CANARY}"}

    tavily = TavilyClient(
        api_key=CANARY, allow_live=True, transport=bad_transport,
        cache=RawCache(root=tmp_path / "ce"), ledger=RequestLedger(path=tmp_path / "e.jsonl"),
        backoff_seconds=0.0,
    )
    with pytest.raises(Exception) as exc_info:
        tavily.search("probe")
    assert CANARY not in str(exc_info.value)

    you = YouClient(
        api_key=CANARY, allow_live=True, transport=bad_transport,
        cache=RawCache(root=tmp_path / "ce2"), ledger=RequestLedger(path=tmp_path / "e2.jsonl"),
        backoff_seconds=0.0,
    )
    with pytest.raises(Exception) as exc_info2:
        you.search("probe")
    assert CANARY not in str(exc_info2.value)


def test_snapshot_sidecar_envelopes_contain_no_credential(tmp_path):
    # Sidecar envelopes are built from response.to_dict() + request records;
    # prove the to_dict layer carries no credential material.
    tavily, you = _clients(tmp_path)
    t_dict = tavily.search("probe").to_dict()
    t_dict["quantitative_use"] = False
    y_dict = you.search("probe").to_dict()
    y_dict["quantitative_use"] = False
    sidecar = {"tavily": t_dict, "you": y_dict}
    (tmp_path / "sidecar.json").write_text(json.dumps(sidecar))
    assert CANARY not in (tmp_path / "sidecar.json").read_text(encoding="utf-8")


def test_env_loader_returns_names_only(tmp_path, monkeypatch):
    from idx_leadership.utils.config import load_project_env

    env_file = tmp_path / ".env"
    env_file.write_text(f"ADV_CANARY_KEY={CANARY}\n", encoding="utf-8")
    monkeypatch.delenv("ADV_CANARY_KEY", raising=False)
    loaded = load_project_env(env_file)
    assert loaded == ["ADV_CANARY_KEY"]
    assert CANARY not in json.dumps(loaded)
    monkeypatch.delenv("ADV_CANARY_KEY", raising=False)
