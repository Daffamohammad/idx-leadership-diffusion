"""Offline tests for the qualitative Tavily context presentation boundary."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_context_helpers_keep_web_sources_separate_from_confirmation_metrics():
    script = r'''import {
      getTavilyCategory,
      getTavilyCategoryStatus,
      getTavilyCrawl,
    } from "./app/web/src/data/researchContext.ts";

    const payload = {
      tavily_context: {
        status: "REQUESTED",
        quantitative_use: false,
        categories: {
          foreign_flow: {
            status: "READY_WITH_GAPS",
            records: [{
              url: "https://www.idx.co.id/en/news/flow",
              title: "Foreign investor context",
              content: "Official source summary",
            }],
          },
          fundamentals: { status: "DATA_GAP", records: [] },
        },
        crawl: { status: "READY_WITH_GAPS", records: [] },
      },
    };
    const flow = getTavilyCategory(payload, "foreign_flow");
    console.log(JSON.stringify({
      flowStatus: getTavilyCategoryStatus(payload, "foreign_flow"),
      fundamentalsStatus: getTavilyCategoryStatus(payload, "fundamentals"),
      flowCount: flow.records.length,
      flowQuantitative: flow.records[0].quantitative_use,
      crawlCount: getTavilyCrawl(payload).records.length,
    }));'''
    result = subprocess.run(
        ["bun", "x", "tsx", "-e", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {
        "flowStatus": "READY_WITH_GAPS",
        "fundamentalsStatus": "DATA_GAP",
        "flowCount": 1,
        "flowQuantitative": False,
        "crawlCount": 0,
    }
