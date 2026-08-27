from __future__ import annotations

from idx_leadership.data.comparability import assess_snapshot_comparability


def _entry(**overrides):
    row = {
        "as_of": "2026-08-20",
        "provider": "fixture",
        "provider_mode": "DEMO_FIXTURE",
        "universe_version": "demo-v1",
        "taxonomy_version": "demo-v1",
        "eligibility_version": "eligibility-v1",
        "method_version": "methodology-v3",
        "feature_version": "features-v3",
        "leadership_version": "leadership-v2",
        "diffusion_version": "diffusion-v2",
        "concentration_version": "concentration-v3",
    }
    row.update(overrides)
    return row


def test_compatible_snapshots_require_earlier_previous():
    current = _entry(as_of="2026-08-20")
    previous = _entry(as_of="2026-08-13")
    result = assess_snapshot_comparability(current, previous)
    assert result.comparable is True
    assert result.status == "COMPATIBLE"


def test_provider_mode_mismatch_is_explicit():
    result = assess_snapshot_comparability(
        _entry(as_of="2026-08-20", provider_mode="SECTORS_LIVE"),
        _entry(as_of="2026-08-13", provider_mode="PUBLIC_PROTOTYPE"),
    )
    assert result.comparable is False
    assert any("provider mode differs" in reason for reason in result.reasons)


def test_method_universe_and_taxonomy_mismatches_are_all_reported():
    result = assess_snapshot_comparability(
        _entry(as_of="2026-08-20"),
        _entry(
            as_of="2026-08-13",
            method_version="methodology-v2",
            universe_version="demo-v0",
            taxonomy_version="demo-v0",
        ),
    )
    assert result.comparable is False
    joined = " | ".join(result.reasons)
    assert "method_version differs" in joined
    assert "universe_version differs" in joined
    assert "taxonomy_version differs" in joined


def test_future_snapshot_cannot_be_previous():
    result = assess_snapshot_comparability(
        _entry(as_of="2026-08-20"),
        _entry(as_of="2026-08-27"),
    )
    assert result.comparable is False
    assert any("not earlier" in reason for reason in result.reasons)

