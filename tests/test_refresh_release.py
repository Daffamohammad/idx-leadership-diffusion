import json

import pytest

from scripts.refresh_release import _run_stages


def test_refresh_runner_refuses_unstaged_output_paths(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    plan = {
        "source_evidence": [],
        "stages": [{
            "name": "validation",
            "module": "scripts.validate_public_panel",
            "args": [
                "--panel-dir", str(staging / "panel"),
                "--target-session", "2026-10-02",
                "--composite-workbook", str(staging / "composite.xlsx"),
                "--stock-summary", str(staging / "summary.xlsx"),
                "--daily-statistics-pdf", str(staging / "daily.pdf"),
                "--out", str(tmp_path / "outside-report.json"),
            ],
            "outputs": [str(staging / "validation.json")],
        }],
    }
    with pytest.raises(ValueError, match="inside the staging directory"):
        _run_stages(plan, staging, "2026-10-02", tmp_path)
    assert not (tmp_path / "outside-report.json").exists()


def test_refresh_runner_does_not_write_to_a_nonempty_staging_directory(tmp_path, monkeypatch):
    from scripts import refresh_release

    blocked_report_dir = tmp_path / "blocked-report"
    def make_tempdir(prefix):
        blocked_report_dir.mkdir()
        return str(blocked_report_dir)
    monkeypatch.setattr(refresh_release.tempfile, "mkdtemp", make_tempdir)
    plan_path = tmp_path / "source-plan.json"
    plan_path.write_text(json.dumps({"schema_version": "idx-release-source-plan-v1", "target_session": "2026-10-02", "stages": []}))
    staging = tmp_path / "already-used"
    staging.mkdir()
    marker = staging / "keep.txt"
    marker.write_text("preserve")
    monkeypatch.setattr("sys.argv", [
        "refresh_release", "--target-session", "2026-10-02", "--sources", str(plan_path), "--out-dir", str(staging),
    ])
    assert refresh_release.main() == 1
    assert marker.read_text() == "preserve"
    assert not (staging / "refresh-report.json").exists()
    assert json.loads((blocked_report_dir / "refresh-report.json").read_text())["publication_readiness"] == "BLOCKED"
