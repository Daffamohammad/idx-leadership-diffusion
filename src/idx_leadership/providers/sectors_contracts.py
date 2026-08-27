"""Runtime checks for the documented Sectors v2 fixture contracts.

The checks deliberately focus on fields the provider actually depends on:
primary identifiers, row granularity, primitive types, and market dates.
Optional vendor fields and field ordering are not pinned.  This gives a future
live-key validation run an obvious failure when a required assumption drifts
without inventing requirements that are absent from the public API docs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from numbers import Real
from typing import Any, Mapping

from ..utils.errors import NormalizationError


@dataclass(frozen=True)
class ContractIssue:
    code: str
    location: str
    message: str


@dataclass
class ContractReport:
    endpoint: str
    granularity: str
    rows: int = 0
    issues: list[ContractIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "granularity": self.granularity,
            "rows": self.rows,
            "valid": self.valid,
            "issues": [asdict(issue) for issue in self.issues],
        }

    def raise_for_errors(self) -> None:
        if self.valid:
            return
        detail = "; ".join(
            f"{issue.code}@{issue.location}: {issue.message}" for issue in self.issues
        )
        raise NormalizationError(f"Sectors contract drift for {self.endpoint}: {detail}")


def _endpoint_kind(endpoint: str) -> tuple[str, str]:
    path = endpoint.split("?", 1)[0]
    if path == "/v2/companies/":
        return "companies", "one row per listed company"
    if path == "/v2/close/":
        return "close", "one row per symbol and market date"
    if path == "/v2/free-float/":
        return "free_float", "one row per listed company"
    if path == "/v2/suspensions/":
        return "suspensions", "one row per suspension event"
    if "/v2/foreign-flow/" in path:
        return "foreign_flow", "one row per symbol and market date"
    if "/v2/company/corporate-actions/" in path:
        return "corporate_actions", "one object per symbol"
    return "unknown", "unknown"


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _valid_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _extract_rows(
    payload: Any, kind: str, report: ContractReport
) -> list[Mapping[str, Any]]:
    if kind in {"foreign_flow", "corporate_actions"}:
        if not isinstance(payload, Mapping):
            report.issues.append(
                ContractIssue("PAYLOAD_TYPE", "$", "expected a JSON object")
            )
            return []
        if kind == "foreign_flow":
            data = payload.get("data")
            if not isinstance(data, list):
                report.issues.append(
                    ContractIssue("REQUIRED_TYPE", "$.data", "expected an array")
                )
                return []
            return [row for row in data if isinstance(row, Mapping)]
        return [payload]

    if isinstance(payload, list):
        raw_rows = payload
    elif isinstance(payload, Mapping):
        if "error" in payload:
            report.issues.append(
                ContractIssue(
                    "API_ERROR_PAYLOAD",
                    "$",
                    f"received error payload: {payload.get('error')}",
                )
            )
            return []
        if "results" not in payload:
            report.issues.append(
                ContractIssue("REQUIRED_KEY", "$.results", "missing paginated results")
            )
            return []
        raw_rows = payload.get("results")
        if not isinstance(raw_rows, list):
            report.issues.append(
                ContractIssue("REQUIRED_TYPE", "$.results", "expected an array")
            )
            return []
        pagination = payload.get("pagination")
        if not isinstance(pagination, Mapping):
            report.issues.append(
                ContractIssue(
                    "REQUIRED_TYPE", "$.pagination", "expected pagination object"
                )
            )
        else:
            for key in ("has_next", "offset", "limit"):
                if key in pagination and not isinstance(
                    pagination[key], bool if key == "has_next" else int
                ):
                    report.issues.append(
                        ContractIssue(
                            "PAGINATION_TYPE",
                            f"$.pagination.{key}",
                            "unexpected pagination type",
                        )
                    )
    else:
        report.issues.append(
            ContractIssue("PAYLOAD_TYPE", "$", "expected an object or array")
        )
        return []

    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(raw_rows):
        if not isinstance(row, Mapping):
            report.issues.append(
                ContractIssue("ROW_TYPE", f"$.results[{index}]", "expected an object")
            )
            continue
        rows.append(row)
    return rows


def validate_sectors_payload(
    endpoint: str,
    payload: Any,
    *,
    expected_date: date | str | None = None,
    raise_on_error: bool = False,
) -> ContractReport:
    """Validate a raw Sectors payload against the fields used by this project."""

    kind, granularity = _endpoint_kind(endpoint)
    report = ContractReport(endpoint=endpoint, granularity=granularity)
    if kind == "unknown":
        report.issues.append(
            ContractIssue("UNKNOWN_ENDPOINT", "$", "no local contract is registered")
        )
        if raise_on_error:
            report.raise_for_errors()
        return report

    rows = _extract_rows(payload, kind, report)
    report.rows = len(rows)
    expected = expected_date.isoformat() if isinstance(expected_date, date) else expected_date

    seen_symbols: set[str] = set()
    parent_symbol = payload.get("symbol") if isinstance(payload, Mapping) else None
    if kind in {"foreign_flow", "corporate_actions"}:
        if not isinstance(parent_symbol, str) or not parent_symbol.strip():
            report.issues.append(
                ContractIssue("PRIMARY_IDENTIFIER", "$.symbol", "missing non-empty symbol")
            )

    for index, row in enumerate(rows):
        location = "$" if kind == "corporate_actions" else f"$.results[{index}]"
        if kind == "foreign_flow":
            location = f"$.data[{index}]"

        if kind not in {"foreign_flow", "corporate_actions"}:
            symbol = row.get("symbol")
            if not isinstance(symbol, str) or not symbol.strip():
                report.issues.append(
                    ContractIssue(
                        "PRIMARY_IDENTIFIER", f"{location}.symbol", "missing non-empty symbol"
                    )
                )
            else:
                canonical = symbol.upper().removesuffix(".JK")
                if canonical in seen_symbols:
                    report.issues.append(
                        ContractIssue(
                            "DUPLICATE_IDENTIFIER",
                            f"{location}.symbol",
                            f"duplicate symbol {symbol}",
                        )
                    )
                seen_symbols.add(canonical)

        if kind == "companies":
            for key in ("sector", "sub_sector", "industry", "sub_industry"):
                value = row.get(key)
                if value is not None and not isinstance(value, str):
                    report.issues.append(
                        ContractIssue(
                            "OPTIONAL_TYPE",
                            f"{location}.{key}",
                            "expected string or null",
                        )
                    )
        elif kind == "close":
            row_date = row.get("date")
            if not _valid_iso_date(row_date):
                report.issues.append(
                    ContractIssue("DATE_TYPE", f"{location}.date", "expected YYYY-MM-DD")
                )
            elif expected is not None and row_date != expected:
                report.issues.append(
                    ContractIssue(
                        "UNEXPECTED_DATE",
                        f"{location}.date",
                        f"expected {expected}, received {row_date}",
                    )
                )
            if not _is_number(row.get("close")):
                report.issues.append(
                    ContractIssue("REQUIRED_TYPE", f"{location}.close", "expected a number")
                )
        elif kind == "free_float":
            if not _is_number(row.get("free_float")):
                report.issues.append(
                    ContractIssue(
                        "REQUIRED_TYPE", f"{location}.free_float", "expected a number"
                    )
                )
        elif kind == "suspensions":
            if not _valid_iso_date(row.get("suspension_date")):
                report.issues.append(
                    ContractIssue(
                        "DATE_TYPE",
                        f"{location}.suspension_date",
                        "expected YYYY-MM-DD",
                    )
                )
        elif kind == "foreign_flow":
            if not _valid_iso_date(row.get("date")):
                report.issues.append(
                    ContractIssue("DATE_TYPE", f"{location}.date", "expected YYYY-MM-DD")
                )
            if not _is_number(row.get("net_foreign_inflow")):
                report.issues.append(
                    ContractIssue(
                        "REQUIRED_TYPE",
                        f"{location}.net_foreign_inflow",
                        "expected a number",
                    )
                )
        elif kind == "corporate_actions":
            actions = row.get("corporate_actions")
            if not isinstance(actions, Mapping):
                report.issues.append(
                    ContractIssue(
                        "REQUIRED_TYPE", "$.corporate_actions", "expected an object"
                    )
                )

    if raise_on_error:
        report.raise_for_errors()
    return report


__all__ = [
    "ContractIssue",
    "ContractReport",
    "validate_sectors_payload",
]
