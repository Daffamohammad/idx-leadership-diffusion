"""First-party IDX statistical-release discovery and parsing.

The IDX website exposes two different publication shapes that are easy to
confuse:

* the statistics index lists dated Daily Statistics PDFs; and
* the Digital Statistic pages render structured HTML tables, including the
  monthly investor-type release used for foreign-flow totals.

Search providers can help discover a candidate page, but they are not the
numeric source.  This module keeps the source URL explicit and parses the
published table deterministically.  It never calls a search provider and it
does not infer per-ticker flow from a market-level release.
"""
from __future__ import annotations

from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen


IDX_STATISTICS_INDEX_URL = (
    "https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/"
)
IDX_MONTHLY_INVESTOR_URL = (
    "https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/"
    "monthly/equity-trading-by-investor/"
    "table-daily-trading-by-type-of-investor"
)
IDX_HOST = "www.idx.co.id"
SCHEMA_VERSION = "idx-investor-trading-v1"
LISTING_SCHEMA_VERSION = "idx-statistics-listing-v1"

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
    "okt": 10,
    "october": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "des": 12,
    "december": 12,
    "desember": 12,
}


class IDXStatisticsError(ValueError):
    """Raised when an IDX release cannot be fetched or validated."""


@dataclass(frozen=True)
class _HTMLTable:
    rows: tuple[tuple[str, ...], ...]

    @property
    def text(self) -> str:
        return " ".join(" ".join(row) for row in self.rows)


class _IDXHTMLParser(HTMLParser):
    """Small dependency-free parser for the table and link shapes we need."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.links: list[dict[str, str]] = []
        self.headings: list[str] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._heading: list[str] | None = None
        self._link_href: str | None = None
        self._link_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = dict(attrs)
        if tag == "table":
            self._table = []
            self.tables.append(self._table)
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []
        elif tag in {"h1", "h2", "h3", "h4"}:
            self._heading = []
        elif tag == "a":
            self._link_href = attributes.get("href") or ""
            self._link_text = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"th", "td"} and self._row is not None and self._cell is not None:
            self._row.append(_clean_text(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._table is not None and self._row is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag in {"h1", "h2", "h3", "h4"} and self._heading is not None:
            text = _clean_text(" ".join(self._heading))
            if text:
                self.headings.append(text)
            self._heading = None
        elif tag == "a" and self._link_text is not None:
            text = _clean_text(" ".join(self._link_text))
            self.links.append({"href": self._link_href or "", "text": text})
            self._link_href = None
            self._link_text = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        if self._heading is not None:
            self._heading.append(data)
        if self._link_text is not None:
            self._link_text.append(data)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _parse_date(value: Any) -> str:
    text = _clean_text(str(value or ""))
    iso = re.fullmatch(r"(\d{4})[-/]([01]\d)[-/]([0-3]\d)", text)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError as exc:
            raise IDXStatisticsError(f"invalid IDX date: {text!r}") from exc
    match = re.fullmatch(r"([0-3]?\d)\s+([A-Za-z]+)\s+(\d{4})", text)
    if match:
        day, month_text, year = match.groups()
        month = _MONTHS.get(month_text.lower())
        if month is not None:
            try:
                return datetime(int(year), month, int(day)).date().isoformat()
            except ValueError as exc:
                raise IDXStatisticsError(f"invalid IDX date: {text!r}") from exc
    raise IDXStatisticsError(f"could not parse IDX date: {text!r}")


def _parse_integer(value: Any, *, label: str) -> int:
    text = _clean_text(str(value or ""))
    if not text or text in {"-", "—", "–", "n/a", "N/A"}:
        raise IDXStatisticsError(f"missing numeric value for {label}")
    negative = text.startswith(("-", "−"))
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        raise IDXStatisticsError(f"invalid numeric value for {label}: {text!r}")
    result = int(digits)
    return -result if negative else result


def _direction(value: int) -> str:
    if value > 0:
        return "NET_BUY"
    if value < 0:
        return "NET_SELL"
    return "FLAT"


def build_monthly_investor_url(year: int, month: int) -> str:
    """Build the canonical IDX monthly investor-type URL."""
    if not 1 <= int(month) <= 12:
        raise ValueError("month must be between 1 and 12")
    filter_payload = {
        "year": str(int(year)),
        "month": str(int(month)),
        "quarter": 0,
        "type": "monthly",
    }
    encoded = urlsafe_b64encode(
        json.dumps(filter_payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return f"{IDX_MONTHLY_INVESTOR_URL}?filter={quote(encoded, safe='')}"


def _assert_idx_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != IDX_HOST:
        raise IDXStatisticsError(
            f"refusing non-first-party IDX URL: expected https://{IDX_HOST}, got {url!r}"
        )


def fetch_idx_html(url: str, *, timeout: int = 30) -> str:
    """Fetch a public IDX page without credentials or search-provider fallback."""
    _assert_idx_url(url)
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
            "User-Agent": "IDXLeadershipDiffusion/0.1 (+public-statistics-parser)",
        },
    )
    try:
        with urlopen(request, timeout=max(1, int(timeout))) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except HTTPError as exc:
        raise IDXStatisticsError(f"IDX page returned HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise IDXStatisticsError(f"IDX page could not be reached: {exc.reason}") from exc
    except OSError as exc:
        raise IDXStatisticsError(f"IDX page fetch failed: {exc}") from exc
    try:
        return raw.decode(charset, errors="replace")
    except LookupError as exc:
        raise IDXStatisticsError(f"unsupported IDX page encoding: {charset}") from exc


def parse_idx_statistics_listing_html(
    html: str,
    *,
    source_url: str = IDX_STATISTICS_INDEX_URL,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Extract dated Daily Statistics PDF links from the IDX listing page."""
    _assert_idx_url(source_url)
    parser = _IDXHTMLParser()
    parser.feed(html)
    publications: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in parser.links:
        href = urljoin(source_url, link["href"])
        label = link["text"] or href.rsplit("/", 1)[-1]
        if not href.lower().split("?", 1)[0].endswith(".pdf"):
            continue
        try:
            as_of = _parse_date(label)
        except IDXStatisticsError:
            date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", href)
            if date_match:
                as_of = _parse_date(date_match.group(1))
            else:
                compact_match = re.search(r"(?:ds|daily)[_/-]?(\d{2})(\d{2})(\d{2})", href, re.I)
                if not compact_match:
                    continue
                yy, month, day = (int(part) for part in compact_match.groups())
                as_of = _parse_date(f"20{yy:02d}-{month:02d}-{day:02d}")
        if href in seen:
            continue
        seen.add(href)
        publications.append(
            {
                "as_of": as_of,
                "title": label,
                "url": href,
                "format": "PDF",
            }
        )
    publications.sort(key=lambda row: (row["as_of"], row["url"]), reverse=True)
    return {
        "schema_version": LISTING_SCHEMA_VERSION,
        "status": "READY" if publications else "DATA_GAP",
        "source": {
            "publisher": "Indonesia Stock Exchange",
            "url": source_url,
            "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
            "parser": "idx_statistics_listing_html",
        },
        "quality": {
            "publication_count": len(publications),
            "dated_pdf_count": len(publications),
            "search_agent_role": "DISCOVERY_ONLY",
        },
        "publications": publications,
        "limitations": [
            "The listing links to official PDFs; PDF contents require a separate PDF extraction step.",
            "A search result is not treated as numeric evidence when the official publication is unavailable.",
        ],
    }


def _select_table(tables: Sequence[_HTMLTable], marker: str) -> _HTMLTable:
    for table in tables:
        if marker.lower() in table.text.lower():
            return table
    raise IDXStatisticsError(f"IDX release table not found: {marker}")


def _table_rows(table: _HTMLTable, *, section: str) -> tuple[dict[str, Any], dict[str, Any]]:
    data_rows: list[dict[str, Any]] = []
    total: dict[str, Any] | None = None
    for row in table.rows[2:]:
        if not row:
            continue
        if row[0].strip().lower() == "total":
            if len(row) < 7:
                raise IDXStatisticsError(f"{section} total row is incomplete")
            total = {
                "volume_first": _parse_integer(row[1], label=f"{section} total volume"),
                "value_first": _parse_integer(row[2], label=f"{section} total value"),
                "frequency_first": _parse_integer(row[3], label=f"{section} total frequency"),
                "volume_second": _parse_integer(row[4], label=f"{section} total volume"),
                "value_second": _parse_integer(row[5], label=f"{section} total value"),
                "frequency_second": _parse_integer(row[6], label=f"{section} total frequency"),
            }
            continue
        if len(row) < 7:
            continue
        try:
            as_of = _parse_date(row[0])
        except IDXStatisticsError:
            # Footnotes or responsive duplicate rows must not become data.
            continue
        data_rows.append(
            {
                "as_of": as_of,
                "volume_first": _parse_integer(row[1], label=f"{section} volume"),
                "value_first": _parse_integer(row[2], label=f"{section} value"),
                "frequency_first": _parse_integer(row[3], label=f"{section} frequency"),
                "volume_second": _parse_integer(row[4], label=f"{section} volume"),
                "value_second": _parse_integer(row[5], label=f"{section} value"),
                "frequency_second": _parse_integer(row[6], label=f"{section} frequency"),
            }
        )
    if not data_rows or total is None:
        raise IDXStatisticsError(f"{section} table has no complete daily rows and total")
    return {row["as_of"]: row for row in data_rows}, total


def _period_from_title(title: str | None) -> dict[str, Any] | None:
    if not title:
        return None
    match = re.search(r"\b([A-Za-z]+)\s+(20\d{2})\b", title)
    if not match:
        return None
    month = _MONTHS.get(match.group(1).lower())
    if month is None:
        return None
    return {"year": int(match.group(2)), "month": month, "label": f"{match.group(1)} {match.group(2)}"}


def parse_idx_monthly_investor_html(
    html: str,
    *,
    source_url: str,
    period: Mapping[str, Any] | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Parse the official daily investor-type tables for one month.

    IDX labels the two relevant blocks ``Foreign Selling`` and ``Domestic
    Selling``.  The derived foreign net is:

    ``domestic investor sell -> foreign investor buy``
    minus
    ``foreign investor sell -> domestic investor buy``.

    Foreign-to-foreign and domestic-to-domestic trades are retained as source
    detail but do not enter the foreign net calculation.
    """
    _assert_idx_url(source_url)
    parser = _IDXHTMLParser()
    parser.feed(html)
    tables = tuple(_HTMLTable(tuple(tuple(row) for row in table)) for table in parser.tables)
    foreign_table = _select_table(tables, "Foreign Investor Sell - Domestic Investor Buy")
    domestic_table = _select_table(tables, "Domestic Investor Sell - Foreign Investor Buy")
    foreign_rows, foreign_total = _table_rows(foreign_table, section="Foreign Selling")
    domestic_rows, domestic_total = _table_rows(domestic_table, section="Domestic Selling")
    foreign_dates = set(foreign_rows)
    domestic_dates = set(domestic_rows)
    if foreign_dates != domestic_dates:
        only_foreign = sorted(foreign_dates - domestic_dates)
        only_domestic = sorted(domestic_dates - foreign_dates)
        raise IDXStatisticsError(
            "IDX investor tables have different trading dates: "
            f"foreign_only={only_foreign}, domestic_only={only_domestic}"
        )

    daily: list[dict[str, Any]] = []
    for as_of in sorted(foreign_dates):
        foreign = foreign_rows[as_of]
        domestic = domestic_rows[as_of]
        foreign_to_domestic = foreign["value_second"]
        domestic_to_foreign = domestic["value_first"]
        net_foreign = domestic_to_foreign - foreign_to_domestic
        daily.append(
            {
                "as_of": as_of,
                "foreign_to_foreign": {
                    "volume": foreign["volume_first"],
                    "value_idr": foreign["value_first"],
                    "frequency": foreign["frequency_first"],
                },
                "foreign_to_domestic": {
                    "volume": foreign["volume_second"],
                    "value_idr": foreign_to_domestic,
                    "frequency": foreign["frequency_second"],
                },
                "domestic_to_foreign": {
                    "volume": domestic["volume_first"],
                    "value_idr": domestic_to_foreign,
                    "frequency": domestic["frequency_first"],
                },
                "domestic_to_domestic": {
                    "volume": domestic["volume_second"],
                    "value_idr": domestic["value_second"],
                    "frequency": domestic["frequency_second"],
                },
                "net_foreign_value_idr": net_foreign,
                "direction": _direction(net_foreign),
            }
        )

    summed_foreign_to_domestic = sum(row["foreign_to_domestic"]["value_idr"] for row in daily)
    summed_domestic_to_foreign = sum(row["domestic_to_foreign"]["value_idr"] for row in daily)
    total_net = domestic_total["value_first"] - foreign_total["value_second"]
    daily_net = sum(row["net_foreign_value_idr"] for row in daily)
    reconciliation = {
        "foreign_to_domestic_matches_total": summed_foreign_to_domestic == foreign_total["value_second"],
        "domestic_to_foreign_matches_total": summed_domestic_to_foreign == domestic_total["value_first"],
        "net_matches_component_totals": daily_net == total_net,
    }
    quality_ready = all(reconciliation.values())
    inferred_period = _period_from_title(parser.headings[0] if parser.headings else None)
    resolved_period = dict(period or inferred_period or {})
    if "year" not in resolved_period or "month" not in resolved_period:
        raise IDXStatisticsError("IDX monthly release period was not provided or found in title")
    resolved_period.setdefault("label", f"{resolved_period['year']}-{int(resolved_period['month']):02d}")
    title = parser.headings[0] if parser.headings else "Table Daily Trading by Type of Investor"
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "IDX",
        "provider_mode": "IDX_OFFICIAL_RELEASE",
        "status": "READY" if quality_ready else "READY_WITH_GAPS",
        "quantitative_use": True,
        "scope": "MONTHLY_EQUITY_TRADING_BY_INVESTOR_TYPE",
        "release": {
            "title": title,
            "period": resolved_period,
            "trading_day_count": len(daily),
        },
        "as_of": {"min": daily[0]["as_of"], "max": daily[-1]["as_of"]},
        "daily": daily,
        "totals": {
            "foreign_to_foreign_value_idr": foreign_total["value_first"],
            "foreign_to_domestic_value_idr": foreign_total["value_second"],
            "domestic_to_foreign_value_idr": domestic_total["value_first"],
            "domestic_to_domestic_value_idr": domestic_total["value_second"],
            "net_foreign_value_idr": total_net,
            "direction": _direction(total_net),
        },
        "quality": {
            "source_table_count": len(tables),
            "daily_rows": len(daily),
            "reconciliation": reconciliation,
            "search_agent_role": "DISCOVERY_ONLY",
            "full_month_release": True,
        },
        "source": {
            "publisher": "Indonesia Stock Exchange",
            "url": source_url,
            "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
            "parser": "idx_monthly_investor_html",
            "table_endpoints": [
                "/api/tabledailytradingbyinvestor/getforeign",
                "/api/tabledailytradingbyinvestor/getdomestic",
            ],
        },
        "limitations": [
            "Net foreign is derived from the two cross-investor value columns published by IDX.",
            "Foreign-to-foreign and domestic-to-domestic trades are retained for audit detail and excluded from net foreign.",
            "This release is market-level investor flow; it does not provide per-ticker ownership flow.",
            "The parser does not use search summaries or infer missing trading days.",
        ],
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a parsed release without exposing a partial JSON file."""
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()
