"""Dry-run Sectors refresh plan expressed in calls/pages/cache hits.

The company screener and full-universe close feed have different documented
page limits. Keep those boundaries separate here even though this planner does
not infer paid-provider credits; the live snapshot preflight is authoritative
for the 1,000-credit ceiling.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

from idx_leadership.utils import data_root, load_yaml


REFRESH_TIERS = {
    "CORE": ("security_master", "taxonomy", "market_close", "benchmark"),
    "ENRICHMENT": ("free_float", "fundamentals", "foreign_flow"),
    "DEEP_DIVE": ("broker", "filings", "news", "corporate_actions"),
}
COMPANIES_PAGE_SIZE = 200
CLOSE_PAGE_SIZE = 30
FREE_FLOAT_PAGE_SIZE = 100


def estimate_refresh_plan(
    *,
    universe_size: int,
    page_size: int = COMPANIES_PAGE_SIZE,
    enrichment_names: int = 0,
    deep_dive_names: int = 0,
    cached: Iterable[str] = (),
) -> dict[str, Any]:
    if universe_size < 0 or page_size < 1 or enrichment_names < 0 or deep_dive_names < 0:
        raise ValueError("refresh-plan counts must be non-negative and page_size positive")
    cached_set = {name.strip() for name in cached if name.strip()}
    company_pages = math.ceil(universe_size / page_size) if universe_size else 0
    close_pages = math.ceil(universe_size / CLOSE_PAGE_SIZE) if universe_size else 0
    free_float_pages = (
        math.ceil(universe_size / FREE_FLOAT_PAGE_SIZE) if universe_size else 0
    )
    specs = [
        ("CORE", "security_master", company_pages),
        # Taxonomy reuses the companies/security-master payload.
        ("CORE", "taxonomy", 0),
        ("CORE", "market_close", close_pages),
        # The live provider uses the native IHSG history route.
        ("CORE", "benchmark", 1 if universe_size else 0),
        ("ENRICHMENT", "free_float", free_float_pages),
        ("ENRICHMENT", "fundamentals", enrichment_names),
        ("ENRICHMENT", "foreign_flow", enrichment_names),
        ("DEEP_DIVE", "broker", deep_dive_names),
        ("DEEP_DIVE", "filings", deep_dive_names),
        ("DEEP_DIVE", "news", deep_dive_names),
        ("DEEP_DIVE", "corporate_actions", deep_dive_names),
    ]
    rows: list[dict[str, Any]] = []
    for tier, category, pages in specs:
        shared_source = {
            "taxonomy": "security_master",
        }.get(category)
        # Shared-source consumers always count as cache reuse within this plan.
        if shared_source is not None:
            http_calls = 0
            cache_hits = 1
        elif category in cached_set:
            http_calls = 0
            cache_hits = max(1, pages)
        else:
            http_calls = pages
            cache_hits = 0
        rows.append(
            {
                "tier": tier,
                "request_category": category,
                "expected_http_calls": http_calls,
                "expected_pages": pages,
                "expected_cache_hits": cache_hits,
                "shared_source": shared_source,
            }
        )
    return {
        "mode": "DRY_RUN",
        "provider_mode": "SECTORS_LIVE",
        "inputs": {
            "universe_size": universe_size,
            "page_size": page_size,
            "documented_page_sizes": {
                "companies": page_size,
                "close": CLOSE_PAGE_SIZE,
                "free_float": FREE_FLOAT_PAGE_SIZE,
            },
            "enrichment_names": enrichment_names,
            "deep_dive_names": deep_dive_names,
            "cached": sorted(cached_set),
        },
        "tiers": {tier: list(categories) for tier, categories in REFRESH_TIERS.items()},
        "requests": rows,
        "totals": {
            "expected_http_calls": sum(row["expected_http_calls"] for row in rows),
            "expected_pages": sum(row["expected_pages"] for row in rows),
            "expected_cache_hits": sum(row["expected_cache_hits"] for row in rows),
        },
        "credit_estimate": "NOT CALCULATED — credit cost is not inferred",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plan_sectors_refresh")
    parser.add_argument("--config", default="config/providers.yaml")
    parser.add_argument("--universe-size", type=int, default=None)
    parser.add_argument("--page-size", type=int, default=None)
    parser.add_argument("--enrichment-names", type=int, default=0)
    parser.add_argument("--deep-dive-names", type=int, default=0)
    parser.add_argument(
        "--cached",
        default="",
        help="Comma-separated request categories already present in cache.",
    )
    parser.add_argument("--out", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_yaml(args.config)
    plan_cfg = cfg.get("refresh_plan", {})
    try:
        report = estimate_refresh_plan(
            universe_size=(
                args.universe_size
                if args.universe_size is not None
                else int(plan_cfg.get("universe_size", 0))
            ),
            page_size=(
                args.page_size
                if args.page_size is not None
                else int(plan_cfg.get("page_size", COMPANIES_PAGE_SIZE))
            ),
            enrichment_names=args.enrichment_names,
            deep_dive_names=args.deep_dive_names,
            cached=args.cached.split(","),
        )
    except ValueError as exc:
        print(f"BLOCKED {exc}", file=sys.stderr)
        return 2
    out_path = (
        Path(args.out)
        if args.out
        else data_root() / "normalized" / "sectors_refresh_plan.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
