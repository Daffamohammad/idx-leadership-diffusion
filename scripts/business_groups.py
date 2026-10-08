"""Reconcile reference catalogue labels with dated, source-linked holdings.

Catalogue labels are analyst research lenses, not a beneficial-owner register.
Only exact named holders and exact listed-issuer legal names are followed.
"""
from __future__ import annotations

import copy
import re
from typing import Any


def legal_name(value: str) -> str:
    words = re.findall(r"[A-Z0-9]+", value.upper())
    return " ".join(word for word in words if word not in {"PT", "TBK", "PERSERO"})


def reconcile(*, definition: dict, legacy: dict, market: dict, ownership: dict) -> tuple[dict, list[dict], dict]:
    if len(definition["groups"]) != 34 or len({g["id"] for g in definition["groups"]}) != 34:
        raise ValueError("business reference must contain 34 distinct groups")
    source = next(s for s in ownership["sources"] if s["as_of"] == ownership["as_of"])
    records = {r["ticker"]: r for r in market["records"]}
    names: dict[str, list[str]] = {}
    for ticker, row in records.items():
        names.setdefault(legal_name(row["company_name"]), []).append(ticker)
    holders: dict[str, list[dict]] = {}
    for row in ownership["registers"]["one"]:
        if not row.get("identity_ambiguous"):
            holders.setdefault(row["holder"], []).append(row)
    view = copy.deepcopy(legacy)
    view["taxonomy_version"] = "documented-business-groups-v2"
    view["taxonomy_name"] = "Business groups and documented portfolios"
    view["definitions"] = {}
    edges = []
    reconciliation = []
    by_id = {g["taxonomy_group_id"]: g for g in view["groups"]}
    old_members = list(view["memberships"])
    for spec in definition["groups"]:
        gid, label = spec["id"], spec["name"]
        by_id[gid] = {"taxonomy_group_id": gid, "taxonomy_group_name": label}
        view["definitions"][gid] = {
            "definition": spec["coverage_note"], "parent_category": "Arthara catalogue reconciliation",
            "inclusion_rules": ["Exact dated disclosed holdings; listed anchor issuers; cited issuer affiliations", definition["indirect_policy"]],
            "exclusion_rules": ["No surname matching, inferred family identity, or implied legal control", "Reference constituent counts are not substituted for verification"],
        }
        evidence: dict[str, list[dict[str, Any]]] = {}
        queue: list[tuple[str, list[str]]] = []

        def add(ticker: str, row: dict, path: list[str], relationship: str, *, url: str | None = None, as_of: str | None = None) -> None:
            ticker = ticker if ticker.endswith(".JK") else ticker + ".JK"
            if ticker not in records:
                return
            edge = {"group_id": gid, "group_name": label, "holder": row.get("holder") or path[0],
                    "ticker": ticker.removesuffix(".JK"), "percentage": row.get("percentage"),
                    "as_of": as_of or ownership["as_of"], "source": url or source["url"],
                    "relationship": relationship, "relationship_path": path + [ticker], "control_source": None}
            if edge not in evidence.setdefault(ticker, []):
                evidence[ticker].append(edge)
                # A disclosed 20% stake is a traversal rule, never a control assertion.
                if row.get("percentage", 0) is not None and row.get("percentage", 0) >= 20:
                    queue.append((ticker, path + [ticker]))

        for row in old_members:
            if row["taxonomy_group_id"] in spec["legacy_portfolios"]:
                ticker = row["ticker"]
                if ticker in records:
                    prior_edge = next((item for item in market.get("ownership_edges", [])
                                       if item["group_id"] == row["taxonomy_group_id"] and item["ticker"] == ticker.removesuffix(".JK")), {})
                    evidence.setdefault(ticker, []).append({**prior_edge, "group_id": gid, "group_name": label,
                        "ticker": ticker.removesuffix(".JK"), "holder": label, "percentage": None,
                        "as_of": row["source_as_of"], "source": row["source"],
                        "relationship": "Documented portfolio membership",
                        "relationship_path": [row["taxonomy_group_id"], ticker], "control_source": prior_edge.get("control_source")})
                    queue.append((ticker, [row["taxonomy_group_id"], ticker]))
        for anchor in spec["listed_anchors"]:
            add(anchor, {}, [label], "Listed anchor in the research lens; does not imply self-ownership",
                url=spec["relationship_source"] or source["url"], as_of=spec["relationship_source_as_of"])
            queue.append((anchor + ".JK", [label, anchor + ".JK"]))
        for holder in spec["holder_names"]:
            for row in holders.get(holder, []):
                add(row["ticker"], row, [holder], "Disclosed named-holder investment")
        for affiliation in spec["issuer_affiliations"]:
            add(affiliation["ticker"], {}, [label], affiliation["relationship"], url=affiliation["source"], as_of=affiliation["source_as_of"])

        visited = set()
        while queue:
            ticker, path = queue.pop(0)
            if ticker in visited or ticker not in records:
                continue
            visited.add(ticker)
            parent_key = legal_name(records[ticker]["company_name"])
            if len(names.get(parent_key, [])) != 1:
                continue  # ambiguous listed legal name: preserve the gap
            for holder, rows in holders.items():
                if legal_name(holder) != parent_key:
                    continue
                for row in rows:
                    if row["ticker"] + ".JK" != ticker:
                        add(row["ticker"], row, path, "Indirect disclosed holding" if len(path) > 2 else "Disclosed listed-parent holding")

        view["memberships"] = [row for row in view["memberships"] if row["taxonomy_group_id"] != gid]
        for ticker, items in sorted(evidence.items()):
            edges.extend(items)
            for item in items:
                view["memberships"].append({"ticker": ticker, "taxonomy_group_id": gid,
                    "taxonomy_group_name": label, "membership_type": "PRIMARY", "confidence": 1.0,
                    "source": item["source"], "source_as_of": item["as_of"], "relationship": item["relationship"]})
        reconciliation.append({"group_id": gid, "reference_name": label, "verified_members": sorted(evidence),
                               "member_count": len(evidence), "coverage_note": spec["coverage_note"],
                               "membership_status": "SOURCED_RESEARCH_LENS" if evidence else "MEMBERSHIP_EVIDENCE_MISSING"})
    view["groups"] = sorted(by_id.values(), key=lambda row: row["taxonomy_group_name"].casefold())
    report = {"schema_version": "business-group-reconciliation-v1", "as_of": ownership["as_of"],
              "reference": definition["reference"], "reference_groups": reconciliation,
              "retained_portfolio_ids": sorted(set(by_id) - {g["id"] for g in definition["groups"]}),
              "policy": definition["indirect_policy"], "issuer_web_retrieved_on": definition.get("reviewed_on"),
              "date_policy": "IDX holdings retain disclosure dates. Undated issuer pages use membership assessment dates, not inferred publication dates; the research lens is retrospective."}
    return view, edges, report
