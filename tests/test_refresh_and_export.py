from __future__ import annotations

import argparse

import pytest

from scripts.refresh_and_export import _operator_blockers


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "full_live": False,
        "allow_live": False,
        "allow_credit_spend": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_full_live_requires_both_explicit_acknowledgements():
    blockers = _operator_blockers(_args(full_live=True))

    assert [item["code"] for item in blockers] == [
        "LIVE_ACK_REQUIRED",
        "CREDIT_ACK_REQUIRED",
    ]


def test_bounded_live_also_blocks_missing_credit_acknowledgement():
    blockers = _operator_blockers(_args(allow_live=True))

    assert len(blockers) == 1
    assert blockers[0]["code"] == "CREDIT_ACK_REQUIRED"


def test_full_live_acknowledgements_require_local_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)

    blockers = _operator_blockers(
        _args(full_live=True, allow_live=True, allow_credit_spend=True)
    )

    assert [item["code"] for item in blockers] == ["SECTORS_API_KEY_UNAVAILABLE"]


def test_full_live_acknowledgements_clear_operator_blockers_with_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SECTORS_API_KEY", "local-test-only")

    assert _operator_blockers(
        _args(full_live=True, allow_live=True, allow_credit_spend=True)
    ) == []
