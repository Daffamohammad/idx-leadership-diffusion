"""Build a small history of snapshots for an existing raw pull.

CLI: python -m scripts.build_history --back-days 30 --step-days 5
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

import pandas as pd

from idx_leadership.pipeline import build_snapshot
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.utils import data_root, get_logger

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_history")
    parser.add_argument("--provider", default="public", choices=["public", "sectors", "fixture"])
    parser.add_argument("--config", default="config/providers.yaml")
    parser.add_argument("--back-days", type=int, default=30, help="Days to look back from today")
    parser.add_argument("--step-days", type=int, default=5, help="Days between snapshot dates")
    args = parser.parse_args()

    provider = build_provider_from_config(args.config, preferred=args.provider)
    today = date.today()
    n = max(1, args.back_days // max(1, args.step_days))
    out_dir = data_root() / "snapshots_history"
    for i in range(n):
        d = today - timedelta(days=(n - 1 - i) * args.step_days)
        print(f"Building snapshot for {d}", file=sys.stderr)
        try:
            build_snapshot(provider, as_of=d, out_dir=out_dir, snapshot_id=f"snap_{d.isoformat()}")
        except Exception as e:  # noqa: BLE001
            print(f"snapshot_failed date={d} err={e}", file=sys.stderr)
    print("history_complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
