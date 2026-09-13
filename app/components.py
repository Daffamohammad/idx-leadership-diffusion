"""UI helper components.

Kept thin so the main app file stays declarative.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


def render_quality(quality: dict[str, Any]) -> None:
    cols = st.columns(3)
    cols[0].metric("Status", quality.get("status", "—"))
    cols[1].metric("Coverage", f"{quality.get('coverage_pct', 0):.1f}%")
    cols[2].metric("Failed securities", quality.get("failed_securities", 0))
    issues = quality.get("issues", [])
    if issues:
        st.caption("Issues:")
        for i in issues:
            st.text(f"- {i}")


def render_change_digest(change: dict[str, Any]) -> None:
    for bucket in ("new_leaders", "lost_leadership", "upgrades", "downgrades", "broadening", "narrowing", "stable"):
        items = change.get(bucket, [])
        if not items:
            continue
        st.subheader(bucket.replace("_", " ").title())
        st.dataframe(pd.DataFrame(items), width='stretch', hide_index=True)
