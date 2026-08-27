"""Configuration loading utilities.

Single source of truth for path resolution and YAML loading.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    """Return the absolute path of the project root (the directory containing pyproject.toml)."""
    # src/idx_leadership/utils/config.py -> project root is 4 levels up.
    return Path(__file__).resolve().parents[3]


def data_root() -> Path:
    """Return the absolute path of the data/ directory."""
    return project_root() / "data"


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file using safe loading.

    Raises FileNotFoundError if missing, ValueError on parse error.
    """
    p = Path(path)
    if not p.is_absolute():
        p = project_root() / p
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    try:
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {p}: {e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at top level of {p}, got {type(data).__name__}")
    return data
