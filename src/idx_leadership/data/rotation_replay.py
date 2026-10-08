"""Dated rotation replay. Never promotes observation dates to publication dates.

This is a chart-only replay; canonical snapshots and diffusion are untouched.
Sources and normalized versions are supplied by the hash-checked CLI ledger.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date

import pandas as pd

from idx_leadership.features.relative_strength import compute_excess_returns, compute_ytd_excess_returns
from idx_leadership.models.security_master import SecurityMasterEntry
from idx_leadership.providers.market_universe import build_market_universe

KINDS = ("SECTOR", "KONGLO", "THEMES")
AXES = ("group_excess_return_ytd", "group_excess_return_20d", "group_excess_return_60d")
METHOD = "equal-weight-ytd-20d-60d-v1"


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def finite(value) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def source_available(source: dict, session: str) -> bool:
    # available_on is an EOD availability bound, with a reviewed evidence note.
    published = source.get("published_on")
    available = source.get("available_on")
    dated = bool(published and available and published <= available)
    captured = bool(source.get("publication_basis") == "capture_upper_bound" and available)
    return bool((dated or captured) and available and source.get("publication_evidence")
                and source["observed_on"] <= session
                and available <= session)


def select_version(versions: list[dict], sources: dict, session: str) -> dict | None:
    candidates = [v for v in versions if v["effective_from"] <= session
                  and (not v.get("effective_to") or session <= v["effective_to"])
                  and all(source_available(sources[key], session) for key in v["source_ids"])]
    if not candidates:
        return None
    return max(candidates, key=lambda v: v["effective_from"])


def endpoints_from_snapshot(payload: dict) -> dict:
    out = {kind: {} for kind in KINDS}
    for row in payload["groups"]:
        out["SECTOR"][row["group_id"]] = {"name": row.get("group_name", row["group_id"]), **{a: row.get(a) for a in AXES}}
    for view in payload.get("taxonomy_views", {}).values():
        kind = view.get("taxonomy_kind")
        if kind not in ("KONGLO", "THEMES"):
            continue
        for row in view.get("groups", []):
            out[kind][row["taxonomy_group_id"]] = {
                "name": row["taxonomy_group_name"],
                **{a: row.get(a.removeprefix("group_")) for a in AXES},
            }
    return out


def replay(*, prices: pd.DataFrame, benchmark: pd.DataFrame, sessions: list[str],
           sources: dict, universes: list[dict], taxonomies: dict[str, list[dict]],
           endpoints: dict, snapshot_id: str, as_of: str, gaps: set[str]) -> dict:
    """Replay canonical returns, splitting on membership/eligibility/data changes.

    All universe versions contain normalized SecurityMaster records; taxonomy
    versions contain explicit group memberships. Neither is inferred from prices.
    """
    if not sessions or sessions != sorted(set(sessions)) or sessions[-1] != as_of:
        raise ValueError("rotation sessions must be unique, ordered and reach the endpoint")
    prices = prices.copy(); benchmark = benchmark.copy()
    for frame, keys in ((prices, ["ticker", "date"]), (benchmark, ["date"])):
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
        if frame.duplicated(keys).any():
            raise ValueError("duplicate rotation price/session")
        for col in (("close", "adjusted_close") if frame is prices else ("close",)):
            if not frame[col].map(lambda v: finite(v) and v > 0).all():
                raise ValueError("nonfinite or nonpositive rotation price")
    all_sessions = sorted(benchmark["date"].tolist())
    expected = [s for s in all_sessions if sessions[0] <= s <= as_of]
    if sessions != expected:
        raise ValueError("rotation is missing a benchmark session")
    if set(prices["ticker"]) & gaps:
        raise ValueError("quarantined or failed ticker present in rotation panel")
    groups = {kind: {gid: dict(group_id=gid, name=row["name"], segments=[], gaps=[],
                              current_segment_id=None, daily_available=False, weekly_available=False,
                              reason="No dated membership and eligibility evidence available by these closes")
                     for gid, row in endpoints[kind].items()} for kind in KINDS}
    for session in sessions:
        universe = select_version(universes, sources, session)
        selected = {kind: select_version(taxonomies.get(kind, []), sources, session) for kind in KINDS}
        eligible: set[str] = set()
        features = pd.DataFrame()
        if universe is not None and any(selected.values()):
            history = prices[prices["date"] <= session]
            master = [SecurityMasterEntry(**row) for row in universe["records"]]
            policy = build_market_universe(security_master_provider=None, cross_section_provider=None,
                security_master=master, as_of=date.fromisoformat(session), price_history=history,
                acquisition_empties=gaps)
            eligible = set(policy.loc[policy["eligible"], "ticker"])
            # Strict full session coverage prevents stale/repeated closes posing
            # as daily observations. The canonical engine still owns formulas.
            position = all_sessions.index(session)
            warmups = {h: set(all_sessions[max(0, position - h):position + 1]) for h in (20, 60)}
            valid = {h: set() for h in (20, 60)}
            current = set()
            for ticker, frame in history.groupby("ticker"):
                dates = set(frame["date"])
                if session in dates:
                    current.add(ticker)
                for horizon, warmup in warmups.items():
                    if len(warmup) == horizon + 1 and warmup <= dates:
                        valid[horizon].add(ticker)
            calculation = history[history["ticker"].isin(eligible)]
            if not calculation.empty:
                day = date.fromisoformat(session)
                features = compute_excess_returns(calculation, benchmark, horizons={"20d": 20, "60d": 60},
                    as_of=day, security_price_col="adjusted_close")
                ytd = compute_ytd_excess_returns(calculation, benchmark, as_of=day, security_price_col="adjusted_close")
                # Left-join the YTD frame so a missing baseline leaves a
                # visible YTD gap instead of discarding valid 20D/60D rows.
                # An entirely empty YTD frame still yields explicit NaN
                # YTD columns rather than an empty feature set.
                if ytd.empty:
                    for column in ("return_ytd", "benchmark_return_ytd", "excess_return_ytd"):
                        features[column] = float("nan")
                else:
                    features = features.merge(ytd, on="ticker", how="left")
                if not features.empty:
                    for horizon in (20, 60):
                        features.loc[~features["ticker"].isin(valid[horizon]), f"excess_return_{horizon}d"] = float("nan")
                    features.loc[~features["ticker"].isin(current), "excess_return_ytd"] = float("nan")
        for kind in KINDS:
            version = selected[kind]
            for gid, group in groups[kind].items():
                members = sorted(set((version or {}).get("groups", {}).get(gid, [])))
                reason = None
                if universe is None or version is None:
                    reason = "Dated membership or eligibility publication evidence unavailable"
                elif not members:
                    reason = "Group absent from the dated taxonomy"
                members_eligible = sorted(set(members) & eligible)
                values = features[features["ticker"].isin(members_eligible)] if not features.empty else pd.DataFrame()
                if reason is None and (values.empty or not members_eligible):
                    reason = "No eligible members with complete session history"
                axes = {}
                contributors = {}
                if reason is None:
                    for axis in AXES:
                        col = axis.removeprefix("group_")
                        observed = values[values[col].map(finite)]
                        contributors[axis] = sorted(observed["ticker"].tolist())
                        axes[axis] = float(observed[col].mean()) if not observed.empty else None
                    # Per-horizon eligibility: a missing YTD baseline must not
                    # suppress valid 20D/60D return points. Only the return
                    # axes gate the session; YTD stays missing when unavailable.
                    if not finite(axes[AXES[1]]) or not finite(axes[AXES[2]]):
                        reason = "Return warm-up unavailable"
                    elif not finite(axes[AXES[0]]):
                        axes[AXES[0]] = None
                if reason:
                    group["gaps"].append({"as_of": session, "reason": reason})
                    continue
                cohort = fingerprint(members_eligible)
                contract = fingerprint({"eligible": cohort, "members": members, "contributors": contributors,
                                        "method": METHOD, "taxonomy_version": version["method_version"]})
                previous = group["segments"][-1] if group["segments"] else None
                prior_session = sessions[sessions.index(session) - 1] if session != sessions[0] else None
                if previous is None or previous["contract_hash"] != contract or previous["sessions"][-1] != prior_session:
                    previous = {"segment_id": fingerprint([kind, gid, session, contract])[:20],
                                "contract_hash": contract, "group_eligible_ticker_set_hash": cohort,
                                "members": members, "eligible_members": members_eligible,
                                "contributors": contributors, "source_ids": [], "sessions": [], "points": []}
                    group["segments"].append(previous)
                previous["source_ids"] = sorted(set(previous["source_ids"]) | set(universe["source_ids"]) | set(version["source_ids"]))
                previous["sessions"].append(session)
                previous["points"].append({"as_of": session, **axes,
                    "universe_eligible_ticker_set_hash": hashlib.sha256(json.dumps(sorted(eligible)).encode()).hexdigest()[:16],
                    "source_ids": sorted(set(universe["source_ids"]) | set(version["source_ids"])),
                    "relative_momentum": axes[AXES[1]] - axes[AXES[2]]})
    for kind in KINDS:
        for gid, group in groups[kind].items():
            segment = group["segments"][-1] if group["segments"] else None
            if segment is None or segment["sessions"][-1] != as_of:
                group["reason"] = group["gaps"][-1]["reason"] if group["gaps"] else group["reason"]
                continue
            endpoint = segment["points"][-1]
            endpoint_expected = endpoints[kind][gid]
            ytd_actual, ytd_expected = endpoint[AXES[0]], endpoint_expected[AXES[0]]
            ytd_match = (finite(ytd_actual) == finite(ytd_expected)) and (
                not finite(ytd_actual) or abs(ytd_actual - ytd_expected) <= 0.00011
            )
            if (not finite(endpoint[AXES[1]]) or not finite(endpoint[AXES[2]]) or not ytd_match
                    or abs(endpoint[AXES[1]] - endpoint_expected[AXES[1]]) > 0.00011
                    or abs(endpoint[AXES[2]] - endpoint_expected[AXES[2]]) > 0.00011):
                raise ValueError(f"rotation endpoint mismatch: {kind}/{gid}")
            group["current_segment_id"] = segment["segment_id"]
            group["daily_available"] = len(segment["sessions"]) >= 3
            weeks = {date.fromisoformat(s).isocalendar()[:2] for s in segment["sessions"]}
            group["weekly_available"] = len(weeks) >= 3
            group["reason"] = None if group["daily_available"] else "Fewer than three comparable observations in the current segment"
    return dict(schema_version="rotation-history-v1", snapshot_id=snapshot_id, as_of=as_of,
                start=sessions[0], sessions=sessions, method=METHOD, sources=sources, taxonomies=groups,
                limitations=["Point-in-time membership and eligibility require publication evidence.",
                             "Historical prices are a later retrieved vintage, not an archived real-time feed.",
                             "Replay does not change canonical diffusion or confirmation gates."])


def validate_asset(payload: dict, endpoints: dict) -> None:
    """Publication gate, independent of availability claims in the report."""
    if payload["schema_version"] != "rotation-history-v1" or payload["method"] != METHOD:
        raise ValueError("rotation asset contract mismatch")
    sessions = payload["sessions"]
    if not sessions or sessions != sorted(set(sessions)) or sessions[-1] != payload["as_of"]:
        raise ValueError("rotation asset sessions invalid")
    if set(payload["taxonomies"]) != set(KINDS):
        raise ValueError("rotation asset missing taxonomy")
    for kind in KINDS:
        if set(payload["taxonomies"][kind]) != set(endpoints[kind]):
            raise ValueError("rotation asset group coverage mismatch")
        for gid, group in payload["taxonomies"][kind].items():
            current = None
            previous_end = ""
            ids = set()
            for segment in group["segments"]:
                dates = segment["sessions"]
                if (not dates or dates != [s for s in sessions if dates[0] <= s <= dates[-1]]
                        or dates[0] <= previous_end or segment["segment_id"] in ids
                        or [p["as_of"] for p in segment["points"]] != dates):
                    raise ValueError("rotation segment has missing or duplicate sessions")
                previous_end = dates[-1]; ids.add(segment["segment_id"])
                for point in segment["points"]:
                    ytd_point = point[AXES[0]]
                    if ((ytd_point is not None and not finite(ytd_point))
                            or not finite(point[AXES[1]]) or not finite(point[AXES[2]])
                            or not finite(point["relative_momentum"])
                            or abs(point["relative_momentum"] - (point[AXES[1]] - point[AXES[2]])) > 1e-8):
                        raise ValueError("rotation axes invalid")
                    if not point["source_ids"] or any(not source_available(payload["sources"][key], point["as_of"]) for key in point["source_ids"]):
                        raise ValueError("rotation source was unavailable on observation date")
                if segment["segment_id"] == group["current_segment_id"]:
                    current = segment
            if current:
                last = current["points"][-1]
                last_expected = endpoints[kind][gid]
                last_ytd, last_ytd_expected = last[AXES[0]], last_expected[AXES[0]]
                last_ytd_match = (finite(last_ytd) == finite(last_ytd_expected)) and (
                    not finite(last_ytd) or abs(last_ytd - last_ytd_expected) <= 0.00011
                )
                if (last["as_of"] != payload["as_of"] or not last_ytd_match
                        or not finite(last[AXES[1]]) or not finite(last[AXES[2]])
                        or abs(last[AXES[1]] - last_expected[AXES[1]]) > 0.00011
                        or abs(last[AXES[2]] - last_expected[AXES[2]]) > 0.00011):
                    raise ValueError("rotation endpoint mismatch")
            elif group["current_segment_id"] is not None:
                raise ValueError("rotation current segment not found")
            daily = bool(current and len(current["sessions"]) >= 3)
            weekly = bool(current and len({date.fromisoformat(s).isocalendar()[:2] for s in current["sessions"]}) >= 3)
            if group["daily_available"] != daily or group["weekly_available"] != weekly:
                raise ValueError("rotation cadence availability mismatch")
