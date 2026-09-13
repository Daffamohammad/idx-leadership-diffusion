"""Agent B — concurrency tests for the owned RequestLedger.

Threads hammer record()/flush(); the ledger must keep exact entry counts
(lock added to the owned file) and a reader during writes must never observe
a torn in-memory view or raise. Flush-file readers tolerate partial lines.
"""
from __future__ import annotations

import json
import threading

from idx_leadership.providers.ledger import RequestLedger


def test_concurrent_record_keeps_exact_count():
    ledger = RequestLedger(path="/tmp/adv_ledger_never_flushed.jsonl")
    threads = [
        threading.Thread(
            target=lambda wid=i: [
                ledger.record(
                    provider="p", endpoint="/e", request_type="GET",
                    parameters={"w": wid, "i": j}, cache_hit=False,
                    status="ok", rows_returned=1, elapsed_ms=0.1,
                )
                for j in range(50)
            ]
        )
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ledger.entries()) == 8 * 50


def test_concurrent_record_and_flush_keeps_exact_total(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = RequestLedger(path=path)
    stop = threading.Event()
    errors: list[BaseException] = []

    def writer(wid: int):
        try:
            for j in range(100):
                ledger.record(
                    provider="p", endpoint="/e", request_type="GET",
                    parameters={"w": wid, "i": j}, cache_hit=False,
                    status="ok", rows_returned=1, elapsed_ms=0.1,
                )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def flusher():
        try:
            while not stop.is_set():
                ledger.flush()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    writers = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    flushers = [threading.Thread(target=flusher) for _ in range(2)]
    for t in writers + flushers:
        t.start()
    for t in writers:
        t.join()
    stop.set()
    for t in flushers:
        t.join()
    ledger.flush()
    assert not errors
    total = len(ledger.entries())
    on_disk = 0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                json.loads(line)
                on_disk += 1
            except json.JSONDecodeError:
                continue  # torn trailing line tolerated by readers
    assert total + on_disk == 4 * 100


def test_reader_during_write_never_raises(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = RequestLedger(path=path)
    stop = threading.Event()
    errors: list[BaseException] = []

    def writer():
        try:
            for j in range(300):
                ledger.record(
                    provider="p", endpoint="/e", request_type="GET",
                    parameters={"i": j}, cache_hit=False,
                    status="ok", rows_returned=1, elapsed_ms=0.1,
                )
                if j % 25 == 0:
                    ledger.flush()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def reader():
        try:
            while not stop.is_set():
                _ = ledger.entries()
                if path.exists():
                    for line in path.read_text(encoding="utf-8").splitlines():
                        try:
                            json.loads(line)
                        except json.JSONDecodeError:
                            continue  # partial line tolerated
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    wt = threading.Thread(target=writer)
    rt = threading.Thread(target=reader)
    wt.start()
    rt.start()
    wt.join()
    stop.set()
    rt.join()
    assert not errors
