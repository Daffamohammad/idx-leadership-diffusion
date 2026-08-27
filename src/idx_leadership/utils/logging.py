"""Lightweight structured logging.

Avoids leaking secrets. Uses a stable key/value format suitable for both
console and log files.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any


_SECRET_KEYS = {"api_key", "token", "secret", "password", "authorization"}


def _redact(record: logging.LogRecord) -> None:
    """Mutate record to redact obvious secret-like fields if any are present."""
    msg = record.getMessage()
    lowered = msg.lower()
    for key in _SECRET_KEYS:
        if key in lowered and "=" in msg:
            # very simple: replace "<key>=<value>" with "<key>=***"
            idx = msg.lower().find(key + "=")
            if idx >= 0:
                end = msg.find(" ", idx)
                end = end if end > 0 else len(msg)
                msg = msg[: idx + len(key) + 1] + "***" + msg[end:]
    record.msg = msg
    record.args = ()


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger. Idempotent across calls."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)

        handler = logging.StreamHandler(sys.stderr)
        fmt = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a structured event with key=value pairs."""
    parts = [event]
    for k, v in fields.items():
        if any(s in k.lower() for s in _SECRET_KEYS):
            v = "***"
        parts.append(f"{k}={v}")
    logger.info(" ".join(parts))
