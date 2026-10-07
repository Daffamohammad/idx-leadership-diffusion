"""Acquire the pinned Sectors sample under a durable 450-call/credit ceiling."""
from __future__ import annotations

import argparse
from datetime import date, timedelta, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any

import pandas as pd

from idx_leadership.data.releases import canonical_json_bytes
from idx_leadership.models import ProviderMode
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.persistent_budget import PersistentRequestBudget
from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.providers.sectors_normalizers import (
    normalize_daily_history,
    normalize_foreign_flow,
    normalize_index_daily,
)
from idx_leadership.providers.sectors import _plan_windows
from idx_leadership.utils import load_project_env


MAX_CALLS = 450
MAX_CREDITS = 450
MAX_REPLACEMENTS = 5
PRICE_START = date(2025, 12, 31)
FLOW_START = date(2026, 1, 1)
COMPLETE_QUARTER_START = date(2026, 7, 1)
COMPLETE_QUARTER_END = date(2026, 9, 30)
MAX_SUSPENSION_PAGES = 15
PAGE_SIZE = 200
MINIMUM_REQUEST_INTERVAL_SECONDS = 2.2


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json_bytes(value) + b"\n"
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    return _sha(raw)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _plan_identity(plan: dict) -> str:
    identity = dict(plan)
    identity.pop("run_id", None)
    declared = identity.pop("plan_sha256", None)
    actual = _sha(canonical_json_bytes(identity))
    if declared != actual:
        raise ValueError("recording manifest hash does not match its frozen contents")
    return actual


def _rows(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "rows"):
            values = payload.get(key)
            if isinstance(values, list):
                return [row for row in values if isinstance(row, dict)]
    return []


def _redact_payload(value: Any) -> Any:
    forbidden = {"api_key", "token", "secret", "password", "authorization"}
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower().replace("-", "_") in forbidden else _redact_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    return value


class RecordingRun:
    def __init__(self, run_dir: Path, *, record: bool) -> None:
        self.run_dir = run_dir.resolve(strict=True)
        self.plan_path = self.run_dir / "recording_manifest.json"
        self.plan = _load_json(self.plan_path)
        self.plan_sha256 = _plan_identity(self.plan)
        self.run_id = self.plan["run_id"]
        self.state_path = self.run_dir / "run_state.json"
        self.receipt_path = self.run_dir / "run_receipt.json"
        if record and self.receipt_path.exists():
            previous_receipt = _load_json(self.receipt_path)
            if previous_receipt.get("status") == "INCOMPLETE":
                archive_dir = self.run_dir / "receipts"
                archive_dir.mkdir(parents=True, exist_ok=True)
                attempt_number = 1
                while (archive_dir / f"attempt-{attempt_number:02d}-incomplete.json").exists():
                    attempt_number += 1
                shutil.copy2(self.receipt_path, archive_dir / f"attempt-{attempt_number:02d}-incomplete.json")
        self.state = _load_json(self.state_path) if self.state_path.exists() else {
            "schema_version": "sectors-recording-state-v1",
            "run_id": self.run_id,
            "plan_sha256": self.plan_sha256,
            "session": None,
            "selected": {sector: list(selection["selected"]) for sector, selection in self.plan["selections"].items()},
            "replacements": {sector: [] for sector in self.plan["sectors"]},
            "failed_replacement_candidates": {sector: [] for sector in self.plan["sectors"]},
            "raw_response_hashes": {},
            "completed": [],
            "minimum_request_interval_seconds": MINIMUM_REQUEST_INTERVAL_SECONDS,
        }
        if self.state.get("run_id") != self.run_id or self.state.get("plan_sha256") != self.plan_sha256:
            raise ValueError("saved recording state belongs to a different pinned plan")
        self.state.setdefault("failed_replacement_candidates", {sector: [] for sector in self.plan["sectors"]})
        self.state.setdefault("minimum_request_interval_seconds", MINIMUM_REQUEST_INTERVAL_SECONDS)
        if self.state["minimum_request_interval_seconds"] != MINIMUM_REQUEST_INTERVAL_SECONDS:
            raise ValueError("saved request pacing differs from this recording run's pinned control")
        for sector in self.plan["sectors"]:
            self.state["failed_replacement_candidates"].setdefault(sector, [])
        self.budget = PersistentRequestBudget(
            self.run_dir / "request_budget.json", run_id=self.run_id, plan_sha256=self.plan_sha256,
        )
        self.receipt = {
            "schema_version": "sectors-recording-receipt-v1",
            "run_id": self.run_id,
            "plan_sha256": self.plan_sha256,
            "status": "PREFLIGHT_ONLY" if not record else "IN_PROGRESS",
            "session": self.state.get("session"),
            "sample_count": sum(map(len, self.state["selected"].values())),
            "replacements": self.state["replacements"],
            "request_budget": self.budget.snapshot(),
            "raw_response_hashes": self.state["raw_response_hashes"],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "api_credential_written": False,
            "minimum_request_interval_seconds": MINIMUM_REQUEST_INTERVAL_SECONDS,
        }
        self._save()
        self.market_path = Path(self.plan["market_release_source"]["path"]).resolve(strict=True)
        market_raw = self.market_path.read_bytes()
        if _sha(market_raw) != self.plan["market_release_source"]["sha256"]:
            raise ValueError("pinned market release source changed after preflight")
        self.market = _load_json(self.market_path)
        self.market_by_ticker = {row["ticker"]: row for row in self.market["records"]}
        self.ledger = RequestLedger(path=self.run_dir / "request_ledger.jsonl")
        self.client = None
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
                force_refresh=True,
                max_retries=2,
                min_request_interval_seconds=MINIMUM_REQUEST_INTERVAL_SECONDS,
                max_estimated_credits=MAX_CREDITS,
                max_http_requests=MAX_CALLS,
                budget_reserver=self.budget.reserve,
            )

    def _save(self) -> None:
        self.receipt["request_budget"] = self.budget.snapshot()
        self.receipt["session"] = self.state.get("session")
        self.receipt["sample_count"] = sum(map(len, self.state["selected"].values()))
        self.receipt["replacements"] = self.state["replacements"]
        self.receipt["raw_response_hashes"] = self.state["raw_response_hashes"]
        _write_json(self.state_path, self.state)
        _write_json(self.receipt_path, self.receipt)

    def fetch(self, relative_path: str, endpoint: str, params: dict) -> Any:
        path = self.run_dir / "responses" / relative_path
        if path.exists():
            envelope = _load_json(path)
            if envelope.get("request") != {"endpoint": endpoint, "parameters": params}:
                raise ValueError(f"saved response request does not match the frozen plan: {relative_path}")
            payload = envelope.get("response")
            if _sha(canonical_json_bytes(payload)) != envelope.get("response_sha256"):
                raise ValueError(f"saved raw response hash mismatch: {relative_path}")
            return payload
        if self.client is None:
            raise RuntimeError("live acquisition is disabled")
        try:
            response = self.client.get(endpoint, params, use_cache=False)
            payload = _redact_payload(response.payload)
            envelope = {
                "request": {"endpoint": endpoint, "parameters": params},
                "response_sha256": _sha(canonical_json_bytes(payload)),
                "response": payload,
            }
            digest = _write_json(path, envelope)
            self.state["raw_response_hashes"][relative_path] = digest
            return payload
        finally:
            self.ledger.flush()
            self._save()

    def resolve_session(self) -> date:
        if self.state.get("session"):
            return date.fromisoformat(self.state["session"])
        payload = self.fetch("session/latest-close.json", "/v2/close/", {"limit": 30, "offset": 0})
        dates = [date.fromisoformat(str(row["date"])[:10]) for row in _rows(payload) if row.get("date")]
        if not dates:
            raise ValueError("Sectors completed-session probe returned no dated close")
        session = max(dates)
        if session > date.today():
            raise ValueError("Sectors completed-session probe returned a future date")
        self.state["session"] = session.isoformat()
        self.receipt["status"] = "IN_PROGRESS"
        self._save()
        return session

    def _price_history(self, ticker: str, session: date) -> tuple[list[dict], list[dict]]:
        windows = _plan_windows(PRICE_START, session)
        if len(windows) > int(self.plan["window_schedule"]["maximum_windows_per_series"]):
            raise ValueError(f"price history needs {len(windows)} windows; pinned plan allows four")
        combined: list[dict] = []
        sources = []
        for index, (start, end) in enumerate(windows, 1):
            rel = f"prices/{ticker.replace('.', '_')}/{index:02d}_{start}_{end}.json"
            payload = self.fetch(rel, f"/v2/daily/{ticker}/", {"start": start.isoformat(), "end": end.isoformat()})
            frame = normalize_daily_history(payload, source="sectors")
            frame = frame[frame["ticker"] == ticker]
            rows = [{**row, "date": row["date"].isoformat()} for row in frame.to_dict(orient="records")]
            if any(not start.isoformat() <= row["date"] <= end.isoformat() for row in rows):
                raise ValueError(f"price response for {ticker} contains a date outside its requested window")
            combined.extend(rows)
            sources.append({"window": [start.isoformat(), end.isoformat()], "path": rel,
                            "sha256": self.state["raw_response_hashes"].get(rel)})
        dates = [row["date"] for row in combined]
        if len(dates) != len(set(dates)):
            raise ValueError(f"price history for {ticker} contains duplicate sessions")
        return sorted(combined, key=lambda row: row["date"]), sources

    def _acquire_prices_and_replacements(self, session: date) -> dict[str, dict]:
        series: dict[str, dict] = {}
        replacement_count = sum(map(len, self.state["replacements"].values()))
        for sector in self.plan["sectors"]:
            selected = list(self.state["selected"][sector])
            replacement_order = self.plan["selections"][sector]["replacement_order"]
            for ticker in selected:
                prices, source_rows = self._price_history(ticker, session)
                if any(row["date"] == session.isoformat() for row in prices):
                    series[ticker] = {"ticker": ticker, "sector": sector, "prices": prices, "price_sources": source_rows}
                    continue
                replaced = False
                while replacement_count < MAX_REPLACEMENTS:
                    tried = set(self.state["failed_replacement_candidates"][sector])
                    tried.update(item["selected"] for item in self.state["replacements"][sector])
                    next_ticker = next((candidate for candidate in replacement_order
                                        if candidate not in self.state["selected"][sector] and candidate not in tried), None)
                    if next_ticker is None:
                        break
                    replacement_prices, replacement_sources = self._price_history(next_ticker, session)
                    if any(row["date"] == session.isoformat() for row in replacement_prices):
                        replacement_count += 1
                        self.state["selected"][sector].remove(ticker)
                        self.state["selected"][sector].append(next_ticker)
                        self.state["replacements"][sector].append({"removed": ticker, "selected": next_ticker,
                                                                     "reason": "no close observation on the pinned session"})
                        series[next_ticker] = {"ticker": next_ticker, "sector": sector,
                                               "prices": replacement_prices, "price_sources": replacement_sources}
                        self._save()
                        replaced = True
                        break
                    self.state["failed_replacement_candidates"][sector].append(next_ticker)
                    self._save()
                if not replaced:
                    raise ValueError(f"no eligible replacement is available for {sector} after {ticker}")
        expected = {ticker for selected in self.state["selected"].values() for ticker in selected}
        for sector in self.plan["sectors"]:
            for ticker in self.state["selected"][sector]:
                if ticker not in series:
                    prices, source_rows = self._price_history(ticker, session)
                    if not any(row["date"] == session.isoformat() for row in prices):
                        raise ValueError(f"selected stock {ticker} lacks the pinned session close")
                    series[ticker] = {"ticker": ticker, "sector": sector, "prices": prices, "price_sources": source_rows}
        if set(series) != expected or len(series) != 66:
            raise ValueError("final price sample is not exactly 66 unique selected stocks")
        return series

    def _foreign_history(
        self, ticker: str, *, start: date, end: date, label: str,
        expected_sessions: set[str] | None = None,
    ) -> dict:
        windows = _plan_windows(start, end)
        if len(windows) > 4:
            raise ValueError(f"foreign flow for {ticker} needs more than four windows")
        all_rows = []
        source_rows = []
        null_value_dates: list[str] = []
        for index, (window_start, window_end) in enumerate(windows, 1):
            rel = f"{label}/{ticker.replace('.', '_')}/{index:02d}_{window_start}_{window_end}.json"
            payload = self.fetch(rel, f"/v2/foreign-flow/{ticker}/", {
                "start": window_start.isoformat(), "end": window_end.isoformat(),
            })
            frame = normalize_foreign_flow(payload)
            rows = []
            for row in frame.to_dict(orient="records"):
                if not row.get("date"):
                    continue
                observed_date = str(row["date"])[:10]
                if row.get("net_foreign_inflow") is None:
                    null_value_dates.append(observed_date)
                else:
                    rows.append({"date": observed_date, "net_foreign_inflow_idr": float(row["net_foreign_inflow"])})
            if any(not window_start.isoformat() <= row["date"] <= window_end.isoformat() for row in rows):
                raise ValueError(f"foreign-flow response for {ticker} contains dates outside its window")
            all_rows.extend(rows)
            source_rows.append({"window": [window_start.isoformat(), window_end.isoformat()], "path": rel,
                                "sha256": self.state["raw_response_hashes"].get(rel)})
        dates = [row["date"] for row in all_rows]
        if len(dates) != len(set(dates)):
            raise ValueError(f"foreign-flow history for {ticker} contains duplicate sessions")
        session_check = None
        if expected_sessions is not None:
            present = set(dates)
            session_check = {
                "expected_sessions": len(expected_sessions),
                "observed_sessions": len(present),
                "missing_sessions": sorted(expected_sessions - present),
                "unexpected_sessions": sorted(present - expected_sessions),
                "null_value_dates": sorted(set(null_value_dates)),
                "duplicates": 0,
            }
        return {"ticker": ticker, "unit": "IDR net foreign inflow", "start": start.isoformat(), "end": end.isoformat(),
                "values": sorted(all_rows, key=lambda row: row["date"]), "sources": source_rows,
                "session_check": session_check}

    def acquire(self) -> dict:
        session = self.resolve_session()
        target = str(self.plan["prepared_from_release_session"])
        if session < date.fromisoformat(target):
            raise ValueError(f"observed Sectors session {session.isoformat()} precedes the pinned membership release {target}")
        session_text = session.isoformat()
        stock_series = self._acquire_prices_and_replacements(session)
        price_start = date.fromisoformat(self.plan["window_schedule"]["price_start"])
        benchmark_values = []
        benchmark_sources = []
        for index, (start, end) in enumerate(_plan_windows(price_start, session), 1):
            rel = f"benchmark/IHSG/{index:02d}_{start}_{end}.json"
            payload = self.fetch(rel, "/v2/index-daily/ihsg/", {"start": start.isoformat(), "end": end.isoformat()})
            frame = normalize_index_daily(payload, benchmark_id="IHSG", source="sectors")
            rows = [{"date": row["date"].isoformat(), "close": float(row["close"]), "price_basis": "close"}
                    for row in frame.to_dict(orient="records")]
            benchmark_values.extend(rows)
            benchmark_sources.append({"window": [start.isoformat(), end.isoformat()], "path": rel,
                                      "sha256": self.state["raw_response_hashes"].get(rel)})
        benchmark_dates = [row["date"] for row in benchmark_values]
        if len(benchmark_dates) != len(set(benchmark_dates)) or session_text not in benchmark_dates:
            raise ValueError("native IHSG history has duplicate dates or misses the pinned session")
        benchmark_values.sort(key=lambda row: row["date"])

        recent_flow_start = max(FLOW_START, session - timedelta(days=89))
        recent_expected_sessions = {
            row["date"] for row in benchmark_values
            if recent_flow_start.isoformat() <= row["date"] <= session_text
        }
        for ticker in sorted(stock_series):
            stock_series[ticker]["foreign_flow"] = self._foreign_history(
                ticker, start=recent_flow_start, end=session, label="foreign_stock",
                expected_sessions=recent_expected_sessions,
            )
        market_flow = self._foreign_history("IHSG", start=FLOW_START, end=session, label="foreign_market")
        expected_market_sessions = {row["date"] for row in benchmark_values if FLOW_START.isoformat() <= row["date"] <= session_text}
        actual_market_sessions = {row["date"] for row in market_flow["values"]}
        missing_market_sessions = sorted(expected_market_sessions - actual_market_sessions)
        unexpected_market_sessions = sorted(actual_market_sessions - expected_market_sessions)
        diagnostic_source = None
        if missing_market_sessions:
            diagnostic_start = date.fromisoformat(missing_market_sessions[0])
            diagnostic_end = date.fromisoformat(missing_market_sessions[-1])
            if (diagnostic_end - diagnostic_start).days > 89:
                raise ValueError("missing market-flow dates span more than one documented request window")
            diagnostic_path = f"foreign_market_reconcile/IHSG/{diagnostic_start}_{diagnostic_end}.json"
            diagnostic_payload = self.fetch(diagnostic_path, "/v2/foreign-flow/IHSG/", {
                "start": diagnostic_start.isoformat(), "end": diagnostic_end.isoformat(),
            })
            diagnostic_frame = normalize_foreign_flow(diagnostic_payload)
            diagnostic_rows = [
                {"date": str(row["date"])[:10], "net_foreign_inflow_idr": float(row["net_foreign_inflow"])}
                for row in diagnostic_frame.to_dict(orient="records")
                if row.get("date") is not None and row.get("net_foreign_inflow") is not None
            ]
            diagnostic_dates = {row["date"] for row in diagnostic_rows}
            market_flow["values"].extend(
                row for row in diagnostic_rows
                if row["date"] in set(missing_market_sessions)
            )
            market_flow["values"].sort(key=lambda row: row["date"])
            if len({row["date"] for row in market_flow["values"]}) != len(market_flow["values"]):
                raise ValueError("market-flow reconciliation introduced duplicate sessions")
            market_flow["sources"].append({
                "window": [diagnostic_start.isoformat(), diagnostic_end.isoformat()],
                "path": diagnostic_path,
                "sha256": self.state["raw_response_hashes"].get(diagnostic_path),
                "role": "targeted check of dates omitted from the original YTD windows",
            })
            market_flow["missing_date_diagnostic"] = {
                "requested_start": diagnostic_start.isoformat(),
                "requested_end": diagnostic_end.isoformat(),
                "dates_recovered": sorted(set(missing_market_sessions) & diagnostic_dates),
                "dates_still_missing": sorted(set(missing_market_sessions) - diagnostic_dates),
                "source_path": diagnostic_path,
                "source_sha256": self.state["raw_response_hashes"].get(diagnostic_path),
            }
            actual_market_sessions = {row["date"] for row in market_flow["values"]}
            missing_market_sessions = sorted(expected_market_sessions - actual_market_sessions)
            unexpected_market_sessions = sorted(actual_market_sessions - expected_market_sessions)
            diagnostic_source = market_flow["missing_date_diagnostic"]
        if unexpected_market_sessions:
            raise ValueError(f"market foreign-flow series contains {len(unexpected_market_sessions)} dates outside the benchmark calendar")

        expected_q3_sessions = {
            row["date"] for row in benchmark_values
            if COMPLETE_QUARTER_START.isoformat() <= row["date"] <= COMPLETE_QUARTER_END.isoformat()
        }
        observed_q3_sessions = {
            row["date"] for row in market_flow["values"]
            if COMPLETE_QUARTER_START.isoformat() <= row["date"] <= COMPLETE_QUARTER_END.isoformat()
        }
        missing_q3_sessions = sorted(expected_q3_sessions - observed_q3_sessions)
        if missing_q3_sessions:
            raise ValueError(f"complete Q3 market-flow check failed: {len(missing_q3_sessions)} sessions are missing")
        market_flow["session_check"] = {
            "expected_sessions": len(expected_market_sessions),
            "observed_sessions": len(actual_market_sessions),
            "duplicates": 0,
            "missing": len(missing_market_sessions),
            "missing_dates": missing_market_sessions,
            "unexpected": 0,
            "unexpected_dates": [],
            "ytd_complete": not missing_market_sessions,
        }
        market_flow["complete_quarter"] = {
            "start": COMPLETE_QUARTER_START.isoformat(),
            "end": COMPLETE_QUARTER_END.isoformat(),
            "values": [row for row in market_flow["values"] if COMPLETE_QUARTER_START.isoformat() <= row["date"] <= COMPLETE_QUARTER_END.isoformat()],
            "session_check": {
                "expected_sessions": len(expected_q3_sessions),
                "observed_sessions": len(observed_q3_sessions),
                "missing": 0,
                "missing_dates": [],
                "duplicates": 0,
                "status": "PASS",
            },
        }

        for ticker, row in sorted(stock_series.items()):
            rel = f"corporate_actions/{ticker.replace('.', '_')}.json"
            payload = self.fetch(rel, f"/v2/company/corporate-actions/{ticker}/", {})
            row["corporate_actions"] = {"response": payload, "source": {"path": rel,
                "sha256": self.state["raw_response_hashes"].get(rel)}}

        suspension_pages = []
        suspension_page_count = 0
        for page in range(MAX_SUSPENSION_PAGES):
            offset = page * PAGE_SIZE
            rel = f"suspensions/page_{page + 1:02d}.json"
            payload = self.fetch(rel, "/v2/suspensions/", {
                "start": price_start.isoformat(), "end": session_text,
                "limit": PAGE_SIZE, "offset": offset,
            })
            rows = _rows(payload)
            suspension_page_count += 1
            suspension_pages.extend(rows)
            if len(rows) < PAGE_SIZE:
                break
        else:
            raise ValueError(f"suspension pagination exceeded the pinned {MAX_SUSPENSION_PAGES}-page allowance")

        relevant_tickers = set(stock_series)
        suspensions = [row for row in suspension_pages if str(row.get("symbol") or "").upper() in relevant_tickers]
        histories = []
        for ticker in sorted(stock_series):
            record = self.market_by_ticker.get(ticker, {})
            histories.append({
                "ticker": ticker,
                "company_name": record.get("company_name"),
                "sector": stock_series[ticker]["sector"],
                "membership_as_of": record.get("classification_as_of"),
                "market_cap_as_of": record.get("last_trade_date"),
                "market_cap_idr": record.get("market_cap"),
                "prices": stock_series[ticker]["prices"],
                "price_sources": stock_series[ticker]["price_sources"],
                "foreign_flow": stock_series[ticker]["foreign_flow"],
                "corporate_actions": stock_series[ticker]["corporate_actions"],
            })
        sector_counts = {sector: sum(row["sector"] == sector for row in histories) for sector in self.plan["sectors"]}
        if any(count != 6 for count in sector_counts.values()) or len(histories) != 66:
            raise ValueError("final Sectors sample does not contain exactly six names in every sector")
        raw_hashes = dict(sorted(self.state["raw_response_hashes"].items()))
        payload = {
            "schema_version": "sectors-recorded-sample-v1",
            "as_of": session_text,
            "label": "Recorded Sectors sample · 66 stocks",
            "scope": "Six preselected current-member common stocks in each of 11 IDX sectors; equal samples do not represent market capitalization weights.",
            "selection": {
                "basis": self.plan["selection_basis"],
                "membership_release_id": self.plan["selection_release_id"],
                "membership_release_manifest_sha256": self.plan["selection_release_manifest_sha256"],
                "membership_release_session": target,
                "membership_as_of": self.plan["membership_as_of"],
                "selected_market_cap_date": self.plan["selection_market_cap_date"],
                "stocks_per_sector": 6, "stock_count": 66,
                "sector_counts": sector_counts,
                "replacements": self.state["replacements"],
            },
            "price_history": {
                "start": price_start.isoformat(), "end": session_text,
                "basis": "Sectors daily close as returned; raw close is preserved. Corporate actions are attached by ticker and no adjusted-price series is claimed.",
                "benchmark": "Native Sectors IHSG close, same session windows",
                "ihsg": benchmark_values,
                "source_windows": benchmark_sources,
            },
            "foreign_flow": {
                "provider": "Sectors v2", "scope": "Market-wide IHSG and selected-stock recent samples",
                "unit": "IDR net foreign inflow; positive means net foreign buying",
                "market_ytd": market_flow,
                "stock_recent_start": recent_flow_start.isoformat(),
                "expected_market_sessions": sorted(expected_market_sessions),
                "session_check": market_flow["session_check"],
                "complete_quarter": market_flow["complete_quarter"],
            },
            "stocks": histories,
            "suspensions": {"requested_start": price_start.isoformat(), "requested_end": session_text,
                            "pages_fetched": suspension_page_count, "relevant_rows": suspensions},
            "validation": {
                "status": "PASS", "observed_session_not_before_membership_release": True,
                "membership_release_session": target,
                "observed_completed_session": session_text,
                "sector_count": 11, "six_per_sector": True, "unique_tickers": len({row["ticker"] for row in histories}) == 66,
                "price_windows_per_series": len(_plan_windows(price_start, session)),
                "max_calendar_days_per_window": 90,
                "native_ihsg_has_target_session": True,
                "market_flow_expected_sessions": len(expected_market_sessions),
                "market_flow_observed_sessions": len(actual_market_sessions),
                "market_flow_missing_sessions": missing_market_sessions,
                "market_flow_unexpected_sessions": unexpected_market_sessions,
                "market_flow_ytd_complete": not missing_market_sessions,
                "market_flow_missing_date_diagnostic": diagnostic_source,
                "market_flow_complete_quarter": market_flow["complete_quarter"]["session_check"],
                "canonical_submission_confirmation": "UNCHANGED; this file is a bounded descriptive sample",
            },
            "sources": {
                "recording_plan_sha256": self.plan_sha256,
                "market_release_source_sha256": self.plan["market_release_source"]["sha256"],
                "raw_responses": raw_hashes,
                "request_ledger_sha256": _sha((self.run_dir / "request_ledger.jsonl").read_bytes()) if (self.run_dir / "request_ledger.jsonl").exists() else None,
                "price_endpoint": "/v2/daily/{symbol}/",
                "ihsg_endpoint": "/v2/index-daily/ihsg/",
                "foreign_flow_endpoint": "/v2/foreign-flow/{symbol}/",
                "corporate_actions_endpoint": "/v2/company/corporate-actions/{symbol}/",
                "suspension_endpoint": "/v2/suspensions/",
            },
            "limitations": [
                "This is a selected sample, not a full-market foreign-flow panel.",
                f"Membership and market-cap ranking are pinned to the {target} submission release; acquired observations end on {session_text}.",
                "Sectors close is kept on its raw close basis; corporate actions are disclosed and returns are not split-adjusted.",
            ],
            "request_policy": {"minimum_interval_seconds": MINIMUM_REQUEST_INTERVAL_SECONDS,
                               "max_retries": 2, "persistent_reserve_before_each_attempt": True},
        }
        self.state["completed"] = ["session", "prices", "native_ihsg", "market_foreign_flow", "stock_foreign_flow", "corporate_actions", "suspensions", "sample_validation"]
        self.receipt["status"] = "ACQUISITIONS_VALIDATED"
        self.receipt["sample_sha256"] = _write_json(self.run_dir / "sectors_recorded_sample.json", payload)
        self.receipt["sample_path"] = str(self.run_dir / "sectors_recorded_sample.json")
        self.receipt["raw_archive_contents"] = "responses/**, recording_manifest.json, run_state.json, run_receipt.json, request_budget.json, request_ledger.jsonl"
        self._save()
        return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--record", action="store_true", help="Acquire fresh data; without this flag only print the pinned plan and current budget.")
    parser.add_argument("--allow-live", action="store_true", help="Required additional gate for live HTTP requests.")
    parser.add_argument("--allow-credit-spend", action="store_true", help="Required additional gate for the pinned 450-credit maximum.")
    args = parser.parse_args()
    run = None
    try:
        if args.record and not (args.allow_live and args.allow_credit_spend):
            raise ValueError("live recording requires both --allow-live and --allow-credit-spend")
        run = RecordingRun(args.run_dir, record=args.record)
        if not args.record:
            print(json.dumps({"status": "PREFLIGHT_ONLY", "run_id": run.run_id,
                              "planned_maximum": 450, "budget": run.budget.snapshot()}, sort_keys=True))
            return 0
        payload = run.acquire()
        print(json.dumps({"status": "PASS", "run_id": run.run_id, "as_of": payload["as_of"],
                          "stocks": len(payload["stocks"]), "budget": run.budget.snapshot(),
                          "sample": str(run.run_dir / "sectors_recorded_sample.json")}, sort_keys=True))
        return 0
    except Exception as exc:  # write a receipt for incomplete runs; no credential enters this report
        if run is not None:
            message = str(exc)
            secret = os.environ.get("SECTORS_API_KEY", "")
            if secret:
                message = message.replace(secret, "[redacted]")
            message = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", message)
            run.receipt["status"] = "INCOMPLETE"
            run.receipt["blocking_reason"] = message[:500]
            run._save()
        public_message = str(exc)
        secret = os.environ.get("SECTORS_API_KEY", "")
        if secret:
            public_message = public_message.replace(secret, "[redacted]")
        public_message = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", public_message)
        print(f"SECTORS_SAMPLE_INCOMPLETE: {public_message[:500]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
