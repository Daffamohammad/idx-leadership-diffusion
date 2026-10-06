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

from idx_leadership.signals.diffusion_v2 import classify_diffusion_v2
from idx_leadership.signals.leadership import classify_leadership
from idx_leadership.taxonomy.aggregation import aggregate_taxonomy
from idx_leadership.taxonomy.models import (
    MembershipType,
    Taxonomy,
    TaxonomyKind,
    TaxonomyMembership,
    TaxonomySourceKind,
)


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
    benchmark_sessions = list(benchmark_dates)
    position = {day: index for index, day in enumerate(benchmark_sessions)}
    ytd_bases = [day for day in benchmark_sessions if day <= "2025-12-31"]
    if not ytd_bases:
        raise ValueError("benchmark is missing the prior-year YTD base")
    ytd_base = ytd_bases[-1]
    endpoint_dates = {ytd_base}
    for day in analysis_dates:
        index = position[day]
        for horizon in (5, 20, 60):
            if index < horizon:
                raise ValueError(f"benchmark lacks {horizon} sessions before {day}")
            endpoint_dates.add(benchmark_sessions[index - horizon])
        endpoint_dates.add(day)
    if not endpoint_dates.issubset(set(benchmark_lookup.index)):
        raise ValueError("benchmark is missing a return-window endpoint")

    price_lookup = prices.pivot(index="ticker", columns="date", values="adjusted_close")
    required_dates = sorted(endpoint_dates)
    price_complete = price_lookup.reindex(columns=required_dates).notna().all(axis=1)
    common_price_tickers = set(price_complete[price_complete].index.astype(str))
    record_by_ticker = {str(row["ticker"]).upper(): row for row in market.get("records", [])}
    view_payloads = snapshot.get("taxonomy_views")
    if not isinstance(view_payloads, dict):
        raise ValueError("selected snapshot has no taxonomy-view membership records")
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
        group_members: dict[str, set[str]] = {}
        for row in memberships:
            ticker = str(row.get("ticker", "")).upper()
            group_id = str(row.get("taxonomy_group_id", ""))
            if not ticker or not group_id:
                continue
            # The selected release's eligibility is frozen for this replay.
            if ticker not in common_price_tickers or record_by_ticker.get(ticker, {}).get("signal_eligible") is not True:
                continue
            group_members.setdefault(group_id, set()).add(ticker)
            group_defs[group_id] = {
                "group_id": group_id,
                "name": str(row.get("taxonomy_group_name") or group_id),
            }
        names_by_ticker = {
            str(row["ticker"]).upper(): str(row.get("company_name") or row["ticker"])
            for row in market.get("records", [])
        }
        definitions = view.get("definitions", {})
        groups: dict[str, dict[str, Any]] = {}
        for group_id in sorted(group_defs, key=lambda key: group_defs[key]["name"].casefold()):
            contributors = sorted(group_members.get(group_id, set()))
            n = len(contributors)
            member_prices = price_lookup.loc[contributors, required_dates] if contributors else pd.DataFrame()
            values_by_date: list[dict[str, Any]] = []
            prior_breadth_count: int | None = None
            for day in analysis_dates:
                end_index = position[day]
                endpoint_by_horizon = {
                    "5d": benchmark_sessions[end_index - 5],
                    "20d": benchmark_sessions[end_index - 20],
                    "60d": benchmark_sessions[end_index - 60],
                    "ytd": ytd_base,
                }
                endpoint_price = member_prices[day].astype(float) if n else pd.Series(dtype=float)
                ticker_metrics: dict[str, pd.Series] = {}
                benchmark_returns: dict[str, float] = {}
                for horizon, start_day in endpoint_by_horizon.items():
                    start_price = member_prices[start_day].astype(float) if n else pd.Series(dtype=float)
                    ticker_returns = (endpoint_price / start_price - 1.0) * 100.0 if n else start_price
                    benchmark_returns[horizon] = (float(benchmark_lookup.loc[day]) / float(benchmark_lookup.loc[start_day]) - 1.0) * 100.0
                    ticker_metrics[horizon] = ticker_returns - benchmark_returns[horizon]
                    ticker_metrics[f"raw_{horizon}"] = ticker_returns
                excess5 = float(ticker_metrics["5d"].mean()) if n else None
                excess20 = float(ticker_metrics["20d"].mean()) if n else None
                excess60 = float(ticker_metrics["60d"].mean()) if n else None
                excess_ytd = float(ticker_metrics["ytd"].mean()) if n else None
                breadth_count = int((ticker_metrics["20d"] > 0).sum()) if n else 0
                breadth_pct = 100.0 * breadth_count / n if n else None
                breadth_change_count = breadth_count - prior_breadth_count if prior_breadth_count is not None else None
                breadth_change_pp = (100.0 * breadth_change_count / n) if n and breadth_change_count is not None else None
                leadership = classify_leadership(
                    excess_return_20d=excess20, excess_return_5d=excess5,
                    excess_return_60d=excess60, eligible=n >= GROUP_SIGNAL_FLOOR,
                ).value
                diffusion = classify_diffusion_v2(
                    breadth_current=breadth_pct,
                    breadth_previous=(100.0 * prior_breadth_count / n if n and prior_breadth_count is not None else None),
                    group_size=n,
                    eligible=n >= GROUP_SIGNAL_FLOOR and prior_breadth_count is not None,
                    breadth_change_count=breadth_change_count,
                ).value
                raw20 = ticker_metrics.get("raw_20d", pd.Series(dtype=float)).abs().sort_values(ascending=False)
                abs_total = float(raw20.sum()) if n else 0.0
                concentration = 100.0 * float(raw20.head(3).sum()) / abs_total if abs_total > 0 else None
                values_by_date.append({
                    "as_of": day,
                    "excess_return_5d": excess5,
                    "excess_return_20d": excess20,
                    "excess_return_60d": excess60,
                    "excess_return_ytd": excess_ytd,
                    "relative_momentum": excess20 - excess60 if excess20 is not None and excess60 is not None else None,
                    "breadth_count": breadth_count if n else None,
                    "breadth_denominator": n,
                    "breadth_pct": breadth_pct,
                    "breadth_change_count": breadth_change_count,
                    "breadth_change_pp": breadth_change_pp,
                    "leadership": leadership,
                    "diffusion": "UNCONFIRMED" if diffusion == "UNCONFIRMED" else diffusion.removesuffix("_FIRM").removesuffix("_FRAGILE"),
                    "diffusion_v2": diffusion,
                    "concentration_top3_pct": concentration,
                    "concentration_change_pp": None,
                    "rotation_phase": (
                        "UNAVAILABLE" if excess_ytd is None or excess20 is None or excess60 is None
                        else "LEADING" if excess_ytd >= 0 and excess20 - excess60 >= 0
                        else "IMPROVING" if excess_ytd < 0 and excess20 - excess60 >= 0
                        else "WEAKENING" if excess_ytd >= 0 and excess20 - excess60 < 0
                        else "LAGGING"
                    ),
                    "coverage_pct": 100.0 if n else 0.0,
                })
                prior_breadth_count = breadth_count if n else None
            weekly = [dict(values_by_date[index]) for index in weekly_indexes]
            for index in range(len(weekly)):
                point = weekly[index]
                previous = weekly[index - 1] if index else None
                weekly_diffusion = classify_diffusion_v2(
                    breadth_current=point["breadth_pct"],
                    breadth_previous=previous["breadth_pct"] if previous else None,
                    group_size=n,
                    eligible=previous is not None and n >= GROUP_SIGNAL_FLOOR,
                    breadth_change_count=(
                        point["breadth_count"] - previous["breadth_count"]
                        if previous is not None
                        and point["breadth_count"] is not None
                        and previous["breadth_count"] is not None
                        else None
                    ),
                ).value
                point["diffusion_v2"] = weekly_diffusion
                point["diffusion"] = (
                    "UNCONFIRMED" if weekly_diffusion == "UNCONFIRMED"
                    else weekly_diffusion.removesuffix("_FIRM").removesuffix("_FRAGILE")
                )
                if index == 0:
                    point["breadth_change_count"] = None
                    point["breadth_change_pp"] = None
                    point["leadership_transition"] = None
                    point["diffusion_transition"] = None
                    point["material_shift"] = None
                    continue
                point["breadth_change_count"] = (
                    point["breadth_count"] - previous["breadth_count"]
                    if point["breadth_count"] is not None and previous["breadth_count"] is not None else None
                )
                point["breadth_change_pp"] = (
                    100.0 * point["breadth_change_count"] / n
                    if n and point["breadth_change_count"] is not None else None
                )
                point["concentration_change_pp"] = (
                    point["concentration_top3_pct"] - previous["concentration_top3_pct"]
                    if point["concentration_top3_pct"] is not None and previous["concentration_top3_pct"] is not None else None
                )
                point["leadership_transition"] = (
                    f"{previous['leadership']} -> {point['leadership']}"
                    if point["leadership"] != previous["leadership"] else None
                )
                point["diffusion_transition"] = (
                    f"{previous['diffusion_v2']} -> {point['diffusion_v2']}"
                    if point["diffusion_v2"] != previous["diffusion_v2"] else None
                )
                excess_change = (
                    point["excess_return_20d"] - previous["excess_return_20d"]
                    if point["excess_return_20d"] is not None and previous["excess_return_20d"] is not None else None
                )
                reasons = []
                if point["breadth_change_pp"] is not None and abs(point["breadth_change_pp"]) >= 10.0:
                    reasons.append(f"breadth {point['breadth_change_pp']:+.1f}pp")
                if excess_change is not None and abs(excess_change) >= 1.5:
                    reasons.append(f"20D excess {excess_change:+.2f}pp")
                point["material_shift"] = "; ".join(reasons) if reasons else None
            persistence = 0
            if weekly:
                current_state = weekly[-1]["leadership"]
                for point in reversed(weekly):
                    if point["leadership"] != current_state:
                        break
                    persistence += 1
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
                "cohort": {"contributors": contributors, "count": n, "sha256": _hash_json(contributors)},
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

    taxonomy_payloads = rotation["taxonomies"].get("SECTOR", {})
    records = {row["ticker"]: row for row in market.get("records", [])}
    group_specs: list[dict[str, Any]] = []
    memberships: list[TaxonomyMembership] = []
    member_sets: dict[str, list[str]] = {}
    for group_id, group in sorted(taxonomy_payloads.items()):
        segments = group.get("segments", [])
        current = next((segment for segment in segments if segment.get("sessions", [])[-1:] == ["2026-10-02"]), None)
        if current is None:
            raise ValueError(f"sector {group_id} has no current rotation segment")
        contributor_lists = current.get("contributors", {})
        dimensions = (
            "group_excess_return_ytd",
            "group_excess_return_20d",
            "group_excess_return_60d",
        )
        contributor_sets = [set(contributor_lists.get(key, [])) for key in dimensions]
        if any(not value for value in contributor_sets):
            raise ValueError(f"sector {group_id} lacks a complete current contributor set")
        fixed = set.intersection(*contributor_sets)
        eligible_members = set(current.get("eligible_members", []))
        fixed &= eligible_members
        fixed = {
            ticker for ticker in fixed
            if ticker in records
            and records[ticker].get("signal_eligible") is True
            and (records[ticker].get("taxonomy") or {}).get("sector") == group.get("name")
        }
        if len(fixed) < 5:
            raise ValueError(f"sector {group_id} has fewer than five matched contributors")
        member_sets[group_id] = sorted(fixed)
        group_specs.append({"id": group_id, "name": group["name"], "members": sorted(fixed)})
        for ticker in sorted(fixed):
            memberships.append(TaxonomyMembership(
                ticker=ticker,
                taxonomy_group_id=group_id,
                taxonomy_group_name=group["name"],
                membership_type=MembershipType.PRIMARY,
                confidence=1.0,
                source="Current documented IDXIC sector classification in selected release",
                source_as_of=date.fromisoformat(records[ticker]["classification_as_of"]),
                relationship="Current membership applied retrospectively to historical prices",
            ))

    all_tickers = [ticker for rows in member_sets.values() for ticker in rows]
    if len(all_tickers) != len(set(all_tickers)):
        raise ValueError("sector replay cohorts overlap; a fixed market cohort must be disjoint")
    if not all_tickers:
        raise ValueError("no eligible replay cohort")
    dates_by_ticker = {
        ticker: set(group["date"])
        for ticker, group in prices[prices["ticker"].isin(all_tickers)].groupby("ticker")
    }
    cohort: dict[str, list[str]] = {}
    for group in group_specs:
        group_id = group["id"]
        names = [
            ticker for ticker in member_sets[group_id]
            if all(target in dates_by_ticker.get(ticker, set()) for target in TARGET_DATES)
            and int((prices[(prices["ticker"] == ticker) & (prices["date"] <= "2026-09-04")]).shape[0]) >= 60
        ]
        if len(names) < 5:
            raise ValueError(f"sector {group_id} has fewer than five complete September-to-October histories")
        cohort[group_id] = names

    flat_tickers = [ticker for names in cohort.values() for ticker in names]
    if len(flat_tickers) != len(set(flat_tickers)):
        raise ValueError("matched sector cohorts overlap")
    cohort_hash = _hash_json(sorted(flat_tickers))
    cohort_by_group = {group["id"]: cohort[group["id"]] for group in group_specs}
    taxonomy = Taxonomy(
        taxonomy_id="sector",
        taxonomy_name="IDX sectors",
        taxonomy_version="captured-idxic-v1",
        taxonomy_kind=TaxonomyKind.SECTOR,
        source_kind=TaxonomySourceKind.PRIMARY_INDEX,
        source_as_of=max(m.source_as_of for m in memberships if m.source_as_of),
        membership_policy="PRIMARY_ONLY",
        provider_mode="PUBLIC_PROTOTYPE",
        memberships=tuple(m for m in memberships if m.ticker in set(flat_tickers)),
    )
    analysis_prices = prices[prices["ticker"].isin(flat_tickers)].copy()
    analysis_benchmark = benchmark[benchmark["date"] <= TARGET_DATES[-1]].copy()
    if not set(TARGET_DATES).issubset(set(analysis_benchmark["date"])):
        raise ValueError("IHSG benchmark misses a comparison date")

    weekly: list[dict[str, Any]] = []
    breadth_by_group: dict[str, float] = {}
    aggregate_by_date: dict[str, dict[str, Any]] = {}
    for as_of in TARGET_DATES:
        aggregates = aggregate_taxonomy(
            taxonomy,
            analysis_prices,
            analysis_benchmark,
            as_of=as_of,
            prev_breadth=breadth_by_group or None,
            prev_as_of=weekly[-1]["as_of"] if weekly else None,
            price_col="adjusted_close",
            min_eligible_constituents=5,
            min_coverage_pct=60.0,
        )
        by_id = {row.taxonomy_group_id: row for row in aggregates}
        if set(by_id) != set(cohort):
            raise ValueError(f"sector calculations are incomplete at {as_of}")
        groups_at_date: list[dict[str, Any]] = []
        for group in group_specs:
            row = by_id[group["id"]]
            expected = len(cohort[group["id"]])
            if row.eligible_constituent_count != expected or row.coverage_pct != 100.0:
                raise ValueError(f"sector {group['id']} calculation differs from its fixed cohort at {as_of}")
            groups_at_date.append({
                "group_id": group["id"], "name": group["name"],
                "cohort_count": expected, "cohort_hash": _hash_json(cohort[group["id"]]),
                "excess_return_20d": row.excess_return_20d,
                "excess_return_60d": row.excess_return_60d,
                "excess_return_ytd": row.excess_return_ytd,
                "relative_momentum": (row.excess_return_20d - row.excess_return_60d)
                    if row.excess_return_20d is not None and row.excess_return_60d is not None else None,
                "breadth_pct": row.breadth_outperforming,
                "breadth_change_pp": row.breadth_delta,
                "leadership": row.leadership_state,
                "diffusion": row.diffusion_state,
                "concentration_top3_pct": row.concentration_top3,
                "coverage_pct": row.coverage_pct,
            })
            if row.breadth_outperforming is None:
                raise ValueError(f"sector {group['id']} has no calculated breadth at {as_of}")
            breadth_by_group[group["id"]] = float(row.breadth_outperforming)
        weekly.append({"as_of": as_of, "groups": groups_at_date})
        aggregate_by_date[as_of] = by_id

    # Reconstruct the existing diffusion-v2 transition rule from the actual
    # matched breadth levels. Concentration is the same absolute-return top-3
    # measure already used by aggregate_taxonomy.
    for i in range(1, len(weekly)):
        prior = {row["group_id"]: row for row in weekly[i - 1]["groups"]}
        for row in weekly[i]["groups"]:
            previous = prior[row["group_id"]]
            row["concentration_change_pp"] = (
                row["concentration_top3_pct"] - previous["concentration_top3_pct"]
                if row["concentration_top3_pct"] is not None and previous["concentration_top3_pct"] is not None
                else None
            )
            row["leadership_transition"] = (
                f"{previous['leadership']} -> {row['leadership']}"
                if previous["leadership"] != row["leadership"] else None
            )
            row["diffusion_transition"] = (
                f"{previous['diffusion']} -> {row['diffusion']}"
                if previous["diffusion"] != row["diffusion"] else None
            )
            breadth_change = row["breadth_change_pp"]
            excess_change = row["excess_return_20d"] - previous["excess_return_20d"]
            reasons = []
            if breadth_change is not None and abs(breadth_change) >= 10.0:
                reasons.append(f"breadth {breadth_change:+.1f}pp")
            if abs(excess_change) >= 1.5:
                reasons.append(f"20D excess {excess_change:+.2f}pp")
            row["material_shift"] = "; ".join(reasons) if reasons else None

    last_breadth: dict[str, float] = {}
    persistence: dict[str, dict[str, int]] = {}
    for group in group_specs:
        states = [next(row for row in point["groups"] if row["group_id"] == group["id"])["leadership"] for point in weekly]
        current_state = states[-1]
        run = 1
        for state in reversed(states[:-1]):
            if state != current_state:
                break
            run += 1
        persistence[group["id"]] = {"current_leadership_weeks": run, "observations": len(states)}

    ownership_edges_path = snapshot_path.parent.parent / "evidence" / "market-ownership-edges.json"
    ownership_edges = _read(ownership_edges_path) if ownership_edges_path.is_file() else []
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

    # Sector stock baskets use the same release cohort. Each group's contributor
    # set is frozen for the full comparison window; IHSG is the provider panel's
    # benchmark series. Both series are rebased at the first Q3 session.
    q3_dates = sorted(d for d in set(benchmark["date"]) if Q3_START <= d <= TARGET_DATES[-1])
    if not q3_dates or q3_dates[0] != Q3_START or q3_dates[-1] != TARGET_DATES[-1]:
        raise ValueError("Q3 basket history does not contain exact start and end sessions")
    basket_groups = []
    for group in group_specs:
        tickers = cohort[group["id"]]
        wide = analysis_prices[analysis_prices["ticker"].isin(tickers) & analysis_prices["date"].isin(q3_dates)]
        pivot = wide.pivot(index="date", columns="ticker", values="adjusted_close").reindex(q3_dates)
        complete = pivot.columns[pivot.notna().all(axis=0)]
        if len(complete) < 5:
            raise ValueError(f"sector {group['id']} has fewer than five complete Q3 basket members")
        normalized = pivot[complete].divide(pivot[complete].iloc[0]).subtract(1.0).mean(axis=1).multiply(100)
        basket_groups.append({
            "group_id": group["id"], "name": group["name"],
            "contributor_count": len(complete), "cohort_hash": _hash_json(sorted(complete)),
            "values": [{"as_of": day, "return_pct": round(float(normalized.loc[day]), 6)} for day in q3_dates],
        })
    ihsg = benchmark.set_index("date").reindex(q3_dates)["close"]
    if ihsg.isna().any() or (ihsg <= 0).any():
        raise ValueError("Q3 basket benchmark history is incomplete")
    benchmark_values = (ihsg / float(ihsg.iloc[0]) - 1.0) * 100.0
    basket = {
        "start": q3_dates[0], "end": q3_dates[-1],
        "basis": "Equal-weight mean of each current member's adjusted-price return, rebased to zero at the first Q3 session",
        "benchmark": "IHSG", "benchmark_basis": "Benchmark close return, rebased to zero on the same session",
        "series": [{"as_of": day, "return_pct": round(float(benchmark_values.loc[day]), 6)} for day in q3_dates],
        "groups": basket_groups,
    }

    sources = {
        "market_release_sha256": _sha(market_path),
        "rotation_release_sha256": _sha(rotation_path),
        "snapshot_membership_payload_sha256": _sha(snapshot_path),
        "adjusted_price_panel_sha256": _sha(prices_path),
        "ihsg_panel_sha256": _sha(benchmark_path),
    }
    if ownership_edges_path.is_file():
        sources["ownership_edges_sha256"] = _sha(ownership_edges_path)
    if konglo_membership_path.is_file():
        sources["konglo_membership_evidence_sha256"] = _sha(konglo_membership_path)
    benchmark_sessions = sorted(benchmark["date"].astype(str).unique())
    ytd_base_dates = [day for day in benchmark_sessions if day <= "2025-12-31"]
    if not ytd_base_dates:
        raise ValueError("benchmark is missing the prior-year YTD base close")
    ytd_base_date = ytd_base_dates[-1]
    ytd_window_sessions = benchmark_sessions.index(TARGET_DATES[-1]) - benchmark_sessions.index(ytd_base_date)
    payload = {
        "schema_version": SCHEMA,
        "as_of": TARGET_DATES[-1],
        "comparison_dates": list(TARGET_DATES),
        "analysis_dates": analysis_dates,
        "title": "Historical price replay using current membership",
        "replay_basis": "Current release's signal-eligible sector members, fixed across every comparison date; yfinance adjusted-price validation panel; equal-weight taxonomy aggregates.",
        "membership_as_of": max(m.source_as_of for m in memberships if m.source_as_of).isoformat(),
        "cohort": {"count": len(flat_tickers), "sha256": cohort_hash,
                   "group_cohorts": {key: {"count": len(value), "sha256": _hash_json(value)} for key, value in cohort.items()}},
        "calculation": {"price_basis": "adjusted_close", "benchmark": "IHSG", "primary_horizon_sessions": 20,
                        "medium_horizon_sessions": 60, "diffusion_version": "diffusion-v2",
                        "return_window_sessions": {"5d": 5, "20d": 20, "60d": 60, "ytd": ytd_window_sessions},
                        "ytd_base_close_as_of": ytd_base_date,
                        "diffusion_threshold_pp": 10.0, "diffusion_constituent_fraction": 0.10,
                        "diffusion_minimum_constituents": 2, "group_minimum_constituents": 5,
                        "minimum_coverage_pct": 60.0, "materiality_breadth_threshold_pp": 10.0,
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
