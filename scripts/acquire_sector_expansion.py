"""Acquire only the 66 added Sectors histories under the pinned 221-credit ceiling."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from idx_leadership.data.releases import canonical_json_bytes
from idx_leadership.models import ProviderMode
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.persistent_budget import PersistentRequestBudget
from idx_leadership.providers.sectors import _plan_windows
from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.providers.sectors_normalizers import normalize_daily_history
from idx_leadership.utils import load_project_env


MAX_REQUESTS = 221
MAX_CREDITS = 221
MINIMUM_RETRY_RESERVE = 23
PRICE_WINDOWS_PER_STOCK = 2
MINIMUM_REQUEST_INTERVAL_SECONDS = 2.2


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json_bytes(value) + b"\n"
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return _sha(raw)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _plan_hash(plan: dict[str, Any]) -> str:
    body = dict(plan)
    declared = body.pop("plan_sha256", None)
    run_id = body.pop("run_id", None)
    actual = _sha(canonical_json_bytes(body))
    if declared != actual or run_id != f"sectors-expansion-{actual[:16]}":
        raise ValueError("expansion plan hash does not match its frozen contents")
    return actual


class ExpansionRun:
    def __init__(self, run_dir: Path, *, record: bool) -> None:
        self.run_dir = run_dir.resolve(strict=True)
        self.plan_path = self.run_dir / "expansion_plan.json"
        self.plan = _read_json(self.plan_path)
        self.plan_sha256 = _plan_hash(self.plan)
        self.run_id = self.plan["run_id"]
        budget_plan = self.plan.get("budget", {})
        if (budget_plan.get("planned_credits") != 198
                or budget_plan.get("retry_reserve") != MINIMUM_RETRY_RESERVE
                or budget_plan.get("hard_credit_ceiling") != MAX_CREDITS
                or budget_plan.get("hard_request_ceiling") != MAX_REQUESTS):
            raise ValueError("expansion plan does not match the pinned 198-plus-23 budget")
        self.state_path = self.run_dir / "expansion_state.json"
        self.receipt_path = self.run_dir / "expansion_receipt.json"
        self.state = _read_json(self.state_path) if self.state_path.exists() else {
            "schema_version": "sectors-expansion-state-v1",
            "run_id": self.run_id,
            "plan_sha256": self.plan_sha256,
            "completed": [],
            "raw_response_hashes": {},
            "fetch_details": {},
        }
        if self.state.get("run_id") != self.run_id or self.state.get("plan_sha256") != self.plan_sha256:
            raise ValueError("saved progress belongs to a different pinned expansion plan")
        self.state.setdefault("raw_response_hashes", {})
        self.state.setdefault("fetch_details", {})
        self.budget = PersistentRequestBudget(
            self.run_dir / "request_budget.json", run_id=self.run_id, plan_sha256=self.plan_sha256,
        )
        self.ledger = RequestLedger(path=self.run_dir / "request_ledger.jsonl")
        self.receipt = _read_json(self.receipt_path) if self.receipt_path.exists() else {
            "schema_version": "sectors-expansion-receipt-v1",
            "run_id": self.run_id,
            "plan_sha256": self.plan_sha256,
            "status": "PREFLIGHT_ONLY" if not record else "IN_PROGRESS",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "api_credential_written": False,
        }
        if self.receipt.get("run_id") != self.run_id or self.receipt.get("plan_sha256") != self.plan_sha256:
            raise ValueError("saved receipt belongs to a different pinned expansion plan")
        self.receipt["status"] = "IN_PROGRESS" if record else "PREFLIGHT_ONLY"
        self.receipt["request_budget"] = self.budget.snapshot()
        self._save()
        self.base_manifest_path = Path(self.plan["base_release"]["manifest_path"]).resolve(strict=True)
        self.market_path = Path(self.plan["market_release_source"]["path"]).resolve(strict=True)
        from idx_leadership.data.releases import validate_manifest_file
        base_payload = _read_json(self.base_manifest_path)
        is_candidate = any("candidate_path" in row for row in base_payload.get("source_evidence", []))
        if is_candidate != self.plan["base_release"].get("is_candidate"):
            raise ValueError("base release validation mode changed after preflight")
        base = validate_manifest_file(self.base_manifest_path, candidate=is_candidate)
        market_raw = self.market_path.read_bytes()
        if base.release_id != self.plan["base_release"]["release_id"] or base.manifest_sha256 != self.plan["base_release"]["manifest_sha256"]:
            raise ValueError("the 66-stock base release changed after preflight")
        if _sha(market_raw) != self.plan["market_release_source"]["sha256"]:
            raise ValueError("the pinned market source changed after preflight")
        self.market = _read_json(self.market_path)
        self.client: SectorsClient | None = None
        if record:
            load_project_env()
            api_key = os.environ.get("SECTORS_API_KEY", "")
            if not api_key.strip():
                raise ValueError("SECTORS_API_KEY is not configured")
            self.client = SectorsClient(
                api_key=api_key,
                allow_live=True,
                mode=ProviderMode.SECTORS_LIVE,
                ledger=self.ledger,
                force_refresh=False,
                max_retries=2,
                min_request_interval_seconds=MINIMUM_REQUEST_INTERVAL_SECONDS,
                max_estimated_credits=MAX_CREDITS,
                max_http_requests=MAX_REQUESTS,
                budget_reserver=self.budget.reserve,
            )

    def _save(self) -> None:
        self.receipt["request_budget"] = self.budget.snapshot()
        self.receipt["completed_requests"] = len(self.state.get("completed", []))
        self.receipt["raw_response_hashes"] = self.state.get("raw_response_hashes", {})
        _write_json(self.state_path, self.state)
        _write_json(self.receipt_path, self.receipt)

    def fetch(self, relative_path: str, endpoint: str, params: dict[str, str]) -> Any:
        path = self.run_dir / "responses" / relative_path
        expected_request = {"endpoint": endpoint, "parameters": params}
        if path.exists():
            envelope = _read_json(path)
            if envelope.get("request") != expected_request:
                raise ValueError(f"saved response does not match the pinned request: {relative_path}")
            payload = envelope.get("response")
            if _sha(canonical_json_bytes(payload)) != envelope.get("response_sha256"):
                raise ValueError(f"saved response hash does not match: {relative_path}")
            file_hash = _sha(path.read_bytes())
            self.state["raw_response_hashes"][relative_path] = file_hash
            self.state["fetch_details"][relative_path] = envelope.get("fetch", {"cache_hit": False, "http_attempts": 0})
            if relative_path not in self.state["completed"]:
                self.state["completed"].append(relative_path)
            self._save()
            return payload
        if self.client is None:
            raise RuntimeError("live acquisition is disabled")
        before = self.client.http_requests_made
        try:
            response = self.client.get(endpoint, params, use_cache=True)
            payload = response.payload
            envelope = {
                "request": expected_request,
                "response_sha256": _sha(canonical_json_bytes(payload)),
                "response": payload,
                "fetch": {
                    "cache_hit": response.cache_hit,
                    "status": response.status,
                    "estimated_credit_cost": response.estimated_credit_cost,
                    "http_attempts": self.client.http_requests_made - before,
                    "request_id": response.request_id,
                },
            }
            file_hash = _write_json(path, envelope)
            self.state["raw_response_hashes"][relative_path] = file_hash
            self.state["fetch_details"][relative_path] = envelope["fetch"]
            self.state["completed"].append(relative_path)
            return payload
        finally:
            self.ledger.flush()
            self._save()

    def acquire(self) -> dict[str, Any]:
        target = date.fromisoformat(self.plan["coverage"]["target_date"])
        window_plan = self.plan["coverage"]["price_windows"]
        if len(window_plan) != PRICE_WINDOWS_PER_STOCK:
            raise ValueError("the pinned plan must contain exactly two price windows per added stock")
        windows = [(date.fromisoformat(pair[0]), date.fromisoformat(pair[1])) for pair in window_plan]
        if windows != _plan_windows(windows[0][0], target, max_window_days=90):
            raise ValueError("pinned price windows are not consecutive, gap-free, and within 90 days")

        records = []
        for item in self.plan["selection"]["additions"]:
            ticker = str(item["ticker"]).upper()
            sector = str(item["sector"])
            source_row = next((row for row in self.market["records"] if str(row.get("ticker", "")).upper() == ticker), None)
            if source_row is None or (source_row.get("taxonomy") or {}).get("sector") != sector:
                raise ValueError(f"added ticker no longer matches the pinned market source: {ticker}")
            combined_prices: list[dict[str, Any]] = []
            price_sources = []
            for index, (start, end) in enumerate(windows, 1):
                relative = f"prices/{ticker.replace('.', '_')}/{index:02d}_{start.isoformat()}_{end.isoformat()}.json"
                payload = self.fetch(relative, f"/v2/daily/{ticker}/", {
                    "start": start.isoformat(), "end": end.isoformat(),
                })
                frame = normalize_daily_history(payload, source="sectors")
                frame = frame[frame["ticker"].astype(str).str.upper() == ticker]
                rows = [{**row, "date": row["date"].isoformat()} for row in frame.to_dict(orient="records")]
                if any(not start.isoformat() <= row["date"] <= end.isoformat() for row in rows):
                    raise ValueError(f"price data for {ticker} falls outside its requested window")
                combined_prices.extend(rows)
                price_sources.append({
                    "window": [start.isoformat(), end.isoformat()],
                    "path": relative,
                    "sha256": self.state["raw_response_hashes"].get(relative),
                })
            combined_prices.sort(key=lambda row: row["date"])
            price_dates = [row["date"] for row in combined_prices]
            if len(price_dates) != len(set(price_dates)):
                raise ValueError(f"price windows contain duplicate dates for {ticker}")
            if any(day > target.isoformat() for day in price_dates):
                raise ValueError(f"price data for {ticker} extends beyond the 2 October target")

            action_path = f"corporate_actions/{ticker.replace('.', '_')}.json"
            actions = self.fetch(action_path, f"/v2/company/corporate-actions/{ticker}/", {})
            market_cap = float(source_row["market_cap"])
            coverage = {
                "requested_start": windows[0][0].isoformat(),
                "requested_end": windows[-1][1].isoformat(),
                "observed_start": price_dates[0] if price_dates else None,
                "observed_end": price_dates[-1] if price_dates else None,
                "window_count": len(windows),
                "price_windows": price_sources,
            }
            records.append({
                "ticker": ticker,
                "company_name": source_row.get("company_name"),
                "sector": sector,
                "membership_as_of": source_row.get("classification_as_of"),
                "market_cap_as_of": source_row.get("last_trade_date"),
                "market_cap_idr": market_cap,
                "prices": combined_prices,
                "price_sources": price_sources,
                "history_coverage": coverage,
                "corporate_actions": {
                    "response": actions,
                    "source": {
                        "path": action_path,
                        "sha256": self.state["raw_response_hashes"].get(action_path),
                    },
                },
            })
            self._save()

        if len(records) != 66 or len({row["ticker"] for row in records}) != 66:
            raise ValueError("the expanded acquisition must contain 66 unique additions")
        per_sector: dict[str, int] = {}
        for row in records:
            per_sector[row["sector"]] = per_sector.get(row["sector"], 0) + 1
        if set(per_sector.values()) != {6} or len(per_sector) != 11:
            raise ValueError("the expanded acquisition does not contain six additions in each of 11 sectors")

        payload = {
            "schema_version": "sectors-expansion-acquisition-v1",
            "as_of": target.isoformat(),
            "plan_sha256": self.plan_sha256,
            "market_release_source_sha256": self.plan["market_release_source"]["sha256"],
            "selection": {
                "stock_count": len(records),
                "stocks_per_sector": 6,
                "sector_counts": per_sector,
                "members": [{"ticker": row["ticker"], "sector": row["sector"]} for row in records],
            },
            "coverage": {
                "daily_replay_dates": self.plan["coverage"]["daily_replay_dates"],
                "weekly_replay_dates": self.plan["coverage"]["weekly_replay_dates"],
                "first_replay_date": self.plan["coverage"]["first_replay_date"],
                "first_required_price_date": self.plan["coverage"]["first_required_price_date"],
                "price_end_date": target.isoformat(),
                "per_stock": {row["ticker"]: row["history_coverage"] for row in records},
            },
            "stocks": records,
            "sources": {
                "raw_response_hashes": dict(sorted(self.state["raw_response_hashes"].items())),
                "request_ledger_sha256": _sha((self.run_dir / "request_ledger.jsonl").read_bytes()) if (self.run_dir / "request_ledger.jsonl").exists() else None,
            },
            "validation": {
                "status": "PASS",
                "added_stocks": 66,
                "six_added_per_sector": True,
                "price_windows_per_stock": 2,
                "maximum_calendar_days_per_window": 90,
                "corporate_action_checks": 66,
                "price_dates_outside_requested_windows": 0,
                "duplicate_price_dates": 0,
                "request_budget": self.budget.snapshot(),
            },
        }
        if payload["validation"]["request_budget"]["requests_reserved"] > MAX_REQUESTS or payload["validation"]["request_budget"]["credits_reserved"] > MAX_CREDITS:
            raise ValueError("the pinned 221-request or 221-credit ceiling was exceeded")
        raw_hash = _write_json(self.run_dir / "sectors_expansion_acquisition.json", payload)
        self.receipt.update({
            "status": "ACQUISITION_VALIDATED",
            "acquisition_sha256": raw_hash,
            "acquisition_path": str(self.run_dir / "sectors_expansion_acquisition.json"),
            "added_stocks": len(records),
            "request_budget": self.budget.snapshot(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save()
        return {
            "status": "PASS",
            "run_id": self.run_id,
            "added_stocks": len(records),
            "daily_dates": len(payload["coverage"]["daily_replay_dates"]),
            "weekly_dates": len(payload["coverage"]["weekly_replay_dates"]),
            "budget": self.budget.snapshot(),
            "acquisition": str(self.run_dir / "sectors_expansion_acquisition.json"),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--record", action="store_true", help="Make the pinned Sectors requests; without this flag only show budget status.")
    parser.add_argument("--allow-live", action="store_true", help="Required gate for live requests.")
    parser.add_argument("--allow-credit-spend", action="store_true", help="Required gate for the separate 221-credit ceiling.")
    args = parser.parse_args()
    run: ExpansionRun | None = None
    try:
        if args.record and not (args.allow_live and args.allow_credit_spend):
            raise ValueError("live expansion requires both --allow-live and --allow-credit-spend")
        run = ExpansionRun(args.run_dir, record=args.record)
        if not args.record:
            print(json.dumps({
                "status": "PREFLIGHT_ONLY",
                "run_id": run.run_id,
                "planned_credits": run.plan["budget"]["planned_credits"],
                "retry_reserve": run.plan["budget"]["retry_reserve"],
                "hard_ceiling": run.plan["budget"]["hard_credit_ceiling"],
                "budget": run.budget.snapshot(),
            }, sort_keys=True))
            return 0
        print(json.dumps(run.acquire(), sort_keys=True))
        return 0
    except Exception as exc:  # the receipt keeps restart and budget evidence
        if run is not None:
            message = str(exc)
            secret = os.environ.get("SECTORS_API_KEY", "")
            if secret:
                message = message.replace(secret, "[redacted]")
            message = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", message)
            run.receipt.update({"status": "INCOMPLETE", "blocking_reason": message[:500]})
            run._save()
        public_message = str(exc)
        secret = os.environ.get("SECTORS_API_KEY", "")
        if secret:
            public_message = public_message.replace(secret, "[redacted]")
        public_message = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", public_message)
        print(f"SECTORS_EXPANSION_INCOMPLETE: {public_message[:500]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
