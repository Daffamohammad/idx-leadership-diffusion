"""Fake-client regression test for the 429 BLOCKED path.

This test proves that the SectorsProvider.get_price_history 429
calibration:
  1. Calculates 429 failures AFTER worker results populate
     history_diagnostics (not before).
  2. Probes one symbol when >50% failed with 429.
  3. Sets blocked=True and raises a clear ProviderError when the
     probe also returns 429.
"""
from __future__ import annotations

import inspect
from datetime import date
import pytest

from idx_leadership.providers.sectors import SectorsProvider
from idx_leadership.providers.sectors_client import SectorsClient, SectorsResponse
from idx_leadership.models import ProviderMode
from idx_leadership.utils.errors import ProviderError


def _make_provider_with_mock_429(all_429: bool = True) -> SectorsProvider:
    """Build a SectorsProvider with a mock client that returns 429 for
    all calls (or 200 for all calls)."""
    from idx_leadership.providers.sectors_client import SectorsClient

    def transport(method, url, params, headers):
        if all_429:
            return 429, {"error": "RATE_LIMIT_EXCEEDED"}, {}
        return 200, {
            "results": [
                {"symbol": "T0.JK", "date": "2026-08-27", "close": 100.0},
                {"symbol": "T0.JK", "date": "2026-08-26", "close": 99.0},
            ],
        }, {}

    client = SectorsClient(
        api_key="fake",
        base_url="https://test.example.com",
        mode=ProviderMode.SECTORS_FIXTURE,
        max_retries=0,
        transport=transport,
        max_estimated_credits=None,
    )
    # Bypass the mode check by setting the attribute after construction
    # Actually, the SectorsClient accepts SECTORS_FIXTURE mode with transport
    return client

    def mock_get(path, params=None, **kwargs):
        if all_429:
            return SectorsResponse(
                payload={"error": "RATE_LIMIT_EXCEEDED"},
                status=429,
                endpoint=path,
                params=dict(params or {}),
                elapsed_ms=0.0,
                rows=0,
            )
        return SectorsResponse(
            payload={
                "symbol": path.split("/")[-1].rstrip("/"),
                "history": [
                    {"date": "2026-08-27", "close": 100.0},
                    {"date": "2026-08-26", "close": 99.0},
                ],
            },
            status=200,
            endpoint=path,
            params=dict(params or {}),
            elapsed_ms=0.0,
            rows=2,
        )

    # Patch the client.get method
    provider.client.get = mock_get
    return provider


def test_429_calibration_timing_calculation_after_workers():
    """The 429 failure count must be calculated AFTER worker results
    populate history_diagnostics, not before."""
    from idx_leadership.providers.sectors import SectorsProvider
    source = inspect.getsource(SectorsProvider.get_price_history)
    # The rate_limit_failures calculation must come AFTER the worker
    # loop (which appends to history_diagnostics["failed_symbols"]).
    loop_start = source.find("as_completed(futures)")
    calc_pos = source.find("rate_limit_failures = [")
    progress_pos = source.find("sectors_daily_history progress=")
    assert loop_start > 0 and calc_pos > 0 and progress_pos > 0
    # The 429 calibration must come AFTER the progress log
    # (which is the last thing in the worker loop)
    assert calc_pos > progress_pos, (
        "rate_limit_failures must be calculated AFTER the worker loop, "
        f"not before. loop_start={loop_start}, progress_pos={progress_pos}, "
        f"calc_pos={calc_pos}"
    )


def test_429_calibration_blocks_when_probe_still_429s():
    """When >50% of symbols fail with 429 AND a safe probe also returns
    429, the run must be BLOCKED with a clear error."""
    from idx_leadership.providers.sectors_client import SectorsClient
    from idx_leadership.models import ProviderName

    def transport_429(method, url, params, headers):
        return 429, {"error": "RATE_LIMIT_EXCEEDED"}, {}

    client = SectorsClient(
        api_key="fake",
        base_url="https://test.example.com",
        mode=ProviderMode.SECTORS_LIVE,
        allow_live=True,
        max_retries=0,
        transport=transport_429,
        max_estimated_credits=None,
        force_refresh=True,  # bypass cache
    )
    provider = SectorsProvider(
        api_key="fake", client=client, mode=ProviderMode.SECTORS_LIVE
    )

    with pytest.raises(ProviderError) as exc_info:
        provider.get_price_history(
            [f"T{i}.JK" for i in range(10)],
            start=date(2026, 5, 29),
            end=date(2026, 8, 27),
        )
    assert "429" in str(exc_info.value)
    assert provider.history_diagnostics.get("blocked") is True
    # Clear error message
    assert "429" in str(exc_info.value)
    # blocked flag set in diagnostics
    assert provider.history_diagnostics.get("blocked") is True


def test_429_calibration_near_threshold_does_not_block():
    """When exactly 50% (boundary) fail with 429 and the probe
    succeeds, the run must continue (threshold is strict > 50%)."""
    from idx_leadership.providers.sectors_client import SectorsClient

    # 10 symbols, exactly 5 (T0-T4) fail with 429, 5 (T5-T9) succeed,
    # probe succeeds. Threshold is strict > 50% = > 5, so 5 is NOT
    # over threshold.
    # Tickers T0-T4 return 429; T5-T9 return 200
    rate_limited = {f"T{i}.JK" for i in range(5)}

    def transport(method, url, params, headers):
        # Extract ticker from url
        parts = url.rstrip("/").split("/")
        ticker = parts[-1] if parts else ""
        if ticker in rate_limited:
            return 429, {"error": "RATE_LIMIT_EXCEEDED"}, {}
        return 200, {
            "results": [
                {"symbol": ticker, "date": "2026-08-27", "close": 100.0},
                {"symbol": ticker, "date": "2026-08-26", "close": 99.0},
            ],
        }, {}

    client = SectorsClient(
        api_key="fake",
        base_url="https://test.example.com",
        mode=ProviderMode.SECTORS_LIVE,
        allow_live=True,
        max_retries=0,
        transport=transport,
        max_estimated_credits=None,
        force_refresh=True,
    )
    provider = SectorsProvider(
        api_key="fake", client=client, mode=ProviderMode.SECTORS_LIVE
    )

    result = provider.get_price_history(
        [f"T{i}.JK" for i in range(10)],
        start=date(2026, 5, 29),
        end=date(2026, 8, 27),
    )
    # 5/10 = 50% failed; threshold is strict > 50%, so NOT blocked
    assert not result.empty
    assert provider.history_diagnostics.get("blocked", False) is False
    # Verify the 429 count is exactly 5
    failed = provider.history_diagnostics.get("failed_symbols", [])
    rate_429 = [f for f in failed if "status=429" in str(f.get("error", ""))]
    assert len(rate_429) == 5, f"Expected 5 429 failures, got {len(rate_429)}"
    assert provider.history_diagnostics.get("blocked", False) is False
