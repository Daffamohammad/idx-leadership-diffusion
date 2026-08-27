"""Group-size diffusion sensitivity.

Renders a small reproducible table of diffusion v2 classifications
across deterministic group sizes (3, 4, 5, 7, 10, 20, 40) for a
canonical +20pp breadth move. This is the offline analogue of the live
group-size calibration the runbook will exercise once a key arrives.

It is not a live IDX calibration. It is a methodology guardrail: the
output is a JSON table plus a one-line summary that the snapshot
auditor can re-run on every methodology change.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from idx_leadership.signals.diffusion_v2 import (
    DiffusionStateV2,
    classify_diffusion_v2,
    constituent_floor,
)


GROUP_SIZES = (3, 4, 5, 7, 10, 20, 40)
DEFAULT_DELTAS = (-30.0, -20.0, -10.0, -5.0, 0.0, 5.0, 10.0, 20.0, 30.0)


def diffusion_grid(
    *,
    deltas: tuple[float, ...] = DEFAULT_DELTAS,
    group_sizes: tuple[int, ...] = GROUP_SIZES,
    fraction: float = 0.10,
    minimum_constituents: int = 2,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for group_size in group_sizes:
        floor = constituent_floor(
            group_size, fraction=fraction, minimum=minimum_constituents
        )
        for delta in deltas:
            state = classify_diffusion_v2(
                breadth_current=50.0 + delta,
                breadth_previous=50.0,
                group_size=group_size,
                fraction=fraction,
                minimum_constituents=minimum_constituents,
            )
            rows.append(
                {
                    "group_size": group_size,
                    "floor": floor,
                    "breadth_delta_pp": delta,
                    "state": state.value,
                }
            )
    return {
        "fraction": fraction,
        "minimum_constituents": minimum_constituents,
        "deltas": list(deltas),
        "group_sizes": list(group_sizes),
        "rows": rows,
    }


def summarize(grid: dict[str, Any]) -> list[str]:
    """Return one bullet per group size summarising the threshold edges."""
    bullets: list[str] = []
    for group_size in grid["group_sizes"]:
        relevant = [r for r in grid["rows"] if r["group_size"] == group_size]
        first_broadening = next(
            (r for r in relevant if r["state"].startswith("BROADENING")), None
        )
        first_narrowing = next(
            (r for r in relevant if r["state"].startswith("NARROWING")), None
        )
        bullet = (
            f"group_size={group_size:>3} floor={first_broadening['floor'] if first_broadening else 'n/a'} "
            f"first_broadening={first_broadening['breadth_delta_pp'] if first_broadening else 'n/a'} "
            f"first_narrowing={first_narrowing['breadth_delta_pp'] if first_narrowing else 'n/a'}"
        )
        bullets.append(bullet)
    return bullets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audit_group_size_diffusion")
    parser.add_argument("--out", default=None)
    parser.add_argument("--fraction", type=float, default=0.10)
    parser.add_argument("--minimum-constituents", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    grid = diffusion_grid(
        fraction=args.fraction,
        minimum_constituents=args.minimum_constituents,
    )
    payload = {
        **grid,
        "bullets": summarize(grid),
        "live_sectors_validated": False,
    }
    out_path = (
        Path(args.out)
        if args.out
        else Path("data/normalized/methodology/group_size_diffusion.json")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for line in payload["bullets"]:
        print(line)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
