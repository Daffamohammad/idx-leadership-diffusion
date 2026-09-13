"""Claim-permission gates: which classes of statement the evidence supports.

Every permission derives from persisted coverage/quality state, never from
a successful HTTP status. Unsupported classes stay BLOCKED or carry an
explicit caveat; the UI and exports must render the caveat, not the claim.
"""
from __future__ import annotations

from typing import Any, Mapping


# Phrases that assert unsupported breadth. Headlines and brief copy must
# never emit these unless market_scope() returns "market-wide".
MARKET_WIDE_PHRASES = (
    "market-wide",
    "entire market",
    "all stocks",
    "full universe",
    "all sectors",
    "broad market",
    "comprehensive",
    "complete market",
)


def _coverage(coverage: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(coverage or {})


def market_scope(coverage: Mapping[str, Any] | None) -> str:
    """Return the strongest scope phrase the coverage state justifies.

    ``market-wide`` requires a COMPLETE state on a market-wide provider
    mode with the coverage gate met. Everything else degrades to
    explicitly partial wording.
    """
    cov = _coverage(coverage)
    state = cov.get("coverage_state")
    gate_met = cov.get("coverage_gate_60pct_met")
    mode = cov.get("provider_mode", "")
    if (
        state == "COMPLETE"
        and gate_met is True
        and str(mode) == "SECTORS_LIVE"
    ):
        return "market-wide"
    if state in ("COMPLETE", None) and gate_met is True:
        return "across covered groups"
    return "within the tracked universe"


def claim_permissions(
    coverage: Mapping[str, Any] | None,
    *,
    has_ytd_baseline: bool = False,
    has_promoted_flow_claim: bool = False,
) -> dict[str, dict[str, str]]:
    """Map claim classes to permission + reason.

    Statuses: PERMITTED | CAVEAT (allowed with stated scope) | BLOCKED.
    """
    scope = market_scope(coverage)
    scope_ok = scope == "market-wide"
    perms: dict[str, dict[str, str]] = {
        "sector_leadership": {
            "status": "PERMITTED",
            "reason": "per-group deterministic classification with denominators",
        },
        "breadth": {
            "status": "PERMITTED" if scope_ok else "CAVEAT",
            "reason": "market-wide"
            if scope_ok
            else f"breadth describes {scope}; denominators in evidence",
        },
        "concentration": {
            "status": "PERMITTED",
            "reason": "per-group deterministic decomposition with statuses",
        },
        "transitions": {
            "status": "PERMITTED",
            "reason": "comparability-gated; suppressed when INCOMPARABLE",
        },
        "ytd": {
            "status": "PERMITTED" if has_ytd_baseline else "CAVEAT",
            "reason": "mutual-baseline YTD"
            if has_ytd_baseline
            else "YTD only where a mutual prior-year baseline exists; otherwise UNCONFIRMED",
        },
        "foreign_flow": {
            "status": "PERMITTED" if has_promoted_flow_claim else "BLOCKED",
            "reason": "promoted quantitative claim"
            if has_promoted_flow_claim
            else "no promoted flow claim; surfaces stay DATA GAP / CONTEXT ONLY",
        },
        "market_wide_narrative": {
            "status": "PERMITTED" if scope_ok else "BLOCKED",
            "reason": "market-wide wording"
            if scope_ok
            else f"coverage justifies only {scope} wording",
        },
    }
    return perms


def assert_no_market_wide_phrasing(text: str) -> None:
    """Guard for headlines/brief copy: fail if unsupported breadth is asserted.

    Callers that hold a market-wide permission should check scope first and
    only then emit such phrasing; this helper enforces the default-deny side.
    """
    lowered = str(text or "").lower()
    for phrase in MARKET_WIDE_PHRASES:
        if phrase in lowered:
            raise ValueError(
                f"unsupported market-wide phrasing: {phrase!r}"
            )
