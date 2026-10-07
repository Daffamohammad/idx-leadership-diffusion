"""Crash-safe request and credit reservations for one recorded API run."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading
from datetime import datetime, timezone

from ..utils.errors import CreditBudgetExceeded


class PersistentRequestBudget:
    """Reserve each paid HTTP attempt durably before it is sent.

    The budget file belongs to one pinned recording manifest. A separate lock
    file serializes reservations across processes; atomic replacement makes a
    completed reservation survive a crash and a later resume.
    """

    SCHEMA = "sectors-recording-budget-v1"

    def __init__(self, path: Path, *, run_id: str, plan_sha256: str) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.run_id = run_id
        self.plan_sha256 = plan_sha256
        self._thread_lock = threading.Lock()

    @classmethod
    def create(
        cls,
        path: Path,
        *,
        run_id: str,
        plan_sha256: str,
        max_requests: int,
        max_credits: float,
        initial_reservations: list[dict] | None = None,
        inherited_budget: dict | None = None,
    ) -> "PersistentRequestBudget":
        if max_requests < 1 or max_credits < 1:
            raise ValueError("recording budget must have positive request and credit limits")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        budget = cls(path, run_id=run_id, plan_sha256=plan_sha256)
        reservations = list(initial_reservations or [])
        if any(not isinstance(row, dict) for row in reservations):
            raise ValueError("inherited reservations must be objects")
        inherited_count = len(reservations)
        inherited_credits = sum(float(row.get("estimated_credits", 0)) for row in reservations)
        if inherited_count > max_requests or inherited_credits > max_credits + 1e-9:
            raise ValueError("inherited reservations already exceed the successor budget")
        if inherited_budget is not None and not isinstance(inherited_budget, dict):
            raise ValueError("inherited budget provenance must be an object")
        with budget._locked_file():
            if path.exists():
                raise FileExistsError(f"recording budget already exists: {path}")
            state = {
                "schema_version": cls.SCHEMA,
                "run_id": run_id,
                "plan_sha256": plan_sha256,
                "max_requests": int(max_requests),
                "max_credits": float(max_credits),
                "requests_reserved": inherited_count,
                "credits_reserved": round(inherited_credits, 6),
                "reservations": reservations,
            }
            if inherited_budget is not None:
                state["inherited_budget"] = dict(inherited_budget)
            budget._write(state)
        return budget

    @contextmanager
    def _locked_file(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            with self.lock_path.open("a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read(self) -> dict:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CreditBudgetExceeded("persistent recording budget cannot be read") from exc
        if (
            state.get("schema_version") != self.SCHEMA
            or state.get("run_id") != self.run_id
            or state.get("plan_sha256") != self.plan_sha256
        ):
            raise CreditBudgetExceeded("persistent budget does not match the pinned recording plan")
        return state

    def _write(self, state: dict) -> None:
        payload = json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n"
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_name, self.path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def reserve(self, endpoint: str, estimated_credits: float) -> None:
        if estimated_credits < 0:
            raise ValueError("estimated credit reservation cannot be negative")
        with self._locked_file():
            state = self._read()
            request_count = int(state["requests_reserved"])
            credit_total = float(state["credits_reserved"])
            if request_count + 1 > int(state["max_requests"]):
                raise CreditBudgetExceeded(
                    f"persistent request ceiling reached ({request_count}/{state['max_requests']})"
                )
            proposed_credits = credit_total + float(estimated_credits)
            if proposed_credits > float(state["max_credits"]) + 1e-9:
                raise CreditBudgetExceeded(
                    f"persistent credit ceiling reached ({credit_total:.2f}+{estimated_credits:.2f}/{state['max_credits']:.2f})"
                )
            state["requests_reserved"] = request_count + 1
            state["credits_reserved"] = round(proposed_credits, 6)
            state["reservations"].append({
                "sequence": request_count + 1,
                "endpoint": endpoint.split("?", 1)[0],
                "estimated_credits": float(estimated_credits),
                "reserved_at": datetime.now(timezone.utc).isoformat(),
            })
            self._write(state)

    def snapshot(self) -> dict:
        with self._locked_file():
            state = self._read()
        return {
            "requests_reserved": int(state["requests_reserved"]),
            "credits_reserved": float(state["credits_reserved"]),
            "max_requests": int(state["max_requests"]),
            "max_credits": float(state["max_credits"]),
        }


__all__ = ["PersistentRequestBudget"]
