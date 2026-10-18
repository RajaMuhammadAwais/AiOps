"""AiOps operational dashboard and integration-backed API."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import logging
import os
import sys
import time
from typing import Any, Mapping

from flask import Flask, Response, g, jsonify, render_template, request
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.platform.config import ConfigurationError, Settings
from src.platform.integrations import (
    AlertmanagerAdapter,
    IntegrationUnavailable,
    ModelAdapter,
    PrometheusAdapter,
)
from src.platform.observability import (
    MetricsRegistry,
    configure_logging,
    new_request_id,
)
from src.platform.security import (
    AuditLog,
    AuthenticationError,
    RateLimitExceeded,
    RequestValidationError,
    SecurityPolicy,
    SlidingWindowRateLimiter,
    authorize,
    fingerprint,
    request_key,
    validate_json_object,
    validate_query,
)
from src.platform.state import BoundedStore

try:
    settings = Settings.from_env()
except ConfigurationError as exc:
    raise SystemExit(f"Configuration error: {exc}") from exc

configure_logging(settings.log_level)
logger = logging.getLogger(settings.service_name)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = settings.max_query_length + 4096
metrics_registry = MetricsRegistry(max_samples=settings.event_store_max_entries)
rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)
audit_log = AuditLog(settings.audit_log_max_entries)
state_store = BoundedStore(settings.event_store_max_entries)
security_policy = SecurityPolicy(input_max_length=settings.max_query_length)
prometheus = PrometheusAdapter(settings)
alertmanager = AlertmanagerAdapter(settings)
model = ModelAdapter(settings)
http = requests.Session()


PUBLIC_PATHS = {"/", "/health/live", "/health/ready"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str, status: int, code: str) -> tuple[Any, int]:
    return (
        jsonify(
            {
                "error": {"code": code, "message": message},
                "request_id": getattr(g, "request_id", None),
            }
        ),
        status,
    )


def _external_json(
    url: str | None,
    label: str,
    params: Mapping[str, Any] | None = None,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
) -> Any:
    if not url:
        raise IntegrationUnavailable(f"{label} is not configured")
    try:
        response = http.request(
            method,
            url,
            params=params,
            json=payload,
            timeout=settings.prometheus_timeout_seconds,
            verify=settings.verify_tls,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise IntegrationUnavailable(f"{label} request failed: {exc}") from exc


def _list_payload(payload: Any, key: str) -> list[dict[str, Any]]:
    values = payload.get(key) if isinstance(payload, dict) else payload
    if not isinstance(values, list):
        raise IntegrationUnavailable(f"Configured source did not return a {key} list")
    return [value for value in values if isinstance(value, dict)]


def _refresh_alerts() -> list[dict[str, Any]]:
    alerts = alertmanager.active_alerts()
    state_store.replace("alerts", alerts)
    return alerts


def _refresh_metrics() -> list[dict[str, Any]]:
    metrics = prometheus.query(settings.metrics_query)
    state_store.replace("metrics", metrics)
    return metrics


def _refresh_incidents() -> list[dict[str, Any]]:
    incidents = _list_payload(
        _external_json(settings.incidents_url, "Incident service"), "incidents"
    )
    state_store.replace("incidents", incidents)
    return incidents


def _refresh_logs() -> list[dict[str, Any]]:
    logs = _list_payload(_external_json(settings.logs_url, "Log service"), "log_events")
    state_store.replace("log_events", logs)
    return logs


def _refresh_actions() -> dict[str, Any]:
    payload = _external_json(settings.actions_url, "Action service")
    if not isinstance(payload, dict):
        raise IntegrationUnavailable("Action service did not return an object")
    state_store.set("self_healing_stats", payload)
    return payload


def _refresh_insights(kind: str | None = None) -> Any:
    params = {"kind": kind} if kind else None
    payload = _external_json(settings.insights_url, "Insight service", params=params)
    state_store.set("insights", payload)
    return payload


def _require_prometheus(expression: str | None) -> list[dict[str, Any]]:
    return prometheus.query(expression)


def _build_context() -> dict[str, Any]:
    context: dict[str, Any] = {}
    if settings.prometheus_url and settings.metrics_query:
        context["metrics"] = _refresh_metrics()
    if settings.alertmanager_url:
        context["alerts"] = _refresh_alerts()
    if settings.incidents_url:
        context["incidents"] = _refresh_incidents()
    return context


@app.before_request
def before_request() -> None:
    g.request_id = request.headers.get("X-Request-ID") or new_request_id()
    g.started_at = time.perf_counter()
    if request.path.startswith("/api") or request.path == "/metrics":
        if not rate_limiter.allow(request_key(request)):
            audit_log.record("rate_limit_denied", g.request_id, path=request.path)
            raise RateLimitExceeded("Request rate limit exceeded")
        authorize(request, settings)


@app.after_request
def after_request(response: Response) -> Response:
    request_id = getattr(g, "request_id", new_request_id())
    started_at = getattr(g, "started_at", time.perf_counter())
    metrics_registry.observe(
        request.method,
        request.path,
        response.status_code,
        time.perf_counter() - started_at,
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = (
        "no-store" if request.path.startswith("/api") else "no-cache"
    )
    origin = request.headers.get("Origin")
    if origin and origin in settings.allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response


@app.errorhandler(RequestValidationError)
def handle_validation_error(error: RequestValidationError):
    return _error(str(error), 400, "invalid_request")


@app.errorhandler(AuthenticationError)
def handle_authentication_error(error: AuthenticationError):
    return _error(str(error), 401, "authentication_required")


@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_error(error: RateLimitExceeded):
    return _error(str(error), 429, "rate_limited")


@app.errorhandler(IntegrationUnavailable)
def handle_integration_error(error: IntegrationUnavailable):
    logger.warning(
        "integration_unavailable", extra={"request_id": getattr(g, "request_id", None)}
    )
    return _error(str(error), 503, "integration_unavailable")


@app.errorhandler(413)
def handle_payload_too_large(_error):
    return _error(
        "Request payload exceeds the configured limit", 413, "payload_too_large"
    )


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    logger.exception(
        "unhandled_request_error", extra={"request_id": getattr(g, "request_id", None)}
    )
    return _error("Unexpected service error", 500, "internal_error")


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        service_name=settings.service_name,
        version=settings.version,
        max_query_length=settings.max_query_length,
        refresh_seconds=settings.refresh_seconds,
    )


@app.route("/health/live")
def health_live():
    return jsonify(
        {
            "status": "alive",
            "service": settings.service_name,
            "version": settings.version,
            "timestamp": _now(),
        }
    )


@app.route("/health/ready")
def health_ready():
    failures = []
    if not settings.prometheus_url:
        failures.append("AIOPS_PROMETHEUS_URL")
    if not settings.status_query:
        failures.append("AIOPS_STATUS_QUERY")
    if not settings.alertmanager_url:
        failures.append("AIOPS_ALERTMANAGER_URL")
    if failures:
        return (
            jsonify({"status": "not_ready", "missing": failures, "timestamp": _now()}),
            503,
        )
    try:
        prometheus.query(settings.status_query)
        alertmanager.active_alerts()
    except IntegrationUnavailable as exc:
        return (
            jsonify({"status": "not_ready", "reason": str(exc), "timestamp": _now()}),
            503,
        )
    return jsonify({"status": "ready", "timestamp": _now()})


@app.route("/metrics")
def metrics():
    return Response(
        metrics_registry.prometheus(settings.service_name),
        mimetype="text/plain; version=0.0.4",
    )


@app.route("/api/status")
def api_status():
    samples = _require_prometheus(settings.status_query)
    alerts = _refresh_alerts() if settings.alertmanager_url else []
    incidents = _refresh_incidents() if settings.incidents_url else []
    return jsonify(
        {
            "status": "operational",
            "source": "prometheus",
            "timestamp": _now(),
            "samples": samples,
            "active_incidents": len(incidents),
            "active_alerts": len(alerts),
            "slo": metrics_registry.slo_snapshot(
                settings.slo_target, settings.slo_window_minutes
            ),
        }
    )


@app.route("/api/incidents")
def api_incidents():
    incidents = _refresh_incidents()
    return jsonify(
        {
            "incidents": incidents,
            "total": len(incidents),
            "source": settings.incidents_url,
        }
    )


@app.route("/api/alerts")
def api_alerts():
    alerts = _refresh_alerts()
    return jsonify(
        {"alerts": alerts, "total": len(alerts), "source": settings.alertmanager_url}
    )


@app.route("/api/metrics")
def api_metrics():
    metrics_data = _refresh_metrics()
    anomalies = (
        _require_prometheus(settings.anomalies_query)
        if settings.anomalies_query
        else []
    )
    return jsonify(
        {
            "metrics": metrics_data,
            "anomalies": anomalies,
            "source": settings.prometheus_url,
        }
    )


@app.route("/api/self-healing")
def api_self_healing():
    return jsonify(_refresh_actions())


@app.route("/api/query", methods=["POST"])
def api_query():
    payload = validate_json_object(request.get_json(silent=True))
    query = validate_query(payload, settings.max_query_length)
    context = _build_context()
    result = model.answer(query, context)
    audit_log.record(
        "ai_query",
        g.request_id,
        query_fingerprint=fingerprint(query),
        model=result.get("model"),
        context_keys=list(context),
    )
    return jsonify(
        {
            "query_fingerprint": fingerprint(query),
            **result,
            "timestamp": _now(),
            "policy": security_policy.__dict__,
        }
    )


@app.route("/api/log-events")
def api_log_events():
    logs = _refresh_logs()
    return jsonify(
        {"log_events": logs, "total": len(logs), "source": settings.logs_url}
    )


@app.route("/api/health-heatmap")
def api_health_heatmap():
    metrics_data = _refresh_metrics()
    return jsonify(
        {
            "components": metrics_data,
            "timestamp": _now(),
            "source": settings.prometheus_url,
        }
    )


@app.route("/api/historical-trends")
def api_historical_trends():
    history_query = settings.metrics_query
    samples = _require_prometheus(history_query)
    return jsonify(
        {"samples": samples, "source": settings.prometheus_url, "timestamp": _now()}
    )


@app.route("/api/anomaly-timeline")
def api_anomaly_timeline():
    anomalies = _require_prometheus(settings.anomalies_query)
    actions = _refresh_actions()
    return jsonify({"anomalies": anomalies, "actions": actions, "timestamp": _now()})


@app.route("/api/ai-recommendations")
def api_ai_recommendations():
    return jsonify(_refresh_insights("recommendations"))


@app.route("/api/rca-insights")
def api_rca_insights():
    return jsonify(_refresh_insights("rca"))


@app.route("/api/suppress-alert", methods=["POST"])
def api_suppress_alert():
    payload = validate_json_object(request.get_json(silent=True))
    alert_id = payload.get("alert_id")
    duration = payload.get("duration")
    comment = payload.get("comment")
    if not isinstance(alert_id, str) or not alert_id.strip():
        raise RequestValidationError("alert_id must be a non-empty string")
    if not isinstance(duration, int) or not 1 <= duration <= 10080:
        raise RequestValidationError(
            "duration must be an integer between 1 and 10080 minutes"
        )
    if not isinstance(comment, str) or not comment.strip():
        raise RequestValidationError("comment must be a non-empty string")
    alerts = _refresh_alerts()
    selected = next((alert for alert in alerts if alert.get("id") == alert_id), None)
    if not selected:
        raise RequestValidationError(
            "alert_id was not found in the active Alertmanager set"
        )
    matchers = [{"name": "fingerprint", "value": alert_id, "isRegex": False}]
    result = alertmanager.create_silence(
        matchers, duration, comment, settings.service_name
    )
    audit_log.record(
        "alert_suppressed",
        g.request_id,
        alert_id=alert_id,
        duration_minutes=duration,
        silence_id=result.get("silence_id"),
    )
    return jsonify({"status": "suppressed", "alert_id": alert_id, **result})


@app.route("/api/grouped-incidents")
def api_grouped_incidents():
    incidents = _refresh_incidents()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for incident in incidents:
        services = (
            incident.get("affected_services")
            or incident.get("service")
            or "unclassified"
        )
        key = ",".join(services) if isinstance(services, list) else str(services)
        groups[key].append(incident)
    return jsonify(
        {
            "groups": [
                {"service": service, "incidents": values, "count": len(values)}
                for service, values in groups.items()
            ]
        }
    )


@app.route("/api/ml-insights")
def api_ml_insights():
    return jsonify(_refresh_insights("ml"))


@app.route("/api/performance-metrics")
def api_performance_metrics():
    return jsonify(
        {
            "samples": _refresh_metrics(),
            "source": settings.prometheus_url,
            "timestamp": _now(),
        }
    )


@app.route("/api/self-healing-timeline")
def api_self_healing_timeline():
    return jsonify(_refresh_actions())


@app.route("/api/set-thresholds", methods=["POST"])
def api_set_thresholds():
    payload = validate_json_object(request.get_json(silent=True))
    required = {"cpu", "mem", "disk"}
    if set(payload) != required:
        raise RequestValidationError("payload must contain exactly cpu, mem, and disk")
    for key, value in payload.items():
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not 0 < float(value) < 100
        ):
            raise RequestValidationError(f"{key} must be a number between 0 and 100")
    result = _external_json(
        settings.thresholds_url, "Threshold service", method="POST", payload=payload
    )
    audit_log.record("thresholds_updated", g.request_id, fields=list(payload))
    return jsonify(result)


@app.route("/api/slo")
def api_slo():
    return jsonify(
        metrics_registry.slo_snapshot(settings.slo_target, settings.slo_window_minutes)
    )


@app.route("/api/audit")
def api_audit():
    try:
        limit = int(request.args.get("limit", "100"))
    except ValueError as exc:
        raise RequestValidationError("limit must be an integer") from exc
    return jsonify({"events": audit_log.snapshot(limit)})


def process_query(query: str) -> dict[str, Any]:
    """Compatibility helper that always delegates to the configured model."""
    clean_query = validate_query({"query": query}, settings.max_query_length)
    return model.answer(clean_query, _build_context())


def run_dashboard() -> None:
    app.run(host=settings.host, port=settings.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_dashboard()
