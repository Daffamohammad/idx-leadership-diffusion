"""Build snapshot-scoped Konglo and Themes taxonomy views.

Each output is tied to one persisted snapshot and, when available, its latest
fail-closed compatible predecessor. The calculation uses the canonical
trading-session return engine and never calls a live provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from idx_leadership.data.comparability import check_snapshot_compatibility
from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.taxonomy import (
    MembershipType,
    Taxonomy,
    TaxonomyRegistry,
    aggregate_taxonomy,
    build_taxonomy_payload,
    load_registry_from_yaml,
)
from idx_leadership.utils import get_logger, project_root

_log = get_logger(__name__)


def _resolve_universe(path: Path) -> list[str]:
    if not path.exists():
        return []
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = payload.get("universe", [])
        return sorted(
            {
                str(item.get("ticker")).strip().upper()
                for item in entries
                if isinstance(item, Mapping) and item.get("ticker")
            }
        )
    frame = pd.read_csv(path)
    if "ticker" not in frame.columns:
        return []
    return sorted({str(value).strip().upper() for value in frame["ticker"].dropna()})


def _manifest_entry(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    entries = (snapshot.get("manifest") or {}).get("entries") or []
    return dict(entries[0]) if entries else {}


def _read_prices(snapshot: Mapping[str, Any], universe: list[str]) -> pd.DataFrame:
    prices = snapshot.get("prices")
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        return pd.DataFrame(columns=["ticker", "date", "close", "adjusted_close"])
    frame = prices.copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    if universe:
        frame = frame[frame["ticker"].isin(set(universe))]
    return frame


def _read_benchmark(snapshot: Mapping[str, Any]) -> pd.DataFrame:
    benchmark = snapshot.get("benchmark")
    if not isinstance(benchmark, pd.DataFrame):
        return pd.DataFrame(columns=["date", "close"])
    return benchmark.copy()


def _price_column(entry: Mapping[str, Any], prices: pd.DataFrame) -> str:
    basis = str(entry.get("price_basis") or "").lower()
    if basis == "adjusted_close" and "adjusted_close" in prices.columns:
        return "adjusted_close"
    return "close"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _snapshot_catalog(reader: SnapshotReader) -> list[tuple[str, dict[str, Any]]]:
    catalog: list[tuple[str, dict[str, Any]]] = []
    for path in reader.list_snapshots():
        has_prices = (path / "prices.parquet").exists() or (path / "prices.csv").exists()
        has_benchmark = (path / "benchmark.parquet").exists() or (
            path / "benchmark.csv"
        ).exists()
        if not (has_prices and has_benchmark and (path / "security_master.json").exists()):
            _log.debug("Ignoring incomplete snapshot-like directory: %s", path)
            continue
        manifest = _load_json(path / "manifest.json")
        entries = manifest.get("entries") or []
        if entries and isinstance(entries[0], Mapping):
            catalog.append((path.name, dict(entries[0])))
    return catalog


def _default_snapshot_id(reader: SnapshotReader) -> str:
    catalog = _snapshot_catalog(reader)
    if not catalog:
        raise FileNotFoundError("no persisted snapshots")
    return max(catalog, key=lambda item: (str(item[1].get("as_of") or ""), item[0]))[0]


def _compatible_previous(
    reader: SnapshotReader,
    current_id: str,
    current_entry: Mapping[str, Any],
    explicit_previous_id: str | None,
) -> tuple[str | None, dict[str, Any] | None, dict[str, Any]]:
    if explicit_previous_id:
        previous = reader.load(explicit_previous_id)
        previous_entry = _manifest_entry(previous)
        comparison = check_snapshot_compatibility(current_entry, previous_entry)
        if not comparison.comparable:
            raise ValueError(
                f"explicit previous snapshot {explicit_previous_id!r} is incompatible: "
                + "; ".join(comparison.reasons)
            )
        if str(previous_entry.get("as_of")) >= str(current_entry.get("as_of")):
            raise ValueError("explicit previous snapshot must be earlier than current")
        return explicit_previous_id, previous, comparison.to_dict()

    candidates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for snapshot_id, entry in _snapshot_catalog(reader):
        if snapshot_id == current_id:
            continue
        if str(entry.get("as_of") or "") >= str(current_entry.get("as_of") or ""):
            continue
        comparison = check_snapshot_compatibility(current_entry, entry)
        if not comparison.comparable:
            continue
        candidates.append((snapshot_id, entry, comparison.to_dict()))
    if not candidates:
        return None, None, {
            "comparable": False,
            "status": "NO_COMPARABLE_PRIOR",
            "reasons": ["no earlier snapshot passed the fail-closed compatibility contract"],
            "warnings": [],
        }
    previous_id, _, comparison = max(
        candidates, key=lambda item: (str(item[1].get("as_of") or ""), item[0])
    )
    return previous_id, reader.load(previous_id), comparison


def _foreign_flow_for_taxonomy(
    taxonomy: Taxonomy,
    flow_payload: Mapping[str, Any],
    *,
    as_of: str,
) -> dict[str, dict[str, Any]]:
    observations = [
        row
        for row in flow_payload.get("company_observations", [])
        if isinstance(row, Mapping)
        and row.get("as_of")
        and str(row["as_of"]) <= as_of
        and row.get("quantitative_use") is True
    ]
    if not observations:
        return {}
    latest_date = max(str(row["as_of"]) for row in observations)
    membership_lookup: dict[str, set[str]] = defaultdict(set)
    for membership in taxonomy.memberships:
        if membership.membership_type == MembershipType.EXCLUDED:
            continue
        membership_lookup[membership.ticker].add(membership.taxonomy_group_id)

    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, set[str]] = defaultdict(set)
    for row in observations:
        if str(row["as_of"]) != latest_date:
            continue
        ticker = str(row.get("ticker") or "").upper()
        net = row.get("net_value_idr")
        if not ticker or not isinstance(net, (int, float)):
            continue
        for group_id in membership_lookup.get(ticker, set()):
            totals[group_id] += int(net)
            counts[group_id].add(ticker)
    return {
        group_id: {
            "as_of": latest_date,
            "net_value_idr": net,
            "direction": "NET_BUY" if net > 0 else "NET_SELL" if net < 0 else "FLAT",
            "observed_company_count": len(counts[group_id]),
            "scope": "TOP_LIST_SAMPLE_CONTEXT",
        }
        for group_id, net in totals.items()
    }


def _breadth_lookup(aggregates: list[Any]) -> dict[str, float]:
    return {
        aggregate.taxonomy_group_id: float(aggregate.breadth_outperforming)
        for aggregate in aggregates
        if aggregate.breadth_outperforming is not None
    }


def _workspace_eligible(path: Path, snapshot_id: str, entry: Mapping[str, Any]) -> set[str]:
    workspace = _load_json(path)
    if workspace.get("snapshot_id") != snapshot_id or workspace.get("as_of") != entry.get("as_of"):
        raise ValueError("eligibility workspace identity mismatch")
    eligible = {r["ticker"] for r in workspace.get("records", []) if r.get("signal_eligible") is True}
    cohort = hashlib.sha256(json.dumps(sorted(eligible)).encode()).hexdigest()[:16]
    if not eligible or cohort != entry.get("eligible_ticker_set_hash"):
        raise ValueError("eligibility workspace cohort mismatch")
    return eligible


def build_taxonomy_views(
    snapshot_root: Path,
    registry: TaxonomyRegistry,
    *,
    snapshot_id: str | None = None,
    previous_snapshot_id: str | None = None,
    universe: list[str] | None = None,
    foreign_flow_path: Path | None = None,
    eligibility_workspace: Path | None = None,
) -> dict[str, dict[str, Any]]:
    reader = SnapshotReader(root=snapshot_root)
    current_id = snapshot_id or _default_snapshot_id(reader)
    current = reader.load(current_id)
    current_entry = _manifest_entry(current)
    current_as_of = str(current_entry.get("as_of") or "")
    if not current_as_of:
        raise ValueError(f"snapshot {current_id!r} has no as_of")

    previous_id, previous, comparison = _compatible_previous(
        reader, current_id, current_entry, previous_snapshot_id
    )
    eligible = _workspace_eligible(eligibility_workspace, current_id, current_entry) if eligibility_workspace else None
    calculation_universe = sorted(eligible) if eligible is not None else universe or []
    current_prices = _read_prices(current, calculation_universe)
    current_benchmark = _read_benchmark(current)
    if current_prices.empty or current_benchmark.empty:
        raise ValueError(f"snapshot {current_id!r} lacks prices or benchmark")

    flow_payload = _load_json(foreign_flow_path) if foreign_flow_path else {}
    payloads: dict[str, dict[str, Any]] = {}
    for taxonomy in registry.taxonomies:
        previous_breadth: dict[str, float] = {}
        previous_as_of: str | None = None
        if previous is not None:
            previous_entry = _manifest_entry(previous)
            previous_as_of = str(previous_entry.get("as_of") or "") or None
            previous_prices = _read_prices(previous, calculation_universe)
            previous_aggregates = aggregate_taxonomy(
                taxonomy,
                previous_prices,
                _read_benchmark(previous),
                as_of=previous_as_of,
                price_col=_price_column(previous_entry, previous_prices),
                min_eligible_constituents=5 if eligible is not None else 2,
            )
            previous_breadth = _breadth_lookup(previous_aggregates)

        flow_by_group = _foreign_flow_for_taxonomy(
            taxonomy, flow_payload, as_of=current_as_of
        )
        aggregates = aggregate_taxonomy(
            taxonomy,
            current_prices,
            current_benchmark,
            as_of=current_as_of,
            prev_breadth=previous_breadth,
            prev_as_of=previous_as_of,
            foreign_flow_by_group=flow_by_group,
            price_col=_price_column(current_entry, current_prices),
            min_eligible_constituents=5 if eligible is not None else 2,
        )
        view = build_taxonomy_payload(
            taxonomy,
            aggregates,
            as_of=current_as_of,
        )
        definition_as_of = taxonomy.source_as_of.isoformat() if taxonomy.source_as_of else None
        view.update(
            {
                "provider_mode": current_entry.get("provider_mode"),
                "snapshot_provider_mode": current_entry.get("provider_mode"),
                "taxonomy_definition_provider_mode": taxonomy.provider_mode,
                "source_snapshot_id": current_id,
                "source_snapshot_price_basis": current_entry.get("price_basis"),
                "previous_snapshot_id": previous_id,
                "comparability": comparison,
                "point_in_time_eligible": bool(
                    definition_as_of is None or definition_as_of <= current_as_of
                ),
                "calculation": {
                    "return_horizons": "TRADING_SESSIONS",
                    "as_of_filtered": True,
                    "front_end_recompute": False,
                    "eligibility_scope": "SNAPSHOT_POLICY_AND_AVAILABLE_RETURNS" if eligible is not None else "AVAILABLE_TAXONOMY_RETURNS",
                    "eligible_ticker_set_hash": current_entry.get("eligible_ticker_set_hash") if eligible is not None else None,
                    "minimum_eligible_constituents": 5 if eligible is not None else 2,
                    "foreign_flow_scope": "LATEST_TOP_LIST_SAMPLE_CONTEXT",
                },
                "calculation_coverage": {
                    "group_count": len(aggregates),
                    "plottable_group_count": sum(
                        aggregate.map_x is not None and aggregate.map_y is not None
                        for aggregate in aggregates
                    ),
                    "eligible_constituent_count": sum(
                        aggregate.eligible_constituent_count for aggregate in aggregates
                    ),
                    "constituent_count": sum(
                        aggregate.constituent_count for aggregate in aggregates
                    ),
                },
            }
        )
        payloads[taxonomy.taxonomy_id] = view
    return payloads


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_taxonomy_views")
    parser.add_argument("--snapshot-root", default="data/snapshots")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--previous-snapshot-id")
    parser.add_argument("--all-snapshots", action="store_true")
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--out-dir", default="data/derived/taxonomy_views")
    parser.add_argument("--universe", default="config/universe.yaml")
    parser.add_argument("--eligibility-workspace", help="Bind expanded taxonomy calculations to the snapshot policy cohort.")
    parser.add_argument(
        "--foreign-flow", default="data/derived/foreign_flow_sample.json"
    )
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    args = parser.parse_args(argv)
    # Root containment for --out/--output (export pattern): outputs must
    # stay within the project root — or the system temp dir used by
    # isolated/pytest harnesses — unless --allow-outside-root is set.
    _project_root = project_root()
    _temp_root = Path(tempfile.gettempdir()).resolve()
    for _label, _value in (("--out-dir", args.out_dir),):
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


    project = project_root()
    snapshot_root = project / args.snapshot_root
    registry = load_registry_from_yaml(
        project / args.config_dir / "konglo.yaml",
        project / args.config_dir / "themes.yaml",
    )
    universe = _resolve_universe(project / args.universe)
    reader = SnapshotReader(root=snapshot_root)
    if args.all_snapshots:
        snapshot_ids = [snapshot_id for snapshot_id, _ in _snapshot_catalog(reader)]
    else:
        snapshot_ids = [args.snapshot_id or _default_snapshot_id(reader)]

    written: list[str] = []
    for snapshot_id in snapshot_ids:
        try:
            payloads = build_taxonomy_views(
                snapshot_root,
                registry,
                snapshot_id=snapshot_id,
                previous_snapshot_id=(
                    args.previous_snapshot_id if len(snapshot_ids) == 1 else None
                ),
                universe=universe,
                foreign_flow_path=project / args.foreign_flow,
                eligibility_workspace=project / args.eligibility_workspace if args.eligibility_workspace else None,
            )
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
            _log.warning("Skipping taxonomy build for %s: %s", snapshot_id, exc)
            continue
        for taxonomy_id, payload in payloads.items():
            target = project / args.out_dir / snapshot_id / f"{taxonomy_id}.json"
            _write_json_atomic(target, payload)
            written.append(str(target.relative_to(project)))
    print(json.dumps({"written": written, "sectors_api_called": False}, sort_keys=True))
    return 0 if written else 2


if __name__ == "__main__":
    sys.exit(main())
