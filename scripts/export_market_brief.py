"""Export the local product contract as a deterministic Markdown brief.

Examples::

    python -m scripts.export_market_brief --mode demo
    python -m scripts.export_market_brief --mode latest --output market_brief.md
    python -m scripts.export_market_brief --snapshot data/snapshots/snap_2026-08-20

The command is deliberately offline. It reads an existing fixture or snapshot
and never constructs a provider client.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from idx_leadership.utils import project_root

from app.data_sources import (
    available_sources,
    load_demo_payload,
    load_snapshot_payload,
)
from app.view_models import build_dashboard_view, render_market_brief


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("demo", "latest"),
        default="demo",
        help="Local source to export when --snapshot is not supplied (default: demo).",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="Explicit persisted snapshot directory. Overrides --mode.",
    )
    parser.add_argument(
        "--selected-group",
        help="Group ID to feature in Selected Evidence (default: top material shift).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Markdown destination. Omit to print to stdout.",
    )
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    return parser.parse_args(argv)


def build_brief(args: argparse.Namespace) -> str:
    if args.snapshot is not None:
        payload = load_snapshot_payload(args.snapshot)
    elif args.mode == "latest":
        snapshots = [option for option in available_sources() if option.kind == "snapshot"]
        if not snapshots:
            raise FileNotFoundError("No persisted local snapshots are available")
        payload = load_snapshot_payload(snapshots[0].path)
    else:
        payload = load_demo_payload()

    view = build_dashboard_view(payload)
    if args.selected_group and view.group(args.selected_group) is None:
        valid = ", ".join(group.group_id for group in view.groups)
        raise ValueError(f"Unknown selected group {args.selected_group!r}; choose one of: {valid}")
    return render_market_brief(view, args.selected_group)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # Root containment for --out/--output (export pattern): outputs must
    # stay within the project root — or the system temp dir used by
    # isolated/pytest harnesses — unless --allow-outside-root is set.
    _project_root = project_root()
    _temp_root = Path(tempfile.gettempdir()).resolve()
    for _label, _value in (("--output", args.output),):
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

    try:
        markdown = build_brief(args)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"export_market_brief: {exc}", file=sys.stderr)
        return 2

    if args.output is None:
        sys.stdout.write(markdown)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
