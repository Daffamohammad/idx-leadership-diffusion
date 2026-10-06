"""Legacy per-family publication entry point.

Market workspaces can no longer switch an independent market index. Build a
complete five-family candidate and use scripts.publish_release to activate it.
"""
from __future__ import annotations

import argparse
from pathlib import Path


_MIGRATION = (
    "per-family publication is disabled; assemble a complete five-family "
    "candidate and activate it with scripts.publish_release"
)


def publish(*_args: Path, **_kwargs: Path) -> dict:
    """Refuse the former independent market-index publication path."""
    raise ValueError(_MIGRATION)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("market", "ownership", "foreign", "out"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.parse_args()
    print(f"PUBLICATION_REFUSED: {_MIGRATION}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
