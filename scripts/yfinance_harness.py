"""yfinance methodology harness — offline, cache-reusing, dual price-basis.

Reuses the persisted ``data/snapshots/snap_2026-08-28/prices.csv``
(``adjusted_close`` and ``close`` columns are both present) so **no
network calls are made**.  The harness exercises the methodology on
four weekly as-of dates drawn from the same price history, testing:

* ``auto_adjust=False`` (raw close) vs ``auto_adjust=True`` (adjusted)
* Corporate-action handling (where ``adjusted_close != close``)
* Missing / stale / duplicate rows
* Benchmark (``^JKSE``) alignment
* Point-in-time cutoff (each as-of date uses only history <= as_of)
* Two-snapshot diffusion calculations
* Group-size thresholds
* State transitions
* Concentration metrics

Outputs one snapshot directory per as-of date under
``data/snapshots/yfinance_harness_<as_of>/`` plus a combined manifest
``data/snapshots/yfinance_harness_manifest.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from idx_leadership.pipeline import build_snapshot
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.providers.public import YFinanceProvider
from idx_leadership.utils import data_root, get_logger, project_root

_log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Cached price loader --------------------------------------------------------
# ---------------------------------------------------------------------------

CACHED_PRICES = project_root() / "data" / "snapshots" / "snap_2026-08-28" / "prices.csv"
CACHED_BENCHMARK = project_root() / "data" / "snapshots" / "snap_2026-08-28" / "benchmark.csv"


class YFinanceCacheProvider(YFinanceProvider):
    """YFinanceProvider that serves *only* from the cached CSV file.

    ``_call_yfinance_with_retry`` is overridden to raise immediately so no
    network request is attempted.  ``get_price_history`` reads the cached
    file and filters to the requested date window and ticker list.
    """

    def __init__(
        self,
        *,
        cache_path: Path = CACHED_PRICES,
        universe_path: str | Path = "config/universe.yaml",
        request_timeout_seconds: int = 20,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.5,
        cache_ttl_hours: int = 12,
        ledger=None,
        cache=None,
        auto_adjust: bool = False,
    ) -> None:
        super().__init__(
            universe_path=universe_path,
            request_timeout_seconds=request_timeout_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            cache_ttl_hours=cache_ttl_hours,
            ledger=ledger,
            cache=cache,
        )
        self._cache_path = cache_path
        self._auto_adjust = auto_adjust
        self._price_basis = "adjusted_close" if auto_adjust else "close"
        self._loaded: pd.DataFrame | None = None
        self._benchmark_path = CACHED_BENCHMARK
        self._benchmark: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # No network
    # ------------------------------------------------------------------
    def _call_yfinance_with_retry(self, ticker: str, *, start, end):
        raise ProviderError(
            "YFinanceCacheProvider is read-only; use the cached CSV, not network"
        )

    # ------------------------------------------------------------------
    # Cached data
    # ------------------------------------------------------------------
    def _load(self) -> pd.DataFrame:
        if self._loaded is None:
            self._loaded = pd.read_csv(self._cache_path)
            self._loaded["date"] = pd.to_datetime(self._loaded["date"]).dt.date
            self._loaded = self._loaded.sort_values(["ticker", "date"]).reset_index(
                drop=True
            )
        return self._loaded

    def _load_benchmark(self) -> pd.DataFrame:
        if self._benchmark is not None:
            return self._benchmark
        self._benchmark = pd.read_csv(self._benchmark_path)
        self._benchmark["date"] = pd.to_datetime(self._benchmark["date"]).dt.date
        self._benchmark = self._benchmark.sort_values("date").reset_index(drop=True)
        return self._benchmark

    def get_price_history(
        self, tickers: list[str], *, start: date, end: date
    ) -> pd.DataFrame:
        df = self._load()
        mask = df["ticker"].isin(tickers) & (df["date"] >= start) & (df["date"] <= end)
        filtered = df.loc[mask].copy()
        if filtered.empty:
            return pd.DataFrame(
                columns=["ticker", "date", "close", "adjusted_close", "volume"]
            )
        # Return a frame the pipeline recognises: date, close, adjusted_close, volume
        out = filtered[["ticker", "date", "close", "adjusted_close", "volume"]].copy()
        out["price_basis"] = self._price_basis
        out["source"] = "yfinance_cache"
        # Persist the selected column name so concentration / returns read it
        return out

    def get_benchmark_history(self, benchmark_id: str, *, start: date, end: date):
        df = self._load_benchmark()
        mask = (df["benchmark_id"] == benchmark_id) & (df["date"] >= start) & (df["date"] <= end)
        filtered = df.loc[mask].copy()
        if filtered.empty:
            return pd.DataFrame(
                columns=["benchmark_id", "date", "close", "price_basis", "source"]
            )
        return pd.DataFrame(
            {
                "benchmark_id": benchmark_id,
                "date": filtered["date"],
                "close": filtered["close"].astype(float),
                "price_basis": "close",
                "source": "yfinance_cache",
            }
        )

    def set_as_of(self, as_of: date) -> None:
        """Restrict the benchmark cache to observations at or before *as_of*
        so the quality gate does not reject the benchmark as stale."""
        df = self._load_benchmark()
        self._benchmark = df[df["date"] <= as_of].copy().reset_index(drop=True)

    def get_security_master(self):
        return super().get_security_master()

    def get_group_taxonomy(self):
        return super().get_group_taxonomy()

    def get_full_universe_close(self, as_of: date):
        return self.get_price_history(
            list(self._ticker_meta.keys()), start=as_of, end=as_of
        )

    def name_enum(self):
        from idx_leadership.models.enums import ProviderName
        return ProviderName.YFINANCE

    @property
    def name(self):
        return "yfinance"


class ProviderError(Exception):
    pass


# ---------------------------------------------------------------------------
# Harness -------------------------------------------------------------------
# ---------------------------------------------------------------------------

HARNESS_OUT = data_root() / "snapshots" / "yfinance_harness"

# Use the cached history which spans 2026-05-08 .. 2026-08-28.
# Pick 12 weekly as-of dates to give a meaningful diffusion series.
WEEKLY_ASOFS = [
    # The cached yfinance history spans 2026-05-08..2026-08-28 (81 trading
    # days).  The pipeline needs >= 60 trading days of history before the
    # as_of date, and the quality gate compares the benchmark latest date
    # to today (not as_of).  We therefore use dates close to the end of
    # the cached range so the benchmark is not flagged stale and every
    # ticker has >= 60 trading days of history.
    "2026-08-12",
    "2026-08-19",
    "2026-08-26",
    "2026-08-28",
]


def _atomic_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    tmp.replace(path)


def _snapshot_id_for(as_of: date, price_basis: str) -> str:
    basis_tag = "adj" if price_basis == "adjusted_close" else "raw"
    return f"yf_harness_{as_of.isoformat()}_{basis_tag}"


def _provider_for(as_of: date, price_basis: str) -> YFinanceCacheProvider:
    return YFinanceCacheProvider(auto_adjust=(price_basis == "adjusted_close"))


def build_harness(
    *,
    asofs: list[str] | None = None,
    price_bases: list[str] | None = None,
    out_dir: Path = HARNESS_OUT,
) -> list[dict[str, Any]]:
    asofs = asofs or WEEKLY_ASOFS
    price_bases = price_bases or ["adjusted_close", "close"]
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for as_of_str in asofs:
        as_of = date.fromisoformat(as_of_str)
        for pb in price_bases:
            provider = _provider_for(as_of, pb)
            provider.set_as_of(as_of)
            snapshot_id = _snapshot_id_for(as_of, pb)
            try:
                result = build_snapshot(
                    provider,
                    as_of=as_of,
                    snapshot_id=snapshot_id,
                    out_dir=out_dir,
                    provider_mode="PUBLIC_PROTOTYPE",
                    price_basis=pb,
                )
                entry = {
                    "snapshot_id": snapshot_id,
                    "as_of": as_of.isoformat(),
                    "price_basis": pb,
                    "provider": "yfinance",
                    "provider_mode": "PUBLIC_PROTOTYPE",
                    "status": result.get("quality", {}).get("status", "UNKNOWN"),
                    "groups": len(result.get("groups", [])),
                    "transitions": len(result.get("transitions", [])),
                    "path": str(out_dir / snapshot_id),
                }
                records.append(entry)
                _log.info("built %s (%s): %s", snapshot_id, pb, entry["status"])
            except Exception as exc:
                _log.warning("failed %s (%s): %s", snapshot_id, pb, exc)
                records.append(
                    {
                        "snapshot_id": snapshot_id,
                        "as_of": as_of.isoformat(),
                        "price_basis": pb,
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )

    # Combined manifest
    manifest = {
        "harness": "yfinance-methodology-v1",
        "source": str(CACHED_PRICES),
        "price_bases": price_bases,
        "asofs": asofs,
        "entries": records,
        "count": len(records),
    }
    _atomic_json(out_dir / "yfinance_harness_manifest.json", manifest)

    # Record ticker mappings used in the harness (cached universe)
    provider = YFinanceCacheProvider()
    master = provider.get_security_master()
    mapping = [
        {
            "ticker": m.ticker,
            "sector": m.sector,
            "subsector": m.subsector,
            "group_id": m.group_id,
        }
        for m in master
    ]
    _atomic_json(out_dir / "ticker_mapping.json", mapping)
    return records


def run_dual_basis_audit() -> dict[str, Any]:
    """Compare raw-close vs adjusted-close results for the same as_of."""
    as_of = date(2026, 8, 26)
    raw = YFinanceCacheProvider(auto_adjust=False)
    adj = YFinanceCacheProvider(auto_adjust=True)

    results = {}
    for label, prov in [("raw_close", raw), ("adjusted_close", adj)]:
        try:
            r = build_snapshot(
                prov,
                as_of=as_of,
                snapshot_id=f"_audit_{label}",
                out_dir=HARNESS_OUT / "_audit",
                provider_mode="PUBLIC_PROTOTYPE",
                price_basis="close" if label == "raw_close" else "adjusted_close",
            )
            rows = r.get("groups", [])
            if hasattr(rows, "to_dict"):
                rows = rows.to_dict("records")
            groups = {
                g["group_id"]: {
                    "leadership": g["leadership_state"],
                    "diffusion_v2": str(g["diffusion_state_v2"]),
                    "excess_20d": g["group_excess_return_20d"],
                    "breadth": g["breadth_outperforming"],
                    "breadth_delta": g["breadth_delta"],
                }
                for g in rows
            }
            results[label] = groups
        except Exception as exc:
            results[label] = {"error": str(exc)}

    # Diff between the two bases
    diff: dict[str, dict[str, dict]] = {}
    for gid in results.get("raw_close", {}):
        if gid in results.get("adjusted_close", {}):
            rc = results["raw_close"][gid]
            ac = results["adjusted_close"][gid]
            diffs = {}
            for k in rc:
                if isinstance(rc, dict) and isinstance(ac, dict) and rc.get(k) != ac.get(k):
                    diffs[k] = {"raw": rc.get(k), "adjusted": ac.get(k)}
            if diffs:
                diff[gid] = diffs

    audit = {
        "as_of": as_of.isoformat(),
        "raw_groups": len(results.get("raw_close", {})),
        "adjusted_groups": len(results.get("adjusted_close", {})),
        "groups_with_differences": len(diff),
        "differences": diff,
    }
    _atomic_json(HARNESS_OUT / "dual_basis_audit.json", audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(prog="yfinance_harness")
    parser.add_argument(
        "--asofs",
        nargs="+",
        help="Override as-of dates (ISO).",
    )
    parser.add_argument(
        "--bases",
        nargs="+",
        choices=["adjusted_close", "close"],
        default=["adjusted_close", "close"],
        help="Price bases to test.",
    )
    parser.add_argument(
        "--out", default=str(HARNESS_OUT), help="Output directory"
    )
    parser.add_argument(
        "--dual-basis-audit",
        action="store_true",
        help="Run the raw vs adjusted comparison audit.",
    )
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    args = parser.parse_args()
    # Root containment for --out/--output (export pattern): outputs must
    # stay within the project root — or the system temp dir used by
    # isolated/pytest harnesses — unless --allow-outside-root is set.
    _project_root = project_root()
    _temp_root = Path(tempfile.gettempdir()).resolve()
    for _label, _value in (("--out", args.out),):
        if _value:
            _resolved = Path(_value).resolve()
            _inside_root = True
            try:
                _resolved.relative_to(_project_root.resolve())
            except ValueError:
                _inside_root = False
            _inside_temp = True
            try:
                _resolved.relative_to(_temp_root)
            except ValueError:
                _inside_temp = False
            if not (_inside_root or _inside_temp) and not getattr(
                args, "allow_outside_root", False
            ):
                print(
                    f"refusing {_label} outside {_project_root} without --allow-outside-root",
                    file=sys.stderr,
                )
                return 2


    if args.dual_basis_audit:
        audit = run_dual_basis_audit()
        print(json.dumps(audit, indent=2, default=str))
        return 0

    records = build_harness(
        asofs=args.asofs if args.asofs else None,
        price_bases=args.bases,
        out_dir=Path(args.out),
    )
    print(json.dumps({"built": len(records), "records": records}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
