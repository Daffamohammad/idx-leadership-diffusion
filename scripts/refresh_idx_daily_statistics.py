"""Parse an official IDX Daily Statistics PDF with LlamaParse.

This command is opt-in and bounded. It never runs from the browser, requires
both a third-party upload acknowledgement and a credit-spend acknowledgement,
and writes the normalized artifact only after the target market cards pass
deterministic checks.

Examples::

    .venv/bin/python -m scripts.refresh_idx_daily_statistics \
        --pdf-file /path/to/ds_260828.pdf \
        --target-pages 1 \
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
from idx_leadership.providers.llama_parse import (
    DEFAULT_LLAMA_CREDIT_BUDGET,
    DEFAULT_LLAMA_TIER,
    DEFAULT_LLAMA_VERSION,
    LlamaParseError,
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
    parser.add_argument(
        "--target-pages",
        default="1",
        help="Bounded 1-based page list/ranges (default: 1).",
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
    try:
        payload, raw_result, markdown = run_llama_parse(
            pdf_path=args.pdf_file,
            source_url=args.source_url,
            target_pages=args.target_pages,
            tier=args.tier,
            version=args.version,
            max_estimated_credits=args.max_estimated_credits,
            allow_cloud_upload=args.allow_cloud_upload,
            allow_credit_spend=args.allow_credit_spend,
            retrieved_at=args.retrieved_at,
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
    except (LlamaParseError, OSError, ValueError) as exc:
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
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
