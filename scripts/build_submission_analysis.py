"""Build the October 2 matched-cohort submission analysis offline.

This supplemental asset is explicitly a historical price replay using the
release's current documented membership. It never changes canonical snapshot
comparability or promotes replayed membership to historical evidence.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.group_readings import group_readings


TARGET_DATES = ("2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25", "2026-10-02")
YTD_START = "2025-12-31"
Q3_START = "2026-07-01"
SCHEMA = "historical-comparison-v2"
ANALYSIS_START = "2026-09-04"
GROUP_SIGNAL_FLOOR = 5


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_taxonomy_replays(
    *, snapshot: dict[str, Any], market: dict[str, Any],
    prices: pd.DataFrame, benchmark: pd.DataFrame,
    ownership_edges: list[dict[str, Any]],
    konglo_memberships: list[dict[str, Any]],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Build same-contributor daily paths from the dated release memberships."""
    benchmark_dates = sorted(benchmark["date"].astype(str).unique())
    analysis_dates = [day for day in benchmark_dates if ANALYSIS_START <= day <= TARGET_DATES[-1]]
    if not analysis_dates or analysis_dates[-1] != TARGET_DATES[-1]:
        raise ValueError("benchmark does not cover the full daily replay window")
    if [day for day in analysis_dates if day in TARGET_DATES] != list(TARGET_DATES):
        raise ValueError("benchmark misses a weekly comparison endpoint")
    benchmark_lookup = benchmark.set_index("date")["close"].astype(float)
    price_lookup = prices.pivot(index="ticker", columns="date", values="adjusted_close")
    record_by_ticker = {str(row["ticker"]).upper(): row for row in market.get("records", [])}
    view_payloads = snapshot.get("taxonomy_views")
    if not isinstance(view_payloads, dict):
        raise ValueError("selected snapshot has no taxonomy-view membership records")
    catalogue_path = Path(market.get("_business_catalogue_path", ""))
    if catalogue_path.is_file():
        view_payloads = {**view_payloads, "konglo": _read(catalogue_path)["view"]}
    ownership_by_member: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in ownership_edges:
        if not isinstance(edge, dict) or not edge.get("group_id") or not edge.get("ticker"):
            continue
        ticker = str(edge["ticker"]).upper()
        if not ticker.endswith(".JK"):
            ticker += ".JK"
        key = (str(edge["group_id"]), ticker)
        ownership_by_member.setdefault(key, []).append(edge)
    konglo_by_member: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in konglo_memberships:
        if not isinstance(row, dict) or not row.get("taxonomy_group_id") or not row.get("ticker"):
            continue
        key = (str(row["taxonomy_group_id"]), str(row["ticker"]).upper())
        konglo_by_member.setdefault(key, []).append(row)

    taxonomies: dict[str, dict[str, Any]] = {}
    view_aliases = [("sector", "SECTOR"), ("konglo", "KONGLO"), ("themes", "IDXIC")]
    curated_path = Path(__file__).resolve().parents[1] / "config" / "market_expansion" / "curated_themes.json"
    curated_definition_sha256 = None
    if curated_path.exists():
        definitions = json.loads(curated_path.read_text(encoding="utf-8"))
        curated_definition_sha256 = _sha(curated_path)
        source_view = view_payloads.get("themes")
        if not isinstance(source_view, dict):
            raise ValueError("curated themes require the dated IDXIC activity catalog")
        activity_rows = source_view.get("memberships", [])
        curated_memberships: list[dict[str, Any]] = []
        curated_groups: list[dict[str, Any]] = []
        for definition in definitions.get("themes", []):
            curated_groups.append({
                "taxonomy_group_id": definition["id"],
                "taxonomy_group_name": definition["name"],
                "constituent_count": 0,
            })
            source_ids = set(definition.get("source_activity_ids", []))
            for row in activity_rows:
                if not isinstance(row, dict) or row.get("taxonomy_group_id") not in source_ids:
                    continue
                curated_memberships.append({
                    **row,
                    "taxonomy_group_id": definition["id"],
                    "taxonomy_group_name": definition["name"],
                    "relationship": "Curated theme roll-up from the dated IDXIC activity classification",
                })
        view_aliases.append(("curated_themes", "CURATED_THEMES"))
        view_payloads["curated_themes"] = {
            "taxonomy_id": "curated_themes",
            "taxonomy_name": "Curated business themes",
            "taxonomy_kind": "CURATED_THEMES",
            "taxonomy_version": str(definitions.get("taxonomy_version", "curated-themes-v1")),
            "source_as_of": source_view.get("source_as_of"),
            "taxonomy_definition_provider_mode": "ANALYST_DEFINED_FROM_DATED_IDXIC_ACTIVITIES",
            "groups": curated_groups,
            "memberships": curated_memberships,
            "definitions": {row["id"]: row for row in definitions.get("themes", [])},
        }
    weekly_indexes = [analysis_dates.index(day) for day in TARGET_DATES]
    for view_id, output_id in view_aliases:
        view = view_payloads.get(view_id)
        if not isinstance(view, dict):
            raise ValueError(f"selected snapshot is missing taxonomy view {view_id}")
        memberships = [
            row for row in view.get("memberships", [])
            if isinstance(row, dict) and row.get("membership_type", "PRIMARY") != "EXCLUDED"
        ]
        group_defs: dict[str, dict[str, Any]] = {
            str(row["taxonomy_group_id"]): {
                "group_id": str(row["taxonomy_group_id"]),
                "name": str(row.get("taxonomy_group_name") or row["taxonomy_group_id"]),
            }
            for row in view.get("groups", [])
            if isinstance(row, dict) and row.get("taxonomy_group_id")
        }
        names_by_ticker = {
            str(row["ticker"]).upper(): str(row.get("company_name") or row["ticker"])
            for row in market.get("records", [])
        }
        definitions = view.get("definitions", {})
        groups: dict[str, dict[str, Any]] = {}
        for group_id in sorted(group_defs, key=lambda key: group_defs[key]["name"].casefold()):
            catalog_members = sorted({str(row["ticker"]).upper() for row in memberships if row.get("taxonomy_group_id") == group_id})
            verified = group_readings(catalog_members, price_lookup, benchmark_lookup, analysis_dates, list(TARGET_DATES),
                                      {ticker for ticker, row in record_by_ticker.items() if row.get("signal_eligible") is True})
            contributors = verified["cohort"]["contributors"]
            n = len(contributors)
            values_by_date, weekly = verified["daily"], verified["weekly"]
            persistence = verified["persistence"]["current_leadership_weeks"]
            catalog_members = sorted({
                str(row["ticker"]).upper() for row in memberships
                if row.get("taxonomy_group_id") == group_id and row.get("membership_type", "PRIMARY") != "EXCLUDED"
            })
            group_membership_rows = [
                row for row in memberships
                if row.get("taxonomy_group_id") == group_id and row.get("membership_type", "PRIMARY") != "EXCLUDED"
            ]
            member_evidence: dict[str, list[dict[str, Any]]] = {}
            for row in group_membership_rows:
                ticker = str(row.get("ticker", "")).upper()
                if not ticker:
                    continue
                joined_edges = ownership_by_member.get((group_id, ticker), [])
                catalog_rows = konglo_by_member.get((group_id, ticker), [row])
                evidence_rows = [
                    (catalog_row, edge)
                    for catalog_row in catalog_rows
                    for edge in (joined_edges or [None])
                ]
                for catalog_row, edge in evidence_rows:
                    member_evidence.setdefault(ticker, []).append({
                        "relationship": catalog_row.get("relationship") or (edge.get("relationship") if edge else row.get("relationship")),
                        "holder": edge.get("holder") if edge else None,
                        "ownership_percentage": edge.get("percentage") if edge else None,
                        "membership_type": row.get("membership_type", "PRIMARY"),
                        "source": (edge.get("source") if edge else None) or catalog_row.get("source") or row.get("source"),
                        "source_as_of": (edge.get("as_of") if edge else None) or catalog_row.get("source_as_of") or row.get("source_as_of"),
                        "control_source": edge.get("control_source") if edge else None,
                    })
            group_definition = definitions.get(group_id, {}) if isinstance(definitions, dict) else {}
            groups[group_id] = {
                **group_defs[group_id],
                "member_count": len(catalog_members),
                "membership": {
                    "version": str(view.get("taxonomy_version") or "unknown"),
                    "source_as_of": max((str(row["source_as_of"]) for row in group_membership_rows if row.get("source_as_of")), default=None),
                    "tickers": catalog_members,
                    "count": len(catalog_members),
                    "sha256": _hash_json(catalog_members),
                    "evidence_sha256": _hash_json(member_evidence),
                },
                "cohort": verified["cohort"],
                "cohorts": verified["cohorts"],
                "coverage_reasons": verified["coverage_reasons"],
                "coverage_by_horizon": verified["coverage_by_horizon"],
                "members": [{
                    "ticker": ticker,
                    "name": names_by_ticker.get(ticker, ticker),
                    "evidence": member_evidence.get(ticker, []),
                } for ticker in catalog_members],
                "definition": group_definition.get("definition"),
                "parent_category": group_definition.get("parent_category"),
                "inclusion_rules": group_definition.get("inclusion_rules", []),
                "exclusion_rules": group_definition.get("exclusion_rules", []),
                "source_activity_ids": group_definition.get("source_activity_ids", []),
                "daily": values_by_date,
                "weekly": weekly,
                "persistence": {"current_leadership_weeks": persistence, "observations": len(weekly)},
            }
        memberships_dates = [row.get("source_as_of") for row in memberships if row.get("source_as_of")]
        taxonomies[output_id] = {
            "taxonomy_id": str(view.get("taxonomy_id") or view_id),
            "taxonomy_name": str(view.get("taxonomy_name") or view_id),
            "taxonomy_version": str(view.get("taxonomy_version") or "unknown"),
            "taxonomy_kind": str(view.get("taxonomy_kind") or "THEMES"),
            "membership_as_of": max(memberships_dates) if memberships_dates else view.get("source_as_of"),
            "membership_source_basis": str(view.get("taxonomy_definition_provider_mode") or view.get("provider_mode") or "selected-release-membership"),
            "membership_payload_sha256": _hash_json(memberships),
            "definition_sha256": curated_definition_sha256 if view_id == "curated_themes" else None,
            "group_count": len(groups),
            "groups": groups,
        }
    return analysis_dates, taxonomies


def build(*, market_path: Path, rotation_path: Path, snapshot_path: Path,
          prices_path: Path, benchmark_path: Path, out: Path) -> dict[str, Any]:
    market = _read(market_path)
    business_catalogue_path = market_path.parent.parent / "evidence" / "business_group_catalogue.json"
    if business_catalogue_path.is_file():
        market["_business_catalogue_path"] = str(business_catalogue_path)
    rotation = _read(rotation_path)
    snapshot = _read(snapshot_path)
    if market.get("as_of") != "2026-10-02" or rotation.get("as_of") != "2026-10-02":
        raise ValueError("submission analysis requires the October 2 release")
    if snapshot.get("as_of") != "2026-10-02" or snapshot.get("snapshot_id") != market.get("snapshot_id"):
        raise ValueError("snapshot memberships do not belong to the selected October 2 market release")
    if rotation.get("schema_version") != "rotation-history-v1":
        raise ValueError("rotation source schema is not supported")
    dates_in_rotation = set(rotation.get("sessions", []))
    if not set(TARGET_DATES).issubset(dates_in_rotation):
        raise ValueError("the rotation source does not contain every comparison session")

    prices = pd.read_csv(prices_path, parse_dates=["date"])
    benchmark = pd.read_csv(benchmark_path, parse_dates=["date"])
    needed = {"ticker", "date", "adjusted_close"}
    if not needed.issubset(prices.columns) or not {"date", "close"}.issubset(benchmark.columns):
        raise ValueError("price panel is missing adjusted prices or the IHSG benchmark")
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    prices["date"] = prices["date"].dt.strftime("%Y-%m-%d")
    benchmark["date"] = benchmark["date"].dt.strftime("%Y-%m-%d")
    if prices.duplicated(["ticker", "date"]).any() or benchmark.duplicated(["date"]).any():
        raise ValueError("price panel has duplicate ticker sessions or benchmark sessions")
    if not prices["adjusted_close"].map(lambda x: pd.notna(x) and float(x) > 0).all():
        raise ValueError("adjusted close panel has missing or invalid prices")

    ownership_edges_path = snapshot_path.parent.parent / "evidence" / "market-ownership-edges.json"
    ownership_edges = _read(ownership_edges_path) if ownership_edges_path.is_file() else []
    if isinstance(ownership_edges, dict):
        ownership_edges = ownership_edges.get("edges", [])
    if not isinstance(ownership_edges, list):
        raise ValueError("ownership edge evidence must be a list")
    konglo_membership_path = snapshot_path.parent.parent / "evidence" / "submission-taxonomy" / "konglo.yaml"
    konglo_memberships: list[dict[str, Any]] = []
    if konglo_membership_path.is_file():
        try:
            import yaml
        except ImportError as exc:
            raise ValueError("Konglo membership evidence requires PyYAML") from exc
        catalog = yaml.safe_load(konglo_membership_path.read_text(encoding="utf-8"))
        konglo_memberships = catalog.get("memberships", []) if isinstance(catalog, dict) else []
        if not isinstance(konglo_memberships, list):
            raise ValueError("Konglo membership evidence must contain a membership list")
    analysis_dates, taxonomy_replays = _build_taxonomy_replays(
        snapshot=snapshot, market=market, prices=prices, benchmark=benchmark,
        ownership_edges=ownership_edges, konglo_memberships=konglo_memberships,
    )

    # All consumers use the same per-horizon readings and contributor lists.
    sector_groups = taxonomy_replays["SECTOR"]["groups"]
    weekly = [{"as_of": day, "groups": [
        {**next(point for point in group["weekly"] if point["as_of"] == day),
         "group_id": group_id, "name": group["name"],
         "cohort_count": group["cohort"]["count"], "cohort_hash": group["cohort"]["sha256"]}
        for group_id, group in sector_groups.items()
    ]} for day in TARGET_DATES]
    cohort = {key: group["cohorts"]["20d"] for key, group in sector_groups.items()}
    flat_tickers = sorted({ticker for names in cohort.values() for ticker in names})
    cohort_hash = _hash_json(flat_tickers)
    persistence = {key: group["persistence"] for key, group in sector_groups.items()}
    q3_dates = sorted(day for day in set(benchmark["date"]) if Q3_START <= day <= TARGET_DATES[-1])
    if not q3_dates:
        raise ValueError("no Q3 benchmark observations")
    basket_groups = []
    for group_id, group in sector_groups.items():
        panel = prices[prices["ticker"].isin(cohort[group_id])].pivot(index="date", columns="ticker", values="adjusted_close").reindex(q3_dates)
        complete = panel.columns[panel.notna().all(axis=0) & panel.gt(0).all(axis=0)]
        normalized = panel[complete].divide(panel[complete].iloc[0]).subtract(1).mean(axis=1).multiply(100) if len(complete) else pd.Series(index=q3_dates, dtype=float)
        basket_groups.append({"group_id": group_id, "name": group["name"], "contributor_count": len(complete),
                              "contributors": sorted(complete), "cohort_hash": _hash_json(sorted(complete)),
                              "values": [{"as_of": day, "return_pct": round(float(normalized.loc[day]), 6) if pd.notna(normalized.loc[day]) else None} for day in q3_dates]})
    ihsg = benchmark.set_index("date").reindex(q3_dates)["close"]
    benchmark_values = (ihsg / float(ihsg.iloc[0]) - 1) * 100
    basket = {"start": q3_dates[0], "end": q3_dates[-1],
              "basis": "Fixed complete contributors; equal-weight mean of individual adjusted-price returns rebased at the first Q3 session",
              "benchmark": "IHSG", "benchmark_basis": "Benchmark close return on identical observed dates",
              "series": [{"as_of": day, "return_pct": round(float(benchmark_values.loc[day]), 6)} for day in q3_dates], "groups": basket_groups}

    sources = {
        "market_release_sha256": _sha(market_path),
        "rotation_release_sha256": _sha(rotation_path),
        "snapshot_membership_payload_sha256": _sha(snapshot_path),
        "adjusted_price_panel_sha256": _sha(prices_path),
        "ihsg_panel_sha256": _sha(benchmark_path),
    }
    if ownership_edges_path.is_file():
        sources["ownership_edges_sha256"] = _sha(ownership_edges_path)
    if business_catalogue_path.is_file():
        sources["business_group_catalogue_sha256"] = _sha(business_catalogue_path)
    if konglo_membership_path.is_file():
        sources["konglo_membership_evidence_sha256"] = _sha(konglo_membership_path)
    benchmark_sessions = sorted(benchmark["date"].astype(str).unique())
    ytd_base_dates = [day for day in benchmark_sessions if day <= "2025-12-31"]
    ytd_base_date = ytd_base_dates[-1] if ytd_base_dates else None
    ytd_window_sessions = benchmark_sessions.index(TARGET_DATES[-1]) - benchmark_sessions.index(ytd_base_date) if ytd_base_date else None
    payload = {
        "schema_version": SCHEMA,
        "reading_contract_version": 2,
        "price_histories": {str(ticker): [{"date": str(row.date), "close": float(row.adjusted_close)} for row in frame.itertuples() if pd.notna(row.adjusted_close) and row.adjusted_close > 0] for ticker, frame in prices.sort_values(["ticker", "date"]).groupby("ticker")},
        "benchmark_history": [{"date": str(row.date), "close": float(row.close)} for row in benchmark.sort_values("date").itertuples()],
        "as_of": TARGET_DATES[-1],
        "comparison_dates": list(TARGET_DATES),
        "analysis_dates": analysis_dates,
        "title": "Historical price replay using current membership",
        "replay_basis": "Dated documented membership applied retrospectively; separate fixed contributors for each horizon across replay dates; adjusted-price research panel; equal-weight stock returns.",
        "membership_as_of": taxonomy_replays["SECTOR"]["membership_as_of"],
        "cohort": {"count": len(flat_tickers), "sha256": cohort_hash,
                   "group_cohorts": {key: {"count": len(value), "sha256": _hash_json(value)} for key, value in cohort.items()}},
        "calculation": {"price_basis": "adjusted_close", "benchmark": "IHSG", "primary_horizon_sessions": 20,
                        "medium_horizon_sessions": 60, "diffusion_version": "diffusion-v2",
                        "return_window_sessions": {"5d": 5, "20d": 20, "60d": 60, "ytd": ytd_window_sessions},
                        "ytd_base_close_as_of": ytd_base_date,
                        "diffusion_threshold_pp": 10.0, "diffusion_constituent_fraction": 0.10,
                        "diffusion_minimum_constituents": 2, "group_minimum_constituents": 5,
                        "minimum_coverage_pct": None, "materiality_breadth_threshold_pp": 10.0,
                        "materiality_excess_threshold_pp": 1.5},
        "weekly": weekly,
        "persistence": persistence,
        "taxonomies": taxonomy_replays,
        "sector_baskets": basket,
        "sources": sources,
        "catalog_definition_sha256": taxonomy_replays.get("CURATED_THEMES", {}).get("definition_sha256"),
        "limitations": [
            "Retrospective price replay uses the selected release's current documented sector membership; it is not historical membership evidence.",
            "Historical prices are from the validated public yfinance research panel, not an official IDX adjusted-price feed.",
            "Sector baskets are equal-weight computed stock baskets and are not IDX sector indices.",
            "Canonical strict snapshot comparability remains unchanged; this supplemental matched-cohort analysis is separately labeled.",
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", required=True, type=Path)
    parser.add_argument("--rotation", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--prices", required=True, type=Path)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(market_path=args.market, rotation_path=args.rotation, snapshot_path=args.snapshot,
                       prices_path=args.prices, benchmark_path=args.benchmark, out=args.out)
        print(json.dumps({"schema_version": SCHEMA, "cohort": result["cohort"]["count"],
                          "sectors": len(result["weekly"][-1]["groups"]),
                          "comparison_dates": result["comparison_dates"],
                          "basket_sessions": len(result["sector_baskets"]["series"])}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SUBMISSION_ANALYSIS_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
