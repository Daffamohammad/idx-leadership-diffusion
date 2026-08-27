"""Build a single dated snapshot.

CLI: python -m scripts.build_snapshot [--as-of YYYY-MM-DD] [--provider ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from idx_leadership.pipeline import build_snapshot
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.utils import data_root, get_logger

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_snapshot")
    parser.add_argument("--as-of", default=None, help="As-of date YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--provider", default="public", choices=["public", "sectors", "fixture"])
    parser.add_argument("--config", default="config/providers.yaml")
    parser.add_argument("--universe", default="config/universe.yaml")
    parser.add_argument("--methodology", default="config/methodology.yaml")
    parser.add_argument("--snapshot-id", default=None)
    args = parser.parse_args()

    provider = build_provider_from_config(args.config, preferred=args.provider)
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    result = build_snapshot(
        provider,
        as_of=as_of,
        universe_path=args.universe,
        methodology_path=args.methodology,
        snapshot_id=args.snapshot_id,
    )
    print(json.dumps({"snapshot_id": result["snapshot_id"], "quality": result["quality"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
