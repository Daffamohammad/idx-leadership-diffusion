from __future__ import annotations

import json
from pathlib import Path

from scripts.build_market_snapshot import _live_credit_preflight


def test_live_preflight_uses_discovered_count_not_prefix_sample(tmp_path: Path):
    snapshot_root = tmp_path / "snapshots"
    live = snapshot_root / "snap_sectors_2026-08-27"
    live.mkdir(parents=True)
    (live / "manifest.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"as_of": "2026-08-27", "provider_mode": "SECTORS_LIVE"}
                ]
            }
        )
    )
    (live / "security_master.json").write_text(json.dumps([{"ticker": "A.JK"}] * 500))
    (live / "coverage.json").write_text(json.dumps({"discovered_count": 962}))
    (live / "security_master_diagnostics.json").write_text(
        json.dumps({"unique_rows": 962})
    )

    plan = _live_credit_preflight(
        snapshot_root=snapshot_root,
        config_path="config/providers.yaml",
        requested_as_of=None,
        max_pages=None,
        max_symbols=None,
        max_estimated_credits=1000.0,
    )

    assert plan["universe_size_for_plan"] == 962
    assert plan["history_symbols_after_cap"] == 962
    assert plan["universe_size_source"].endswith("discovered metadata")
