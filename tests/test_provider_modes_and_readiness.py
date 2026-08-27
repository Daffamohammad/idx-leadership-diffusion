"""Focused regression tests for provider modes and credential-day tooling."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.data import RawCache
from idx_leadership.models import ProviderMode
from idx_leadership.providers.factory import (
    build_provider_from_config,
    parse_provider_mode,
)
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.providers.sectors_contracts import validate_sectors_payload
from idx_leadership.utils.errors import NormalizationError, ProviderError
from scripts.audit_price_basis import LIVE_BLOCKED, main as price_basis_main
from scripts.audit_sectors_credit import BALANCE_UNAVAILABLE, build_credit_audit
from scripts.compare_providers import (
    PARITY_CLASSIFICATIONS,
    PARITY_COLUMNS,
    build_parity_table,
)
from scripts.plan_sectors_refresh import estimate_refresh_plan
from scripts.validate_sectors_live import main as validate_live_main, sanitize_payload


SECTORS_FIXTURES = Path("data/fixtures/sectors")


def _json(path: str) -> dict:
    return json.loads((SECTORS_FIXTURES / path).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("DEMO_FIXTURE", ProviderMode.DEMO_FIXTURE),
        ("public", ProviderMode.PUBLIC_PROTOTYPE),
        ("sectors_fixture", ProviderMode.SECTORS_FIXTURE),
        ("sectors", ProviderMode.SECTORS_LIVE),
    ],
)
def test_provider_mode_parser_has_explicit_legacy_mapping(raw, expected):
    assert parse_provider_mode(raw) is expected


def test_factory_builds_all_non_live_modes_without_fallback():
    demo = build_provider_from_config(mode=ProviderMode.DEMO_FIXTURE)
    public = build_provider_from_config(mode=ProviderMode.PUBLIC_PROTOTYPE)
    fixture = build_provider_from_config(mode=ProviderMode.SECTORS_FIXTURE)
    assert demo.mode is ProviderMode.DEMO_FIXTURE
    assert public.mode is ProviderMode.PUBLIC_PROTOTYPE
    assert fixture.mode is ProviderMode.SECTORS_FIXTURE
    assert fixture.name == "sectors_fixture"


def test_live_mode_does_not_downgrade_without_credentials(monkeypatch):
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)
    provider = build_provider_from_config(
        mode=ProviderMode.SECTORS_LIVE, allow_live=True
    )
    assert provider.mode is ProviderMode.SECTORS_LIVE
    with pytest.raises(ProviderError, match="credential missing"):
        provider.get_security_master()


@pytest.mark.parametrize(
    ("allow_live", "api_key", "message"),
    [
        (False, "VALID_LOOKING_KEY", "disabled"),
        (True, "", "credential missing"),
    ],
)
def test_live_cache_cannot_bypass_mode_or_credential_gate(
    tmp_path, allow_live, api_key, message
):
    cache = RawCache(root=tmp_path / "cache")
    client = SectorsClient(
        api_key=api_key,
        cache=cache,
        ledger=RequestLedger(path=tmp_path / "ledger.jsonl"),
        allow_live=allow_live,
    )
    url = "https://api.sectors.app/v2/close/"
    params = {"date": "2026-08-20"}
    cache.set(client._cache_key("GET", url, params), {"results": []})
    with pytest.raises(ProviderError, match=message):
        client.get("/v2/close/", params)


def test_force_refresh_bypasses_cache_only_after_live_gates(tmp_path):
    calls = {"count": 0}

    def transport(method, url, params, headers):
        calls["count"] += 1
        return 200, {
            "results": [{"symbol": "BBCA.JK", "date": "2026-08-20", "close": 101.0}],
            "pagination": {"limit": 30, "offset": 0, "has_next": False},
        }

    cache = RawCache(root=tmp_path / "cache")
    client = SectorsClient(
        api_key="K",
        cache=cache,
        ledger=RequestLedger(path=tmp_path / "ledger.jsonl"),
        allow_live=True,
        transport=transport,
        force_refresh=True,
        validate_contracts=True,
    )
    params = {"date": "2026-08-20"}
    key = client._cache_key("GET", "https://api.sectors.app/v2/close/", params)
    cache.set(
        key,
        {
            "results": [{"symbol": "BBCA.JK", "date": "2026-08-20", "close": 99.0}],
            "pagination": {"limit": 30, "offset": 0, "has_next": False},
        },
    )
    response = client.get("/v2/close/", params)
    assert calls["count"] == 1
    assert response.payload["results"][0]["close"] == 101.0


def test_sectors_fixture_walks_pagination_and_handles_null_taxonomy():
    provider = build_provider_from_config(mode=ProviderMode.SECTORS_FIXTURE)
    master = provider.get_security_master()
    assert [row.ticker for row in master] == ["BBCA.JK", "ADRO.JK", "KLBF.JK"]
    assert master[-1].subindustry is None
    assert {entry.provider for entry in provider.ledger.entries()} == {"sectors_fixture"}
    assert sum(entry.estimated_credit_cost for entry in provider.ledger.entries()) == 0


def test_sectors_fixture_close_and_empty_page_are_deterministic():
    provider = build_provider_from_config(mode=ProviderMode.SECTORS_FIXTURE)
    full = provider.get_full_universe_close(date(2026, 8, 20))
    empty = provider.get_full_universe_close(date(2026, 8, 21))
    assert set(full["ticker"]) == {"BBCA.JK", "ADRO.JK", "KLBF.JK", "IHSG.JK"}
    assert set(full["source"]) == {"sectors_fixture"}
    assert empty.empty


def test_sectors_fixture_api_error_is_not_normalized():
    provider = build_provider_from_config(mode=ProviderMode.SECTORS_FIXTURE)
    with pytest.raises(ProviderError, match="SYNTHETIC_API_ERROR"):
        provider.client.get("/v2/test/error/", {}, use_cache=False)


def test_contract_allows_extra_fields_and_null_optional_taxonomy():
    for name in ("companies_page_1.json", "companies_page_2.json"):
        report = validate_sectors_payload("/v2/companies/", _json(name))
        assert report.valid, report.to_dict()


@pytest.mark.parametrize(
    ("fixture", "endpoint", "expected_date", "code"),
    [
        ("cases/companies_duplicate.json", "/v2/companies/", None, "DUPLICATE_IDENTIFIER"),
        ("cases/close_missing_symbol.json", "/v2/close/", "2026-08-20", "PRIMARY_IDENTIFIER"),
        ("cases/close_unexpected_date.json", "/v2/close/", "2026-08-20", "UNEXPECTED_DATE"),
    ],
)
def test_contract_drift_fails_loudly(fixture, endpoint, expected_date, code):
    report = validate_sectors_payload(
        endpoint, _json(fixture), expected_date=expected_date
    )
    assert not report.valid
    assert code in {issue.code for issue in report.issues}
    with pytest.raises(NormalizationError):
        report.raise_for_errors()


def test_validate_live_defaults_to_network_free_dry_run(monkeypatch, capsys):
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)
    assert validate_live_main([]) == 0
    assert "DRY RUN — NO SECTORS HTTP REQUESTS" in capsys.readouterr().out


def test_validate_live_requires_both_intent_flags(monkeypatch, capsys):
    monkeypatch.setenv("SECTORS_API_KEY", "must-not-be-used")
    assert validate_live_main(["--live"]) == 2
    assert "--allow-credit-spend" in capsys.readouterr().err


def test_validate_live_missing_key_is_blocked_before_network(monkeypatch, capsys):
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)
    assert validate_live_main(["--live", "--allow-credit-spend"]) == 2
    assert "SECTORS_API_KEY is unavailable" in capsys.readouterr().err


def test_sanitizer_strips_nested_secrets():
    payload = {
        "results": [{"symbol": "BBCA"}],
        "headers": {"Authorization": "secret"},
        "access_token": "secret-2",
    }
    clean = sanitize_payload(payload)
    assert clean["headers"] == "[REDACTED]"
    assert clean["access_token"] == "[REDACTED]"
    assert "secret" not in json.dumps(clean)


def test_credit_audit_preserves_balance_unavailable():
    report = build_credit_audit([], request_category="CORE")
    assert report["before_balance"] == BALANCE_UNAVAILABLE
    assert report["after_balance"] == BALANCE_UNAVAILABLE
    assert report["observed_delta"] == BALANCE_UNAVAILABLE


def test_credit_audit_computes_only_observed_delta():
    report = build_credit_audit(
        [], request_category="CORE", before_balance=100.0, after_balance=97.5
    )
    assert report["observed_delta"] == 2.5
    assert report["balance_status"] == "OBSERVED"


def test_refresh_plan_has_calls_pages_cache_hits_but_no_credit_number():
    report = estimate_refresh_plan(
        universe_size=61,
        page_size=30,
        enrichment_names=2,
        deep_dive_names=1,
        cached=["security_master"],
    )
    assert report["totals"]["expected_http_calls"] >= 1
    assert report["totals"]["expected_pages"] >= 3
    assert report["totals"]["expected_cache_hits"] >= 1
    assert report["credit_estimate"] == "NOT CALCULATED — credit cost is not inferred"


def _frame(ticker: str, day: str, value: float, column: str) -> pd.DataFrame:
    return pd.DataFrame([{"ticker": ticker, "date": day, column: value}])


def test_parity_schema_and_allowed_classifications_are_exact():
    tables = [
        build_parity_table(
            _frame("AAA.JK", "2026-08-20", 100.0, "close"),
            _frame("AAA.JK", "2026-08-20", 100.0, "close"),
            public_value="close",
            sectors_value="close",
        ),
        build_parity_table(
            _frame("AAA.JK", "2026-08-20", 100.0, "close"),
            _frame("AAA.JK", "2026-08-20", 100.05, "close"),
            public_value="close",
            sectors_value="close",
        ),
        build_parity_table(
            _frame("AAA.JK", "2026-08-20", 100.0, "adjusted_close"),
            _frame("AAA.JK", "2026-08-20", 95.0, "close"),
            price_basis_confirmed=True,
        ),
        build_parity_table(
            _frame("AAA.JK", "2026-08-20", 100.0, "close"),
            _frame("AAA.JK", "2026-08-20", 80.0, "close"),
            public_value="close",
            sectors_value="close",
            corporate_actions=[{"date": "2026-08-20"}],
        ),
        build_parity_table(
            _frame("AAA", "2026-08-20", 100.0, "close"),
            _frame("AAA.JK", "2026-08-20", 100.0, "close"),
            public_value="close",
            sectors_value="close",
        ),
        build_parity_table(
            _frame("AAA.JK", "2026-08-20", 100.0, "close"),
            _frame("AAA.JK", "2026-08-21", 100.0, "close"),
            public_value="close",
            sectors_value="close",
        ),
        build_parity_table(
            _frame("AAA.JK", "2026-08-20", 100.0, "close"),
            _frame("AAA.JK", "2026-08-20", 80.0, "close"),
            public_value="close",
            sectors_value="close",
        ),
    ]
    result = pd.concat(tables, ignore_index=True)
    assert tuple(result.columns) == PARITY_COLUMNS
    assert set(result["Classification"]) == set(PARITY_CLASSIFICATIONS)


def test_price_basis_fixture_report_keeps_live_blocker_explicit(tmp_path, capsys):
    out = tmp_path / "basis"
    rc = price_basis_main(
        [
            "--ticker",
            "BBCA.JK",
            "--start",
            "2026-08-20",
            "--end",
            "2026-08-20",
            "--corporate-action-date",
            "2026-08-20",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["sectors_live_status"] == LIVE_BLOCKED
    assert report["fixture_warning"].startswith("SYNTHETIC")
    assert LIVE_BLOCKED in capsys.readouterr().out
