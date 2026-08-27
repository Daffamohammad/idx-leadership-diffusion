"""Offline Sectors-shaped provider backed by explicitly synthetic fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional

from ..data import RawCache
from ..models import ProviderMode
from ..utils import project_root
from ..utils.errors import ProviderError
from .ledger import RequestLedger
from .sectors import SectorsProvider
from .sectors_client import SectorsClient
from .sectors_contracts import validate_sectors_payload


class _NoopFixtureCache(RawCache):
    """Fixtures are cheap; always re-read them so contract changes are visible."""

    def __init__(self) -> None:
        # Deliberately skip RawCache.__init__, which creates a filesystem root.
        pass

    def get(self, key: str, ttl_seconds: int | None = None) -> None:
        return None

    def set(self, key: str, data: Any) -> None:
        return None


class SectorsFixtureTransport:
    """Tiny route-table transport; it never opens a network connection.

    ``manifest.json`` marks the fixture set as synthetic and maps a path plus a
    subset of request parameters to one raw JSON response.  Every successful
    payload is contract-checked before it reaches a normalizer.
    """

    is_fixture_transport = True

    def __init__(self, fixtures_dir: str | Path) -> None:
        root = Path(fixtures_dir)
        if not root.is_absolute():
            root = project_root() / root
        self.root = root.resolve()
        manifest_path = self.root / "manifest.json"
        if not manifest_path.exists():
            raise ProviderError(f"Sectors fixture manifest not found: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Invalid Sectors fixture manifest: {exc}") from exc
        if manifest.get("fixture_kind") != "SYNTHETIC_SECTORS_V2" or not manifest.get(
            "not_live", False
        ):
            raise ProviderError(
                "Sectors fixture manifest must declare SYNTHETIC_SECTORS_V2 and not_live=true"
            )
        routes = manifest.get("routes")
        if not isinstance(routes, list):
            raise ProviderError("Sectors fixture manifest routes must be an array")
        self.manifest = manifest
        self.routes = routes

    def __call__(
        self,
        method: str,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> tuple[int, Any]:
        if method.upper() != "GET":
            raise ProviderError("Sectors fixture transport only supports GET")
        path = "/" + url.split("/", 3)[-1] if "/" in url else url
        if "/v2/" in url:
            path = "/v2/" + url.split("/v2/", 1)[1]

        candidates = [route for route in self.routes if route.get("path") == path]
        for route in candidates:
            expected = route.get("params") or {}
            if all(str(params.get(key)) == str(value) for key, value in expected.items()):
                payload_path = (self.root / str(route.get("file", ""))).resolve()
                if self.root not in payload_path.parents:
                    raise ProviderError("Sectors fixture route escapes its fixture directory")
                try:
                    payload = json.loads(payload_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ProviderError(f"Invalid Sectors fixture payload: {exc}") from exc
                status = int(route.get("status", 200))
                if status < 400:
                    validate_sectors_payload(
                        path,
                        payload,
                        expected_date=params.get("date") if path == "/v2/close/" else None,
                        raise_on_error=True,
                    )
                return status, payload
        raise ProviderError(
            f"No synthetic Sectors fixture route for path={path} params={dict(params)}"
        )


class SectorsFixtureProvider(SectorsProvider):
    """Sectors provider behavior exercised end-to-end without credentials."""

    name = "sectors_fixture"
    mode = ProviderMode.SECTORS_FIXTURE

    def __init__(
        self,
        *,
        fixtures_dir: str | Path = "data/fixtures/sectors",
        ledger: Optional[RequestLedger] = None,
        cache: Optional[RawCache] = None,
        max_pages: Optional[int] = None,
    ) -> None:
        fixture_root = Path(fixtures_dir)
        if not fixture_root.is_absolute():
            fixture_root = project_root() / fixture_root
        resolved_ledger = ledger or RequestLedger()
        transport = SectorsFixtureTransport(fixture_root)
        # Fixtures are re-read by default so a changed contract cannot be hidden
        # by a stale fixture cache. Tests may still inject a cache explicitly.
        resolved_cache = cache or _NoopFixtureCache()
        client = SectorsClient(
            api_key="",
            ledger=resolved_ledger,
            cache=resolved_cache,
            transport=transport,
            allow_live=False,
            mode=ProviderMode.SECTORS_FIXTURE,
            validate_contracts=True,
        )
        super().__init__(
            api_key="",
            ledger=resolved_ledger,
            client=client,
            mode=ProviderMode.SECTORS_FIXTURE,
            max_pages=max_pages,
        )
        self.fixtures_dir = fixture_root


__all__ = ["SectorsFixtureProvider", "SectorsFixtureTransport"]
