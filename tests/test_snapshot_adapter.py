"""Tests for the persisted-row to UI-model boundary."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.snapshot_adapter import row_to_group_snapshot
from idx_leadership.models import DiffusionStateV2


def test_row_to_group_snapshot_normalizes_nullable_parquet_values():
    row = pd.Series(
        {
            "snapshot_date": date(2026, 8, 20),
            "group_id": "Consumer",
            "group_name": "Consumer",
            "constituent_count": 1,
            "eligible_count": 1,
            "missing_count": 0,
            "leadership_state": "UNCONFIRMED",
            "diffusion_state": "UNCONFIRMED",
            "diffusion_state_v2": DiffusionStateV2.UNCONFIRMED.value,
            "top1_contribution_share": np.nan,
            "top3_contribution_share": np.nan,
            "top5_contribution_share": np.nan,
            "hhi_contribution": np.nan,
            "contributor_count": 1,
            "method_version": "methodology-v2",
            "feature_version": "features-v2",
        }
    )

    snapshot = row_to_group_snapshot(row)

    assert snapshot.group_id == "Consumer"
    assert snapshot.diffusion_state_v2 == DiffusionStateV2.UNCONFIRMED
    assert snapshot.concentration.top1_contribution_share is None
    assert snapshot.concentration.top3_contribution_share is None
    assert snapshot.concentration.hhi_contribution is None
    assert snapshot.method_version == "methodology-v2"


def test_row_to_group_snapshot_normalizes_pandas_na():
    row = {
        "snapshot_date": date(2026, 8, 20),
        "group_id": "Industrial",
        "leadership_state": pd.NA,
        "diffusion_state": pd.NA,
        "top1_contribution_share": pd.NA,
    }
    snapshot = row_to_group_snapshot(row)
    assert snapshot.leadership_state.value == "UNCONFIRMED"
    assert snapshot.diffusion_state.value == "UNCONFIRMED"
    assert snapshot.concentration.top1_contribution_share is None
