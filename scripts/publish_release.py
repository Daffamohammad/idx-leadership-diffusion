"""Activate a verified five-family release candidate or roll back one release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from idx_leadership.data.releases import activate_candidate, rollback_to_previous
from idx_leadership.utils.config import project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--candidate",
        type=Path,
        help="staged candidate manifest.json to verify and activate",
    )
    action.add_argument(
        "--manifest",
        type=Path,
        help="the active pointer's previous retained manifest.json to reverify and select",
    )
    parser.add_argument(
        "--expect-active",
        required=True,
        help="expected active release ID, or 'none' before the first activation",
    )
    parser.add_argument(
        "--public-root",
        type=Path,
        default=project_root() / "app" / "web" / "public",
        help="frontend public directory (defaults to app/web/public)",
    )
    args = parser.parse_args()
    expected_active = None if args.expect_active == "none" else args.expect_active

    try:
        if args.candidate:
            pointer = activate_candidate(
                args.candidate,
                args.public_root,
                expected_active_release_id=expected_active,
            )
        else:
            pointer = rollback_to_previous(
                args.manifest,
                args.public_root,
                expected_active_release_id=expected_active,
            )
        print(json.dumps(pointer, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"PUBLICATION_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
