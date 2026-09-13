"""Agent B — hygiene grep proofs for src/app/scripts.

Asserts no pickle/eval/exec/shell=True reach the codebase, and reports the
single innerHTML site (safe empty-string clear before createElement appends)
or a clean verdict. Fails closed: any new hit fails the suite.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FORBIDDEN = {
    "pickle": re.compile(r"^\s*(import\s+pickle|from\s+pickle\s+import)", re.M),
    "eval(": re.compile(r"(?<![\w.])eval\s*\(", re.M),
    "exec(": re.compile(r"(?<![\w.])exec\s*\(", re.M),
    "shell=True": re.compile(r"shell\s*=\s*True", re.M),
}

TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".sh"}
SKIP_DIRS = {".venv", "node_modules", ".git", "__pycache__", "dist", ".pytest_cache"}


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def test_no_pickle_eval_exec_shell_in_src_scripts():
    hits: list[str] = []
    for root in (REPO / "src", REPO / "scripts"):
        for path in _iter_files(root):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for name, pattern in FORBIDDEN.items():
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    hits.append(f"{path.relative_to(REPO)}:{line} [{name}]")
    assert hits == [], f"forbidden constructs found: {hits}"


def test_no_eval_exec_shell_in_app():
    hits: list[str] = []
    app_patterns = {
        k: v for k, v in FORBIDDEN.items() if k != "pickle"
    }
    for path in _iter_files(REPO / "app"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for name, pattern in app_patterns.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{path.relative_to(REPO)}:{line} [{name}]")
    assert hits == [], f"forbidden constructs found in app: {hits}"


def test_innerHTML_single_reviewed_site():
    hits: list[str] = []
    pattern = re.compile(r"\binnerHTML\b")
    for path in _iter_files(REPO / "app"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            hits.append(f"{path.relative_to(REPO)}:{line}")
    # Zero innerHTML sites: TradingViewWidget clears its own container with
    # replaceChildren(), then appends createElement nodes; the ticker is
    # sanitized to IDX format. Any new site fails closed.
    assert hits == [], f"innerHTML sites changed — re-review required: {hits}"
    widget = (REPO / "app/web/src/components/TradingViewWidget.tsx").read_text(
        encoding="utf-8"
    )
    assert "replaceChildren()" in widget
    assert "createElement" in widget
