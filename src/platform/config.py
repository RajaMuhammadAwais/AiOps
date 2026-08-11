"""Deployment configuration for the AiOps service.

Runtime telemetry, alerting, and model integrations are deliberately required
through environment variables. The service does not synthesize operational data
when those integrations are absent.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Tuple


class ConfigurationError(ValueError):
    """Raised when a deployment configuration is invalid or incomplete."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
    return value


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _as_bool(name: str, default: bool | None = None) -> bool:
    value = os.getenv(name)
    if value is None:
        if default is None:
            raise ConfigurationError(f"{name} is required")
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


def _as_int(name: str, default: int | None, minimum: int, maximum: int) -> int:
    value = os.getenv(name)
    if value is None:
        if default is None:
            raise ConfigurationError(f"{name} is required")
        parsed = default
    else:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _as_float(
    name: str, default: float | None, minimum: float, maximum: float
) -> float:
    value = os.getenv(name)
    if value is None:
        if default is None:
            raise ConfigurationError(f"{name} is required")
        parsed = default
    else:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(f"{name} must be a number") from exc
    if not minimum <= parsed <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _origins() -> Tuple[str, ...]:
    value = _optional("AIOPS_ALLOWED_ORIGINS")
    if not value:
        return ()
    origins = tuple(item.strip() for item in value.split(",") if item.strip())
    if not origins or "*" in origins:
        raise ConfigurationError("AIOPS_ALLOWED_ORIGINS must contain explicit origins")
    return origins


@dataclass(frozen=True)
class Settings:
    environment: str
    service_name: str
    version: str
    api_key: str | None
    allowed_origins: Tuple[str, ...]
    prometheus_url: str | None
    alertmanager_url: str | None
    incidents_url: str | None
    logs_url: str | None
    actions_url: str | None
    insights_url: str | None
    thresholds_url: str | None
    status_query: str | None
    metrics_query: str | None
    anomalies_query: str | None
    llm_url: str | None
    llm_api_key: str | None
    llm_model: str | None
    prometheus_timeout_seconds: int
    verify_tls: bool
    max_query_length: int
    rate_limit_per_minute: int
    audit_log_max_entries: int
    event_store_max_entries: int
    slo_target: float
    slo_window_minutes: int
    refresh_seconds: int
    host: str
    port: int
    log_level: str

    @property
    def production(self) -> bool:
        return self.environment in {"production", "prod"}

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def integrations_configured(self) -> bool:
        return bool(self.prometheus_url or self.alertmanager_url)

    @classmethod
    def from_env(cls) -> "Settings":
        environment = _required("AIOPS_ENV").lower()
        if environment not in {
            "development",
            "dev",
            "test",
            "staging",
            "production",
            "prod",
        }:
            raise ConfigurationError(
                "AIOPS_ENV must be development, test, staging, or production"
            )

        api_key = _optional("AIOPS_API_KEY")
        if environment in {"production", "prod"} and (not api_key or len(api_key) < 24):
            raise ConfigurationError(
                "AIOPS_API_KEY of at least 24 characters is required in production"
            )
        if api_key and len(api_key) < 24:
            raise ConfigurationError("AIOPS_API_KEY must be at least 24 characters")

        log_level = _required("AIOPS_LOG_LEVEL").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("AIOPS_LOG_LEVEL is invalid")

        return cls(
            environment=environment,
            service_name=_required("AIOPS_SERVICE_NAME"),
            version=_required("AIOPS_VERSION"),
            api_key=api_key,
            allowed_origins=_origins(),
            prometheus_url=_optional("AIOPS_PROMETHEUS_URL"),
            alertmanager_url=_optional("AIOPS_ALERTMANAGER_URL"),
            incidents_url=_optional("AIOPS_INCIDENTS_URL"),
            logs_url=_optional("AIOPS_LOGS_URL"),
            actions_url=_optional("AIOPS_ACTIONS_URL"),
            insights_url=_optional("AIOPS_INSIGHTS_URL"),
            thresholds_url=_optional("AIOPS_THRESHOLDS_URL"),
            status_query=_optional("AIOPS_STATUS_QUERY"),
            metrics_query=_optional("AIOPS_METRICS_QUERY"),
            anomalies_query=_optional("AIOPS_ANOMALIES_QUERY"),
            llm_url=_optional("AIOPS_LLM_URL"),
            llm_api_key=_optional("AIOPS_LLM_API_KEY"),
            llm_model=_optional("AIOPS_LLM_MODEL"),
            prometheus_timeout_seconds=_as_int(
                "AIOPS_PROMETHEUS_TIMEOUT_SECONDS", None, 1, 60
            ),
            verify_tls=_as_bool("AIOPS_VERIFY_TLS", default=None),
            max_query_length=_as_int("AIOPS_MAX_QUERY_LENGTH", None, 32, 10000),
            rate_limit_per_minute=_as_int(
                "AIOPS_RATE_LIMIT_PER_MINUTE", None, 1, 10000
            ),
            audit_log_max_entries=_as_int(
                "AIOPS_AUDIT_LOG_MAX_ENTRIES", None, 100, 100000
            ),
            event_store_max_entries=_as_int(
                "AIOPS_EVENT_STORE_MAX_ENTRIES", None, 100, 100000
            ),
            slo_target=_as_float("AIOPS_SLO_TARGET", None, 90.0, 100.0),
            slo_window_minutes=_as_int("AIOPS_SLO_WINDOW_MINUTES", None, 5, 10080),
            refresh_seconds=_as_int("AIOPS_REFRESH_SECONDS", None, 5, 3600),
            host=_required("AIOPS_HOST"),
            port=_as_int("AIOPS_PORT", None, 1, 65535),
            log_level=log_level,
        )
