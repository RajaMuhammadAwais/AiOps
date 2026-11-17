"""Deployment configuration for the AiOps service.

Runtime telemetry, alerting, and model integrations are deliberately required
through environment variables. The service does not synthesize operational data
when those integrations are absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Mapping, Tuple
from urllib.parse import parse_qsl, urlsplit


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


def _secret(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def _upstream_url(name: str) -> str | None:
    value = _optional(name)
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} is not a valid URL") from exc
    if parsed.username is not None or parsed.password is not None:
        raise ConfigurationError(f"{name} must not contain URL credentials")
    sensitive_query_keys = {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "bearer_token",
        "client_secret",
        "credential",
        "password",
        "refresh_token",
        "secret",
        "sig",
        "signature",
        "token",
    }
    if any(
        key.lower().replace("-", "_") in sensitive_query_keys
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise ConfigurationError(f"{name} must not contain credentials in its query")
    return value


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


@dataclass(frozen=True)
class UpstreamSettings:
    """One upstream's request policy; credentials are intentionally not repr'd."""

    timeout_seconds: int
    verify_tls: bool
    auth_type: str = "none"
    bearer_token: str | None = field(default=None, repr=False)
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, int)
            or not 1 <= self.timeout_seconds <= 60
        ):
            raise ConfigurationError(
                "Upstream timeout must be between 1 and 60 seconds"
            )
        if not isinstance(self.verify_tls, bool):
            raise ConfigurationError("Upstream TLS verification must be a boolean")
        if self.auth_type not in {"none", "bearer", "basic"}:
            raise ConfigurationError(
                "Upstream auth type must be none, bearer, or basic"
            )
        credentials_present = any(
            credential is not None
            for credential in (self.bearer_token, self.username, self.password)
        )
        if self.auth_type == "none" and credentials_present:
            raise ConfigurationError("Upstream credentials require an auth type")
        if self.auth_type == "bearer" and (
            not self.bearer_token
            or self.username is not None
            or self.password is not None
        ):
            raise ConfigurationError("Bearer auth requires only a bearer token")
        if self.auth_type == "basic" and (
            not self.username or not self.password or self.bearer_token is not None
        ):
            raise ConfigurationError("Basic auth requires only username and password")
        if self.bearer_token and any(char.isspace() for char in self.bearer_token):
            raise ConfigurationError("Bearer token must not contain whitespace")

    @property
    def headers(self) -> dict[str, str]:
        if self.auth_type == "bearer" and self.bearer_token:
            return {"Authorization": f"Bearer {self.bearer_token}"}
        return {}

    @property
    def basic_auth(self) -> tuple[str, str] | None:
        if self.auth_type == "basic" and self.username and self.password:
            return self.username, self.password
        return None


def _optional_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = _optional(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _optional_bool(name: str, default: bool) -> bool:
    value = _optional(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


def _upstream_settings(
    prefix: str, default_timeout: int, default_verify_tls: bool
) -> UpstreamSettings:
    auth_type = (_optional(f"{prefix}_AUTH_TYPE") or "none").lower()
    token = _secret(f"{prefix}_BEARER_TOKEN")
    username = _secret(f"{prefix}_USERNAME")
    password = _secret(f"{prefix}_PASSWORD")
    credentials_present = any(
        credential is not None for credential in (token, username, password)
    )
    if auth_type not in {"none", "bearer", "basic"}:
        raise ConfigurationError(f"{prefix}_AUTH_TYPE must be none, bearer, or basic")
    if auth_type == "none" and credentials_present:
        raise ConfigurationError(
            f"{prefix} credentials require bearer or basic authentication"
        )
    if auth_type == "bearer" and (
        not token or username is not None or password is not None
    ):
        raise ConfigurationError(
            f"{prefix} bearer authentication requires only a bearer token"
        )
    if auth_type == "basic" and (not username or not password or token is not None):
        raise ConfigurationError(
            f"{prefix} basic authentication requires username and password only"
        )
    if token and any(char.isspace() for char in token):
        raise ConfigurationError(f"{prefix}_BEARER_TOKEN must not contain whitespace")
    return UpstreamSettings(
        timeout_seconds=_optional_int(
            f"{prefix}_TIMEOUT_SECONDS", default_timeout, 1, 60
        ),
        verify_tls=_optional_bool(f"{prefix}_VERIFY_TLS", default_verify_tls),
        auth_type=auth_type,
        bearer_token=token,
        username=username,
        password=password,
    )


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
    api_key: str | None = field(repr=False)
    approval_url: str | None = field(repr=False)
    approval_api_key: str | None = field(repr=False)
    allowed_origins: Tuple[str, ...]
    prometheus_url: str | None = field(repr=False)
    alertmanager_url: str | None = field(repr=False)
    incidents_url: str | None = field(repr=False)
    logs_url: str | None = field(repr=False)
    actions_url: str | None = field(repr=False)
    insights_url: str | None = field(repr=False)
    thresholds_url: str | None = field(repr=False)
    status_query: str | None
    metrics_query: str | None
    anomalies_query: str | None
    llm_url: str | None = field(repr=False)
    llm_api_key: str | None = field(repr=False)
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
    gateway_token: str | None = field(default=None, repr=False)
    upstream_configs: Mapping[str, UpstreamSettings] = field(
        default_factory=dict, repr=False
    )

    @property
    def production(self) -> bool:
        return self.environment in {"production", "prod"}

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key or self.gateway_token)

    def upstream(self, name: str) -> UpstreamSettings:
        """Return request policy for an upstream, with legacy shared defaults."""
        configured = self.upstream_configs.get(name)
        if configured is not None:
            return configured
        if name == "llm" and self.llm_api_key:
            return UpstreamSettings(
                timeout_seconds=self.prometheus_timeout_seconds,
                verify_tls=self.verify_tls,
                auth_type="bearer",
                bearer_token=self.llm_api_key,
            )
        return UpstreamSettings(
            timeout_seconds=self.prometheus_timeout_seconds,
            verify_tls=self.verify_tls,
        )

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

        prometheus_url = _upstream_url("AIOPS_PROMETHEUS_URL")
        if environment in {"production", "prod"} and not prometheus_url:
            raise ConfigurationError(
                "AIOPS_PROMETHEUS_URL is required in production for shared SLO data"
            )

        api_key = _optional("AIOPS_API_KEY")
        if environment in {"production", "prod"} and (not api_key or len(api_key) < 24):
            raise ConfigurationError(
                "AIOPS_API_KEY of at least 24 characters is required in production"
            )
        if api_key and len(api_key) < 24:
            raise ConfigurationError("AIOPS_API_KEY must be at least 24 characters")

        gateway_token = _optional("AIOPS_GATEWAY_TOKEN")
        if gateway_token and len(gateway_token) < 32:
            raise ConfigurationError(
                "AIOPS_GATEWAY_TOKEN must be at least 32 characters"
            )

        approval_url = _optional("AIOPS_APPROVAL_URL")
        approval_api_key = _optional("AIOPS_APPROVAL_API_KEY")
        if approval_api_key and len(approval_api_key) < 24:
            raise ConfigurationError(
                "AIOPS_APPROVAL_API_KEY must be at least 24 characters"
            )
        if bool(approval_url) != bool(approval_api_key):
            raise ConfigurationError(
                "AIOPS_APPROVAL_URL and AIOPS_APPROVAL_API_KEY must be configured together"
            )
        if approval_url:
            parsed_approval_url = urlsplit(approval_url)
            if (
                parsed_approval_url.scheme != "https"
                or not parsed_approval_url.hostname
                or parsed_approval_url.username
                or parsed_approval_url.password
                or parsed_approval_url.query
                or parsed_approval_url.fragment
            ):
                raise ConfigurationError(
                    "AIOPS_APPROVAL_URL must use HTTPS without credentials, query, or fragment data"
                )

        log_level = _required("AIOPS_LOG_LEVEL").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("AIOPS_LOG_LEVEL is invalid")

        timeout_seconds = _as_int("AIOPS_PROMETHEUS_TIMEOUT_SECONDS", None, 1, 60)
        verify_tls = _as_bool("AIOPS_VERIFY_TLS", default=None)
        upstream_prefixes = {
            "prometheus": "AIOPS_PROMETHEUS",
            "alertmanager": "AIOPS_ALERTMANAGER",
            "incidents": "AIOPS_INCIDENTS",
            "logs": "AIOPS_LOGS",
            "actions": "AIOPS_ACTIONS",
            "insights": "AIOPS_INSIGHTS",
            "thresholds": "AIOPS_THRESHOLDS",
        }
        upstream_configs = {
            name: _upstream_settings(prefix, timeout_seconds, verify_tls)
            for name, prefix in upstream_prefixes.items()
        }
        return cls(
            environment=environment,
            service_name=_required("AIOPS_SERVICE_NAME"),
            version=_required("AIOPS_VERSION"),
            api_key=api_key,
            approval_url=approval_url,
            approval_api_key=approval_api_key,
            gateway_token=gateway_token,
            allowed_origins=_origins(),
            prometheus_url=prometheus_url,
            alertmanager_url=_upstream_url("AIOPS_ALERTMANAGER_URL"),
            incidents_url=_upstream_url("AIOPS_INCIDENTS_URL"),
            logs_url=_upstream_url("AIOPS_LOGS_URL"),
            actions_url=_upstream_url("AIOPS_ACTIONS_URL"),
            insights_url=_upstream_url("AIOPS_INSIGHTS_URL"),
            thresholds_url=_upstream_url("AIOPS_THRESHOLDS_URL"),
            status_query=_optional("AIOPS_STATUS_QUERY"),
            metrics_query=_optional("AIOPS_METRICS_QUERY"),
            anomalies_query=_optional("AIOPS_ANOMALIES_QUERY"),
            llm_url=_upstream_url("AIOPS_LLM_URL"),
            llm_api_key=_optional("AIOPS_LLM_API_KEY"),
            llm_model=_optional("AIOPS_LLM_MODEL"),
            prometheus_timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
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
            upstream_configs=upstream_configs,
        )
