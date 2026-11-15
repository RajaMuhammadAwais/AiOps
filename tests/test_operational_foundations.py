"""Route-level tests for the injectable Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import pytest
import requests
from werkzeug.test import Client
from werkzeug.wrappers import Response

import web_dashboard
from src.platform.config import ConfigurationError, Settings
from src.platform.integrations import IntegrationUnavailable
from src.platform.security import (
    ALERT_SILENCE_SCOPE,
    READ_SCOPE,
    THRESHOLDS_WRITE_SCOPE,
)
from web_dashboard import DashboardDependencies, create_app

GATEWAY_TOKEN = "g" * 40
TEST_ORIGIN = "http://test.invalid"


def gateway_headers(
    *scopes: str,
    origin: str | None = TEST_ORIGIN,
    principal: str = "operator-1",
) -> dict[str, str]:
    headers = {
        "X-AiOps-Gateway-Token": GATEWAY_TOKEN,
        "X-AiOps-Principal": principal,
        "X-AiOps-Scopes": " ".join(scopes),
    }
    if origin is not None:
        headers["Origin"] = origin
    return headers


class FakePrometheus:
    def __init__(
        self, result: list[dict[str, Any]] | None = None, error: Exception | None = None
    ):
        self.result = result or []
        self.error = error
        self.queries: list[str | None] = []

    def query(self, expression: str | None) -> list[dict[str, Any]]:
        self.queries.append(expression)
        if self.error:
            raise self.error
        return self.result


class FakeAlertmanager:
    def __init__(self, alerts: list[dict[str, Any]] | None = None):
        self.alerts = alerts or []
        self.silences: list[tuple[list[dict[str, Any]], int, str, str]] = []

    def active_alerts(self) -> list[dict[str, Any]]:
        return self.alerts

    def create_silence(
        self,
        matchers: list[dict[str, Any]],
        duration_minutes: int,
        comment: str,
        created_by: str,
    ) -> dict[str, Any]:
        self.silences.append((matchers, duration_minutes, comment, created_by))
        return {"silence_id": "silence-1", "ends_at": "2030-01-01T00:00:00Z"}


class FakeModel:
    def __init__(self, response: dict[str, Any] | None = None):
        self.response = response or {
            "response": "based on supplied context",
            "model": "test-model",
        }
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def answer(self, query: str, context: Mapping[str, Any]) -> dict[str, Any]:
        self.calls.append((query, context))
        return self.response


class FakeResponse:
    def __init__(self, payload: Any, *, fail: bool = False):
        self.payload = payload
        self.fail = fail

    def raise_for_status(self) -> None:
        if self.fail:
            raise RuntimeError("upstream failure")

    def json(self) -> Any:
        return self.payload


class FakeHttp:
    def __init__(self, payload: Any = None, *, error: Exception | None = None):
        self.payload = {"accepted": True} if payload is None else payload
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        timeout: int,
        verify: bool,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "json": json,
                "timeout": timeout,
                "verify": verify,
            }
        )
        if self.error:
            raise self.error
        return FakeResponse(self.payload)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "service_name": "aiops-test",
        "version": "test-version",
        "api_key": None,
        "gateway_token": None,
        "allowed_origins": (TEST_ORIGIN,),
        "prometheus_url": None,
        "alertmanager_url": None,
        "incidents_url": None,
        "logs_url": None,
        "actions_url": None,
        "insights_url": None,
        "thresholds_url": None,
        "status_query": None,
        "metrics_query": None,
        "anomalies_query": None,
        "llm_url": None,
        "llm_api_key": None,
        "llm_model": None,
        "prometheus_timeout_seconds": 5,
        "verify_tls": True,
        "max_query_length": 2000,
        "rate_limit_per_minute": 120,
        "audit_log_max_entries": 500,
        "event_store_max_entries": 200,
        "slo_target": 99.5,
        "slo_window_minutes": 60,
        "refresh_seconds": 30,
        "host": "127.0.0.1",
        "port": 5000,
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(**values)


def make_client(
    *,
    settings: Settings | None = None,
    prometheus: FakePrometheus | None = None,
    alertmanager: FakeAlertmanager | None = None,
    model: FakeModel | None = None,
    http: FakeHttp | None = None,
):
    app = create_app(
        settings or make_settings(),
        dependencies=DashboardDependencies(
            prometheus=prometheus,
            alertmanager=alertmanager,
            model=model,
            http=http,
        ),
    )
    return app.test_client()


def test_factory_import_is_environment_independent_and_wsgi_target_is_callable():
    env = {"PATH": os.environ.get("PATH", "")}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import web_dashboard; assert callable(web_dashboard.app)",
        ],
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_apps_use_independent_settings_dependencies_and_runtime_state():
    first_prometheus = FakePrometheus([{"name": "up", "value": 1}])
    second_prometheus = FakePrometheus([{"name": "up", "value": 0}])
    first = create_app(
        make_settings(service_name="first", status_query="up"),
        dependencies=DashboardDependencies(prometheus=first_prometheus),
    )
    second = create_app(
        make_settings(service_name="second", status_query="up"),
        dependencies=DashboardDependencies(prometheus=second_prometheus),
    )

    assert first.test_client().get("/health/live").get_json()["service"] == "first"
    assert second.test_client().get("/health/live").get_json()["service"] == "second"
    assert (
        first.extensions["aiops"].metrics_registry
        is not second.extensions["aiops"].metrics_registry
    )
    assert first.test_client().get("/api/status").get_json()["samples"] == [
        {"name": "up", "value": 1}
    ]
    assert second.test_client().get("/api/status").get_json()["samples"] == [
        {"name": "up", "value": 0}
    ]


def test_wsgi_lazy_entry_point_builds_app_through_factory(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = make_settings(service_name="wsgi-test")
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(web_dashboard, "configure_logging", lambda _level: None)
    wsgi_app = web_dashboard.LazyWSGIApplication()
    assert wsgi_app._application is None

    response = Client(wsgi_app, Response).get("/health/live")

    assert response.status_code == 200
    assert response.json["service"] == "wsgi-test"
    assert wsgi_app._application is not None


def test_liveness_and_request_id_are_available_without_dependencies():
    response = make_client().get(
        "/health/live", headers={"X-Request-ID": "req 123/abc"}
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "alive"
    assert response.headers["X-Request-ID"] == "req123abc"


def test_readiness_reports_missing_dependencies_and_successful_dependencies():
    missing = make_client().get("/health/ready")
    assert missing.status_code == 503
    assert missing.get_json()["status"] == "not_ready"
    assert "AIOPS_PROMETHEUS_URL" in missing.get_json()["missing"]

    prometheus = FakePrometheus([])
    alertmanager = FakeAlertmanager([])
    ready = make_client(
        settings=make_settings(
            prometheus_url="https://prometheus.test",
            alertmanager_url="https://alertmanager.test",
            status_query="up",
        ),
        prometheus=prometheus,
        alertmanager=alertmanager,
    ).get("/health/ready")
    assert ready.status_code == 200
    assert ready.get_json()["status"] == "ready"
    assert prometheus.queries == ["up"]


def test_readiness_maps_unavailable_upstream_to_503():
    response = make_client(
        settings=make_settings(
            prometheus_url="https://prometheus.test",
            alertmanager_url="https://alertmanager.test",
            status_query="up",
        ),
        prometheus=FakePrometheus(error=IntegrationUnavailable("connection failed")),
    ).get("/health/ready")

    assert response.status_code == 503
    assert response.get_json()["status"] == "not_ready"


def test_api_authentication_requires_configured_key_and_accepts_valid_key():
    settings = make_settings(api_key="k" * 24, status_query="up")
    client = make_client(settings=settings, prometheus=FakePrometheus([]))

    denied = client.get("/api/status")
    allowed = client.get("/api/status", headers={"X-AiOps-API-Key": "k" * 24})

    assert denied.status_code == 401
    assert denied.get_json()["error"]["code"] == "authentication_required"
    assert allowed.status_code == 200


def test_gateway_authentication_does_not_confuse_cors_with_authentication():
    client = make_client(
        settings=make_settings(gateway_token=GATEWAY_TOKEN, status_query="up"),
        prometheus=FakePrometheus([]),
    )

    unauthenticated = client.get("/api/status", headers={"Origin": TEST_ORIGIN})
    authenticated = client.get("/api/status", headers=gateway_headers(READ_SCOPE))

    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["Access-Control-Allow-Origin"] == TEST_ORIGIN
    assert authenticated.status_code == 200


def test_public_health_remains_available_when_gateway_auth_is_enabled():
    client = make_client(settings=make_settings(gateway_token=GATEWAY_TOKEN))

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert ready.status_code == 503
    assert ready.get_json()["status"] == "not_ready"


def test_gateway_token_configuration_requires_a_long_secret(
    monkeypatch: pytest.MonkeyPatch,
):
    required = {
        "AIOPS_ENV": "test",
        "AIOPS_SERVICE_NAME": "aiops-test",
        "AIOPS_VERSION": "test-version",
        "AIOPS_LOG_LEVEL": "INFO",
        "AIOPS_PROMETHEUS_TIMEOUT_SECONDS": "5",
        "AIOPS_VERIFY_TLS": "true",
        "AIOPS_MAX_QUERY_LENGTH": "2000",
        "AIOPS_RATE_LIMIT_PER_MINUTE": "120",
        "AIOPS_AUDIT_LOG_MAX_ENTRIES": "500",
        "AIOPS_EVENT_STORE_MAX_ENTRIES": "200",
        "AIOPS_SLO_TARGET": "99.5",
        "AIOPS_SLO_WINDOW_MINUTES": "60",
        "AIOPS_REFRESH_SECONDS": "30",
        "AIOPS_HOST": "127.0.0.1",
        "AIOPS_PORT": "5000",
        "AIOPS_API_KEY": "",
        "AIOPS_ALLOWED_ORIGINS": "",
    }
    for name, value in required.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("AIOPS_GATEWAY_TOKEN", "short")

    with pytest.raises(ConfigurationError, match="AIOPS_GATEWAY_TOKEN"):
        Settings.from_env()

    monkeypatch.setenv("AIOPS_GATEWAY_TOKEN", GATEWAY_TOKEN)
    assert Settings.from_env().auth_enabled


def test_api_key_is_read_only_and_cannot_authorize_mutation():
    client = make_client(
        settings=make_settings(api_key="k" * 24, gateway_token=GATEWAY_TOKEN)
    )

    response = client.post(
        "/api/suppress-alert",
        json={"alert_id": "alert-1", "duration": 5, "comment": "approved"},
        headers={"X-AiOps-API-Key": "k" * 24, "Origin": TEST_ORIGIN},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_gateway_scopes_are_granular_and_writes_require_same_origin():
    alertmanager = FakeAlertmanager([{"id": "alert-1"}])
    client = make_client(
        settings=make_settings(gateway_token=GATEWAY_TOKEN),
        alertmanager=alertmanager,
        http=FakeHttp({"updated": True}),
    )
    payload = {"alert_id": "alert-1", "duration": 5, "comment": "approved"}

    read_only = client.post(
        "/api/suppress-alert", json=payload, headers=gateway_headers(READ_SCOPE)
    )
    wrong_scope = client.post(
        "/api/suppress-alert",
        json=payload,
        headers=gateway_headers(THRESHOLDS_WRITE_SCOPE),
    )
    missing_origin = client.post(
        "/api/suppress-alert",
        json=payload,
        headers=gateway_headers(ALERT_SILENCE_SCOPE, origin=None),
    )
    foreign_origin = client.post(
        "/api/suppress-alert",
        json=payload,
        headers=gateway_headers(ALERT_SILENCE_SCOPE, origin="https://evil.invalid"),
    )
    authorized = client.post(
        "/api/suppress-alert",
        json=payload,
        headers=gateway_headers(ALERT_SILENCE_SCOPE),
    )
    cross_action = client.post(
        "/api/set-thresholds",
        json={"cpu": 80, "mem": 85, "disk": 90},
        headers=gateway_headers(ALERT_SILENCE_SCOPE),
    )

    assert read_only.status_code == 403
    assert wrong_scope.status_code == 403
    assert missing_origin.status_code == 403
    assert missing_origin.get_json()["error"]["code"] == "csrf_failed"
    assert foreign_origin.status_code == 403
    assert foreign_origin.get_json()["error"]["code"] == "csrf_failed"
    assert authorized.status_code == 200
    assert cross_action.status_code == 403
    assert len(alertmanager.silences) == 1


def test_gateway_claims_need_valid_secret_and_known_scope_names():
    client = make_client(settings=make_settings(gateway_token=GATEWAY_TOKEN))

    invalid_token = client.get(
        "/api/status",
        headers={**gateway_headers(READ_SCOPE), "X-AiOps-Gateway-Token": "wrong"},
    )
    unknown_scope = client.get("/api/status", headers=gateway_headers("admin"))

    assert invalid_token.status_code == 401
    assert unknown_scope.status_code == 401


def test_query_validation_and_successful_fake_model_request():
    model = FakeModel()
    client = make_client(model=model)

    missing = client.post("/api/query", json={})
    blank = client.post("/api/query", json={"query": "   "})
    successful = client.post("/api/query", json={"query": "summarize status"})

    assert missing.status_code == 400
    assert blank.status_code == 400
    assert successful.status_code == 200
    assert successful.get_json()["response"] == "based on supplied context"
    assert model.calls == [("summarize status", {})]
    audit = client.get("/api/audit").get_json()["events"]
    assert audit[-1]["event"] == "ai_query"
    assert "summarize status" not in str(audit[-1])


def test_query_maps_unavailable_upstream_to_503():
    client = make_client(
        settings=make_settings(
            prometheus_url="https://prometheus.test", metrics_query="up"
        ),
        prometheus=FakePrometheus(error=IntegrationUnavailable("upstream unavailable")),
    )

    response = client.post("/api/query", json={"query": "summarize status"})

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "integration_unavailable"


def test_threshold_validation_and_successful_fake_upstream_request():
    http = FakeHttp({"updated": True})
    client = make_client(
        settings=make_settings(
            thresholds_url="https://thresholds.test/api",
            gateway_token=GATEWAY_TOKEN,
        ),
        http=http,
    )

    headers = gateway_headers(THRESHOLDS_WRITE_SCOPE)
    invalid = client.post(
        "/api/set-thresholds", json={"cpu": 80, "mem": 85}, headers=headers
    )
    successful = client.post(
        "/api/set-thresholds",
        json={"cpu": 80, "mem": 85, "disk": 90},
        headers=headers,
    )

    assert invalid.status_code == 400
    assert successful.status_code == 200
    assert successful.get_json() == {"updated": True}
    assert http.calls[0]["method"] == "POST"
    assert http.calls[0]["json"] == {"cpu": 80, "mem": 85, "disk": 90}
    audit = client.get(
        "/api/audit",
        headers=gateway_headers(READ_SCOPE, THRESHOLDS_WRITE_SCOPE),
    ).get_json()["events"][-1]
    assert audit["event"] == "thresholds_updated"
    assert audit["details"]["actor"] == "operator-1"


def test_threshold_upstream_unavailable_is_not_synthesized():
    client = make_client(
        settings=make_settings(
            thresholds_url="https://thresholds.test/api",
            gateway_token=GATEWAY_TOKEN,
        ),
        http=FakeHttp(error=requests.ConnectionError("threshold endpoint unavailable")),
    )

    response = client.post(
        "/api/set-thresholds",
        json={"cpu": 80, "mem": 85, "disk": 90},
        headers=gateway_headers(THRESHOLDS_WRITE_SCOPE),
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "integration_unavailable"


def test_silence_rejects_invalid_durations_and_accepts_valid_request():
    alertmanager = FakeAlertmanager([{"id": "alert-1"}])
    client = make_client(
        settings=make_settings(gateway_token=GATEWAY_TOKEN),
        alertmanager=alertmanager,
    )
    headers = gateway_headers(ALERT_SILENCE_SCOPE)

    for duration in (True, False, 0, 10081):
        response = client.post(
            "/api/suppress-alert",
            json={
                "alert_id": "alert-1",
                "duration": duration,
                "comment": "test suppression",
            },
            headers=headers,
        )
        assert response.status_code == 400
    assert alertmanager.silences == []

    successful = client.post(
        "/api/suppress-alert",
        json={
            "alert_id": "alert-1",
            "duration": 5,
            "comment": "test suppression",
        },
        headers={**headers, "X-Request-ID": "silence-123"},
    )

    assert successful.status_code == 200
    assert successful.get_json()["status"] == "suppressed"
    assert alertmanager.silences == [
        (
            [{"name": "fingerprint", "value": "alert-1", "isRegex": False}],
            5,
            "test suppression",
            "operator-1",
        )
    ]
    event = client.get(
        "/api/audit",
        headers=gateway_headers(READ_SCOPE, ALERT_SILENCE_SCOPE),
    ).get_json()["events"][-1]
    assert event["event"] == "alert_suppressed"
    assert event["request_id"] == "silence-123"
    assert event["details"]["actor"] == "operator-1"


def test_audit_redacts_secrets_and_does_not_store_raw_query():
    client = make_client(model=FakeModel())
    runtime = client.application.extensions["aiops"]
    runtime.audit_log.record(
        "redaction_check", "trace-1", authorization="Bearer top-secret-token"
    )
    client.post("/api/query", json={"query": "private operational question"})

    events = client.get("/api/audit").get_json()["events"]

    redaction_event = next(
        event for event in events if event["event"] == "redaction_check"
    )
    assert redaction_event["details"]["authorization"] == "Bearer [REDACTED]"
    query_event = next(event for event in events if event["event"] == "ai_query")
    assert "private operational question" not in str(query_event)


def test_template_does_not_render_source_data_as_html():
    template = Path(__file__).parents[1] / "templates" / "dashboard.html"
    content = template.read_text(encoding="utf-8")
    assert "innerHTML" not in content
    assert "textContent" in content
    assert "random." not in content
    assert "AIOPS_API_KEY" not in content
    assert "AIOPS_GATEWAY_TOKEN" not in content
    assert "credentials: 'same-origin'" in content
