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
from src.platform.config import ConfigurationError, Settings, UpstreamSettings
from src.platform.integrations import (
    AlertmanagerAdapter,
    ApprovalRejected,
    IntegrationUnavailable,
    PrometheusAdapter,
)
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


class FakeApproval:
    def __init__(self, *, reject: bool = False):
        self.reject = reject
        self.calls: list[tuple[str, str, Mapping[str, Any]]] = []

    def verify_and_consume(
        self, approval_id: str, action: str, operation: Mapping[str, Any]
    ) -> dict[str, str]:
        self.calls.append((approval_id, action, dict(operation)))
        if self.reject:
            raise ApprovalRejected("approval denied")
        return {
            "approval_id": approval_id,
            "approved_by": "approver@example.test",
            "approved_at": "2026-11-16T00:00:00+00:00",
            "action": action,
            "payload_sha256": "test-payload-digest",
        }


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
    def __init__(
        self,
        payload: Any,
        *,
        fail: bool = False,
        json_error: Exception | None = None,
    ):
        self.payload = payload
        self.fail = fail
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.fail:
            raise requests.HTTPError("upstream failure")

    def json(self) -> Any:
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeHttp:
    def __init__(
        self,
        payload: Any = None,
        *,
        error: Exception | None = None,
        fail: bool = False,
        json_error: Exception | None = None,
    ):
        self.payload = {"accepted": True} if payload is None else payload
        self.error = error
        self.fail = fail
        self.json_error = json_error
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        timeout: int,
        verify: bool,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "json": json,
                "headers": headers,
                "auth": auth,
                "timeout": timeout,
                "verify": verify,
            }
        )
        if self.error:
            raise self.error
        return FakeResponse(self.payload, fail=self.fail, json_error=self.json_error)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "service_name": "aiops-test",
        "version": "test-version",
        "api_key": None,
        "approval_url": None,
        "approval_api_key": None,
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
    approvals: FakeApproval | None = None,
    alertmanager: FakeAlertmanager | None = None,
    model: FakeModel | None = None,
    http: FakeHttp | None = None,
):
    app = create_app(
        settings or make_settings(),
        dependencies=DashboardDependencies(
            prometheus=prometheus,
            approvals=approvals,
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


def test_production_configuration_requires_shared_prometheus_for_slo(
    monkeypatch: pytest.MonkeyPatch,
):
    values = {
        "AIOPS_ENV": "production",
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
        "AIOPS_API_KEY": "k" * 24,
        "AIOPS_ALLOWED_ORIGINS": "",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ConfigurationError, match="required in production"):
        Settings.from_env()

    monkeypatch.setenv("AIOPS_PROMETHEUS_URL", "https://prometheus.example")
    settings = Settings.from_env()
    assert settings.production
    assert settings.prometheus_url == "https://prometheus.example"


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
    approvals = FakeApproval()
    client = make_client(
        settings=make_settings(
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=approvals,
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
        headers={
            **gateway_headers(ALERT_SILENCE_SCOPE),
            "X-AiOps-Approval-ID": "approval-1",
        },
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
    assert approvals.calls == [("approval-1", "suppress_alert", payload)]


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
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=FakeApproval(),
        http=http,
    )

    headers = {
        **gateway_headers(THRESHOLDS_WRITE_SCOPE),
        "X-AiOps-Approval-ID": "threshold-approval-1",
    }
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
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=FakeApproval(),
        http=FakeHttp(error=requests.ConnectionError("threshold endpoint unavailable")),
    )

    response = client.post(
        "/api/set-thresholds",
        json={"cpu": 80, "mem": 85, "disk": 90},
        headers={
            **gateway_headers(THRESHOLDS_WRITE_SCOPE),
            "X-AiOps-Approval-ID": "threshold-approval-2",
        },
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "integration_unavailable"


def test_silence_rejects_invalid_durations_and_accepts_valid_request():
    alertmanager = FakeAlertmanager([{"id": "alert-1"}])
    approvals = FakeApproval()
    client = make_client(
        settings=make_settings(
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=approvals,
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
        headers={
            **headers,
            "X-Request-ID": "silence-123",
            "X-AiOps-Approval-ID": "silence-approval-1",
        },
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


def test_missing_or_rejected_approval_never_executes_a_mutation():
    alertmanager = FakeAlertmanager([{"id": "alert-1"}])
    payload = {"alert_id": "alert-1", "duration": 5, "comment": "test"}
    no_service = make_client(
        settings=make_settings(gateway_token=GATEWAY_TOKEN),
        alertmanager=alertmanager,
    ).post(
        "/api/suppress-alert",
        json=payload,
        headers={
            **gateway_headers(ALERT_SILENCE_SCOPE),
            "X-AiOps-Approval-ID": "approval-unconfigured",
        },
    )

    rejection_alertmanager = FakeAlertmanager([{"id": "alert-1"}])
    rejected = make_client(
        settings=make_settings(
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=FakeApproval(reject=True),
        alertmanager=rejection_alertmanager,
    ).post(
        "/api/suppress-alert",
        json=payload,
        headers={
            **gateway_headers(ALERT_SILENCE_SCOPE),
            "X-AiOps-Approval-ID": "approval-rejected",
        },
    )

    assert no_service.status_code == 503
    assert no_service.get_json()["error"]["code"] == "integration_unavailable"
    assert rejected.status_code == 403
    assert rejected.get_json()["error"]["code"] == "approval_required"
    assert alertmanager.silences == []
    assert rejection_alertmanager.silences == []


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
    assert redaction_event["details"]["authorization"] == "[REDACTED]"
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


def test_production_slo_uses_prometheus_aggregated_increase_across_workers():
    class SummedPrometheus:
        def __init__(self):
            self.queries: list[str | None] = []
            self.results = iter(([{"value": 198.0}], [{"value": 200.0}]))

        def query(self, expression: str | None) -> list[dict[str, Any]]:
            self.queries.append(expression)
            return next(self.results)

    prometheus = SummedPrometheus()
    client = make_client(
        settings=make_settings(
            environment="production",
            gateway_token=GATEWAY_TOKEN,
            prometheus_url="https://prometheus.test",
        ),
        prometheus=prometheus,
    )

    response = client.get("/api/slo", headers=gateway_headers(READ_SCOPE))
    snapshot = response.get_json()

    assert response.status_code == 200
    assert snapshot["source"] == "prometheus"
    assert snapshot["aggregation_scope"].startswith("all instances")
    assert snapshot["good_events"] == 198.0
    assert snapshot["total_events"] == 200.0
    assert snapshot["availability_percent"] == 99.0
    assert len(prometheus.queries) == 2
    assert all(
        query.startswith("sum(increase(aiops_http_requests_total{")
        for query in prometheus.queries
    )
    assert 'service="aiops-test"' in prometheus.queries[0]
    assert 'scope="api"' in prometheus.queries[0]
    assert 'status=~"2..|3.."' in prometheus.queries[0]
    assert 'status=~"2..|3..|429|5.."' in prometheus.queries[1]
    assert "[60m]" in prometheus.queries[0]


def test_production_slo_fails_closed_when_shared_prometheus_is_unavailable():
    client = make_client(
        settings=make_settings(
            environment="production",
            gateway_token=GATEWAY_TOKEN,
            prometheus_url="https://prometheus.test",
        ),
        prometheus=FakePrometheus(
            error=IntegrationUnavailable("Prometheus unavailable")
        ),
    )

    response = client.get("/api/slo", headers=gateway_headers(READ_SCOPE))

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "integration_unavailable"


def test_development_slo_is_clearly_labeled_as_process_local():
    response = make_client().get("/api/slo")
    snapshot = response.get_json()

    assert response.status_code == 200
    assert snapshot["source"] == "process_local"
    assert snapshot["measurement_state"] == "no_data"
    assert snapshot["availability_percent"] is None


def test_unmatched_api_paths_do_not_become_metric_labels():
    client = make_client()
    secret_path_segment = "customer-id-should-not-be-a-label"

    response = client.get(f"/api/not-a-route/{secret_path_segment}")
    method_not_allowed = client.post("/api/slo")
    exposition = client.application.extensions["aiops"].metrics_registry.prometheus(
        "aiops-test"
    )
    slo_snapshot = client.get("/api/slo").get_json()

    assert response.status_code == 404
    assert method_not_allowed.status_code == 405
    assert secret_path_segment not in response.get_json()["error"]["message"]
    assert secret_path_segment not in exposition
    assert 'route="__unmatched__"' in exposition
    assert slo_snapshot["measurement_state"] == "no_data"
    assert slo_snapshot["excluded_client_errors"] == 2


class FakeRequestsSession:
    def __init__(
        self,
        response: FakeResponse,
        *,
        error: Exception | None = None,
    ):
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "GET", "url": url, **kwargs})
        if self.error:
            raise self.error
        return self.response

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        if self.error:
            raise self.error
        return self.response


def prometheus_vector(*samples: Any) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {"resultType": "vector", "result": list(samples)},
    }


def valid_prometheus_sample() -> dict[str, Any]:
    return {
        "metric": {"__name__": "up", "job": "api"},
        "value": [1710000000, "1"],
    }


def valid_alertmanager_alert() -> dict[str, Any]:
    return {
        "fingerprint": "fingerprint-1",
        "labels": {"alertname": "CpuHigh", "severity": "warning"},
        "annotations": {"summary": "CPU is high"},
        "receivers": [{"name": "default"}],
        "startsAt": "2030-01-01T00:00:00Z",
        "updatedAt": "2030-01-01T00:00:00Z",
        "endsAt": "2030-01-01T01:00:00Z",
        "status": {
            "state": "active",
            "silencedBy": [],
            "inhibitedBy": [],
            "mutedBy": [],
        },
    }


def test_upstream_env_configuration_is_independent_and_secrets_are_not_reprd(
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
        "AIOPS_GATEWAY_TOKEN": "",
        "AIOPS_ALLOWED_ORIGINS": "",
    }
    prefixes = {
        "PROMETHEUS": "prometheus",
        "ALERTMANAGER": "alertmanager",
        "INCIDENTS": "incidents",
        "LOGS": "logs",
        "ACTIONS": "actions",
        "INSIGHTS": "insights",
        "THRESHOLDS": "thresholds",
    }
    for name, value in required.items():
        monkeypatch.setenv(name, value)
    for prefix in prefixes:
        for suffix in (
            "AUTH_TYPE",
            "BEARER_TOKEN",
            "USERNAME",
            "PASSWORD",
            "TIMEOUT_SECONDS",
            "VERIFY_TLS",
        ):
            monkeypatch.delenv(f"AIOPS_{prefix}_{suffix}", raising=False)

    monkeypatch.setenv("AIOPS_PROMETHEUS_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("AIOPS_PROMETHEUS_AUTH_TYPE", "bearer")
    monkeypatch.setenv("AIOPS_PROMETHEUS_BEARER_TOKEN", "prom-secret")
    monkeypatch.setenv("AIOPS_ALERTMANAGER_AUTH_TYPE", "basic")
    monkeypatch.setenv("AIOPS_ALERTMANAGER_USERNAME", "alert-user")
    monkeypatch.setenv("AIOPS_ALERTMANAGER_PASSWORD", "alert-password")
    monkeypatch.setenv("AIOPS_ALERTMANAGER_TIMEOUT_SECONDS", "9")
    monkeypatch.setenv("AIOPS_ALERTMANAGER_VERIFY_TLS", "false")

    settings = Settings.from_env()

    assert settings.upstream("prometheus").headers == {
        "Authorization": "Bearer prom-secret"
    }
    assert settings.upstream("alertmanager").basic_auth == (
        "alert-user",
        "alert-password",
    )
    assert settings.upstream("alertmanager").timeout_seconds == 9
    assert settings.upstream("alertmanager").verify_tls is False
    assert settings.upstream("incidents").timeout_seconds == 5
    assert all(
        settings.upstream(name).auth_type == "none"
        for name in ("incidents", "logs", "actions", "insights", "thresholds")
    )
    assert "prom-secret" not in repr(settings)
    assert "alert-password" not in repr(settings)

    monkeypatch.setenv(
        "AIOPS_INCIDENTS_URL", "https://user:password@incidents.test/api"
    )
    with pytest.raises(ConfigurationError, match="URL credentials"):
        Settings.from_env()
    monkeypatch.setenv(
        "AIOPS_INCIDENTS_URL", "https://incidents.test/api?api_key=secret"
    )
    with pytest.raises(ConfigurationError, match="credentials in its query"):
        Settings.from_env()


def test_upstream_credentials_cannot_be_silently_ignored(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("AIOPS_ENV", "test")
    monkeypatch.setenv("AIOPS_SERVICE_NAME", "aiops-test")
    monkeypatch.setenv("AIOPS_VERSION", "test-version")
    monkeypatch.setenv("AIOPS_LOG_LEVEL", "INFO")
    monkeypatch.setenv("AIOPS_PROMETHEUS_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("AIOPS_VERIFY_TLS", "true")
    monkeypatch.setenv("AIOPS_MAX_QUERY_LENGTH", "2000")
    monkeypatch.setenv("AIOPS_RATE_LIMIT_PER_MINUTE", "120")
    monkeypatch.setenv("AIOPS_AUDIT_LOG_MAX_ENTRIES", "500")
    monkeypatch.setenv("AIOPS_EVENT_STORE_MAX_ENTRIES", "200")
    monkeypatch.setenv("AIOPS_SLO_TARGET", "99.5")
    monkeypatch.setenv("AIOPS_SLO_WINDOW_MINUTES", "60")
    monkeypatch.setenv("AIOPS_REFRESH_SECONDS", "30")
    monkeypatch.setenv("AIOPS_HOST", "127.0.0.1")
    monkeypatch.setenv("AIOPS_PORT", "5000")
    monkeypatch.setenv("AIOPS_API_KEY", "")
    monkeypatch.setenv("AIOPS_ALLOWED_ORIGINS", "")
    monkeypatch.setenv("AIOPS_INCIDENTS_BEARER_TOKEN", "unused-secret")
    monkeypatch.setenv("AIOPS_INCIDENTS_AUTH_TYPE", "none")

    with pytest.raises(ConfigurationError, match="credentials require"):
        Settings.from_env()


@pytest.mark.parametrize(
    "settings",
    [
        {"timeout_seconds": 0, "verify_tls": True},
        {"timeout_seconds": 61, "verify_tls": True},
        {"timeout_seconds": 5, "verify_tls": True, "auth_type": "digest"},
        {"timeout_seconds": 5, "verify_tls": True, "auth_type": "bearer"},
        {
            "timeout_seconds": 5,
            "verify_tls": True,
            "auth_type": "none",
            "bearer_token": "unexpected-secret",
        },
        {
            "timeout_seconds": 5,
            "verify_tls": True,
            "auth_type": "basic",
            "username": "user",
        },
    ],
)
def test_direct_upstream_settings_reject_invalid_request_policies(
    settings: dict[str, Any],
):
    with pytest.raises(ConfigurationError):
        UpstreamSettings(**settings)


def test_prometheus_contract_normalizes_samples_and_applies_auth_policy(
    monkeypatch: pytest.MonkeyPatch,
):
    secret = "prometheus-test-secret"
    session = FakeRequestsSession(
        FakeResponse(prometheus_vector(valid_prometheus_sample()))
    )
    monkeypatch.setattr(requests, "Session", lambda: session)
    settings = make_settings(
        prometheus_url="https://prometheus.test",
        upstream_configs={
            "prometheus": UpstreamSettings(7, True, "bearer", bearer_token=secret)
        },
    )

    result = PrometheusAdapter(settings).query("up")

    assert result == [
        {
            "name": "up",
            "value": 1.0,
            "timestamp": 1710000000.0,
            "labels": {"job": "api"},
        }
    ]
    assert session.calls[0]["params"] == {"query": "up"}
    assert session.calls[0]["headers"] == {"Authorization": f"Bearer {secret}"}
    assert session.calls[0]["timeout"] == 7
    assert session.calls[0]["verify"] is True
    assert secret not in repr(settings)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"status": "error"},
        {"status": "success", "data": {}},
        {"status": "success", "data": {"resultType": "matrix", "result": []}},
        prometheus_vector(valid_prometheus_sample(), None),
        prometheus_vector({"metric": {}, "value": [1, "NaN"]}),
        prometheus_vector({"metric": {"job": 3}, "value": [1, "1"]}),
        prometheus_vector({"metric": {}, "value": ["1710000000", "1"]}),
        prometheus_vector({"metric": {}, "value": [1710000000, 1]}),
    ],
)
def test_prometheus_contract_rejects_malformed_or_partial_samples(
    monkeypatch: pytest.MonkeyPatch, payload: Any
):
    session = FakeRequestsSession(FakeResponse(payload))
    monkeypatch.setattr(requests, "Session", lambda: session)
    adapter = PrometheusAdapter(make_settings(prometheus_url="https://prometheus.test"))

    with pytest.raises(IntegrationUnavailable):
        adapter.query("up")


@pytest.mark.parametrize("failure", ["valid", "malformed", "timeout", "http", "json"])
def test_prometheus_transport_failures_are_sanitized_and_consistent(
    monkeypatch: pytest.MonkeyPatch, failure: str
):
    secret = "prometheus-secret"
    response = FakeResponse(
        prometheus_vector(
            None if failure == "malformed" else valid_prometheus_sample()
        ),
        fail=failure == "http",
        json_error=ValueError(secret) if failure == "json" else None,
    )
    session = FakeRequestsSession(
        response,
        error=requests.Timeout(secret) if failure == "timeout" else None,
    )
    monkeypatch.setattr(requests, "Session", lambda: session)
    settings = make_settings(
        prometheus_url="https://prometheus.test",
        status_query="up",
        upstream_configs={
            "prometheus": UpstreamSettings(5, True, "bearer", bearer_token=secret)
        },
    )
    client = make_client(settings=settings)

    result = client.get("/api/status")

    if failure == "valid":
        assert result.status_code == 200
        assert result.get_json()["samples"][0]["name"] == "up"
        assert result.get_json()["source"] == "prometheus"
    else:
        assert result.status_code == 503
        assert result.get_json()["error"]["code"] == "integration_unavailable"
    assert secret not in result.get_data(as_text=True)


def test_readiness_logs_do_not_emit_chained_upstream_credentials(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    secret = "readiness-upstream-secret"
    session = FakeRequestsSession(
        FakeResponse({}), error=requests.Timeout(f"Bearer {secret}")
    )
    monkeypatch.setattr(requests, "Session", lambda: session)
    client = make_client(
        settings=make_settings(
            prometheus_url="https://prometheus.test",
            alertmanager_url="https://alertmanager.test",
            status_query="up",
        )
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert secret not in caplog.text


def test_alertmanager_contract_validates_alert_and_applies_basic_auth(
    monkeypatch: pytest.MonkeyPatch,
):
    session = FakeRequestsSession(
        FakeResponse(
            [
                valid_alertmanager_alert(),
                {**valid_alertmanager_alert(), "fingerprint": "fp-2"},
            ]
        )
    )
    monkeypatch.setattr(requests, "Session", lambda: session)
    settings = make_settings(
        alertmanager_url="https://alertmanager.test",
        upstream_configs={
            "alertmanager": UpstreamSettings(
                8, False, "basic", username="alert-user", password="alert-pass"
            )
        },
    )

    alerts = AlertmanagerAdapter(settings).active_alerts()

    assert len(alerts) == 2
    assert alerts[0]["id"] == "fingerprint-1"
    assert alerts[0]["name"] == "CpuHigh"
    assert alerts[0]["status"] == "active"
    assert session.calls[0]["params"] == {
        "active": "true",
        "silenced": "false",
        "inhibited": "false",
    }
    assert session.calls[0]["auth"] == ("alert-user", "alert-pass")
    assert session.calls[0]["timeout"] == 8
    assert session.calls[0]["verify"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [None],
        [{**valid_alertmanager_alert(), "fingerprint": ""}],
        [{**valid_alertmanager_alert(), "labels": {"alertname": 7}}],
        [{**valid_alertmanager_alert(), "annotations": None}],
        [{**valid_alertmanager_alert(), "status": None}],
        [
            {
                key: value
                for key, value in valid_alertmanager_alert().items()
                if key != "startsAt"
            }
        ],
        [
            {
                key: value
                for key, value in valid_alertmanager_alert().items()
                if key != "updatedAt"
            }
        ],
        [
            {
                key: value
                for key, value in valid_alertmanager_alert().items()
                if key != "endsAt"
            }
        ],
        [{**valid_alertmanager_alert(), "startsAt": "not-a-timestamp"}],
        [{**valid_alertmanager_alert(), "receivers": [None]}],
        [
            {
                **valid_alertmanager_alert(),
                "status": {
                    **valid_alertmanager_alert()["status"],
                    "state": "unknown",
                },
            }
        ],
        [
            {
                **valid_alertmanager_alert(),
                "status": {
                    key: value
                    for key, value in valid_alertmanager_alert()["status"].items()
                    if key != "mutedBy"
                },
            }
        ],
        [{**valid_alertmanager_alert(), "labels": {"severity": "warning"}}],
    ],
)
def test_alertmanager_contract_rejects_malformed_alerts(
    monkeypatch: pytest.MonkeyPatch, payload: Any
):
    session = FakeRequestsSession(FakeResponse(payload))
    monkeypatch.setattr(requests, "Session", lambda: session)
    adapter = AlertmanagerAdapter(
        make_settings(alertmanager_url="https://alertmanager.test")
    )

    with pytest.raises(IntegrationUnavailable):
        adapter.active_alerts()


def test_alertmanager_silence_response_requires_an_identifier(
    monkeypatch: pytest.MonkeyPatch,
):
    session = FakeRequestsSession(FakeResponse({"silenceID": 12}))
    monkeypatch.setattr(requests, "Session", lambda: session)
    adapter = AlertmanagerAdapter(
        make_settings(alertmanager_url="https://alertmanager.test")
    )

    with pytest.raises(IntegrationUnavailable):
        adapter.create_silence([], 5, "maintenance", "operator-1")


def test_alertmanager_silence_contract_posts_expected_fields_and_returns_id(
    monkeypatch: pytest.MonkeyPatch,
):
    session = FakeRequestsSession(FakeResponse({"silenceID": "silence-42"}))
    monkeypatch.setattr(requests, "Session", lambda: session)
    adapter = AlertmanagerAdapter(
        make_settings(alertmanager_url="https://alertmanager.test")
    )

    result = adapter.create_silence(
        [{"name": "fingerprint", "value": "fp-1", "isRegex": False}],
        15,
        "maintenance window",
        "operator-1",
    )

    assert result["silence_id"] == "silence-42"
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"] == "https://alertmanager.test/api/v2/silences"
    assert set(session.calls[0]["json"]) == {
        "matchers",
        "startsAt",
        "endsAt",
        "createdBy",
        "comment",
    }
    assert session.calls[0]["json"]["createdBy"] == "operator-1"
    assert session.calls[0]["json"]["comment"] == "maintenance window"


@pytest.mark.parametrize("failure", ["valid", "malformed", "timeout", "http", "json"])
def test_alertmanager_route_maps_contract_and_transport_failures_to_503(
    monkeypatch: pytest.MonkeyPatch, failure: str
):
    payload = (
        [valid_alertmanager_alert(), None]
        if failure == "malformed"
        else [valid_alertmanager_alert()]
    )
    session = FakeRequestsSession(
        FakeResponse(
            payload,
            fail=failure == "http",
            json_error=ValueError("invalid JSON") if failure == "json" else None,
        ),
        error=requests.Timeout("upstream timeout") if failure == "timeout" else None,
    )
    monkeypatch.setattr(requests, "Session", lambda: session)
    client = make_client(
        settings=make_settings(alertmanager_url="https://alertmanager.test")
    )

    response = client.get("/api/alerts")

    if failure == "valid":
        assert response.status_code == 200
        assert response.get_json()["alerts"][0]["id"] == "fingerprint-1"
        assert response.get_json()["source"] == "alertmanager"
    else:
        assert response.status_code == 503
        assert response.get_json()["error"]["code"] == "integration_unavailable"


@pytest.mark.parametrize(
    "path,settings_overrides",
    [
        ("/api/status", {"status_query": "up"}),
        ("/api/alerts", {}),
    ],
)
def test_missing_typed_upstream_route_returns_503(
    path: str, settings_overrides: dict[str, Any]
):
    client = make_client(settings=make_settings(**settings_overrides))

    response = client.get(path)

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "integration_unavailable"


GENERIC_UPSTREAM_CASES = [
    (
        "incidents",
        "incidents_url",
        "/api/incidents",
        "GET",
        {"incidents": []},
        {"incidents": [{"id": "i-1"}, None]},
    ),
    (
        "logs",
        "logs_url",
        "/api/log-events",
        "GET",
        {"log_events": []},
        {"log_events": ["not-an-object"]},
    ),
    ("actions", "actions_url", "/api/self-healing", "GET", {"actions": []}, []),
    (
        "insights",
        "insights_url",
        "/api/ai-recommendations",
        "GET",
        {"items": []},
        ["not-an-object"],
    ),
    (
        "thresholds",
        "thresholds_url",
        "/api/set-thresholds",
        "POST",
        {"updated": True},
        [],
    ),
]


@pytest.mark.parametrize(
    "upstream,url_field,path,method,valid,malformed", GENERIC_UPSTREAM_CASES
)
@pytest.mark.parametrize("failure", ["valid", "malformed", "timeout", "http", "json"])
def test_generic_upstream_contract_matrix_maps_to_valid_response_or_503(
    upstream: str,
    url_field: str,
    path: str,
    method: str,
    valid: Any,
    malformed: Any,
    failure: str,
):
    settings = make_settings(
        **{url_field: "https://upstream.test"},
        gateway_token=GATEWAY_TOKEN if method == "POST" else None,
        approval_url=(
            "https://approval.test/verify-and-consume" if method == "POST" else None
        ),
        approval_api_key="a" * 24 if method == "POST" else None,
    )
    request_payload = {"cpu": 80, "mem": 85, "disk": 90} if method == "POST" else None
    if failure == "valid":
        fake_http = FakeHttp(valid)
    elif failure == "malformed":
        fake_http = FakeHttp(malformed)
    elif failure == "timeout":
        fake_http = FakeHttp(error=requests.Timeout("upstream timeout"))
    elif failure == "http":
        fake_http = FakeHttp(fail=True)
    else:
        fake_http = FakeHttp(json_error=ValueError("invalid JSON"))
    client = make_client(
        settings=settings,
        approvals=FakeApproval() if method == "POST" else None,
        http=fake_http,
    )

    if method == "POST":
        headers = {
            **gateway_headers(THRESHOLDS_WRITE_SCOPE),
            "X-AiOps-Approval-ID": "approval-threshold-test",
        }
        response = client.post(
            path,
            json=request_payload,
            headers=headers,
        )
    else:
        response = client.get(path)

    expected_status = 200 if failure == "valid" else 503
    assert response.status_code == expected_status
    if expected_status == 503:
        assert response.get_json()["error"]["code"] == "integration_unavailable"
    else:
        result = response.get_json()
        if upstream in {"incidents", "logs"}:
            key = "incidents" if upstream == "incidents" else "log_events"
            assert result[key] == valid[key]
            assert result["source"] == upstream
        else:
            assert result == valid
        assert fake_http.calls[0]["timeout"] == 5
        assert fake_http.calls[0]["verify"] is True
        assert fake_http.calls[0]["method"] == method
        if upstream == "insights":
            assert fake_http.calls[0]["params"] == {"kind": "recommendations"}
        if method == "POST":
            assert fake_http.calls[0]["json"] == request_payload


@pytest.mark.parametrize(
    "upstream,url_field,path,method,valid,malformed", GENERIC_UPSTREAM_CASES
)
def test_missing_generic_upstream_is_503_not_an_empty_success(
    upstream: str,
    url_field: str,
    path: str,
    method: str,
    valid: Any,
    malformed: Any,
):
    settings = make_settings(
        gateway_token=GATEWAY_TOKEN if method == "POST" else None,
        approval_url=(
            "https://approval.test/verify-and-consume" if method == "POST" else None
        ),
        approval_api_key="a" * 24 if method == "POST" else None,
    )
    http = FakeHttp(valid)
    client = make_client(
        settings=settings,
        approvals=FakeApproval() if method == "POST" else None,
        http=http,
    )
    if method == "POST":
        response = client.post(
            path,
            json={"cpu": 80, "mem": 85, "disk": 90},
            headers={
                **gateway_headers(THRESHOLDS_WRITE_SCOPE),
                "X-AiOps-Approval-ID": "approval-threshold-missing-source",
            },
        )
    else:
        response = client.get(path)

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "integration_unavailable"
    assert http.calls == []


def test_per_upstream_credentials_are_used_and_never_returned_on_error():
    secret = "incidents-super-secret"
    settings = make_settings(
        incidents_url="https://incidents.test/api",
        upstream_configs={
            "incidents": UpstreamSettings(11, True, "bearer", bearer_token=secret)
        },
    )
    http = FakeHttp(error=requests.HTTPError(f"rejected Bearer {secret}"))
    client = make_client(settings=settings, http=http)

    response = client.get("/api/incidents")

    assert response.status_code == 503
    assert secret not in response.get_data(as_text=True)
    assert http.calls[0]["headers"] == {"Authorization": f"Bearer {secret}"}
    assert http.calls[0]["timeout"] == 11
    assert http.calls[0]["verify"] is True


def test_unexpected_upstream_errors_are_not_logged_or_returned(
    caplog: pytest.LogCaptureFixture,
):
    secret = "unexpected-upstream-secret"
    client = make_client(
        settings=make_settings(incidents_url="https://incidents.test/api"),
        http=FakeHttp(error=RuntimeError(f"Bearer {secret}")),
    )

    response = client.get("/api/incidents")

    assert response.status_code == 500
    assert secret not in response.get_data(as_text=True)
    assert secret not in caplog.text


def test_configured_source_url_is_not_returned_by_api():
    source_url = "https://incidents.test/api/private-token-path"
    settings = make_settings(incidents_url=source_url)
    assert "private-token-path" not in repr(settings)
    client = make_client(
        settings=settings,
        http=FakeHttp({"incidents": []}),
    )

    response = client.get("/api/incidents")

    assert response.status_code == 200
    assert response.get_json()["source"] == "incidents"
    assert source_url not in response.get_data(as_text=True)


def test_invalid_generic_json_number_is_not_returned_or_cached_as_success():
    settings = make_settings(incidents_url="https://incidents.test/api")
    http = FakeHttp({"incidents": [{"id": "fresh"}]})
    client = make_client(settings=settings, http=http)
    first = client.get("/api/incidents")
    http.payload = {"incidents": [{"id": "invalid", "value": float("nan")}]}

    second = client.get("/api/incidents")

    assert first.status_code == 200
    assert second.status_code == 503
    assert second.get_json()["error"]["code"] == "integration_unavailable"
