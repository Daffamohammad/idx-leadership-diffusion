from __future__ import annotations

from scripts.export_snapshot_json import (
    _normalize_first_party_idx_urls,
    _read_listed_universe_rows,
)


def test_normalize_export_urls_only_rewrites_exact_idx_prefix() -> None:
    payload = {
        "idx": "http://www.idx.co.id/Portals/0/report.pdf",
        "nested": [
            "http://www.idx.co.id/",
            "https://www.idx.co.id/en/",
            "http://idx.co.id/report.pdf",
            "http://www.idx.co.id.evil/report.pdf",
            "http://localhost:5173/snapshots/demo.json",
        ],
        "number": 7,
    }

    normalized = _normalize_first_party_idx_urls(payload)

    assert normalized == {
        "idx": "https://www.idx.co.id/Portals/0/report.pdf",
        "nested": [
            "https://www.idx.co.id/",
            "https://www.idx.co.id/en/",
            "http://idx.co.id/report.pdf",
            "http://www.idx.co.id.evil/report.pdf",
            "http://localhost:5173/snapshots/demo.json",
        ],
        "number": 7,
    }
    assert payload["idx"] == "http://www.idx.co.id/Portals/0/report.pdf"


def test_read_listed_universe_rows_handles_missing_and_existing_csv(tmp_path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()

    assert _read_listed_universe_rows(snapshot_dir) == []

    (snapshot_dir / "listed_universe.csv").write_text(
        "ticker,company_name\nBBCA,Bank Central Asia\n",
        encoding="utf-8",
    )

    assert _read_listed_universe_rows(snapshot_dir) == [
        {"ticker": "BBCA", "company_name": "Bank Central Asia"}
    ]
