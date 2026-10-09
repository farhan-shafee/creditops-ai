"""Sanitize diagnostic data and enforce bounded, fail-closed demo budgets."""

from __future__ import annotations

import hmac
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

REDACTED = "[REDACTED]"
SENSITIVE_KEYS = re.compile(
    r"(?i)(password|passwd|secret|(?:^|[_-])token(?:$|[_-])|authorization|api[_-]?key|database[_-]?url|email|account[_-]?id)"
)
PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r'(?i)\b(?:postgres(?:ql)?|mysql|mongodb)(?:\+[\w]+)?://[^\s<>"\x27]+'),
    re.compile(
        r'(?i)\b(?:api[_-]?key|password|passwd|secret|(?:access|refresh)[_-]?token)\s*[=:]\s*["\x27]?[^\s,"\x27}]+'
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


def sanitize(value: Any, _depth: int = 0) -> Any:
    """Preserve telemetry meaning, including injection text, while removing secrets."""
    if _depth > 12:
        return "[TRUNCATED]"
    if isinstance(value, str):
        result = value[:12000]
        for pattern in PATTERNS:
            result = pattern.sub(REDACTED, result)
        return result
    if isinstance(value, dict):
        return {
            str(key): REDACTED if SENSITIVE_KEYS.search(str(key)) else sanitize(item, _depth + 1)
            for key, item in list(value.items())[:100]
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item, _depth + 1) for item in value[:100]]
    return value


def authorize_admin(header: str | None, configured_key: str | None) -> bool:
    if not configured_key or not header or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header[7:].encode(), configured_key.encode())


class RateLimiter:
    """Single-instance sliding budget. Multi-replica deployments need shared storage."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10000,
    ):
        if limit < 1 or window_seconds <= 0 or max_keys < 1:
            raise ValueError("Rate-limit settings must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.max_keys = max_keys
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            expired = [
                identity
                for identity, entries in self._requests.items()
                if not entries or entries[-1] <= now - self.window_seconds
            ]
            for identity in expired:
                del self._requests[identity]
            if key not in self._requests and len(self._requests) >= self.max_keys:
                return False
            entries = self._requests.setdefault(key, deque())
            while entries and entries[0] <= now - self.window_seconds:
                entries.popleft()
            if len(entries) >= self.limit:
                return False
            entries.append(now)
            return True
