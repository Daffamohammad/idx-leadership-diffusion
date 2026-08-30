#!/usr/bin/env python3
"""One-command refresh-and-export wrapper.

Runs the full pipeline atomically:
  1. scripts/build_market_snapshot.py
  2. scripts/export_snapshot_json.py
  3. Update app/web/public/snapshots/index.json

SAFETY: This wrapper defaults to PREFLIGHT-ONLY mode (no paid request,
no export, no index.json update). To execute a paid live refresh, you
MUST pass both --allow-live AND --allow-credit-spend explicitly:

    python -m scripts.refresh_and_export \
        --as-of 2026-08-27 \
        --max-symbols 500 \
        --max-pages 5 \
        --max-estimated-credits 1000 \
        --allow-live \
        --allow-credit-spend

The 1,000 credit ceiling is a CLIENT-SIDE estimate only. The provider
balance and actual debit remain UNAVAILABLE from the client.

Behavior by mode:
  - Default (no --allow-live): preflight-only; no export; index.json
    is NOT updated. Safe to run at any time.
  - --allow-live --allow-credit-spend: runs a paid live refresh,
    exports the resulting snapshot, and updates index.json atomically.

This wrapper preserves the partial-universe disclosure and ensures
the browser payload is always in sync with the latest live snapshot.

For a complete live run, pass ``--full-live`` together with both explicit
live/spend acknowledgements. The complete run uses the latest discovered
universe and unbounded pagination; it never silently falls back to the
bounded 500-symbol smoke configuration.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from idx_leadership.utils import data_root, load_project_env, project_root


def main() -> int:
    parser = argparse.ArgumentParser(prog="refresh_and_export")
    parser.add_argument("--as-of", type=str, default=None,
                        help="Market date (YYYY-MM-DD). Default: latest.")
    parser.add_argument(
        "--full-live", action="store_true",
        help="Use the latest discovered universe and all provider pages. "
             "Requires --allow-live and --allow-credit-spend.",
    )
    parser.add_argument("--max-symbols", type=int, default=500,
                        help="Max symbols to fetch (default: 500)")
    parser.add_argument("--max-pages", type=int, default=5,
                        help="Max pages per endpoint (default: 5)")
    parser.add_argument("--max-estimated-credits", type=float, default=1000.0,
                        help="Max estimated credits (default: 1000)")
    parser.add_argument("--snapshot-id", type=str, default=None,
                        help="Specific snapshot ID to export (default: latest)")
    # These flags are NOT auto-injected. The operator must pass them
    # explicitly to acknowledge a paid Sectors request. Without these
    # flags, the wrapper runs --preflight-only (no paid request).
    parser.add_argument(
        "--allow-live", action="store_true",
        help="Explicitly acknowledge a paid Sectors live request. "
             "Without this flag, only the preflight runs.",
    )
    parser.add_argument(
        "--allow-credit-spend", action="store_true",
        help="Explicitly acknowledge the 1,000 credit ceiling is a "
             "client-side ESTIMATE only; provider balance is UNAVAILABLE.",
    )
    args = parser.parse_args()
    load_project_env()

    effective_max_symbols = None if args.full_live else args.max_symbols
    effective_max_pages = None if args.full_live else args.max_pages

    blockers = _operator_blockers(args)
    if blockers:
        print(json.dumps({
            "status": "BLOCKED",
            "mode": "FULL_LIVE" if args.full_live else "BOUNDED_LIVE",
            "blockers": blockers,
            "next_action": blockers[0]["next_action"],
        }, indent=2))
        return 2

    project_root_path = project_root()
    snapshot_root = data_root() / "snapshots"
    public_dir = project_root_path / "app" / "web" / "public" / "snapshots"

    # Step 1: Run the live refresh
    print("=" * 60)
    print("Step 1: Running live refresh")
    print("=" * 60)
    # The 1,000 credit ceiling is a CLIENT-SIDE estimate only.
    # The provider balance and actual debit remain UNAVAILABLE from
    # the client. This is a planning constraint, not a guarantee.
    if args.max_estimated_credits > 1000:
        print("ERROR: max_estimated_credits cannot exceed 1000")
        return 2
    # Require explicit --allow-live and --allow-credit-spend flags.
    # This wrapper does NOT auto-inject them; the operator must
    # pass them explicitly to acknowledge the paid request.
    cmd = [
        sys.executable, "-m", "scripts.build_market_snapshot",
        "--max-estimated-credits", str(args.max_estimated_credits),
    ]
    if effective_max_symbols is not None:
        cmd.extend(["--max-symbols", str(effective_max_symbols)])
    if effective_max_pages is not None:
        cmd.extend(["--max-pages", str(effective_max_pages)])
    preflight_only = not args.allow_live
    if preflight_only:
        cmd.append("--preflight-only")
        print("Running in PREFLIGHT-ONLY mode (no paid request, no export)")
    else:
        cmd.append("--allow-live")
    if args.allow_credit_spend:
        cmd.append("--allow-credit-spend")
    if args.as_of:
        cmd.extend(["--as-of", args.as_of])
    result = subprocess.run(cmd, cwd=str(project_root_path))
    if result.returncode != 0:
        print("ERROR: Live refresh failed")
        return result.returncode

    # If preflight-only, stop here. The preflight does NOT write a snapshot
    # bundle, so there is nothing to export. Do NOT overwrite index.json
    # with a stale entry.
    if preflight_only:
        print("=" * 60)
        print("Preflight complete. No snapshot was written;")
        print("index.json was NOT updated.")
        print("=" * 60)
        return 0

    # Step 2: Determine which snapshot to export
    snapshot_id = args.snapshot_id
    if not snapshot_id:
        snapshot_id = _latest_live_snapshot_id(snapshot_root)
        if not snapshot_id:
            print("ERROR: No live Sectors snapshot found")
            return 1
    manifest_entry = _read_manifest_entry(snapshot_root / snapshot_id)
    if not manifest_entry or manifest_entry.get("provider_mode") != "SECTORS_LIVE":
        print(f"ERROR: {snapshot_id} is not a SECTORS_LIVE snapshot")
        return 1
    print(f"Using snapshot: {snapshot_id}")

    # Step 3: Verify partial-universe disclosure is preserved
    snapshot_dir = snapshot_root / snapshot_id
    coverage_path = snapshot_dir / "coverage.json"
    if coverage_path.exists():
        with open(coverage_path) as f:
            coverage = json.load(f)
        if coverage.get("is_prefix_sample"):
            used = coverage.get("used_count")
            discovered = coverage.get("discovered_count")
            disclosure = coverage.get("discovered_universe_disclosure")
            print(f"Partial universe: {used} of {discovered} discovered")
            print(f"Disclosure: {disclosure}")

    # Step 4: Export to browser JSON
    print("=" * 60)
    print("Step 2: Exporting to browser JSON")
    print("=" * 60)
    cmd = [
        sys.executable, "-m", "scripts.export_snapshot_json",
        "--snapshot-id", snapshot_id,
    ]
    result = subprocess.run(cmd, cwd=str(project_root_path))
    if result.returncode != 0:
        print("ERROR: Export failed")
        return result.returncode

    # Step 5: Update index.json through the canonical index builder. It
    # validates payload/manifest parity and keeps mixed-provider snapshots out
    # of the live browser index.
    print("=" * 60)
    print("Step 3: Updating index.json")
    print("=" * 60)
    cmd = [
        sys.executable,
        "-m",
        "scripts.build_snapshot_index",
        "--provider-mode",
        "SECTORS_LIVE",
    ]
    result = subprocess.run(cmd, cwd=str(project_root_path))
    if result.returncode != 0:
        print("ERROR: index update failed")
        return result.returncode
    print(f"Updated {public_dir / 'index.json'} via canonical live index builder")

    print("=" * 60)
    print("Refresh-and-export complete")
    print("=" * 60)
    return 0


def _operator_blockers(args: argparse.Namespace) -> list[dict[str, str]]:
    """Return actionable blockers before invoking the snapshot builder.

    This is intentionally local and network-free. The builder still performs
    the authoritative validation after loading the project environment.
    """
    blockers: list[dict[str, str]] = []
    if args.full_live and not args.allow_live:
        blockers.append({
            "code": "LIVE_ACK_REQUIRED",
            "reason": "Full live mode requires the explicit --allow-live acknowledgement.",
            "next_action": "Re-run with --allow-live after reviewing the preflight estimate.",
        })
    if args.full_live and not args.allow_credit_spend:
        blockers.append({
            "code": "CREDIT_ACK_REQUIRED",
            "reason": "Full live mode requires the explicit --allow-credit-spend acknowledgement.",
            "next_action": "Re-run with --allow-credit-spend only after approving the client-side credit ceiling.",
        })
    if args.allow_live and not args.allow_credit_spend:
        blockers.append({
            "code": "CREDIT_ACK_REQUIRED",
            "reason": "A live Sectors request cannot run without the credit-spend acknowledgement.",
            "next_action": "Add --allow-credit-spend or run without --allow-live for preflight-only mode.",
        })
    if args.full_live and args.allow_live and args.allow_credit_spend and not os.environ.get("SECTORS_API_KEY", "").strip():
        blockers.append({
            "code": "SECTORS_API_KEY_UNAVAILABLE",
            "reason": "The Sectors API key is not available in the local environment.",
            "next_action": "Store SECTORS_API_KEY in the local .env or shell environment, then rerun the bounded preflight before approving spend.",
        })
    return blockers


def _read_manifest_entry(snapshot_dir: Path) -> dict | None:
    try:
        manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entries = manifest.get("entries") or []
    return entries[0] if entries and isinstance(entries[0], dict) else None


def _latest_live_snapshot_id(snapshot_root: Path) -> str | None:
    candidates: list[tuple[str, str]] = []
    try:
        snapshot_dirs = [path for path in snapshot_root.iterdir() if path.is_dir()]
    except OSError:
        return None
    for path in snapshot_dirs:
        entry = _read_manifest_entry(path)
        if entry and entry.get("provider_mode") == "SECTORS_LIVE":
            as_of = str(entry.get("as_of") or "")
            if as_of:
                candidates.append((as_of, path.name))
    return max(candidates)[1] if candidates else None


if __name__ == "__main__":
    raise SystemExit(main())
