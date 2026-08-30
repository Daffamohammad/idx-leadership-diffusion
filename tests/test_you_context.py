"""Offline tests for the qualitative You.com context presentation boundary."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_you_context_helpers_keep_web_sources_separate_from_confirmation_metrics():
    script = r'''import {
      getYouCategory,
      getYouCategoryStatus,
      normalizeYouContext,
    } from "./app/web/src/data/researchContext.ts";

    const payload = {
      you_context: {
        status: "REQUESTED",
        completion_status: "READY_WITH_GAPS",
        quantitative_use: false,
        scope: "qualitative_web_context_only",
        source_policy: ["idx.co.id", "ojk.go.id"],
        categories: {
          foreign_flow: {
            status: "READY_WITH_GAPS",
            query: "IDX foreign investor flow",
            source_count: 1,
            research_answer: "First-party disclosure [[1]]",
            records: [{
              url: "https://www.idx.co.id/en/news/flow",
              title: "Foreign investor context",
              content: "You.com summary",
            }],
          },
          fundamentals: { status: "DATA_GAP", records: [] },
        },
      },
    };
    const flow = getYouCategory(payload, "foreign_flow");
    const ctx = normalizeYouContext(payload.you_context);
    console.log(JSON.stringify({
      flowStatus: getYouCategoryStatus(payload, "foreign_flow"),
      fundamentalsStatus: getYouCategoryStatus(payload, "fundamentals"),
      flowCount: flow.records.length,
      flowQuantitative: flow.records[0].quantitative_use,
      flowProvider: flow.records[0].provider,
      researchAnswer: ctx?.categories.foreign_flow?.research_answer,
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
        "flowProvider": "you",
        "researchAnswer": "First-party disclosure [[1]]",
    }


def test_you_context_normalizer_rejects_quantitative_payload():
    script = r'''import { normalizeYouContext } from "./app/web/src/data/researchContext.ts";
    const ctx = normalizeYouContext({ quantitative_use: true, categories: {} });
    console.log(JSON.stringify({ rejected: ctx === null }));'''
    result = subprocess.run(
        ["bun", "x", "tsx", "-e", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {"rejected": True}
