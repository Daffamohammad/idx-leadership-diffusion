"""Offline regression tests for the cached yfinance methodology harness."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.pipeline import build_snapshot
from idx_leadership.providers.public import _payload_to_frame
from scripts.yfinance_harness import YFinanceCacheProvider


def _write_universe(path: Path, tickers: list[str]) -> None:
    lines = [
        "benchmark: ^JKSE",
        "universe_version: harness-v1",
        "taxonomy_version: harness-v1",
        "universe:",
    ]
    lines.extend(
        f"  - {{ticker: {ticker}, sectors: Test, sub_sectors: Test}}"
        for ticker in tickers
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_cached_prices(
    prices_path: Path,
    benchmark_path: Path,
    tickers: list[str],
    as_of: date,
) -> None:
    dates = [as_of - timedelta(days=90 - index) for index in range(91)]
    price_rows = []
    for ticker_index, ticker in enumerate(tickers):
        for index, current_date in enumerate(dates):
            close = 100.0 + ticker_index * 3.0 + index * 0.5
            # Keep the corporate-action difference outside the 20D window but
            # inside the 60D window so the selected basis is observable.
            adjusted = close * (0.75 if index < 35 else 1.0)
            price_rows.append(
                {
                    "ticker": ticker,
                    "date": current_date,
                    "close": close,
                    "adjusted_close": adjusted,
                    "volume": 1_000_000,
                }
            )
    pd.DataFrame(price_rows).to_csv(prices_path, index=False)

    benchmark_dates = dates
    pd.DataFrame(
        {
            "benchmark_id": "^JKSE",
            "date": benchmark_dates,
            "close": [5_000.0 + index * 2.0 for index in range(len(benchmark_dates))],
        }
    ).to_csv(benchmark_path, index=False)


def test_cached_provider_never_calls_network_and_reports_selected_basis(tmp_path):
    prices_path = tmp_path / "prices.csv"
    benchmark_path = tmp_path / "benchmark.csv"
    universe_path = tmp_path / "universe.yaml"
    _write_universe(universe_path, ["A.JK"])
    _write_cached_prices(prices_path, benchmark_path, ["A.JK"], date(2026, 8, 28))

    raw = YFinanceCacheProvider(
        cache_path=prices_path,
        universe_path=universe_path,
        auto_adjust=False,
    )
    adjusted = YFinanceCacheProvider(
        cache_path=prices_path,
        universe_path=universe_path,
        auto_adjust=True,
    )
    start = date(2026, 6, 1)
    end = date(2026, 8, 28)

    raw_frame = raw.get_price_history(["A.JK"], start=start, end=end)
    adjusted_frame = adjusted.get_price_history(["A.JK"], start=start, end=end)

    assert set(raw_frame["price_basis"]) == {"close"}
    assert set(adjusted_frame["price_basis"]) == {"adjusted_close"}
    assert (raw_frame["close"] != raw_frame["adjusted_close"]).any()


def test_pipeline_harness_basis_reaches_feature_calculation(tmp_path):
    tickers = [f"H{i}.JK" for i in range(5)]
    as_of = date(2026, 8, 28)
    prices_path = tmp_path / "prices.csv"
    benchmark_path = tmp_path / "benchmark.csv"
    universe_path = tmp_path / "universe.yaml"
    methodology_path = Path(__file__).resolve().parents[1] / "config" / "methodology.yaml"
    _write_universe(universe_path, tickers)
    _write_cached_prices(prices_path, benchmark_path, tickers, as_of)

    raw_provider = YFinanceCacheProvider(
        cache_path=prices_path,
        universe_path=universe_path,
        auto_adjust=False,
    )
    raw_provider._benchmark_path = benchmark_path
    raw_provider.set_as_of(as_of)
    adjusted_provider = YFinanceCacheProvider(
        cache_path=prices_path,
        universe_path=universe_path,
        auto_adjust=True,
    )
    adjusted_provider._benchmark_path = benchmark_path
    adjusted_provider.set_as_of(as_of)

    raw_root = tmp_path / "raw"
    adjusted_root = tmp_path / "adjusted"
    build_snapshot(
        raw_provider,
        as_of=as_of,
        universe_path=universe_path,
        methodology_path=methodology_path,
        out_dir=raw_root,
        snapshot_id="raw",
        provider_mode="PUBLIC_PROTOTYPE",
        price_basis="close",
    )
    build_snapshot(
        adjusted_provider,
        as_of=as_of,
        universe_path=universe_path,
        methodology_path=methodology_path,
        out_dir=adjusted_root,
        snapshot_id="adjusted",
        provider_mode="PUBLIC_PROTOTYPE",
        price_basis="adjusted_close",
    )

    raw_snapshot = SnapshotReader(root=raw_root).load("raw")
    adjusted_snapshot = SnapshotReader(root=adjusted_root).load("adjusted")
    raw_manifest = json.loads((raw_root / "raw" / "manifest.json").read_text())
    adjusted_manifest = json.loads(
        (adjusted_root / "adjusted" / "manifest.json").read_text()
    )

    assert raw_manifest["price_basis"] == "close"
    assert adjusted_manifest["price_basis"] == "adjusted_close"
    raw_features = raw_snapshot["features"].set_index("ticker")
    adjusted_features = adjusted_snapshot["features"].set_index("ticker")
    assert not raw_features["return_60d"].equals(adjusted_features["return_60d"])


def test_live_probe_fixture_replays_deterministically():
    """Offline replay of the bounded 2026-09-13 BBCA.JK live probe (5 rows).

    The live receipt (1 call, 0 credits, keyless) lives in the closure
    shared ledger; this fixture pins the rows so interpretation stays
    deterministic without network.
    """
    fixture = json.loads(
        (Path("tests/fixtures") / "yfinance_probe_bbca_2026-09-06_12.json").read_text()
    )
    assert fixture["receipt"]["rows_returned"] == 5
    assert fixture["receipt"]["live_calls"] == 1
    frame = _payload_to_frame({"rows": fixture["rows"]}, ticker="BBCA.JK")
    assert len(frame) == 5
    assert set(frame["ticker"].unique().tolist()) == {"BBCA.JK"}
    assert frame["date"].min().isoformat() == "2026-09-07"
    assert frame["date"].max().isoformat() == "2026-09-11"
    assert (frame["close"] > 0).all()
    assert (frame["adjusted_close"] > 0).all()
