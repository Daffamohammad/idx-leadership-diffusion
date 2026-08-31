"""Parse an official IDX Daily Statistics PDF with LlamaParse.

This command is opt-in and bounded. It never runs from the browser, requires
both a third-party upload acknowledgement and a credit-spend acknowledgement,
and writes the normalized artifact only after the target market cards pass
deterministic checks.

Examples::

    .venv/bin/python -m scripts.refresh_idx_daily_statistics \
        --pdf-file /path/to/ds_260828.pdf \
        --target-pages 1-2 \
        --allow-cloud-upload \
        --allow-credit-spend

    .venv/bin/python -m scripts.refresh_idx_daily_statistics \
        --source-url https://www.idx.co.id/Media/example/ds_260828.pdf \
        --target-pages 1 \
        --allow-cloud-upload \
        --allow-credit-spend \
        --public-output app/web/public/idx/idx_daily_statistics_latest.json

The command expects ``LLAMA_CLOUD_API_KEY`` in the local environment or the
ignored project ``.env`` file. Never paste that key into chat or commit it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from idx_leadership.providers.idx_statistics import write_json_atomic
from idx_leadership.providers.idx_discovery import (
    IDXDiscoveryError,
    discover_and_retrieve_idx_daily_statistics,
)
from idx_leadership.providers.llama_parse import (
    DEFAULT_LLAMA_CREDIT_BUDGET,
    DEFAULT_LLAMA_TIER,
    DEFAULT_LLAMA_VERSION,
    LlamaParseError,
    estimate_credit_cost,
    recover_llama_parse_job,
    run_llama_parse,
    write_text_atomic,
)
from idx_leadership.utils import data_root, load_project_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="refresh_idx_daily_statistics")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--pdf-file",
        type=Path,
        help="Local official IDX Daily Statistics PDF to upload for parsing.",
    )
    source.add_argument(
        "--source-url",
        help="HTTPS URL of an official IDX Daily Statistics PDF.",
    )
    source.add_argument(
        "--discover-latest",
        action="store_true",
        help="Use the bounded search-agent -> crawl/retrieve -> LlamaParse pipeline.",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Target publication date for discovery (YYYY-MM-DD); omitted means latest dated result.",
    )
    parser.add_argument(
        "--search-provider",
        choices=("auto", "tavily", "you"),
        default="auto",
        help="Search agent for discovery; auto prefers Tavily when its local key is available.",
    )
    parser.add_argument(
        "--allow-search-live",
        action="store_true",
        help="Acknowledge live search-agent/crawl requests.",
    )
    parser.add_argument(
        "--allow-search-credit-spend",
        action="store_true",
        help="Acknowledge search-agent credit usage.",
    )
    parser.add_argument(
        "--search-max-results",
        type=int,
        default=10,
        help="Maximum search-agent result rows (default: 10).",
    )
    parser.add_argument(
        "--crawl-limit",
        type=int,
        default=5,
        help="Maximum bounded crawl/retrieve result rows (default: 5).",
    )
    parser.add_argument(
        "--retrieved-pdf-output",
        type=Path,
        default=None,
        help="Optional local PDF path; defaults to ignored data/raw/idx_daily_statistics/.",
    )
    parser.add_argument(
        "--retrieved-pdf-file",
        type=Path,
        default=None,
        help="Existing browser-retrieved PDF to verify and upload when IDX serves a dynamic asset.",
    )
    parser.add_argument(
        "--resolved-pdf-url",
        default=None,
        help="Browser-resolved official PDF URL used only when discovery APIs expose no dynamic asset link.",
    )
    parser.add_argument(
        "--discovery-output",
        type=Path,
        default=None,
        help="Optional provenance JSON for search/crawl/retrieve stages.",
    )
    parser.add_argument(
        "--target-pages",
        default="1-2",
        help="Bounded 1-based page list/ranges (default: 1-2; use 1-9 for the current full release).",
    )
    parser.add_argument(
        "--tier",
        choices=("fast", "cost_effective", "agentic", "agentic_plus"),
        default=DEFAULT_LLAMA_TIER,
        help="LlamaParse v2 tier (default: agentic).",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_LLAMA_VERSION,
        help="LlamaParse version; pin a dated version after benchmarking (default: latest).",
    )
    parser.add_argument(
        "--max-estimated-credits",
        type=float,
        default=DEFAULT_LLAMA_CREDIT_BUDGET,
        help="Client-side credit ceiling; provider billing remains authoritative (default: 20000).",
    )
    parser.add_argument(
        "--allow-cloud-upload",
        action="store_true",
        help="Acknowledge that the selected public PDF is sent to LlamaCloud.",
    )
    parser.add_argument(
        "--allow-credit-spend",
        action="store_true",
        help="Acknowledge that the request can consume LlamaCloud credits.",
    )
    parser.add_argument(
        "--retrieved-at",
        default=None,
        help="Optional fixed retrieval timestamp for reproducible artifacts.",
    )
    parser.add_argument(
        "--reuse-job-id",
        default=None,
        help="Read and normalize an existing COMPLETED LlamaParse job; never creates a new job.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Normalized JSON path; defaults to data/derived/idx_daily_statistics_<date>.json.",
    )
    parser.add_argument(
        "--public-output",
        type=Path,
        default=None,
        help="Optional public web JSON path, written only after validation passes.",
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=None,
        help="Optional ignored JSON sidecar containing the raw LlamaParse response.",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help="Optional ignored text sidecar containing the parsed markdown.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_project_env()
    discovery = None
    try:
        pdf_file = args.pdf_file
        source_url = args.source_url
        if args.discover_latest:
            default_pdf_name = f"idx_daily_statistics_{args.as_of or 'latest'}.pdf"
            retrieved_pdf_output = args.retrieved_pdf_output or (
                data_root() / "raw" / "idx_daily_statistics" / default_pdf_name
            )
            discovery = discover_and_retrieve_idx_daily_statistics(
                target_as_of=args.as_of,
                search_provider=args.search_provider,
                destination=retrieved_pdf_output,
                allow_live=args.allow_search_live,
                allow_credit_spend=args.allow_search_credit_spend,
                max_search_results=args.search_max_results,
                max_crawl_results=args.crawl_limit,
                resolved_pdf_url=args.resolved_pdf_url,
                local_pdf_path=args.retrieved_pdf_file,
            )
            pdf_file = discovery.local_pdf.path
            source_url = discovery.pdf_url
        if args.reuse_job_id is not None:
            if args.pdf_file is not None or source_url is None:
                raise LlamaParseError(
                    "--reuse-job-id requires --source-url, or --discover-latest for provenance"
                )
            payload, raw_result, markdown = recover_llama_parse_job(
                args.reuse_job_id,
                source_url=source_url,
                source_file_name=pdf_file.name if pdf_file is not None else None,
                retrieved_at=args.retrieved_at,
                parser_version=args.version,
                tier=args.tier,
                estimated_credit_cost=estimate_credit_cost(args.target_pages, tier=args.tier),
                source_provenance=discovery.provenance if discovery is not None else None,
            )
        else:
            payload, raw_result, markdown = run_llama_parse(
                pdf_path=pdf_file,
                source_url=source_url,
                target_pages=args.target_pages,
                tier=args.tier,
                version=args.version,
                max_estimated_credits=args.max_estimated_credits,
                allow_cloud_upload=args.allow_cloud_upload,
                allow_credit_spend=args.allow_credit_spend,
                retrieved_at=args.retrieved_at,
                source_provenance=discovery.provenance if discovery is not None else None,
            )
        if discovery is not None and payload["as_of"] != discovery.as_of:
            raise LlamaParseError(
                "LlamaParse release date does not match the discovered IDX publication: "
                f"discovered={discovery.as_of} parsed={payload['as_of']}"
            )
        output = args.output or (
            data_root() / "derived" / f"idx_daily_statistics_{payload['as_of']}.json"
        )
        write_json_atomic(output, payload)
        if args.public_output is not None:
            write_json_atomic(args.public_output, payload)
        if args.raw_output is not None:
            write_json_atomic(args.raw_output, raw_result)
        if args.markdown_output is not None:
            write_text_atomic(args.markdown_output, markdown)
        if args.discovery_output is not None and discovery is not None:
            write_json_atomic(args.discovery_output, discovery.provenance)
    except (IDXDiscoveryError, LlamaParseError, OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": payload["status"],
                "as_of": payload["as_of"],
                "source": payload["source"].get("url") or payload["source"].get("file_name"),
                "estimated_credit_cost": payload["llama"]["estimated_credit_cost"],
                "actual_credit_cost": payload["llama"]["actual_credit_cost"],
                "actual_credit_cost_known": payload["llama"]["actual_credit_cost_known"],
                "output": str(output),
                "discovery": discovery.provenance if discovery is not None else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
