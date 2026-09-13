"""Lightweight structured logging.

Avoids leaking secrets. Uses a stable key/value format suitable for both
console and log files.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any


_SECRET_KEYS = {"api_key", "token", "secret", "password", "authorization"}

# Fail-closed patterns for credential-shaped material in rendered log lines.
# The filter never sees raw secret values, so it redacts by shape:
#   key=value / key: value / "key": "value"  and  Bearer <token>.
_RE_KEY_VALUE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?[^\s'\",;}\]]+"
)
_RE_JSON_VALUE = re.compile(
    r'(?i)("(?:api[_-]?key|token|secret|password|authorization)"\s*:\s*")[^"]+(")'
)
_RE_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/=]+")


def _scrub_text(text: str) -> str:
    # Bearer first: otherwise the generic key=value rule consumes the
    # "Authorization:" prefix and leaves the token itself exposed.
    scrubbed = _RE_BEARER.sub("Bearer ***", text)
    scrubbed = _RE_JSON_VALUE.sub(r"\1***\2", scrubbed)
    scrubbed = _RE_KEY_VALUE.sub(lambda m: m.group(1) + "=***", scrubbed)
    return scrubbed


def _redact(record: logging.LogRecord) -> bool:
    """Mutate record to redact obvious secret-like fields if any are present."""
    try:
        msg = record.getMessage()
    except Exception:
        msg = str(record.msg)
    if not isinstance(msg, str):
        msg = str(msg)
    for key in _SECRET_KEYS:
        if key in msg.lower() and "=" in msg:
            # very simple: replace "<key>=<value>" with "<key>=***"
            idx = msg.lower().find(key + "=")
            if idx >= 0:
                end = msg.find(" ", idx)
                end = end if end > 0 else len(msg)
                msg = msg[: idx + len(key) + 1] + "***" + msg[end:]
    msg = _scrub_text(msg)
    record.msg = msg
    record.args = ()
    return True


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
        handler.addFilter(_redact)
        logger.addHandler(handler)
        logger.propagate = False
    if _redact not in getattr(logger, "filters", []):
        try:
            logger.addFilter(_redact)
        except Exception:
            pass
    return logger


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a structured event with key=value pairs."""
    parts = [event]
    for k, v in fields.items():
        if any(s in k.lower() for s in _SECRET_KEYS):
            v = "***"
        parts.append(f"{k}={v}")
    logger.info(" ".join(parts))
