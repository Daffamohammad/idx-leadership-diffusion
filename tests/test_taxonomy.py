"""Tests for the reusable taxonomy backend."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.taxonomy import (
    MembershipType,
    Taxonomy,
    TaxonomyKind,
    TaxonomyMembership,
    TaxonomyRegistry,
    TaxonomySourceKind,
    aggregate_taxonomy,
    build_taxonomy_payload,
    load_registry_from_yaml,
)
from scripts.build_taxonomy_views import _compatible_previous


def _make_taxonomy(memberships: list[TaxonomyMembership]) -> Taxonomy:
    return Taxonomy(
        taxonomy_id="test",
        taxonomy_name="Test",
        taxonomy_version="v1",
        taxonomy_kind=TaxonomyKind.SECTOR,
        source_kind=TaxonomySourceKind.PROTOTYPE_CONFIG,
        source_as_of=date(2026, 8, 30),
        membership_policy="PRIMARY_ONLY",
        provider_mode="PUBLIC_PROTOTYPE",
        memberships=tuple(memberships),
    )


def _sample_prices() -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-08-28", periods=66)
    rows: list[dict[str, object]] = []
    for index, trading_date in enumerate(dates):
        rows.extend(
            [
                {
                    "ticker": "A.JK",
                    "date": trading_date,
                    "close": 100.0 + index,
                },
                {
                    "ticker": "B.JK",
                    "date": trading_date,
                    "close": 80.0 + (index * 0.5),
                },
            ]
        )
    return pd.DataFrame(rows)


def _sample_benchmark() -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-08-28", periods=66)
    return pd.DataFrame(
        {
            "date": dates,
            "close": [1000.0 + (index * 2.0) for index in range(len(dates))],
        }
    )


def test_registry_keeps_unique_taxonomy_ids():
    memberships = [
        TaxonomyMembership(ticker="A.JK", taxonomy_group_id="G1", taxonomy_group_name="Group 1")
    ]
    with pytest.raises(ValueError):
        TaxonomyRegistry([_make_taxonomy(memberships), _make_taxonomy(memberships)])


def test_aggregate_taxonomy_produces_one_aggregate_per_group():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(ticker="A.JK", taxonomy_group_id="G1", taxonomy_group_name="Group 1"),
            TaxonomyMembership(ticker="B.JK", taxonomy_group_id="G1", taxonomy_group_name="Group 1"),
            TaxonomyMembership(ticker="A.JK", taxonomy_group_id="G2", taxonomy_group_name="Group 2"),
        ]
    )
    aggregates = aggregate_taxonomy(
        taxonomy, _sample_prices(), _sample_benchmark(), as_of="2026-08-28"
    )
    assert {a.taxonomy_group_id for a in aggregates} == {"G1", "G2"}
    g1 = next(a for a in aggregates if a.taxonomy_group_id == "G1")
    assert g1.equal_weight_return_20d is not None
    assert g1.benchmark_return_20d is not None
    assert g1.excess_return_20d is not None


def test_aggregate_uses_exact_trading_session_offset():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(
                ticker="A.JK",
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
            )
        ]
    )
    aggregate = aggregate_taxonomy(
        taxonomy,
        _sample_prices(),
        _sample_benchmark(),
        as_of="2026-08-28",
        min_eligible_constituents=1,
    )[0]
    expected = ((165.0 / 145.0) - 1.0) * 100.0
    assert aggregate.equal_weight_return_20d == pytest.approx(expected, abs=1e-4)


def test_aggregate_filters_future_observations_at_as_of():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(
                ticker="A.JK",
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
            ),
            TaxonomyMembership(
                ticker="B.JK",
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
            ),
        ]
    )
    baseline = aggregate_taxonomy(
        taxonomy, _sample_prices(), _sample_benchmark(), as_of="2026-08-28"
    )[0]
    future_prices = pd.concat(
        [
            _sample_prices(),
            pd.DataFrame(
                {
                    "ticker": ["A.JK", "B.JK"],
                    "date": pd.to_datetime(["2026-08-31", "2026-08-31"]),
                    "close": [9999.0, 1.0],
                }
            ),
        ],
        ignore_index=True,
    )
    future_benchmark = pd.concat(
        [
            _sample_benchmark(),
            pd.DataFrame(
                {"date": pd.to_datetime(["2026-08-31"]), "close": [99999.0]}
            ),
        ],
        ignore_index=True,
    )
    with_future = aggregate_taxonomy(
        taxonomy, future_prices, future_benchmark, as_of="2026-08-28"
    )[0]
    assert with_future.equal_weight_return_20d == baseline.equal_weight_return_20d
    assert with_future.excess_return_20d == baseline.excess_return_20d


def test_aggregate_reports_actual_coverage_and_missing_member():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(
                ticker=ticker,
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
            )
            for ticker in ("A.JK", "B.JK", "MISSING.JK")
        ]
    )
    aggregate = aggregate_taxonomy(
        taxonomy, _sample_prices(), _sample_benchmark(), as_of="2026-08-28"
    )[0]
    assert aggregate.constituent_count == 3
    assert aggregate.eligible_constituent_count == 2
    assert aggregate.coverage_pct == pytest.approx(66.67)
    assert aggregate.data_quality == "READY_WITH_GAPS"


def test_zero_previous_breadth_is_a_valid_comparison_value():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(
                ticker=ticker,
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
            )
            for ticker in ("A.JK", "B.JK")
        ]
    )
    aggregate = aggregate_taxonomy(
        taxonomy,
        _sample_prices(),
        _sample_benchmark(),
        as_of="2026-08-28",
        prev_breadth={"G1": 0.0},
        prev_as_of="2026-08-20",
    )[0]
    assert aggregate.prev_breadth_outperforming == 0.0
    assert aggregate.breadth_delta is not None
    assert aggregate.diffusion_state == "BROADENING"


def test_missing_comparable_prior_keeps_diffusion_unconfirmed():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(
                ticker=ticker,
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
            )
            for ticker in ("A.JK", "B.JK")
        ]
    )
    aggregate = aggregate_taxonomy(
        taxonomy, _sample_prices(), _sample_benchmark(), as_of="2026-08-28"
    )[0]
    assert aggregate.breadth_outperforming is not None
    assert aggregate.prev_breadth_outperforming is None
    assert aggregate.breadth_delta is None
    assert aggregate.diffusion_state == "UNCONFIRMED"


def test_excluded_membership_does_not_count_in_aggregate():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(ticker="A.JK", taxonomy_group_id="G1", taxonomy_group_name="Group 1"),
            TaxonomyMembership(
                ticker="B.JK",
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
                membership_type=MembershipType.EXCLUDED,
            ),
        ]
    )
    aggregates = aggregate_taxonomy(taxonomy, _sample_prices(), _sample_benchmark())
    assert len(aggregates) == 1
    assert aggregates[0].constituent_count == 1


def test_overlapping_memberships_emit_per_group_aggregates():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(
                ticker="A.JK",
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
                membership_type=MembershipType.PRIMARY,
            ),
            TaxonomyMembership(
                ticker="A.JK",
                taxonomy_group_id="G2",
                taxonomy_group_name="Group 2",
                membership_type=MembershipType.SECONDARY,
            ),
        ]
    )
    aggregates = aggregate_taxonomy(taxonomy, _sample_prices(), _sample_benchmark())
    by_group = {a.taxonomy_group_id: a for a in aggregates}
    assert set(by_group) == {"G1", "G2"}
    assert by_group["G1"].membership_kind_breakdown["PRIMARY"] == 1
    assert by_group["G2"].membership_kind_breakdown["SECONDARY"] == 1


def test_build_taxonomy_payload_includes_metadata():
    taxonomy = _make_taxonomy(
        [TaxonomyMembership(ticker="A.JK", taxonomy_group_id="G1", taxonomy_group_name="Group 1")]
    )
    aggregates = aggregate_taxonomy(taxonomy, _sample_prices(), _sample_benchmark())
    payload = build_taxonomy_payload(taxonomy, aggregates, as_of="2026-08-28")
    assert payload["taxonomy_id"] == "test"
    assert payload["benchmark_id"] == "^JKSE"
    assert payload["schema_version"] == "taxonomy-view-v2"
    assert payload["memberships"][0]["ticker"] == "A.JK"
    assert payload["groups"]


def test_konglo_yaml_loads_and_validates():
    registry = load_registry_from_yaml("config/konglo.yaml")
    konglo = registry.get("konglo")
    assert konglo is not None
    assert konglo.taxonomy_kind == TaxonomyKind.KONGLO
    warnings = registry.validate()
    assert not warnings


def test_themes_yaml_loads_with_multiple_themes():
    registry = load_registry_from_yaml("config/themes.yaml")
    themes = registry.get("themes")
    assert themes is not None
    assert themes.taxonomy_kind == TaxonomyKind.THEMES
    group_ids = themes.groups()
    assert len(group_ids) >= 5


def test_aggregate_taxonomy_returns_data_gap_when_prices_missing():
    taxonomy = _make_taxonomy(
        [TaxonomyMembership(ticker="MISSING.JK", taxonomy_group_id="G1", taxonomy_group_name="Group 1")]
    )
    aggregates = aggregate_taxonomy(
        taxonomy, _sample_prices(), _sample_benchmark()
    )
    assert aggregates
    assert all(a.data_quality == "DATA_GAP" for a in aggregates)


def test_aggregate_taxonomy_preserves_groups_when_price_frame_is_empty():
    taxonomy = _make_taxonomy(
        [
            TaxonomyMembership(
                ticker=ticker,
                taxonomy_group_id="G1",
                taxonomy_group_name="Group 1",
            )
            for ticker in ("A.JK", "B.JK")
        ]
    )
    empty_prices = pd.DataFrame(columns=["ticker", "date", "close"])

    aggregates = aggregate_taxonomy(taxonomy, empty_prices, _sample_benchmark())

    assert len(aggregates) == 1
    assert aggregates[0].taxonomy_group_id == "G1"
    assert aggregates[0].constituent_count == 2
    assert aggregates[0].eligible_constituent_count == 0
    assert aggregates[0].data_quality == "DATA_GAP"


def test_load_registry_yaml_handles_extra_keys(tmp_path: Path):
    yaml_path = tmp_path / "test.yaml"
    yaml_path.write_text(
        """
taxonomy_id: smoke
taxonomy_name: Smoke test
taxonomy_version: smoke-v1
taxonomy_kind: THEMES
source_kind: ANALYST_DEFINED
source_as_of: 2026-08-30
membership_policy: MULTI
provider_mode: PUBLIC_PROTOTYPE
memberships:
  - ticker: A.JK
    taxonomy_group_id: G1
    taxonomy_group_name: Group 1
    confidence: 0.9
""",
        encoding="utf-8",
    )
    registry = load_registry_from_yaml(yaml_path)
    smoke = registry.get("smoke")
    assert smoke is not None
    assert smoke.memberships[0].confidence == pytest.approx(0.9)


def _compatibility_manifest(as_of: str, *, price_basis: str = "adjusted_close"):
    return {
        "snapshot_id": f"snap-{as_of}-{price_basis}",
        "as_of": as_of,
        "provider_mode": "PUBLIC_PROTOTYPE",
        "price_basis": price_basis,
        "method_version": "methodology-v3",
        "feature_version": "features-v3",
        "leadership_version": "leadership-v3",
        "diffusion_version": "diffusion-v2",
        "concentration_version": "concentration-v2",
        "eligibility_version": "eligibility-v2",
        "universe_version": "universe-v1",
        "taxonomy_version": "taxonomy-v1",
        "eligible_ticker_set_hash": "same-universe",
    }


def test_taxonomy_builder_selects_latest_compatible_price_basis(tmp_path: Path):
    entries = {
        "older-compatible": _compatibility_manifest("2026-08-12"),
        "latest-compatible": _compatibility_manifest("2026-08-26"),
        "latest-wrong-basis": _compatibility_manifest(
            "2026-08-27", price_basis="close"
        ),
    }
    paths: list[Path] = []
    for snapshot_id, entry in entries.items():
        path = tmp_path / snapshot_id
        path.mkdir()
        (path / "manifest.json").write_text(
            json.dumps({"entries": [entry]}), encoding="utf-8"
        )
        (path / "prices.csv").write_text("ticker,date,close\n", encoding="utf-8")
        (path / "benchmark.csv").write_text("date,close\n", encoding="utf-8")
        (path / "security_master.json").write_text("[]", encoding="utf-8")
        paths.append(path)

    class FakeReader:
        def list_snapshots(self):
            return paths

        def load(self, snapshot_id):
            return {"manifest": {"entries": [entries[snapshot_id]]}}

    previous_id, _, comparison = _compatible_previous(
        FakeReader(),
        "current",
        _compatibility_manifest("2026-08-28"),
        None,
    )
    assert previous_id == "latest-compatible"
    assert comparison["status"] == "COMPATIBLE"
