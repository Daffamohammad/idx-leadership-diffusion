"""Tests for config and utility helpers."""
from __future__ import annotations

from datetime import date

import pytest

from idx_leadership.utils import load_yaml, project_root
from idx_leadership.utils.dates import asof_resolve, parse_date, to_iso
from idx_leadership.utils.errors import ConfigurationError
from idx_leadership.utils.logging import get_logger


def test_load_yaml_universe():
    cfg = load_yaml("config/universe.yaml")
    assert cfg["benchmark"] == "^JKSE"
    assert len(cfg["universe"]) > 0
    assert "ticker" in cfg["universe"][0]
    assert "sectors" in cfg["universe"][0]


def test_load_yaml_methodology():
    cfg = load_yaml("config/methodology.yaml")
    assert "horizons" in cfg
    assert cfg["horizons"]["short"] == 5
    assert cfg["horizons"]["primary"] == 20
    assert "breadth" in cfg
    assert "leadership" in cfg


def test_load_yaml_missing_file():
    with pytest.raises(FileNotFoundError):
        load_yaml("nonexistent.yaml")


def test_parse_date_accepts_string():
    assert parse_date("2026-01-01") == date(2026, 1, 1)


def test_parse_date_accepts_date():
    d = date(2026, 5, 1)
    assert parse_date(d) == d


def test_to_iso():
    assert to_iso(date(2026, 8, 20)) == "2026-08-20"


def test_asof_resolve_picks_latest_before_cutoff():
    dates = [date(2026, 1, 1), date(2026, 1, 5), date(2026, 1, 10)]
    assert asof_resolve(dates, date(2026, 1, 7)) == date(2026, 1, 5)


def test_asof_resolve_returns_none_when_stale():
    dates = [date(2026, 1, 1)]
    assert asof_resolve(dates, date(2026, 2, 1), tolerance_days=7) is None


def test_asof_resolve_returns_none_for_empty():
    assert asof_resolve([], date(2026, 1, 1)) is None


def test_get_logger_is_idempotent():
    a = get_logger("test.logger")
    b = get_logger("test.logger")
    assert a is b
