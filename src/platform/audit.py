"""Versioned audit-event contracts for operational actions.

This module defines the data contract only. It does not claim durable storage,
provide a production fallback, or select a storage vendor. A deployment must
supply an :class:`AuditSink` implementation before sensitive writes can be
considered durably audited.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
import hashlib
import hmac
import json
import re
from typing import Any, Mapping, Protocol

SCHEMA_VERSION = "1.0"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^\s,;]+"),
)


class AuditEventValidationError(ValueError):
    """Raised when an audit event violates its contract."""


class AuditSinkUnavailable(RuntimeError):
    """Raised when an audit event cannot be accepted by the configured sink."""


class AuditSink(Protocol):
    """Storage-neutral interface for accepting a validated audit event."""

    def append(self, event: "AuditEvent") -> None:
        """Accept an event or raise an explicit sink error."""


def redact(value: Any) -> Any:
    """Return a JSON-compatible value with common secret forms redacted."""
    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        return redacted
    if isinstance(value, Mapping):
        return {str(key): redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise AuditEventValidationError(
        f"audit details contain unsupported value type: {type(value).__name__}"
    )


def _validate_required_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditEventValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _validate_timestamp(value: str) -> str:
    timestamp = _validate_required_text("occurred_at", value)
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditEventValidationError(
            "occurred_at must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuditEventValidationError("occurred_at must include a timezone")
    return timestamp


def _canonical_json(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise AuditEventValidationError(
            "audit event contains values that cannot be serialized as JSON"
        ) from exc


@dataclass(frozen=True)
class AuditEvent:
    """Immutable, redacted, hashable audit event.

    ``previous_digest`` links the event to the preceding event in a stream.
    The digest supplies tamper evidence for the canonical event payload; it is
    not a substitute for durable storage, signatures, or access control.
    """

    event_id: str
    schema_version: str
    occurred_at: str
    event_type: str
    request_id: str
    actor: str
    tenant: str
    environment: str
    outcome: str
    details: Mapping[str, Any] = field(default_factory=dict)
    previous_digest: str | None = None
    digest: str = ""

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        occurred_at: str,
        event_type: str,
        request_id: str,
        actor: str,
        tenant: str,
        environment: str,
        outcome: str,
        details: Mapping[str, Any] | None = None,
        previous_digest: str | None = None,
        schema_version: str = SCHEMA_VERSION,
    ) -> "AuditEvent":
        validated_schema_version = _validate_required_text(
            "schema_version", schema_version
        )
        event = cls(
            event_id=_validate_required_text("event_id", event_id),
            schema_version=validated_schema_version,
            occurred_at=_validate_timestamp(occurred_at),
            event_type=_validate_required_text("event_type", event_type),
            request_id=_validate_required_text("request_id", request_id),
            actor=_validate_required_text("actor", actor),
            tenant=_validate_required_text("tenant", tenant),
            environment=_validate_required_text("environment", environment),
            outcome=_validate_required_text("outcome", outcome),
            details=redact(details or {}),
            previous_digest=previous_digest,
        )
        if event.previous_digest is not None:
            _validate_required_text("previous_digest", event.previous_digest)
        return replace(event, digest=event.compute_digest())

    def payload(self) -> dict[str, Any]:
        """Return the canonical digest input without the digest itself."""
        return {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at,
            "event_type": self.event_type,
            "request_id": self.request_id,
            "actor": self.actor,
            "tenant": self.tenant,
            "environment": self.environment,
            "outcome": self.outcome,
            "details": self.details,
            "previous_digest": self.previous_digest,
        }

    def compute_digest(self) -> str:
        """Compute the SHA-256 digest of the canonical protected payload."""
        canonical = _canonical_json(self.payload()).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def verify(self) -> bool:
        """Verify that the event digest matches its protected payload."""
        if not self.digest:
            return False
        return hmac.compare_digest(self.digest, self.compute_digest())

    def serialize(self) -> str:
        """Serialize the complete event deterministically as JSON."""
        if not self.verify():
            raise AuditEventValidationError("audit event digest is invalid")
        return _canonical_json({**self.payload(), "digest": self.digest})
