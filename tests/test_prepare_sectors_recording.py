import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.prepare_sectors_recording import SECTORS, freeze_plan


def _market():
    rows = []
    for sector_index, sector in enumerate(SECTORS):
        for index in range(8):
            rows.append({
                "ticker": f"{chr(65 + sector_index)}{chr(65 + index)}AA.JK",
                "instrument_type": "LISTED_STOCK",
                "signal_eligible": True,
                "traded": True,
                "last_trade_date": "2026-10-02",
                "close": 100 + index,
                "market_cap": 1000 - index,
                "taxonomy": {"sector": sector},
                "classification_as_of": "2026-08-27",
            })
    return {"as_of": "2026-10-02", "records": rows}


def test_recording_plan_freezes_six_by_market_cap_and_full_replacement_order(tmp_path, monkeypatch):
    market = tmp_path / "market.json"
    market.write_text(json.dumps(_market()), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    digest = hashlib.sha256(market.read_bytes()).hexdigest()
    import scripts.prepare_sectors_recording as recording
    monkeypatch.setattr(recording, "validate_manifest_file", lambda *_args, **_kwargs: SimpleNamespace(
        manifest={"families": {"market": {"sha256": digest}}},
        release_id="rel-" + "a" * 64, manifest_sha256="b" * 64,
    ))
    report = freeze_plan(market_path=market, release_manifest=manifest, out_dir=tmp_path / "run")
    plan = json.loads((tmp_path / "run/recording_manifest.json").read_text())

    assert report["selected_stocks"] == 66
    assert report["planned_with_reserve"] == 450
    for sector in SECTORS:
        selection = plan["selections"][sector]
        assert len(selection["selected"]) == 6
        assert len(selection["replacement_order"]) == 2
        assert selection["selected"][0].endswith("AAA.JK")


def test_recording_preflight_refuses_sector_with_fewer_than_six_stocks(tmp_path, monkeypatch):
    market_data = _market()
    market_data["records"] = [row for row in market_data["records"] if row["taxonomy"]["sector"] != SECTORS[0]][:]
    market = tmp_path / "market.json"
    market.write_text(json.dumps(market_data), encoding="utf-8")

    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("scripts.prepare_sectors_recording.validate_manifest_file", lambda *_args, **_kwargs: SimpleNamespace(
        manifest={"families": {"market": {"sha256": hashlib.sha256(market.read_bytes()).hexdigest()}}},
        release_id="rel-" + "a" * 64, manifest_sha256="b" * 64,
    ))
    with pytest.raises(ValueError, match="fewer than six"):
        freeze_plan(market_path=market, release_manifest=manifest, out_dir=tmp_path / "run")
