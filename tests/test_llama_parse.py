"""Offline contract tests for the optional LlamaParse PDF lane."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from idx_leadership.providers.llama_parse import (
    LlamaParseError,
    build_parse_request,
    estimate_credit_cost,
    normalize_daily_statistics_markdown,
    parse_target_pages,
    recover_llama_parse_job,
    run_llama_parse,
)
from scripts.refresh_idx_daily_statistics import main


DAILY_MARKDOWN = """# IDX DAILY STATISTICS
Friday, 28 August 2026

## IDX Composite Index (IHSG)
# **6,518.121** ▼ **-3,629 (-0.06%)**

<table>
  <tr><th>Previous</th><th>Highest</th><th>Lowest</th></tr>
  <tr><td>6,521.750</td><td>6,566.905</td><td>6,495.737</td></tr>
</table>

## NET FOREIGN
<table>
  <tr><th></th><th>(billion IDR)</th><th>(billion IDR)</th></tr>
  <tr><td><b>Today</b></td><td><b>-482.24</b></td><td><b>-70,360.99</b></td></tr>
  <tr><td><b>Net Sell</b></td><td><b>-27.24</b> (million USD~)</td><td><b>-3,974.52</b> (million USD)</td></tr>
</table>

## FUNDAMENTAL
<table>
  <tr><th>Market PER (x)</th><th>Market PBV (x)</th></tr>
  <tr><td><b>13.07</b></td><td><b>1.73</b></td></tr>
</table>
"""


CURRENT_AGENT_MARKDOWN = """# IDX DAILY STATISTICS
Friday, 28 August 2026

IDX Composite Index (IHSG)

# 6,518.121

-3.629 (-0.06%)

<table>
  <tr><th>Previous</th><th>Highest</th><th>Lowest</th></tr>
  <tr><td>6,521.750</td><td>6,566.905</td><td>6,495.737</td></tr>
</table>

## AVERAGE DAILY TRADING (YTD)

## NET FOREIGN
<table>
  <tr><th>Today</th><th>YTD</th></tr>
  <tr><td>-482.24</td><td>-70,360.99</td></tr>
  <tr><td>(billion IDR)</td><td>(billion IDR)</td></tr>
  <tr><td>Net Sell</td><td>Net Sell</td></tr>
  <tr><td>-27.24</td><td>-3,974.52</td></tr>
  <tr><td>(million USD~)</td><td>(million USD)</td></tr>
</table>

## FUNDAMENTAL
<table>
  <tr><th>Market PER (x)</th><th>Market PBV (x)</th></tr>
  <tr><td>13.07</td><td>1.73</td></tr>
</table>
"""


def test_target_pages_are_bounded_and_credit_estimate_is_explicit():
    assert parse_target_pages("1, 3-4, 4") == (1, 3, 4)
    assert estimate_credit_cost("1-8", tier="agentic") == 104.0
    request = build_parse_request("1", tier="agentic", version="2026-08-01")
    assert request["page_ranges"] == {"target_pages": "1"}
    assert request["output_options"]["granular_bboxes"] == ["line", "cell"]
    assert "Today" in request["agentic_options"]["custom_prompt"]


def test_markdown_reducer_repairs_provable_decimal_separator_and_maps_cards():
    payload = normalize_daily_statistics_markdown(
        DAILY_MARKDOWN,
        source_url="https://www.idx.co.id/Media/example/ds_260828.pdf",
        retrieved_at="2026-08-31T00:00:00+00:00",
        estimated_credit_cost=13.0,
        actual_credit_cost=13.0,
        job_id="job-1",
    )

    assert payload["status"] == "READY_WITH_GAPS"
    assert payload["as_of"] == "2026-08-28"
    assert payload["metrics"]["ihsg"]["change"] == -3.629
    assert payload["metrics"]["ihsg"]["change_pct"] == -0.06
    assert payload["metrics"]["net_foreign"]["today"]["idr_billion"] == -482.24
    assert payload["metrics"]["net_foreign"]["today"]["usd_million"] == -27.24
    assert payload["metrics"]["net_foreign"]["ytd"]["idr_billion"] == -70360.99
    assert payload["metrics"]["net_foreign"]["ytd"]["usd_million"] == -3974.52
    assert payload["metrics"]["fundamental"] == {"market_per": 13.07, "market_pbv": 1.73}
    assert payload["quality"]["checks"]["ihsg_change_reconciles"] is True
    assert payload["quality"]["checks"]["net_foreign_column_labels_preserved"] is False
    assert payload["quality"]["warnings"]
    assert payload["llama"]["actual_credit_cost"] == 13.0
    json.dumps(payload, allow_nan=False)


def test_markdown_reducer_rejects_unreconciled_ihsg_change():
    with pytest.raises(LlamaParseError, match="IHSG change does not reconcile"):
        normalize_daily_statistics_markdown(
            DAILY_MARKDOWN.replace("-3,629", "-99,999"),
        )


def test_markdown_reducer_accepts_current_plain_agentic_layout():
    payload = normalize_daily_statistics_markdown(CURRENT_AGENT_MARKDOWN)
    assert payload["status"] == "READY"
    assert payload["metrics"]["ihsg"]["change"] == -3.629
    assert payload["quality"]["checks"]["net_foreign_column_labels_preserved"] is True


def test_run_uses_official_sdk_shape_and_keeps_raw_response_separate(tmp_path: Path):
    pdf_path = tmp_path / "ds_260828.pdf"
    pdf_path.write_bytes(b"%PDF-1.7 fixture")

    class FakeFiles:
        def create(self, **kwargs):
            assert kwargs == {"file": str(pdf_path), "purpose": "parse"}
            return {"id": "file-1"}

    class FakeParsing:
        # Match the current SDK's explicit parse signature closely enough to
        # catch create-only parameters accidentally leaking into parse().
        def parse(
            self,
            *,
            tier,
            version,
            client_name,
            agentic_options,
            output_options,
            page_ranges,
            file_id,
            expand,
        ):
            assert tier == "agentic"
            assert version == "latest"
            assert client_name == "idx-leadership-diffusion"
            assert file_id == "file-1"
            assert page_ranges == {"target_pages": "1"}
            assert "usage" in expand
            return {
                "id": "job-1",
                "usage": {"credits": 13},
                "markdown": {"pages": [{"page_number": 1, "markdown": DAILY_MARKDOWN}]},
            }

    class FakeClient:
        files = FakeFiles()
        parsing = FakeParsing()

    payload, raw, markdown = run_llama_parse(
        pdf_path=pdf_path,
        target_pages="1",
        max_estimated_credits=20_000,
        allow_cloud_upload=True,
        allow_credit_spend=True,
        client_factory=lambda: FakeClient(),
    )

    assert payload["llama"]["file_id"] == "file-1"
    assert payload["llama"]["job_id"] == "job-1"
    assert payload["llama"]["actual_credit_cost"] == 13.0
    assert raw["id"] == "job-1"
    assert "NET FOREIGN" in markdown


def test_run_requires_both_external_side_effect_acknowledgements(tmp_path: Path):
    pdf_path = tmp_path / "ds_260828.pdf"
    pdf_path.write_bytes(b"%PDF-1.7 fixture")
    with pytest.raises(LlamaParseError, match="cloud upload is blocked"):
        run_llama_parse(pdf_path=pdf_path, client_factory=lambda: None)
    with pytest.raises(LlamaParseError, match="credit spend is blocked"):
        run_llama_parse(pdf_path=pdf_path, allow_cloud_upload=True, client_factory=lambda: None)


def test_recover_completed_job_is_read_only_and_preserves_provenance():
    calls: list[tuple[str, list[str]]] = []

    class FakeParsing:
        def get(self, job_id, *, expand):
            calls.append((job_id, expand))
            return {
                "id": "job-1",
                "job": {"status": "COMPLETED"},
                "usage": {"credits": 13},
                "markdown": {"pages": [{"page_number": 1, "markdown": DAILY_MARKDOWN}]},
            }

    class FakeClient:
        parsing = FakeParsing()

    payload, raw, markdown = recover_llama_parse_job(
        "job-1",
        source_url="https://www.idx.co.id/Media/example/ds_260828.pdf",
        source_file_name="ds_260828.pdf",
        retrieved_at="2026-08-31T00:00:00+00:00",
        estimated_credit_cost=13.0,
        source_provenance={"stage": "search-crawl-retrieve"},
        client_factory=lambda: FakeClient(),
    )

    assert calls == [
        (
            "job-1",
            ["markdown", "text", "items", "metadata", "job_metadata", "usage"],
        )
    ]
    assert payload["status"] == "READY_WITH_GAPS"
    assert payload["llama"]["job_id"] == "job-1"
    assert payload["llama"]["actual_credit_cost"] == 13.0
    assert payload["source"]["discovery"] == {"stage": "search-crawl-retrieve"}
    assert raw["job"]["status"] == "COMPLETED"
    assert "NET FOREIGN" in markdown


def test_recover_refuses_non_completed_job_without_writing_or_reducing():
    class FakeParsing:
        def get(self, job_id, *, expand):
            return {"id": job_id, "job": {"status": "RUNNING"}}

    class FakeClient:
        parsing = FakeParsing()

    with pytest.raises(LlamaParseError, match="is not completed"):
        recover_llama_parse_job("job-running", client_factory=lambda: FakeClient())


def test_source_url_must_be_first_party_https_pdf():
    with pytest.raises(LlamaParseError, match="HTTPS IDX URL"):
        run_llama_parse(
            source_url="https://example.com/daily-statistics.pdf",
            allow_cloud_upload=True,
            allow_credit_spend=True,
        )
    with pytest.raises(LlamaParseError, match="IDX PDF"):
        run_llama_parse(
            source_url="https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/",
            allow_cloud_upload=True,
            allow_credit_spend=True,
        )


def test_cli_does_not_write_without_explicit_acknowledgement(tmp_path: Path):
    pdf_path = tmp_path / "ds_260828.pdf"
    output_path = tmp_path / "daily.json"
    pdf_path.write_bytes(b"%PDF-1.7 fixture")
    result = main(["--pdf-file", str(pdf_path), "--output", str(output_path)])
    assert result == 2
    assert not output_path.exists()


def test_cli_does_not_write_when_reconciliation_fails(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "ds_260828.pdf"
    output_path = tmp_path / "daily.json"
    pdf_path.write_bytes(b"%PDF-1.7 fixture")

    def fail_closed(**kwargs):
        raise LlamaParseError("IHSG change does not reconcile")

    monkeypatch.setattr("scripts.refresh_idx_daily_statistics.run_llama_parse", fail_closed)
    result = main(
        [
            "--pdf-file",
            str(pdf_path),
            "--output",
            str(output_path),
            "--allow-cloud-upload",
            "--allow-credit-spend",
        ]
    )
    assert result == 2
    assert not output_path.exists()
