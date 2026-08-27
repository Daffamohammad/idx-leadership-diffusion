"""Refresh the Sectors core data: security master, taxonomy, full-universe
close, free-float, suspensions.

This is a Tier 1 refresh only — no foreign flow, no fundamentals, no
per-symbol drilldown.

Usage:

  python -m scripts.refresh_sectors_core --as-of 2026-08-20 --allow-live

With `--allow-live`, the Sectors HTTP client makes real API calls
(gated by `SECTORS_API_KEY`). Without it, the run is BLOCKED.

Each call is recorded in the request ledger; the credit audit
script consumes that ledger.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.utils import data_root, get_logger, load_yaml
from idx_leadership.utils.errors import ProviderError

_log = get_logger(__name__)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(prog="refresh_sectors_core")
    parser.add_argument("--as-of", default=None, help="As-of date YYYY-MM-DD; defaults to today.")
    parser.add_argument("--config", default="config/providers.yaml")
    parser.add_argument("--out", default=None, help="Override output root (default: data/normalized/sectors/<asof>)")
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Permit live Sectors HTTP calls. Required for any real data.",
    )
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    out_dir = Path(args.out) if args.out else (data_root() / "normalized" / "sectors" / as_of.isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building SectorsProvider (allow_live={args.allow_live})")
    provider = build_provider_from_config(args.config, preferred="sectors", allow_live=args.allow_live)

    out: dict[str, Any] = {"as_of": as_of.isoformat(), "endpoints": {}, "errors": []}

    # 1. Security master
    try:
        master = provider.get_security_master()
        rows = [m.model_dump(mode="json") for m in master]
        _write_json(out_dir / "security_master.json", rows)
        out["endpoints"]["security_master"] = {
            "rows": len(rows),
            "file": str((out_dir / "security_master.json").relative_to(out_dir.parent.parent)),
        }
    except ProviderError as e:
        out["errors"].append({"endpoint": "security_master", "error": str(e)})

    # 2. Taxonomy
    try:
        tax = provider.get_group_taxonomy()
        if not tax.empty:
            tax.to_csv(out_dir / "taxonomy.csv", index=False)
        out["endpoints"]["taxonomy"] = {
            "rows": int(len(tax)),
            "unique_sectors": int(tax["group_id"].nunique()) if "group_id" in tax.columns else 0,
        }
    except ProviderError as e:
        out["errors"].append({"endpoint": "taxonomy", "error": str(e)})

    # 3. Full-universe close
    try:
        cs = provider.get_full_universe_close(as_of)
        if not cs.empty:
            cs.to_csv(out_dir / "close.csv", index=False)
        out["endpoints"]["close"] = {"rows": int(len(cs))}
    except ProviderError as e:
        out["errors"].append({"endpoint": "close", "error": str(e)})

    # 4. IHSG via the same cross-section (when present)
    try:
        if "close" in out["endpoints"]:
            ihsg = cs[cs["ticker"] == "IHSG.JK"] if not cs.empty else pd.DataFrame()
            if not ihsg.empty:
                ihsg.to_csv(out_dir / "ihsg.csv", index=False)
                out["endpoints"]["ihsg"] = {"rows": int(len(ihsg))}
            else:
                out["endpoints"]["ihsg"] = {"rows": 0, "note": "IHSG.JK not in cross-section"}
    except Exception as e:  # noqa: BLE001
        out["errors"].append({"endpoint": "ihsg", "error": str(e)})

    # 5. Free-float
    try:
        ff = provider.get_free_float()
        if not ff.empty:
            ff.to_csv(out_dir / "free_float.csv", index=False)
        out["endpoints"]["free_float"] = {"rows": int(len(ff))}
    except ProviderError as e:
        out["errors"].append({"endpoint": "free_float", "error": str(e)})

    # 6. Suspensions
    try:
        from datetime import timedelta
        susp = provider.get_suspensions(start=as_of - timedelta(days=90), end=as_of)
        if not susp.empty:
            susp.to_csv(out_dir / "suspensions.csv", index=False)
        out["endpoints"]["suspensions"] = {"rows": int(len(susp))}
    except ProviderError as e:
        out["errors"].append({"endpoint": "suspensions", "error": str(e)})

    _write_json(out_dir / "refresh_summary.json", out)
    if provider.ledger:
        provider.ledger.flush()
    print(json.dumps(out, indent=2, default=str))
    return 0 if not out["errors"] else 2


if __name__ == "__main__":
    sys.exit(main())
