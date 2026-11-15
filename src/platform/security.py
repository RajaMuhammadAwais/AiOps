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


class AuthorizationError(PermissionError):
    """Raised when an authenticated principal lacks a required scope."""


class CsrfError(AuthorizationError):
    """Raised when a gateway-authenticated unsafe request is cross-origin."""


class RateLimitExceeded(PermissionError):
    """Raised when a client exceeds the configured request budget."""


READ_SCOPE = "aiops:read"
ALERT_SILENCE_SCOPE = "aiops:alerts:silence"
THRESHOLDS_WRITE_SCOPE = "aiops:thresholds:write"
ALLOWED_SCOPES = frozenset({READ_SCOPE, ALERT_SILENCE_SCOPE, THRESHOLDS_WRITE_SCOPE})


@dataclass(frozen=True)
class Principal:
    """Authenticated identity and its explicitly granted AiOps scopes."""

    subject: str
    scopes: frozenset[str]
    auth_method: str


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


def authorize(request: Request, settings: Settings) -> Principal:
    """Authenticate a service key or a trusted gateway's user assertion."""
    gateway_token = request.headers.get("X-AiOps-Gateway-Token")
    if gateway_token is not None:
        if not settings.gateway_token or not hmac.compare_digest(
            gateway_token, settings.gateway_token
        ):
            raise AuthenticationError("Authentication required")
        subject = request.headers.get("X-AiOps-Principal", "").strip()
        raw_scopes = request.headers.get("X-AiOps-Scopes", "")
        scopes = frozenset(raw_scopes.split())
        if (
            not subject
            or len(subject) > 128
            or any(ord(char) < 32 for char in subject)
            or not scopes
            or not scopes.issubset(ALLOWED_SCOPES)
        ):
            raise AuthenticationError("Invalid trusted gateway identity")
        return Principal(subject, scopes, "gateway")

    supplied = request.headers.get("X-AiOps-API-Key", "")
    if not supplied:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
    if supplied:
        if not settings.api_key or not hmac.compare_digest(supplied, settings.api_key):
            raise AuthenticationError("Authentication required")
        return Principal("service-api-key", frozenset({READ_SCOPE}), "api_key")
    if settings.api_key or settings.gateway_token or settings.production:
        raise AuthenticationError("Authentication required")
    return Principal("anonymous", frozenset({READ_SCOPE}), "development")


def require_scope(principal: Principal, scope: str) -> None:
    """Require one exact scope; no write scope implies another permission."""
    if scope not in principal.scopes:
        raise AuthorizationError("Insufficient permissions")


def require_same_origin(request: Request, settings: Settings) -> None:
    """Require a configured Origin on gateway-authenticated unsafe requests."""
    origin = request.headers.get("Origin")
    if not origin or origin not in settings.allowed_origins:
        raise CsrfError("A same-origin request is required")


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
