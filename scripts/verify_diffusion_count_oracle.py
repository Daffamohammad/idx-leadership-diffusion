"""Independent integer-count oracle for diffusion v2 labels.

Recomputes every daily and weekly diffusion state, the legacy v1
projection, and every weekly transition directly from the stored
breadth counts using pure integer arithmetic. Never imports the
production classifier, so it can detect floating-point or cadence
drift in the builder output.

Exit code 0 means zero mismatches across every observation and
transition in the analyzed asset.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

GROUP_SIGNAL_FLOOR = 5


def oracle_state(*, delta_count: int, group_size: int) -> str:
    """Integer oracle: broadening d*10 >= n, narrowing d*10 <= -n,
    firm floor max(2, (n+9)//10)."""
    floor = max(2, (group_size + 9) // 10)
    if delta_count * 10 >= group_size and abs(delta_count) >= floor:
        return "BROADENING_FIRM"
    if delta_count * 10 <= -group_size and abs(delta_count) >= floor:
        return "NARROWING_FIRM"
    if delta_count * 10 >= group_size:
        return "BROADENING_FRAGILE"
    if delta_count * 10 <= -group_size:
        return "NARROWING_FRAGILE"
    return "STABLE"


def expected_state(*, breadth_change_count: int | None, group_size: int | None) -> str:
    if breadth_change_count is None or group_size is None or group_size < GROUP_SIGNAL_FLOOR:
        return "UNCONFIRMED"
    return oracle_state(delta_count=breadth_change_count, group_size=group_size)


def legacy_projection(v2: str) -> str:
    if v2 == "UNCONFIRMED":
        return "UNCONFIRMED"
    if v2.endswith("_FIRM") or v2.endswith("_FRAGILE"):
        return v2.removesuffix("_FIRM").removesuffix("_FRAGILE")
    return v2


def check_cadence(
    observations: list[dict[str, Any]],
    *,
    cadence: str,
    mismatches: list[dict[str, Any]],
) -> int:
    checked = 0
    for index, obs in enumerate(observations):
        expected = expected_state(
            breadth_change_count=obs.get("breadth_change_count"),
            group_size=obs.get("breadth_denominator"),
        )
        actual = obs.get("diffusion_v2")
        checked += 1
        if actual != expected:
            mismatches.append({
                "cadence": cadence,
                "as_of": obs.get("as_of"),
                "actual": actual,
                "expected": expected,
                "breadth_change_count": obs.get("breadth_change_count"),
                "breadth_denominator": obs.get("breadth_denominator"),
            })
        actual_legacy = obs.get("diffusion")
        if actual_legacy != legacy_projection(expected):
            mismatches.append({
                "cadence": cadence,
                "kind": "legacy_diffusion",
                "as_of": obs.get("as_of"),
                "actual": actual_legacy,
                "expected": legacy_projection(expected),
            })
        if cadence == "weekly" and index > 0:
            previous = observations[index - 1]
            previous_expected = expected_state(
                breadth_change_count=previous.get("breadth_change_count"),
                group_size=previous.get("breadth_denominator"),
            )
            expected_transition = (
                f"{previous_expected} -> {expected}"
                if previous_expected != expected
                else None
            )
            if obs.get("diffusion_transition") != expected_transition:
                mismatches.append({
                    "cadence": "weekly",
                    "kind": "diffusion_transition",
                    "as_of": obs.get("as_of"),
                    "actual": obs.get("diffusion_transition"),
                    "expected": expected_transition,
                })
    return checked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_diffusion_count_oracle")
    parser.add_argument("--analysis", required=True, type=Path)
    args = parser.parse_args(argv)

    payload = json.loads(args.analysis.read_text(encoding="utf-8"))
    mismatches: list[dict[str, Any]] = []
    daily_checked = 0
    weekly_checked = 0
    group_count = 0
    for taxonomy in payload.get("taxonomies", {}).values():
        for group in taxonomy.get("groups", {}).values():
            group_count += 1
            daily_checked += check_cadence(group.get("daily", []), cadence="daily", mismatches=mismatches)
            weekly_checked += check_cadence(group.get("weekly", []), cadence="weekly", mismatches=mismatches)

    print(f"groups: {group_count}")
    print(f"daily observations checked: {daily_checked}")
    print(f"weekly observations checked: {weekly_checked}")
    print(f"mismatches: {len(mismatches)}")
    for row in mismatches[:20]:
        print(json.dumps(row, sort_keys=True))
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
