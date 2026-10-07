import hashlib
import json

import pytest

from idx_leadership.providers.idx_ownership import source as ownership_source
from scripts.record_acquisition import _preserve_capture, append_acquisition


def test_captured_bytes_are_preserved_under_a_new_versioned_path(tmp_path):
    source = tmp_path / "incoming" / "ownership.xlsx"
    source.parent.mkdir()
    source.write_bytes(b"original captured bytes")
    destination = _preserve_capture(source, tmp_path / "acquisitions" / "ownership-2026-10-05")
    assert destination.read_bytes() == source.read_bytes()
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        _preserve_capture(source, destination.parent)


def test_acquisition_inventory_is_append_only_by_id(tmp_path):
    inventory = tmp_path / "inventory.jsonl"
    record = {"acquisition_id": "source-2026-10-05", "sha256": "a" * 64}
    append_acquisition(record, inventory)
    before = inventory.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        append_acquisition(record, inventory)
    assert inventory.read_bytes() == before
    assert json.loads(before) == record


def test_ownership_provenance_uses_official_name_for_versioned_capture(tmp_path):
    capture = tmp_path / "capture.xlsx"
    capture.write_bytes(b"captured workbook")

    row = ownership_source(
        capture,
        "https://www.idx.co.id/Media/example/peng-2026-09-00024-satu-persen.xlsx",
        "2026-09-30",
    )

    assert row["filename"] == "peng-2026-09-00024-satu-persen.xlsx"
    assert row["sha256"] == hashlib.sha256(capture.read_bytes()).hexdigest()
