"""Credential-gated LlamaParse ingestion for official IDX Daily Statistics PDFs.

The LlamaCloud call is deliberately kept outside the browser/runtime path. A
successful job is reduced to a small, typed market-statistics artifact only
after deterministic checks pass. The optional SDK is imported lazily so the
offline project and its tests do not need a LlamaCloud installation.

This adapter is intentionally narrower than a general document parser. It
promotes only the first-page market cards needed by the product:

* IHSG close, previous close, change, and percentage change;
* Today/YTD net foreign IDR and USD values; and
* Market PER and Market PBV.

The full LlamaParse response can be saved separately as an audit artifact,
but it is never copied wholesale into the application payload.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse


LLAMA_DAILY_STATISTICS_SCHEMA_VERSION = "idx-daily-statistics-v1"
LLAMA_PROVIDER_MODE = "IDX_OFFICIAL_DAILY_STATISTICS"
DEFAULT_LLAMA_TIER = "agentic"
DEFAULT_LLAMA_VERSION = "latest"
DEFAULT_LLAMA_CREDIT_BUDGET = 20_000.0

_FIRST_PARTY_HOSTS = {"idx.co.id", "www.idx.co.id"}
_TIER_CREDITS_PER_PAGE = {
    "fast": 1.0,
    "cost_effective": 3.0,
    "agentic": 10.0,
    "agentic_plus": 45.0,
}
_LAYOUT_CREDITS_PER_PAGE = 3.0
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

_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+−]?\d[\d,]*(?:\.\d+)?%?")
_IHSG_LINE_RE = re.compile(
    r"\*\*(?P<close>[-+−]?\d[\d,]*(?:\.\d+)?)\*\*"
    r"\s*(?:[▲▼]|↑|↓)?\s*"
    r"\*\*(?P<change>[-+−]?\d[\d,]*(?:\.\d+)?)\s*"
    r"\((?P<pct>[-+−]?\d[\d,]*(?:\.\d+)?)%\)\*\*",
    re.IGNORECASE,
)


class LlamaParseError(ValueError):
    """Raised when a LlamaParse request or IDX reduction cannot be trusted."""


def _jsonable(value: Any) -> Any:
    """Convert SDK/Pydantic response objects without logging credentials."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _jsonable(model_dump(mode="json"))
        except TypeError:
            return _jsonable(model_dump())
    as_dict = getattr(value, "dict", None)
    if callable(as_dict):
        return _jsonable(as_dict())
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _walk_mappings(value: Any) -> Sequence[Mapping[str, Any]]:
    """Yield mapping nodes from a JSONable response for usage/job lookup."""
    nodes: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        nodes.append(value)
        for item in value.values():
            nodes.extend(_walk_mappings(item))
    elif isinstance(value, list):
        for item in value:
            nodes.extend(_walk_mappings(item))
    return nodes


def _extract_credit_usage(raw_result: Mapping[str, Any]) -> float | None:
    """Find an observed usage value without guessing from response metadata."""
    keys = {
        "credits",
        "credits_used",
        "credits_billed",
        "total_credits",
        "credit_cost",
    }
    for node in _walk_mappings(raw_result):
        for key in keys:
            if key in node:
                value = _number(node[key])
                if value is not None:
                    return value
    return None


def _extract_identifier(raw_result: Mapping[str, Any], key: str) -> str | None:
    for node in _walk_mappings(raw_result):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _parse_decimal_token(token: str) -> Decimal:
    """Parse English IDX number formatting, retaining decimal precision."""
    text = token.strip().replace("−", "-").replace("%", "")
    if not text:
        raise LlamaParseError("empty numeric token")
    if "," in text and "." in text:
        normalized = text.replace(",", "")
    elif text.count(",") == 1:
        head, tail = text.split(",")
        # IDX uses commas as thousands separators in the English release. A
        # one- or two-digit suffix is the only form treated as a decimal comma.
        normalized = f"{head}.{tail}" if len(tail) <= 2 else text.replace(",", "")
    else:
        normalized = text.replace(",", "")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise LlamaParseError(f"invalid numeric token: {token!r}") from exc


def _decimal_json(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _flow_direction(value: Decimal) -> str:
    if value > 0:
        return "NET_BUY"
    if value < 0:
        return "NET_SELL"
    return "FLAT"


def parse_target_pages(value: str) -> tuple[int, ...]:
    """Parse LlamaParse's 1-based page-range syntax into unique page numbers."""
    pages: set[int] = set()
    text = (value or "").strip()
    if not text:
        raise LlamaParseError("target pages must be explicit; refusing an unbounded parse")
    for part in text.split(","):
        item = part.strip()
        if not item:
            raise LlamaParseError(f"invalid empty page range in {value!r}")
        if re.fullmatch(r"\d+", item):
            start = end = int(item)
        else:
            match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", item)
            if not match:
                raise LlamaParseError(f"invalid target page range: {item!r}")
            start, end = (int(group) for group in match.groups())
        if start < 1 or end < start:
            raise LlamaParseError(f"invalid target page range: {item!r}")
        if end - start > 500:
            raise LlamaParseError("target page range is too large; split the ingest into bounded jobs")
        pages.update(range(start, end + 1))
    return tuple(sorted(pages))


def estimate_credit_cost(
    target_pages: str,
    *,
    tier: str = DEFAULT_LLAMA_TIER,
    layout_output: bool = True,
) -> float:
    """Return a conservative client-side estimate; provider usage is authoritative."""
    if tier not in _TIER_CREDITS_PER_PAGE:
        raise LlamaParseError(f"unsupported LlamaParse tier: {tier!r}")
    page_count = len(parse_target_pages(target_pages))
    per_page = _TIER_CREDITS_PER_PAGE[tier]
    if layout_output:
        per_page += _LAYOUT_CREDITS_PER_PAGE
    return page_count * per_page


def build_parse_request(
    target_pages: str,
    *,
    tier: str = DEFAULT_LLAMA_TIER,
    version: str = DEFAULT_LLAMA_VERSION,
) -> dict[str, Any]:
    """Build a bounded Parse v2 request for the official release layout."""
    parse_target_pages(target_pages)
    if tier not in _TIER_CREDITS_PER_PAGE:
        raise LlamaParseError(f"unsupported LlamaParse tier: {tier!r}")
    if not version.strip():
        raise LlamaParseError("LlamaParse version cannot be empty")
    return {
        "tier": tier,
        "version": version,
        "page_ranges": {"target_pages": target_pages},
        "output_options": {
            "markdown": {
                "tables": {
                    "merge_continued_tables": True,
                    "output_tables_as_markdown": False,
                }
            },
            "spatial_text": {
                "preserve_layout_alignment_across_pages": True,
                "preserve_very_small_text": True,
                "do_not_unroll_columns": True,
            },
            "granular_bboxes": ["line", "cell"],
            "extract_printed_page_number": True,
        },
        "agentic_options": {
            "custom_prompt": (
                "This is an official IDX Daily Statistics PDF. Preserve every "
                "table header, column relationship, sign, decimal point, unit, "
                "and period exactly. In the NET FOREIGN card, preserve Today "
                "and YTD as explicit columns and keep the IDR and USD rows "
                "separate. Do not infer or recalculate values."
            )
        },
        "user_metadata": {
            "project": "idx-leadership-diffusion",
            "document": "idx-daily-statistics",
        },
    }


def _assert_official_pdf_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname not in _FIRST_PARTY_HOSTS:
        raise LlamaParseError(
            "LlamaParse source URL must be an HTTPS IDX URL; arbitrary remote sources are refused"
        )
    if not parsed.path.lower().endswith(".pdf"):
        raise LlamaParseError("LlamaParse source URL must point to an IDX PDF")


def _validate_inputs(
    *,
    pdf_path: Path | None,
    source_url: str | None,
    target_pages: str,
    tier: str,
    max_estimated_credits: float,
) -> tuple[Path | None, str | None, float]:
    if (pdf_path is None) == (source_url is None):
        raise LlamaParseError("provide exactly one of pdf_path or source_url")
    if pdf_path is not None:
        resolved = Path(pdf_path).expanduser()
        if not resolved.is_file():
            raise LlamaParseError(f"IDX Daily Statistics PDF not found: {resolved}")
        if resolved.suffix.lower() != ".pdf":
            raise LlamaParseError("pdf_path must have a .pdf extension")
        pdf_path = resolved
    if source_url is not None:
        _assert_official_pdf_url(source_url)
    if not isinstance(max_estimated_credits, (int, float)) or max_estimated_credits <= 0:
        raise LlamaParseError("max_estimated_credits must be positive")
    estimate = estimate_credit_cost(target_pages, tier=tier)
    if estimate > float(max_estimated_credits):
        raise LlamaParseError(
            f"client-side estimate {estimate:g} credits exceeds ceiling "
            f"{float(max_estimated_credits):g}; no LlamaParse request was made"
        )
    return pdf_path, source_url, estimate


def _page_markdown(raw_result: Mapping[str, Any]) -> list[tuple[int, str]]:
    markdown = raw_result.get("markdown")
    if isinstance(markdown, str):
        return [(1, markdown)]
    if isinstance(markdown, Mapping):
        pages = markdown.get("pages")
        if isinstance(pages, list):
            output: list[tuple[int, str]] = []
            for index, page in enumerate(pages, start=1):
                if not isinstance(page, Mapping):
                    continue
                content = page.get("markdown") or page.get("content")
                if not isinstance(content, str) or not content.strip():
                    continue
                page_number = page.get("page_number") or page.get("page") or index
                output.append((int(page_number), content))
            if output:
                return output
    pages = raw_result.get("pages")
    if isinstance(pages, list):
        output = []
        for index, page in enumerate(pages, start=1):
            if isinstance(page, Mapping) and isinstance(page.get("markdown"), str):
                output.append((int(page.get("page_number") or index), page["markdown"]))
        if output:
            return output
    raise LlamaParseError("LlamaParse response did not include markdown pages")


def _find_release_date(markdown: str) -> str:
    match = re.search(r"\b([0-3]?\d)\s+([A-Za-z]+)\s+(20\d{2})\b", markdown)
    if not match:
        raise LlamaParseError("IDX release date was not found in LlamaParse output")
    day, month_text, year = match.groups()
    month = _MONTHS.get(month_text.lower())
    if month is None:
        raise LlamaParseError(f"unsupported IDX release month: {month_text!r}")
    try:
        parsed = datetime(int(year), month, int(day)).date()
    except ValueError as exc:
        raise LlamaParseError(f"invalid IDX release date: {day} {month_text} {year}") from exc
    return parsed.isoformat()


def _section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ims)^##\s+{re.escape(heading)}\s*$.*?(?=^##\s+|\Z)"
    )
    match = pattern.search(markdown)
    if not match:
        raise LlamaParseError(f"required IDX section was not found: {heading}")
    return match.group(0)


def _extract_previous_close(ihsg_section: str) -> Decimal:
    match = re.search(
        r"<th>\s*Previous\s*</th>.*?"
        r"<tr>\s*<td>\s*(?P<value>[-+−]?\d[\d,]*(?:\.\d+)?)\s*</td>",
        ihsg_section,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise LlamaParseError("IHSG previous close was not found")
    return _parse_decimal_token(match.group("value"))


def _extract_ihsg(markdown: str) -> tuple[dict[str, Any], list[str], dict[str, bool]]:
    section = _section(markdown, "IDX Composite Index (IHSG)")
    match = _IHSG_LINE_RE.search(section)
    if not match:
        raise LlamaParseError("IHSG close/change line was not found")
    close_token = match.group("close")
    change_token = match.group("change")
    pct_token = match.group("pct")
    close = _parse_decimal_token(close_token)
    parsed_change = _parse_decimal_token(change_token)
    change_pct = _parse_decimal_token(pct_token)
    previous = _extract_previous_close(section)
    expected_change = close - previous
    warnings: list[str] = []
    change = parsed_change
    change_reconciles = abs(change - expected_change) <= Decimal("0.005")
    if not change_reconciles:
        # LlamaParse has been observed to turn a decimal point into a comma in
        # a one-decimal-place-change token (for example -3.629 -> -3,629).
        # Repair only when the source token and the independently parsed close
        # values prove the alternative unambiguously; retain the raw token.
        if change_token.count(",") == 1 and "." not in change_token:
            head, tail = change_token.replace("−", "-").split(",")
            if len(tail) == 3:
                candidate = Decimal(f"{head}.{tail}")
                if abs(candidate - expected_change) <= Decimal("0.005"):
                    change = candidate
                    change_reconciles = True
                    warnings.append(
                        f"IHSG change normalized from {change_token!r} to "
                        f"{_decimal_json(candidate)!r} by close/previous reconciliation"
                    )
    pct_expected = (change / previous * Decimal("100")) if previous else Decimal("0")
    pct_reconciles = abs(pct_expected - change_pct) <= Decimal("0.02")
    if not change_reconciles:
        raise LlamaParseError(
            "IHSG change does not reconcile with close and previous close; "
            "refusing to write a Daily Statistics artifact"
        )
    if not pct_reconciles:
        raise LlamaParseError(
            "IHSG percentage change does not reconcile with the parsed close values; "
            "refusing to write a Daily Statistics artifact"
        )
    return (
        {
            "close": _decimal_json(close),
            "previous": _decimal_json(previous),
            "change": _decimal_json(change),
            "change_pct": _decimal_json(change_pct),
            "raw_change": change_token,
        },
        warnings,
        {
            "ihsg_change_reconciles": change_reconciles,
            "ihsg_percentage_reconciles": pct_reconciles,
        },
    )


def _extract_net_foreign(markdown: str) -> tuple[dict[str, Any], dict[str, bool], list[str]]:
    section = _section(markdown, "NET FOREIGN")
    lower = section.lower()
    if "today" not in lower or "net sell" not in lower:
        raise LlamaParseError("NET FOREIGN Today/Net Sell labels are incomplete")
    if "billion idr" not in lower or "million usd" not in lower:
        raise LlamaParseError("NET FOREIGN units are incomplete")
    tokens = _NUMBER_RE.findall(section)
    if len(tokens) != 4:
        raise LlamaParseError(
            "NET FOREIGN expected four numeric values (Today/YTD IDR and USD), "
            f"found {len(tokens)}"
        )
    values = [_parse_decimal_token(token) for token in tokens]
    # The IDX card is visually two columns and two metric rows. LlamaParse's
    # markdown result is row-major: Today/YTD IDR first, then Today/YTD USD.
    # A new run is prompted to retain the column labels; the explicit warning
    # keeps this known source-layout inference visible in the artifact.
    labels_preserved = bool(re.search(r"\bytd\b", lower))
    warnings: list[str] = []
    if not labels_preserved:
        warnings.append(
            "LlamaParse omitted the explicit YTD column label; values were mapped "
            "using the fixed IDX NET FOREIGN row/column layout"
        )
    today_idr, ytd_idr, today_usd, ytd_usd = values
    return (
        {
            "today": {
                "idr_billion": _decimal_json(today_idr),
                "usd_million": _decimal_json(today_usd),
                "usd_approximate": True,
                "direction": _flow_direction(today_idr),
            },
            "ytd": {
                "idr_billion": _decimal_json(ytd_idr),
                "usd_million": _decimal_json(ytd_usd),
                "usd_approximate": False,
                "direction": _flow_direction(ytd_idr),
            },
        },
        {
            "net_foreign_four_values_found": True,
            "net_foreign_units_found": True,
            "net_foreign_column_labels_preserved": labels_preserved,
        },
        warnings,
    )


def _extract_fundamental(markdown: str) -> tuple[dict[str, Any], dict[str, bool]]:
    section = _section(markdown, "FUNDAMENTAL")
    if not re.search(r"Market\s+PER\s*\(x\)", section, re.I):
        raise LlamaParseError("Market PER label was not found")
    if not re.search(r"Market\s+PBV\s*\(x\)", section, re.I):
        raise LlamaParseError("Market PBV label was not found")
    tokens = _NUMBER_RE.findall(section)
    if len(tokens) != 2:
        raise LlamaParseError(
            "Market PER/PBV expected two numeric values, "
            f"found {len(tokens)}"
        )
    return (
        {
            "market_per": _decimal_json(_parse_decimal_token(tokens[0])),
            "market_pbv": _decimal_json(_parse_decimal_token(tokens[1])),
        },
        {"fundamental_values_found": True},
    )


def normalize_daily_statistics_markdown(
    markdown: str,
    *,
    source_url: str | None = None,
    source_file_name: str | None = None,
    retrieved_at: str | None = None,
    parser_version: str = DEFAULT_LLAMA_VERSION,
    tier: str = DEFAULT_LLAMA_TIER,
    estimated_credit_cost: float | None = None,
    actual_credit_cost: float | None = None,
    job_id: str | None = None,
    file_id: str | None = None,
) -> dict[str, Any]:
    """Reduce LlamaParse markdown to a validated Daily Statistics payload."""
    if not isinstance(markdown, str) or not markdown.strip():
        raise LlamaParseError("LlamaParse markdown is empty")
    as_of = _find_release_date(markdown)
    ihsg, ihsg_warnings, ihsg_checks = _extract_ihsg(markdown)
    net_foreign, flow_checks, flow_warnings = _extract_net_foreign(markdown)
    fundamental, fundamental_checks = _extract_fundamental(markdown)
    warnings = [*ihsg_warnings, *flow_warnings]
    checks = {**ihsg_checks, **flow_checks, **fundamental_checks}
    # A missing YTD label is retained as an explicit review warning. The
    # source layout is fixed and the numeric order is checked, so the result is
    # usable for this release, but the caveat must remain machine-visible and
    # must lower the artifact status to READY_WITH_GAPS.
    if not checks["net_foreign_column_labels_preserved"]:
        warnings.append("Review the NET FOREIGN column mapping against the source PDF")
    source: dict[str, Any] = {
        "publisher": "Indonesia Stock Exchange",
        "url": source_url,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "parser": "llamaparse_v2_daily_statistics",
        "parser_version": parser_version,
        "tier": tier,
    }
    if source_file_name:
        source["file_name"] = Path(source_file_name).name
    payload: dict[str, Any] = {
        "schema_version": LLAMA_DAILY_STATISTICS_SCHEMA_VERSION,
        "provider": "IDX",
        "provider_mode": LLAMA_PROVIDER_MODE,
        "status": "READY_WITH_GAPS" if warnings else "READY",
        "quantitative_use": True,
        "scope": "DAILY_STATISTICS_TARGET_METRICS",
        "as_of": as_of,
        "metrics": {
            "ihsg": ihsg,
            "net_foreign": net_foreign,
            "fundamental": fundamental,
        },
        "quality": {
            "checks": checks,
            "warnings": warnings,
            "warning_count": len(warnings),
            "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        },
        "llama": {
            "job_id": job_id,
            "file_id": file_id,
            "tier": tier,
            "version": parser_version,
            "estimated_credit_cost": estimated_credit_cost,
            "actual_credit_cost": actual_credit_cost,
            "actual_credit_cost_known": actual_credit_cost is not None,
        },
        "source": source,
        "limitations": [
            "This artifact promotes only validated first-page market cards; other PDF tables remain in the raw parse audit output.",
            "Net foreign is market-level and does not establish per-ticker or per-group ownership flow.",
            "A missing YTD label in the markdown output is handled with the fixed IDX card layout and remains an explicit warning.",
            "LlamaParse credit usage is provider-reported when present; the client estimate is not a billing guarantee.",
        ],
    }
    return payload


def normalize_llama_result(
    raw_result: Mapping[str, Any],
    *,
    source_url: str | None = None,
    source_file_name: str | None = None,
    retrieved_at: str | None = None,
    parser_version: str = DEFAULT_LLAMA_VERSION,
    tier: str = DEFAULT_LLAMA_TIER,
    estimated_credit_cost: float | None = None,
) -> tuple[dict[str, Any], str]:
    """Normalize a JSONable LlamaParse result and return payload plus markdown."""
    pages = _page_markdown(raw_result)
    markdown = "\n\n".join(content for _, content in sorted(pages, key=lambda item: item[0]))
    payload = normalize_daily_statistics_markdown(
        markdown,
        source_url=source_url,
        source_file_name=source_file_name,
        retrieved_at=retrieved_at,
        parser_version=parser_version,
        tier=tier,
        estimated_credit_cost=estimated_credit_cost,
        actual_credit_cost=_extract_credit_usage(raw_result),
        job_id=_extract_identifier(raw_result, "id"),
        file_id=_extract_identifier(raw_result, "file_id"),
    )
    payload["quality"]["parsed_page_count"] = len(pages)
    payload["quality"]["parsed_page_numbers"] = [page for page, _ in pages]
    return payload, markdown


def _load_client() -> Any:
    if not os.environ.get("LLAMA_CLOUD_API_KEY", "").strip():
        raise LlamaParseError(
            "LLAMA_CLOUD_API_KEY is unavailable; save it in the local .env or export it"
        )
    try:
        from llama_cloud import LlamaCloud  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise LlamaParseError(
            "llama-cloud is not installed; install the optional dependency with "
            "pip install -e '.[llama]'"
        ) from exc
    return LlamaCloud()


def run_llama_parse(
    *,
    pdf_path: Path | None = None,
    source_url: str | None = None,
    target_pages: str = "1",
    tier: str = DEFAULT_LLAMA_TIER,
    version: str = DEFAULT_LLAMA_VERSION,
    max_estimated_credits: float = DEFAULT_LLAMA_CREDIT_BUDGET,
    allow_cloud_upload: bool = False,
    allow_credit_spend: bool = False,
    retrieved_at: str | None = None,
    client_factory: Callable[[], Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Run a bounded LlamaParse job and return normalized payload/raw/markdown.

    The two explicit acknowledgements are required even for a public IDX PDF:
    the file is sent to a third party and the request consumes account credits.
    """
    pdf_path, source_url, estimate = _validate_inputs(
        pdf_path=pdf_path,
        source_url=source_url,
        target_pages=target_pages,
        tier=tier,
        max_estimated_credits=max_estimated_credits,
    )
    if not allow_cloud_upload:
        raise LlamaParseError(
            "cloud upload is blocked; pass --allow-cloud-upload after reviewing the data boundary"
        )
    if not allow_credit_spend:
        raise LlamaParseError(
            "credit spend is blocked; pass --allow-credit-spend after reviewing the estimate"
        )
    request = build_parse_request(target_pages, tier=tier, version=version)
    try:
        client = client_factory() if client_factory is not None else _load_client()
        if pdf_path is not None:
            uploaded = client.files.create(file=str(pdf_path), purpose="parse")
            file_id = getattr(uploaded, "id", None)
            if file_id is None and isinstance(uploaded, Mapping):
                file_id = uploaded.get("id")
            if not isinstance(file_id, str) or not file_id:
                raise LlamaParseError("LlamaCloud file upload returned no file id")
            request["file_id"] = file_id
        else:
            request["source_url"] = source_url
        expand = ["markdown", "text", "items", "metadata", "job_metadata", "usage"]
        result = client.parsing.parse(**request, expand=expand)
    except LlamaParseError:
        raise
    except Exception as exc:  # SDK errors vary by installed version.
        raise LlamaParseError(f"LlamaParse request failed: {type(exc).__name__}") from exc
    raw_result = _jsonable(result)
    if not isinstance(raw_result, Mapping):
        raise LlamaParseError("LlamaParse returned an unexpected response shape")
    payload, markdown = normalize_llama_result(
        raw_result,
        source_url=source_url,
        source_file_name=pdf_path.name if pdf_path is not None else None,
        retrieved_at=retrieved_at,
        parser_version=version,
        tier=tier,
        estimated_credit_cost=estimate,
    )
    payload["llama"]["file_id"] = payload["llama"].get("file_id") or (
        request.get("file_id") if isinstance(request.get("file_id"), str) else None
    )
    return payload, dict(raw_result), markdown


def write_text_atomic(path: Path, content: str) -> None:
    """Write a text sidecar atomically, creating only the requested path."""
    import os as _os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            _os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


__all__ = [
    "DEFAULT_LLAMA_CREDIT_BUDGET",
    "DEFAULT_LLAMA_TIER",
    "DEFAULT_LLAMA_VERSION",
    "LLAMA_DAILY_STATISTICS_SCHEMA_VERSION",
    "LLAMA_PROVIDER_MODE",
    "LlamaParseError",
    "build_parse_request",
    "estimate_credit_cost",
    "normalize_daily_statistics_markdown",
    "normalize_llama_result",
    "parse_target_pages",
    "run_llama_parse",
    "write_text_atomic",
]
