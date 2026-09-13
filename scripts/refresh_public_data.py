"""Refresh public-data prototype.

CLI: python -m scripts.refresh_public_data [--provider public|sectors|fixture]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.providers.public import YFinanceProvider
from idx_leadership.utils import data_root, get_logger, project_root

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="refresh_public_data")
    parser.add_argument("--provider", default="public", choices=["public", "sectors", "fixture"])
    parser.add_argument("--config", default="config/providers.yaml")
    parser.add_argument("--out", default=None, help="Override raw output directory")
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    args = parser.parse_args()
    # Root containment for --out/--output (export pattern): outputs must
    # stay within the project root — or the system temp dir used by
    # isolated/pytest harnesses — unless --allow-outside-root is set.
    _project_root = project_root()
    _temp_root = Path(tempfile.gettempdir()).resolve()
    for _label, _value in (("--out", args.out),):
        if _value:
            _resolved = Path(_value).resolve()
            _inside_root = True
            try:
                _resolved.relative_to(_project_root.resolve())
            except ValueError:
                _inside_root = False
            _inside_temp = True
            try:
                _resolved.relative_to(_temp_root)
            except ValueError:
                _inside_temp = False
            if not (_inside_root or _inside_temp) and not getattr(
                args, "allow_outside_root", False
            ):
                print(
                    f"refusing {_label} outside {_project_root} without --allow-outside-root",
                    file=sys.stderr,
                )
                return 2


    provider = build_provider_from_config(args.config, preferred=args.provider)
    if not isinstance(provider, YFinanceProvider):
        print("Only the public (yfinance) provider supports raw refresh in groundwork.", file=sys.stderr)
        return 2

    master = provider.get_security_master()
    tickers = [m.ticker for m in master]
    today = pd.Timestamp.utcnow().normalize().date()
    start = today - pd.Timedelta(days=int(60 * 1.6 + 20))

    print(f"Refreshing {len(tickers)} tickers from {start} to {today}", file=sys.stderr)
    prices = provider.get_price_history(tickers, start=start, end=today)
    benchmark = provider.get_benchmark_history("^JKSE", start=start, end=today)

    out_dir = Path(args.out) if args.out else (data_root() / "raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    prices.to_csv(out_dir / "prices_raw.csv", index=False)
    benchmark.to_csv(out_dir / "benchmark_raw.csv", index=False)
    (out_dir / "security_master.json").write_text(
        json.dumps([m.model_dump(mode="json") for m in master], indent=2, default=str),
        encoding="utf-8",
    )
    provider.ledger.flush()
    print(f"Refreshed {len(prices)} price rows and {len(benchmark)} benchmark rows.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
