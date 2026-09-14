"""Provider factory with explicit, user-visible execution modes.

Legacy provider aliases remain accepted for existing CLIs, but each alias maps
to exactly one mode. In particular ``sectors`` always means ``SECTORS_LIVE``;
there is no fallback to Yahoo or to a fixture when credentials are absent.
"""
from __future__ import annotations

import importlib
import os
from typing import Any

from ..models import ProviderMode
from ..utils import ConfigurationError, load_yaml
from .base import MarketDataProvider
from .ledger import RequestLedger
from .sectors_client import SectorsClient


_LEGACY_MODE_ALIASES: dict[str, ProviderMode] = {
    "demo": ProviderMode.DEMO_FIXTURE,
    "demo_fixture": ProviderMode.DEMO_FIXTURE,
    "fixture": ProviderMode.DEMO_FIXTURE,
    "public": ProviderMode.PUBLIC_PROTOTYPE,
    "public_prototype": ProviderMode.PUBLIC_PROTOTYPE,
    "sectors_fixture": ProviderMode.SECTORS_FIXTURE,
    "sectors": ProviderMode.SECTORS_LIVE,
    "sectors_live": ProviderMode.SECTORS_LIVE,
}

_DEFAULT_PROVIDER_KEYS: dict[ProviderMode, str] = {
    ProviderMode.DEMO_FIXTURE: "fixture",
    ProviderMode.PUBLIC_PROTOTYPE: "public",
    ProviderMode.SECTORS_FIXTURE: "sectors_fixture",
    ProviderMode.SECTORS_LIVE: "sectors",
}


def parse_provider_mode(value: ProviderMode | str) -> ProviderMode:
    if isinstance(value, ProviderMode):
        return value
    raw = str(value).strip()
    try:
        return ProviderMode(raw.upper())
    except ValueError:
        alias = _LEGACY_MODE_ALIASES.get(raw.lower())
        if alias is None:
            supported = ", ".join(mode.value for mode in ProviderMode)
            raise ConfigurationError(
                f"Unknown provider mode '{value}'. Supported modes: {supported}"
            )
        return alias


def build_provider_from_config(
    config_path: str = "config/providers.yaml",
    *,
    mode: ProviderMode | str | None = None,
    preferred: str | None = None,
    allow_live: bool = False,
    max_pages: int | None = None,
    force_refresh: bool = False,
    max_estimated_credits: float | None = None,
    max_http_requests: int | None = SectorsClient.DEFAULT_MAX_HTTP_REQUESTS,
    ledger: RequestLedger | None = None,
) -> MarketDataProvider:
    """Construct one provider without any mode fallback.

    ``mode`` is the canonical API. ``preferred`` is retained as a compatibility
    alias and may not conflict with ``mode``.
    """
    cfg = load_yaml(config_path)
    providers = cfg.get("providers", {})
    if not isinstance(providers, dict) or not providers:
        raise ConfigurationError(f"No providers declared in {config_path}")

    if mode is not None and preferred is not None:
        parsed_mode = parse_provider_mode(mode)
        parsed_preferred = parse_provider_mode(preferred)
        if parsed_mode is not parsed_preferred:
            raise ConfigurationError(
                f"Conflicting provider selection: mode={parsed_mode.value}, preferred={preferred}"
            )
    elif mode is not None:
        parsed_mode = parse_provider_mode(mode)
    elif preferred is not None:
        parsed_mode = parse_provider_mode(preferred)
    else:
        parsed_mode = parse_provider_mode(
            cfg.get("default_mode", ProviderMode.PUBLIC_PROTOTYPE.value)
        )

    mode_map = cfg.get("mode_map", {})
    provider_key = mode_map.get(parsed_mode.value, _DEFAULT_PROVIDER_KEYS[parsed_mode])
    if provider_key not in providers:
        raise ConfigurationError(
            f"Mode {parsed_mode.value} maps to undeclared provider '{provider_key}'"
        )
    spec = providers[provider_key]
    class_path = spec.get("class")
    if not class_path:
        raise ConfigurationError(f"Provider '{provider_key}' missing 'class' entry")
    options = spec.get("options", {}) or {}

    module_path, _, class_name = class_path.rpartition(".")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ConfigurationError(f"Cannot import module {module_path}: {exc}") from exc
    try:
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ConfigurationError(f"Class {class_name} not in {module_path}") from exc

    resolved_ledger = ledger or RequestLedger()
    if parsed_mode is ProviderMode.SECTORS_LIVE:
        # Every production factory path gets the same conservative ceiling,
        # including older audit CLIs that do not expose a budget flag.
        resolved_max_estimated_credits = (
            SectorsClient.DEFAULT_MAX_ESTIMATED_CREDITS
            if max_estimated_credits is None
            else max_estimated_credits
        )
        kwargs: dict[str, Any] = {
            "api_key": os.environ.get(options.get("api_key_env", "SECTORS_API_KEY"), ""),
            "base_url": options.get("base_url", "https://api.sectors.app"),
            "ledger": resolved_ledger,
            "allow_live": bool(allow_live),
            "mode": ProviderMode.SECTORS_LIVE,
            "max_pages": max_pages,
            "force_refresh": bool(force_refresh),
            "max_estimated_credits": resolved_max_estimated_credits,
            "max_http_requests": max_http_requests,
            "timeout": int(options.get("request_timeout_seconds", 30)),
            "max_retries": int(options.get("max_retries", 2)),
            "backoff_seconds": float(options.get("retry_backoff_seconds", 1.5)),
            "cache_ttl_seconds": int(options.get("cache_ttl_hours", 1)) * 60 * 60,
            "history_workers": int(options.get("history_workers", 4)),
            "min_request_interval_seconds": float(
                options.get("request_interval_seconds", 0.0)
            ),
        }
    elif parsed_mode is ProviderMode.SECTORS_FIXTURE:
        kwargs = {
            "fixtures_dir": options.get("fixtures_dir", "data/fixtures/sectors"),
            "ledger": resolved_ledger,
            "max_pages": max_pages,
        }
    elif parsed_mode is ProviderMode.DEMO_FIXTURE:
        kwargs = {
            "fixtures_dir": options.get("fixtures_dir", "tests/fixtures"),
            "ledger": resolved_ledger,
            "mode": ProviderMode.DEMO_FIXTURE,
        }
    else:
        kwargs = {
            "universe_path": options.get(
                "default_universe", spec.get("default_universe", "config/universe.yaml")
            ),
            "request_timeout_seconds": int(options.get("request_timeout_seconds", 20)),
            "max_retries": int(options.get("max_retries", 2)),
            "retry_backoff_seconds": float(options.get("retry_backoff_seconds", 1.5)),
            "cache_ttl_hours": int(options.get("cache_ttl_hours", 12)),
            "ledger": resolved_ledger,
        }
    provider = cls(**kwargs)
    provider.mode = parsed_mode
    return provider


__all__ = ["build_provider_from_config", "parse_provider_mode"]
