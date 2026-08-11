"""Security primitives for the AiOps HTTP surface.

These helpers intentionally implement a small, dependency-light baseline.  A
production deployment should still place the service behind an identity-aware
reverse proxy or service mesh and use a durable audit sink.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import re
import threading
import time
from typing import Any, Deque, Dict, Mapping

from flask import Request

from .config import Settings

SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^\s,;]+"),
)


class RequestValidationError(ValueError):
    """Raised when a request payload violates the API contract."""


class AuthenticationError(PermissionError):
    """Raised when an API request is not authorized."""


class RateLimitExceeded(PermissionError):
    """Raised when a client exceeds the configured request budget."""


def redact(value: Any) -> Any:
    """Return a log-safe representation without exposing common secrets."""
    if isinstance(value, str):
        redacted = value
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        return redacted
    if isinstance(value, Mapping):
        return {str(key): redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def request_key(request: Request) -> str:
    """Use the direct peer address; do not trust spoofable forwarding headers."""
    return request.remote_addr or "unknown"


def authorize(request: Request, settings: Settings) -> None:
    """Enforce the configured API key using constant-time comparison."""
    if not settings.auth_enabled:
        return
    supplied = request.headers.get("X-AiOps-API-Key", "")
    if not supplied:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, settings.api_key or ""):
        raise AuthenticationError("Authentication required")


class SlidingWindowRateLimiter:
    """Thread-safe, process-local limiter suitable for a single web worker."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class AuditLog:
    """Bounded in-memory audit log with secret redaction.

    The log is intentionally append-only from the application perspective.
    Operators should export these events to a durable, access-controlled sink
    before enabling sensitive remediation workflows.
    """

    def __init__(self, max_entries: int = 5000) -> None:
        self._entries: Deque[dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def record(self, event: str, request_id: str, **details: Any) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "request_id": request_id,
            "details": redact(details),
        }
        with self._lock:
            self._entries.append(entry)
        return entry

    def snapshot(self, limit: int = 100) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 1000))
        with self._lock:
            return list(self._entries)[-bounded_limit:]


def validate_json_object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RequestValidationError("JSON object body required")
    return payload


def validate_query(payload: Mapping[str, Any], max_length: int) -> str:
    query = payload.get("query")
    if not isinstance(query, str):
        raise RequestValidationError("query must be a string")
    query = query.strip()
    if not query:
        raise RequestValidationError("query must not be empty")
    if len(query) > max_length:
        raise RequestValidationError(f"query exceeds the {max_length}-character limit")
    return query


def fingerprint(value: str) -> str:
    """Create a non-reversible identifier for audit correlation."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SecurityPolicy:
    """Public summary of controls applied to an AI request."""

    input_max_length: int
    secret_redaction_enabled: bool = True
    autonomous_actions_enabled: bool = False
    human_approval_required: bool = True
