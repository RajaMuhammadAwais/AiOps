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
from src.platform.audit import AuditEvent, AuditSinkUnavailable
from src.platform.config import ConfigurationError, Settings
from src.platform.integrations import ApprovalRejected, IntegrationUnavailable
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


class FakeAuditSink:
    def __init__(self, *, fail_calls: set[int] | None = None):
        self.fail_calls = fail_calls or set()
        self.calls = 0
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self.calls += 1
        if self.calls in self.fail_calls:
            raise AuditSinkUnavailable("fake sink failure")
        if not event.verify():
            raise AssertionError("invalid event reached the audit sink")
        self.events.append(event)


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
    audit_sink: FakeAuditSink | None = None,
    use_default_audit_sink: bool = True,
):
    app = create_app(
        settings or make_settings(),
        dependencies=DashboardDependencies(
            prometheus=prometheus,
            approvals=approvals,
            alertmanager=alertmanager,
            model=model,
            http=http,
            audit_sink=(
                audit_sink
                if audit_sink is not None
                else (FakeAuditSink() if use_default_audit_sink else None)
            ),
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
    audit_sink = FakeAuditSink()
    client = make_client(
        settings=make_settings(
            thresholds_url="https://thresholds.test/api",
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=FakeApproval(),
        http=http,
        audit_sink=audit_sink,
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
    assert "threshold-approval-1" not in str(audit)
    assert "approval_id_fingerprint" in audit["details"]
    assert [event.outcome for event in audit_sink.events[-2:]] == [
        "started",
        "succeeded",
    ]
    final_event = audit_sink.events[-1]
    assert final_event.schema_version == "1.0"
    assert final_event.request_id == successful.headers["X-Request-ID"]
    assert final_event.actor == "operator-1"
    assert final_event.details["action"] == "set_thresholds"
    assert final_event.details["target"] == "thresholds"


def test_threshold_upstream_unavailable_is_not_synthesized():
    audit_sink = FakeAuditSink()
    client = make_client(
        settings=make_settings(
            thresholds_url="https://thresholds.test/api",
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=FakeApproval(),
        http=FakeHttp(error=requests.ConnectionError("threshold endpoint unavailable")),
        audit_sink=audit_sink,
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
    assert [event.outcome for event in audit_sink.events] == ["started", "unknown"]


def test_silence_rejects_invalid_durations_and_accepts_valid_request():
    alertmanager = FakeAlertmanager([{"id": "alert-1"}])
    approvals = FakeApproval()
    audit_sink = FakeAuditSink()
    client = make_client(
        settings=make_settings(
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=approvals,
        alertmanager=alertmanager,
        audit_sink=audit_sink,
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
    assert "silence-approval-1" not in str(event)
    assert "approval_id_fingerprint" in event["details"]
    final_event = audit_sink.events[-1]
    assert final_event.event_type == "mutation.suppress_alert"
    assert final_event.schema_version == "1.0"
    assert final_event.outcome == "succeeded"
    assert final_event.request_id == "silence-123"
    assert final_event.actor == "operator-1"
    assert final_event.details["target"] == "alert-1"
    assert "test suppression" not in final_event.serialize()


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
    audit_sink = FakeAuditSink()
    client = make_client(model=FakeModel(), audit_sink=audit_sink)
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
    assert audit_sink.events == []


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


def test_mutation_routes_fail_closed_without_an_audit_sink():
    alertmanager = FakeAlertmanager([{"id": "alert-1"}])
    http = FakeHttp({"updated": True})
    app = create_app(
        make_settings(
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
            thresholds_url="https://thresholds.test/api",
        ),
        dependencies=DashboardDependencies(
            approvals=FakeApproval(), alertmanager=alertmanager, http=http
        ),
    )
    client = app.test_client()

    silence = client.post(
        "/api/suppress-alert",
        json={"alert_id": "alert-1", "duration": 5, "comment": "change"},
        headers={
            **gateway_headers(ALERT_SILENCE_SCOPE),
            "X-AiOps-Approval-ID": "approval-1",
        },
    )
    thresholds = client.post(
        "/api/set-thresholds",
        json={"cpu": 80, "mem": 85, "disk": 90},
        headers={
            **gateway_headers(THRESHOLDS_WRITE_SCOPE),
            "X-AiOps-Approval-ID": "approval-2",
        },
    )

    assert silence.status_code == thresholds.status_code == 503
    for response in (silence, thresholds):
        assert response.get_json()["error"]["code"] == "audit_sink_unavailable"
        assert response.get_json()["operation_outcome"] == "not_started"
    assert alertmanager.silences == []
    assert http.calls == []


def test_sink_failure_before_mutation_prevents_approval_and_upstream_calls():
    sink = FakeAuditSink(fail_calls={1})
    approvals = FakeApproval()
    http = FakeHttp({"updated": True})
    client = make_client(
        settings=make_settings(
            thresholds_url="https://thresholds.test/api",
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=approvals,
        http=http,
        audit_sink=sink,
    )

    response = client.post(
        "/api/set-thresholds",
        json={"cpu": 80, "mem": 85, "disk": 90},
        headers={
            **gateway_headers(THRESHOLDS_WRITE_SCOPE),
            "X-AiOps-Approval-ID": "approval-1",
        },
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "audit_sink_unavailable"
    assert response.get_json()["operation_outcome"] == "not_started"
    assert approvals.calls == []
    assert http.calls == []


def test_result_sink_failure_after_write_reports_success_and_reconcile_instruction():
    sink = FakeAuditSink(fail_calls={2})
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
        audit_sink=sink,
    )

    response = client.post(
        "/api/set-thresholds",
        json={"cpu": 80, "mem": 85, "disk": 90},
        headers={
            **gateway_headers(THRESHOLDS_WRITE_SCOPE),
            "X-AiOps-Approval-ID": "approval-1",
        },
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "audit_sink_unavailable"
    assert response.get_json()["operation_outcome"] == "succeeded"
    assert "reconcile before retrying" in response.get_json()["error"]["message"]
    assert len(http.calls) == 1
    assert [event.outcome for event in sink.events] == ["started"]


def test_rejected_approval_records_result_without_sending_mutation():
    sink = FakeAuditSink()
    alertmanager = FakeAlertmanager([{"id": "alert-1"}])
    client = make_client(
        settings=make_settings(
            gateway_token=GATEWAY_TOKEN,
            approval_url="https://approval.test/verify-and-consume",
            approval_api_key="a" * 24,
        ),
        approvals=FakeApproval(reject=True),
        alertmanager=alertmanager,
        audit_sink=sink,
    )

    response = client.post(
        "/api/suppress-alert",
        json={"alert_id": "alert-1", "duration": 5, "comment": "change"},
        headers={
            **gateway_headers(ALERT_SILENCE_SCOPE),
            "X-AiOps-Approval-ID": "approval-rejected",
        },
    )

    assert response.status_code == 403
    assert [event.outcome for event in sink.events] == ["started", "rejected"]
    assert alertmanager.silences == []


def test_authorization_denial_is_versioned_and_correlated_in_the_sink():
    sink = FakeAuditSink()
    client = make_client(
        settings=make_settings(gateway_token=GATEWAY_TOKEN), audit_sink=sink
    )

    response = client.post(
        "/api/suppress-alert",
        json={"alert_id": "alert-1", "duration": 5, "comment": "private comment"},
        headers={
            **gateway_headers(READ_SCOPE),
            "X-Request-ID": "denied-request-1",
        },
    )

    assert response.status_code == 403
    event = sink.events[-1]
    assert event.outcome == "authorization_denied"
    assert event.details["phase"] == "denial"
    assert event.request_id == "denied-request-1"
    assert event.actor == "operator-1"
    assert "private comment" not in event.serialize()


def test_authentication_denial_remains_denied_when_best_effort_sink_fails():
    sink = FakeAuditSink(fail_calls={1})
    client = make_client(
        settings=make_settings(gateway_token=GATEWAY_TOKEN), audit_sink=sink
    )

    response = client.post(
        "/api/suppress-alert",
        json={"alert_id": "alert-1", "duration": 5, "comment": "secret"},
        headers={
            **gateway_headers(ALERT_SILENCE_SCOPE),
            "X-AiOps-Gateway-Token": "invalid-token",
            "X-Request-ID": "denied-request-2",
        },
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"
    assert sink.events == []
