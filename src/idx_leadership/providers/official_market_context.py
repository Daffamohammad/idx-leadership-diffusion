"""Reduce an official, parser-produced market release to typed context.

This adapter is intentionally separate from the per-security flow pipeline.
Search agents locate a first-party publication; LlamaCloud/LlamaParse extracts
the selected pages; this module promotes only values that survive deterministic
label, unit, date, and narrative checks.  Market-level values must never be
presented as ticker- or group-level confirmation.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from html.parser import HTMLParser
import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


OJK_RDK_JUNE_2026_URL = (
    "https://ojk.go.id/id/berita-dan-kegiatan/siaran-pers/Documents/Pages/"
    "RDKB-Juni-2026/SP%20131%20Resiliensi%20Dan%20Kinerja%20Intermediasi%20"
    "Sektor%20Jasa%20Keuangan%20Terjaga%20Sebagai%20Modalitas%20Mendorong%20"
    "Pertumbuhan%20RDKB%20Juni%202026.pdf"
)
OFFICIAL_MARKET_CONTEXT_SCHEMA_VERSION = "official-market-context-v1"

_MONTHS = {
    "jan": 1,
    "january": 1,
    "januari": 1,
    "feb": 2,
    "february": 2,
    "februari": 2,
    "mar": 3,
    "march": 3,
    "maret": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "mei": 5,
    "jun": 6,
    "june": 6,
    "juni": 6,
    "jul": 7,
    "july": 7,
    "juli": 7,
    "aug": 8,
    "august": 8,
    "agustus": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    "des": 12,
    "desember": 12,
}

_NUMBER_RE = re.compile(r"[-+−]?\d[\d.,]*(?:%|\b)")


class OfficialMarketContextError(ValueError):
    """Raised when a parser response cannot support a safe promotion."""


class _TableParser(HTMLParser):
    """Extract simple HTML tables preserved inside parser markdown."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._table = []
            self.tables.append(self._table)
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._table is not None and self._row is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _parse_number(token: str) -> float:
    """Parse Indonesian/English thousands and decimal separators."""
    text = _clean(token).replace("−", "-").replace("%", "")
    if not text:
        raise OfficialMarketContextError("empty numeric token")
    if "," in text and "." in text:
        # 5.643,19 -> 5643.19; 5,643.19 -> 5643.19.
        if text.rfind(",") > text.rfind("."):
            normalized = text.replace(".", "").replace(",", ".")
        else:
            normalized = text.replace(",", "")
    elif "," in text:
        head, tail = text.rsplit(",", 1)
        normalized = f"{head.replace(',', '')}.{tail}" if len(tail) <= 2 else text.replace(",", "")
    elif "." in text:
        head, tail = text.rsplit(".", 1)
        normalized = f"{head.replace('.', '')}.{tail}" if len(tail) <= 2 else text.replace(".", "")
    else:
        normalized = text
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:
        raise OfficialMarketContextError(f"invalid numeric token: {token!r}") from exc
    return float(value)


def _number_tokens(value: str) -> list[str]:
    return [token for token in _NUMBER_RE.findall(_clean(value)) if token not in {"-", "+"}]


def _parse_date(day: str, month: str, year: str) -> str:
    month_number = int(month) if month.isdigit() else _MONTHS.get(month.lower().rstrip("."))
    if month_number is None:
        raise OfficialMarketContextError(f"unsupported release month: {month!r}")
    try:
        return date(int(year), month_number, int(day)).isoformat()
    except ValueError as exc:
        raise OfficialMarketContextError("invalid release date") from exc


def _extract_period_end(markdown: str) -> str:
    candidates: list[str] = []
    for match in re.finditer(
        r"\b([0-3]?\d)[-/]([A-Za-z]+|\d{1,2})[-/](20\d{2})\b",
        markdown,
        flags=re.IGNORECASE,
    ):
        try:
            candidates.append(_parse_date(*match.groups()))
        except OfficialMarketContextError:
            continue
    if not candidates:
        raise OfficialMarketContextError("period-end date is missing from parser output")
    return max(candidates)


def _assert_official_source_url(source_url: str) -> None:
    parsed = urlparse(source_url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "ojk.go.id" or host.endswith(".ojk.go.id")
        or host == "idx.co.id" or host.endswith(".idx.co.id")
    ):
        raise OfficialMarketContextError(
            "market context source must be an HTTPS OJK or IDX URL"
        )


def _extract_release_date(markdown: str) -> str:
    match = re.search(
        r"\b(?:Jakarta\s*,?\s*)?([0-3]?\d)\s+([A-Za-z]+)\s+(20\d{2})\b",
        markdown,
        re.IGNORECASE,
    )
    if not match:
        raise OfficialMarketContextError("release date is missing from parser output")
    return _parse_date(*match.groups())


def _extract_table_rows(markdown: str) -> list[list[str]]:
    parser = _TableParser()
    try:
        parser.feed(markdown)
    except Exception as exc:  # pragma: no cover - defensive HTMLParser boundary
        raise OfficialMarketContextError("parser output table is malformed") from exc
    rows = [row for table in parser.tables for row in table]
    if rows:
        return rows
    # LlamaCloud can return a compact markdown table after stripping HTML.
    for line in markdown.splitlines():
        if "|" not in line:
            continue
        cells = [_clean(part) for part in line.strip().strip("|").split("|")]
        if cells and not all(set(cell) <= {"-", ":", " "} for cell in cells):
            rows.append(cells)
    return rows


def _last_numeric_cell(row: Sequence[str], *, percent: bool = False) -> float | None:
    for cell in reversed(row[1:] if len(row) > 1 else row):
        tokens = _number_tokens(cell)
        if percent:
            tokens = [token for token in tokens if "%" in token]
        if tokens:
            return _parse_number(tokens[0])
    return None


def _extract_table_metrics(markdown: str) -> tuple[dict[str, float], dict[str, bool]]:
    metrics: dict[str, float] = {}
    checks = {
        "ihsg_row_found": False,
        "local_ownership_row_found": False,
        "market_cap_row_found": False,
        "rnth_row_found": False,
        "equity_flow_ytd_row_found": False,
    }
    for row in _extract_table_rows(markdown):
        if not row:
            continue
        label = _clean(row[0]).lower()
        if label == "ihsg" or label.startswith("ihsg "):
            cell = row[-1] if len(row) > 1 else ""
            tokens = _number_tokens(cell)
            if len(tokens) >= 2:
                metrics["ihsg_close"] = _parse_number(tokens[0])
                metrics["ihsg_ytd_pct"] = _parse_number(tokens[1])
                checks["ihsg_row_found"] = True
        elif "kepemilikan lokal" in label:
            value = _last_numeric_cell(row)
            if value is not None:
                metrics["local_ownership_pct"] = value
                checks["local_ownership_row_found"] = True
        elif "market cap saham" in label:
            value = _last_numeric_cell(row)
            if value is not None:
                metrics["market_cap_idr_trillion"] = value
                checks["market_cap_row_found"] = True
        elif label.startswith("rnth saham") or "rnth saham" in label:
            value = _last_numeric_cell(row)
            if value is not None:
                metrics["equity_rnth_idr_trillion"] = value
                checks["rnth_row_found"] = True
        elif label == "saham (rp t)" or (label.startswith("saham") and "rp t" in label):
            value = _last_numeric_cell(row)
            if value is not None:
                metrics["equity_flow_ytd_idr_trillion"] = value
                checks["equity_flow_ytd_row_found"] = True
    return metrics, checks


def _extract_foreign_sell(markdown: str) -> tuple[float, str, dict[str, bool]]:
    matches = list(
        re.finditer(
            r"(?i)(?P<direction>net\s+(?:sell|buy)|jual\s+bersih|beli\s+bersih)"
            r".*?Rp\s*(?P<value>\d[\d.,]*)\s*(?:triliun|trillion)",
            markdown,
            flags=re.DOTALL,
        )
    )
    if not matches:
        raise OfficialMarketContextError("market-level foreign flow narrative is missing")
    match = matches[0]
    direction_text = match.group("direction").lower()
    value = _parse_number(match.group("value"))
    direction = "NET_SELL" if ("sell" in direction_text or "jual" in direction_text) else "NET_BUY"
    signed = -abs(value) if direction == "NET_SELL" else abs(value)
    return signed, direction, {"foreign_flow_narrative_found": True}


def build_official_market_context_payload(
    markdown: str,
    *,
    source_url: str,
    source_published_at: str | None = None,
    parsed_pages: Sequence[int] = (1, 2),
    parser_agent: str = "LlamaCloud",
    parser_version: str = "llamacloud-parse-v1",
    retrieved_at: str | None = None,
    source_file_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a market-level context artifact from bounded parsed pages."""
    if not isinstance(markdown, str) or not markdown.strip():
        raise OfficialMarketContextError("parser markdown is empty")
    _assert_official_source_url(source_url)
    release_date = _extract_release_date(markdown)
    period_end = _extract_period_end(markdown)
    metrics, checks = _extract_table_metrics(markdown)
    net_foreign, flow_direction, flow_checks = _extract_foreign_sell(markdown)
    checks.update(flow_checks)
    checks["source_url_present"] = bool(source_url.strip())
    required = {
        "ihsg_close",
        "ihsg_ytd_pct",
        "local_ownership_pct",
        "market_cap_idr_trillion",
        "equity_rnth_idr_trillion",
        "equity_flow_ytd_idr_trillion",
    }
    missing = sorted(required.difference(metrics))
    if missing:
        raise OfficialMarketContextError(
            "required OJK market metrics are missing: " + ", ".join(missing)
        )
    if not source_url.strip():
        raise OfficialMarketContextError("source URL is required")
    source: dict[str, Any] = {
        "publisher": "Otoritas Jasa Keuangan",
        "url": source_url,
        "published_at": source_published_at or release_date,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "parser_agent": parser_agent,
        "parser_version": parser_version,
        "parsed_pages": [int(page) for page in parsed_pages],
    }
    if source_file_sha256:
        source["file_sha256"] = source_file_sha256
    payload = {
        "schema_version": OFFICIAL_MARKET_CONTEXT_SCHEMA_VERSION,
        "provider": "OJK",
        "provider_mode": "OJK_OFFICIAL_RELEASE",
        "status": "READY",
        "quantitative_use": True,
        "scope": "MONTHLY_MARKET_CONTEXT",
        "release_date": release_date,
        "period_end": period_end,
        "metrics": {
            "ihsg_close": round(metrics["ihsg_close"], 4),
            "ihsg_ytd_pct": round(metrics["ihsg_ytd_pct"], 4),
            "equity_net_foreign_idr_trillion": round(net_foreign, 4),
            "equity_net_foreign_direction": flow_direction,
            "equity_flow_ytd_idr_trillion": round(metrics["equity_flow_ytd_idr_trillion"], 4),
            "equity_rnth_idr_trillion": round(metrics["equity_rnth_idr_trillion"], 4),
            "local_ownership_pct": round(metrics["local_ownership_pct"], 4),
            "market_cap_idr_trillion": round(metrics["market_cap_idr_trillion"], 4),
        },
        "quality": {
            "checks": checks,
            "warning_count": 0,
            "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
            "search_agent_role": "DISCOVERY_ONLY",
            "parser_agent": parser_agent,
        },
        "source": source,
        "context_compatibility": {
            "role": "DESCRIPTIVE_MARKET_CONTEXT",
            "used_in_leadership_or_diffusion": False,
            "not_per_ticker": True,
            "not_per_group": True,
        },
        "limitations": [
            "These values describe the market-level OJK release and are not assigned to individual securities or taxonomy groups.",
            "The release is a monthly context source; it does not replace the bounded daily per-security flow sample.",
        ],
    }
    return payload


__all__ = [
    "OJK_RDK_JUNE_2026_URL",
    "OFFICIAL_MARKET_CONTEXT_SCHEMA_VERSION",
    "OfficialMarketContextError",
    "build_official_market_context_payload",
]
