"""Configuration loading utilities.

Single source of truth for path resolution, local environment loading, and
YAML loading. The environment loader is deliberately small and local-only:
it supports the project's ``.env`` file without adding a runtime dependency
or printing credential values. Existing process environment variables always
win over values in the file.
"""
from __future__ import annotations

import os
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


def load_project_env(path: str | Path | None = None) -> list[str]:
    """Load simple ``KEY=VALUE`` entries from the project ``.env`` file.

    This is intended for local CLI/UI startup where the user has saved keys in
    ``.env`` but has not exported them into the shell. It intentionally does
    not implement shell expansion or command substitution. Values already
    present in ``os.environ`` are never replaced, which keeps CI/deployment
    configuration authoritative.

    Returns the names loaded into the process; values are never returned or
    logged. Missing files are a normal state and return an empty list.
    """

    env_path = Path(path) if path is not None else project_root() / ".env"
    if not env_path.is_absolute():
        env_path = project_root() / env_path
    if not env_path.exists():
        return []

    loaded: list[str] = []
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return loaded

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or not all(character.isalnum() or character == "_" for character in key):
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


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
