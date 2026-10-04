"""Fetch and persist the long public price panel for the snapshot chain.

One bounded yfinance pass (public provider, retries + cache + request
ledger) over ``config/universe.yaml`` and the benchmark, covering
``--start`` (default 2025-12-15, so the YTD baseline of the last common
session <= 2025-12-31 is inside the window) through the latest available
trading session (``--end`` defaults to today).

Outputs (deterministic, offline-reusable by ``build_snapshot_chain``):

    data/raw/public/panel_<start>_<end>/
        prices.csv            ticker,date,close,adjusted_close,volume,...
        benchmark.csv         benchmark_id,date,close,price_basis,source
        source_manifest.json  URLs, window, counts, units, basis, sha256s

Counts reported separately per refresh contract:
requested / downloaded / failed / empty / usable / ytd-baseline-present.

CLI::

    python -m scripts.refresh_public_panel
    python -m scripts.refresh_public_panel --start 2025-12-15 --end 2026-10-04
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.public import YFinanceProvider
from idx_leadership.utils import data_root, get_logger, project_root

_log = get_logger(__name__)

# Day before the prior-year YTD baseline window opens (pipeline requests
# history from Dec 20 of the prior year); 2025-12-15 leaves several
# sessions of slack before the 2025-12-30 baseline.
DEFAULT_START = date(2025, 12, 15)
YTD_BASELINE_CUTOFF = date(2025, 12, 31)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _guard_out(path: Path) -> int | None:
    _project_root = project_root()
    _temp_root = Path(tempfile.gettempdir()).resolve()
    resolved = path.resolve()
    for root in (_project_root, _temp_root):
        try:
            resolved.relative_to(root.resolve())
            return None
        except ValueError:
            continue
    print(f"refusing --out-dir outside {_project_root}", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(prog="refresh_public_panel")
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--universe", default="config/universe.yaml")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        print("--end must be on or after --start", file=sys.stderr)
        return 2

    from idx_leadership.utils import load_yaml

    universe_cfg = load_yaml(args.universe)
    benchmark_id = str(universe_cfg.get("benchmark", "^JKSE"))
    tickers = [str(row["ticker"]) for row in universe_cfg.get("universe", [])]
    if not tickers:
        print("universe is empty", file=sys.stderr)
        return 2

    if args.out_dir:
        out_dir = Path(args.out_dir)
        if not args.allow_outside_root:
            guard = _guard_out(out_dir)
            if guard is not None:
                return guard
    else:
        out_dir = data_root() / "raw" / "public" / f"panel_{start.isoformat()}_{end.isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    ledger = RequestLedger()
    provider = build_provider_from_config(
        "config/providers.yaml", mode="PUBLIC_PROTOTYPE", ledger=ledger, universe_path=args.universe
    )
    if not isinstance(provider, YFinanceProvider):
        print("refresh_public_panel requires the public (yfinance) provider", file=sys.stderr)
        return 2

    print(
        f"Fetching {len(tickers)} tickers + {benchmark_id} "
        f"from {start} to {end} ...",
        file=sys.stderr,
    )
    prices = provider.get_price_history(tickers, start=start, end=end)
    diagnostics = dict(provider.history_diagnostics or {})
    benchmark = provider.get_benchmark_history(benchmark_id, start=start, end=end)
    ledger.flush()

    if prices.empty or benchmark.empty:
        print(
            f"empty fetch: prices={len(prices)} benchmark={len(benchmark)}",
            file=sys.stderr,
        )
        return 2

    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    prices = prices.sort_values(["ticker", "date"]).reset_index(drop=True)
    benchmark = benchmark.copy()
    benchmark["date"] = pd.to_datetime(benchmark["date"]).dt.date
    benchmark = benchmark.sort_values("date").reset_index(drop=True)

    per_ticker = prices.groupby("ticker")["date"].agg(["min", "max", "count"])
    downloaded = sorted(per_ticker.index.tolist())
    failed = sorted(diagnostics.get("failed_symbols") or [])
    empty = sorted(diagnostics.get("empty_symbols") or [])
    baseline_date = max(
        (d for d in prices["date"].unique() if d <= YTD_BASELINE_CUTOFF), default=None
    )
    baseline_present = (
        sorted(prices.loc[prices["date"] == baseline_date, "ticker"].unique().tolist())
        if baseline_date
        else []
    )
    usable = sorted(
        ticker
        for ticker, row in per_ticker.iterrows()
        if int(row["count"]) >= 60 and row["max"] <= end
    )
    latest_session = max(prices["date"].unique())
    benchmark_latest = max(benchmark["date"].unique())

    # Corporate-action disclosure: adjusted_close vs raw close divergence.
    divergence = (
        prices.loc[prices["close"] != prices["adjusted_close"], "ticker"]
        .value_counts()
        .to_dict()
    )
    corp_action_tickers = sorted(str(t) for t in divergence)

    prices_path = out_dir / "prices.csv"
    benchmark_path = out_dir / "benchmark.csv"
    prices.to_csv(prices_path, index=False)
    benchmark.to_csv(benchmark_path, index=False)

    manifest: dict[str, Any] = {
        "kind": "PUBLIC_PRICE_PANEL",
        "provider": "yfinance",
        "provider_mode": "PUBLIC_PROTOTYPE",
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "universe_path": args.universe,
        "universe_sha256": _sha256(Path(args.universe)),
        "universe_version": str(universe_cfg.get("universe_version")),
        "benchmark_id": benchmark_id,
        "endpoint": (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            "<ticker>?range/period1+period2&interval=1d (via yfinance yf.download)"
        ),
        "units": {
            "price": "IDR per share",
            "volume": "shares",
            "benchmark": "IDX Composite (IHSG) index points",
        },
        "price_basis": {
            "stocks": "close (raw) and adjusted_close both persisted; "
            "methodology return series use adjusted_close",
            "benchmark": "close",
        },
        "counts": {
            "requested": len(tickers),
            "downloaded": len(downloaded),
            "failed": len(failed),
            "empty": len(empty),
            "usable_ge_60_sessions": len(usable),
            "ytd_baseline_present": len(baseline_present),
            "rows": int(len(prices)),
            "benchmark_rows": int(len(benchmark)),
        },
        "sessions": {
            "latest_session": latest_session.isoformat(),
            "benchmark_latest_session": benchmark_latest.isoformat(),
            "ytd_baseline_date": baseline_date.isoformat() if baseline_date else None,
            "per_ticker": {
                t: {
                    "first": r["min"].isoformat(),
                    "last": r["max"].isoformat(),
                    "sessions": int(r["count"]),
                }
                for t, r in per_ticker.iterrows()
            },
        },
        "diagnostics": {
            "failed_symbols": failed,
            "empty_symbols": empty,
        },
        "corporate_actions": {
            "tickers_with_adjusted_close_divergence": corp_action_tickers,
            "divergent_row_counts": {str(k): int(v) for k, v in divergence.items()},
            "note": (
                "adjusted_close diverges from close where Yahoo applied "
                "dividends/splits in the window; raw close remains available "
                "for official-price comparison"
            ),
        },
        "files": {
            "prices.csv": {
                "sha256": _sha256(prices_path),
                "rows": int(len(prices)),
            },
            "benchmark.csv": {
                "sha256": _sha256(benchmark_path),
                "rows": int(len(benchmark)),
            },
        },
    }
    (out_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    counts = manifest["counts"]
    print(
        "panel fetched: "
        + ", ".join(f"{k}={v}" for k, v in counts.items()),
        file=sys.stderr,
    )
    print(
        f"latest_session={latest_session} ytd_baseline={baseline_date} "
        f"out={out_dir}",
        file=sys.stderr,
    )
    if failed or empty:
        print(
            f"unavailable tickers: failed={failed} empty={empty}",
            file=sys.stderr,
        )
    if not baseline_date:
        print("ERROR: no YTD baseline session in window", file=sys.stderr)
        return 2
    if len(downloaded) < len(tickers) - 5:
        print("ERROR: too many missing tickers", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
