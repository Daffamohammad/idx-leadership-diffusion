"""Build the dated public snapshot chain offline from the persisted panel.

Uses ``scripts.refresh_public_panel`` output (``data/raw/public/panel_*``)
and an offline ``PanelCacheProvider`` (network path raises) to build one
snapshot per chain date under ``data/snapshots/snap_public_<date>``:

* same contract every time (PUBLIC_PROTOTYPE, adjusted_close, prototype
  versions) so the fail-closed comparability gate can verify membership
  parity via ``eligible_ticker_set_hash``;
* point-in-time: the provider serves only rows with date <= as_of;
* chronological builds so each snapshot sees the previous one as a
  compatible prior (real ``previous_snapshot_id``, real breadth deltas,
  real diffusion states, dated breadth history).

The script asserts hash parity across all new snapshots and exits 2 on
any mismatch (fail-closed; no forged hashes).  It also reports whether
the chain connects to the existing August public snapshots
(``snap_public_2026-08-20`` / ``snap_2026-08-28``).

CLI::

    python -m scripts.build_snapshot_chain
    python -m scripts.build_snapshot_chain --asofs 2026-09-04 2026-09-11
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.pipeline import build_snapshot
from idx_leadership.providers.public import YFinanceProvider
from idx_leadership.utils import get_logger, project_root

_log = get_logger(__name__)

DEFAULT_ASOFS = ["2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25", "2026-10-02"]
SNAPSHOTS_ROOT = project_root() / "data" / "snapshots"
LEGACY_HASH = "a08b5e598af9551c"  # snap_public_2026-08-20 / snap_2026-08-28


class PanelCacheProvider(YFinanceProvider):
    """YFinanceProvider that serves only from the persisted panel CSVs.

    Any network attempt raises immediately; the chain build is fully
    offline and deterministic.  Rows are filtered to the requested
    window and ``date <= as_of`` by construction.
    """

    def __init__(self, panel_dir: Path, *, as_of: date, universe_path: str | Path = "config/universe.yaml") -> None:
        super().__init__(universe_path=universe_path)
        self._as_of = as_of
        self._prices = pd.read_csv(panel_dir / "prices.csv", parse_dates=["date"])
        self._benchmark = pd.read_csv(panel_dir / "benchmark.csv", parse_dates=["date"])

    def set_as_of(self, as_of: date) -> None:
        self._as_of = as_of

    def _call_yfinance_with_retry(self, ticker: str, *, start: date, end: date):
        raise RuntimeError(
            "PanelCacheProvider is offline; refresh the panel first "
            "(scripts.refresh_public_panel)"
        )

    def _fetch_one(
        self, ticker: str, *, start: date, end: date, is_benchmark: bool = False
    ) -> pd.DataFrame:
        if is_benchmark:
            frame = self._benchmark
            mask = (frame["date"].dt.date >= start) & (frame["date"].dt.date <= end)
            subset = frame.loc[mask]
            return pd.DataFrame(
                {
                    "date": subset["date"].dt.date,
                    "close": subset["close"].astype(float),
                }
            )
        mask = (
            (self._prices["ticker"] == ticker)
            & (self._prices["date"].dt.date >= start)
            & (self._prices["date"].dt.date <= end)
        )
        subset = self._prices.loc[mask]
        return pd.DataFrame(
            {
                "ticker": ticker,
                "date": subset["date"].dt.date,
                "close": subset["close"].astype(float),
                "adjusted_close": subset["adjusted_close"].astype(float),
                "volume": subset["volume"],
            }
        )


def _latest_panel() -> Path:
    root = project_root() / "data" / "raw" / "public"
    dirs = sorted(
        (d for d in root.glob("panel_*") if (d / "prices.csv").is_file()),
        key=lambda d: d.name,
    )
    if not dirs:
        raise SystemExit(f"no panel_* directory under {root}; run scripts.refresh_public_panel first")
    return dirs[-1]


def _resolve_asof(requested: str, panel_dir: Path) -> tuple[str, date]:
    benchmark = pd.read_csv(panel_dir / "benchmark.csv", parse_dates=["date"])
    sessions = sorted(d.date() for d in benchmark["date"])
    target = date.fromisoformat(requested)
    if target in sessions:
        return requested, target
    earlier = [d for d in sessions if d < target]
    if not earlier:
        raise SystemExit(f"no panel session earlier than {requested}")
    chosen = earlier[-1]
    print(
        f"note: {requested} is not a panel session; using {chosen.isoformat()}",
        file=sys.stderr,
    )
    return chosen.isoformat(), chosen


def _summarize(snapshot_dir: Path) -> dict[str, Any]:
    manifest = json.loads((snapshot_dir / "manifest.json").read_text())
    entry = manifest["entries"][0]
    comparability = json.loads((snapshot_dir / "comparability.json").read_text())
    groups = pd.read_parquet(snapshot_dir / "groups.parquet")
    features = pd.read_parquet(snapshot_dir / "features.parquet")
    ytd_starts = sorted(
        {
            str(d)[:10]
            for d in features.get("return_ytd_start_date", pd.Series(dtype=str)).dropna().unique()
        }
    )
    diffusion = groups["diffusion_state_v2"].value_counts().to_dict() if "diffusion_state_v2" in groups else {}
    breadth_delta_nonnull = (
        int(groups["breadth_delta"].notna().sum()) if "breadth_delta" in groups else 0
    )
    return {
        "snapshot_id": entry["snapshot_id"],
        "as_of": entry["as_of"],
        "provider_mode": entry["provider_mode"],
        "price_basis": entry["price_basis"],
        "eligible_ticker_set_hash": entry["eligible_ticker_set_hash"],
        "eligible_ticker_count": entry["eligible_ticker_count"],
        "coverage_status": entry.get("coverage_status"),
        "coverage_pct": entry.get("coverage_pct"),
        "notes": entry.get("notes"),
        "ytd_baseline_dates": ytd_starts,
        "diffusion_states": {str(k): int(v) for k, v in diffusion.items()},
        "breadth_delta_nonnull": breadth_delta_nonnull,
        "comparability_status": comparability.get("status"),
        "selected_previous": comparability.get("selected_previous"),
        "selected_previous_as_of": comparability.get("selected_previous_as_of"),
    }


PROVENANCE_FILENAME = "panel_provenance.json"


def _panel_fingerprints(panel_dir: Path) -> dict[str, str]:
    """Content hashes of the panel files a snapshot is derived from."""
    return {
        name: hashlib.sha256((panel_dir / name).read_bytes()).hexdigest()
        for name in ("prices.csv", "benchmark.csv")
    }


def _write_provenance(out_dir: Path, *, as_of: str, panel_dir: Path, fingerprints: dict[str, str], input_contracts: dict[str, str] | None = None) -> None:
    payload = {
        "kind": "PUBLIC_PANEL_PROVENANCE",
        "as_of": as_of,
        "panel_dir": str(panel_dir),
        "panel_files": fingerprints,
        "input_contracts": input_contracts,
        "bound_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / PROVENANCE_FILENAME).write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _verify_existing(
    out_dir: Path,
    *,
    snapshot_id: str,
    panel_dir: Path,
    fingerprints: dict[str, str],
    force_rebuild: bool,
    input_contracts: dict[str, str] | None = None,
    require_input_contracts: bool = False,
) -> bool:
    """Decide whether an existing snapshot may be reused as-is.

    A snapshot is only reusable when it was built from exactly these panel
    files. Otherwise the bundle on disk silently describes different inputs
    while the chain report would still credit the current panel, so the run
    must stop instead of "skipping" a stale bundle.
    """
    if force_rebuild:
        return False
    path = out_dir / PROVENANCE_FILENAME
    if not path.is_file():
        print(
            f"ERROR: {snapshot_id} exists without panel provenance; it cannot be "
            f"verified against panel {panel_dir}. Re-run with --force-rebuild to "
            f"rebuild it from the current panel.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        recorded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"ERROR: {snapshot_id} panel provenance is unreadable ({exc}); "
            f"re-run with --force-rebuild",
            file=sys.stderr,
        )
        raise SystemExit(2)
    recorded_files = recorded.get("panel_files") or {}
    recorded_inputs = recorded.get("input_contracts")
    if input_contracts is not None and (require_input_contracts or recorded_inputs is not None):
        if recorded_inputs != input_contracts:
            print(f"ERROR: {snapshot_id} input contract mismatch; rebuild the chain explicitly with --force-rebuild", file=sys.stderr)
            raise SystemExit(2)
    mismatched = sorted(
        name
        for name, digest in fingerprints.items()
        if recorded_files.get(name) != digest
    )
    if mismatched:
        print(
            f"ERROR: {snapshot_id} was built from a different price panel "
            f"(differing files: {mismatched}). Refusing to reuse it with panel "
            f"{panel_dir}. Re-run with --force-rebuild to rebuild the whole chain.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_snapshot_chain")
    parser.add_argument("--panel-dir", default=None)
    parser.add_argument("--asofs", nargs="*", default=DEFAULT_ASOFS)
    parser.add_argument("--snapshots-root", default=str(SNAPSHOTS_ROOT))
    parser.add_argument("--universe", default="config/universe.yaml")
    parser.add_argument("--snapshot-prefix", default="snap_public")
    parser.add_argument("--report", default=None)
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help=(
            "Rebuild snapshots that already exist. Use this when the price panel "
            "changed; reuse is refused automatically on any provenance mismatch."
        ),
    )
    args = parser.parse_args()
    from idx_leadership.data.snapshots import validate_snapshot_id

    validate_snapshot_id(f"{args.snapshot_prefix}_2000-01-01")

    panel_dir = Path(args.panel_dir) if args.panel_dir else _latest_panel()
    snapshots_root = Path(args.snapshots_root)
    snapshots_root.mkdir(parents=True, exist_ok=True)
    fingerprints = _panel_fingerprints(panel_dir)
    input_contracts = {
        "universe_sha256": hashlib.sha256(Path(args.universe).read_bytes()).hexdigest(),
        "methodology_sha256": hashlib.sha256((project_root() / "config/methodology.yaml").read_bytes()).hexdigest(),
    }
    # Historical default bundles predate config hashes. Keep that immutable
    # lane reusable; every new or injected-universe bundle binds its inputs.
    require_input_contracts = Path(args.universe).resolve() != (project_root() / "config/universe.yaml").resolve() or args.snapshot_prefix != "snap_public"

    records: list[dict[str, Any]] = []
    hashes: set[str] = set()
    for requested in args.asofs:
        as_of_str, as_of = _resolve_asof(requested, panel_dir)
        snapshot_id = f"{args.snapshot_prefix}_{as_of_str}"
        out_dir = snapshots_root / snapshot_id
        if (out_dir / "manifest.json").is_file() and _verify_existing(
            out_dir,
            snapshot_id=snapshot_id,
            panel_dir=panel_dir,
            fingerprints=fingerprints,
            force_rebuild=args.force_rebuild,
            input_contracts=input_contracts,
            require_input_contracts=require_input_contracts,
        ):
            print(f"reuse verified {snapshot_id}", file=sys.stderr)
        else:
            if args.force_rebuild and out_dir.exists():
                # Remove the previous bundle first: a leftover manifest.json
                # would make the rebuild treat its own directory as an earlier
                # snapshot, and stale files could survive into the new bundle.
                shutil.rmtree(out_dir)
            provider = PanelCacheProvider(panel_dir, as_of=as_of, universe_path=args.universe)
            provider.set_as_of(as_of)
            print(f"building {snapshot_id} ...", file=sys.stderr)
            build_snapshot(
                provider,
                as_of=as_of,
                snapshot_id=snapshot_id,
                out_dir=snapshots_root,
                provider_mode="PUBLIC_PROTOTYPE",
                price_basis="adjusted_close",
                universe_path=args.universe,
            )
            _write_provenance(
                out_dir, as_of=as_of_str, panel_dir=panel_dir, fingerprints=fingerprints, input_contracts=input_contracts
            )
        summary = _summarize(out_dir)
        summary["panel_files"] = fingerprints
        records.append(summary)
        hashes.add(summary["eligible_ticker_set_hash"])

    if len(hashes) > 1:
        print(f"ERROR: eligible_ticker_set_hash mismatch across chain: {sorted(hashes)}", file=sys.stderr)
        return 2

    chain_hash = next(iter(hashes), None)
    report = {
        "kind": "PUBLIC_SNAPSHOT_CHAIN",
        "panel_dir": str(panel_dir.relative_to(project_root())) if str(panel_dir).startswith(str(project_root())) else str(panel_dir),
        "panel_files": fingerprints,
        "input_contracts": input_contracts,
        "chain_hash": chain_hash,
        "connects_to_august_priors": chain_hash == LEGACY_HASH,
        "legacy_august_hash": LEGACY_HASH,
        "snapshots": records,
    }
    out_path = (
        Path(args.report) if args.report
        else project_root() / "data" / "normalized" / "public_chain_report.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for record in records:
        print(
            f"{record['snapshot_id']}: hash={record['eligible_ticker_set_hash']} "
            f"elig={record['eligible_ticker_count']} ytd={record['ytd_baseline_dates']} "
            f"prev={record['selected_previous']} ({record['selected_previous_as_of']})",
            file=sys.stderr,
        )
    print(f"chain hash={chain_hash} connects_to_august={chain_hash == LEGACY_HASH}", file=sys.stderr)
    print(f"report -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
