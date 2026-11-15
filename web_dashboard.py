"""AiOps operational dashboard and integration-backed API."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any, Mapping, Protocol, cast

from flask import (
    Blueprint,
    Flask,
    Response,
    current_app,
    g,
    jsonify,
    render_template,
    request,
)
import requests

from src.platform.config import Settings
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

routes = Blueprint("aiops", __name__)


class PrometheusClient(Protocol):
    def query(self, expression: str | None) -> list[dict[str, Any]]: ...


class AlertmanagerClient(Protocol):
    def active_alerts(self) -> list[dict[str, Any]]: ...

    def create_silence(
        self,
        matchers: list[dict[str, Any]],
        duration_minutes: int,
        comment: str,
        created_by: str,
    ) -> dict[str, Any]: ...


class ModelClient(Protocol):
    def answer(self, query: str, context: Mapping[str, Any]) -> dict[str, Any]: ...


class HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> Any: ...


class HttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        timeout: int,
        verify: bool,
    ) -> HttpResponse: ...


@dataclass(frozen=True)
class DashboardDependencies:
    """External clients optionally supplied by a deployment or a test."""

    prometheus: PrometheusClient | None = None
    alertmanager: AlertmanagerClient | None = None
    model: ModelClient | None = None
    http: HttpClient | None = None


@dataclass
class DashboardRuntime:
    """State scoped to one Flask application instance."""

    settings: Settings
    prometheus: PrometheusClient
    alertmanager: AlertmanagerClient
    model: ModelClient
    http: HttpClient
    metrics_registry: MetricsRegistry
    rate_limiter: SlidingWindowRateLimiter
    audit_log: AuditLog
    state_store: BoundedStore
    security_policy: SecurityPolicy


def _runtime() -> DashboardRuntime:
    """Return the runtime bound to the current Flask application."""
    return cast(DashboardRuntime, current_app.extensions["aiops"])


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
    runtime = _runtime()
    if not url:
        raise IntegrationUnavailable(f"{label} is not configured")
    try:
        response = runtime.http.request(
            method,
            url,
            params=params,
            json=payload,
            timeout=runtime.settings.prometheus_timeout_seconds,
            verify=runtime.settings.verify_tls,
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
    runtime = _runtime()
    alerts = runtime.alertmanager.active_alerts()
    runtime.state_store.replace("alerts", alerts)
    return alerts


def _refresh_metrics() -> list[dict[str, Any]]:
    runtime = _runtime()
    metrics = runtime.prometheus.query(runtime.settings.metrics_query)
    runtime.state_store.replace("metrics", metrics)
    return metrics


def _refresh_incidents() -> list[dict[str, Any]]:
    runtime = _runtime()
    incidents = _list_payload(
        _external_json(runtime.settings.incidents_url, "Incident service"), "incidents"
    )
    runtime.state_store.replace("incidents", incidents)
    return incidents


def _refresh_logs() -> list[dict[str, Any]]:
    runtime = _runtime()
    logs = _list_payload(
        _external_json(runtime.settings.logs_url, "Log service"), "log_events"
    )
    runtime.state_store.replace("log_events", logs)
    return logs


def _refresh_actions() -> dict[str, Any]:
    runtime = _runtime()
    payload = _external_json(runtime.settings.actions_url, "Action service")
    if not isinstance(payload, dict):
        raise IntegrationUnavailable("Action service did not return an object")
    runtime.state_store.set("self_healing_stats", payload)
    return payload


def _refresh_insights(kind: str | None = None) -> Any:
    runtime = _runtime()
    params = {"kind": kind} if kind else None
    payload = _external_json(
        runtime.settings.insights_url, "Insight service", params=params
    )
    runtime.state_store.set("insights", payload)
    return payload


def _require_prometheus(expression: str | None) -> list[dict[str, Any]]:
    return _runtime().prometheus.query(expression)


def _build_context() -> dict[str, Any]:
    runtime = _runtime()
    settings = runtime.settings
    context: dict[str, Any] = {}
    if settings.prometheus_url and settings.metrics_query:
        context["metrics"] = _refresh_metrics()
    if settings.alertmanager_url:
        context["alerts"] = _refresh_alerts()
    if settings.incidents_url:
        context["incidents"] = _refresh_incidents()
    return context


@routes.route("/")
def dashboard():
    settings = _runtime().settings
    return render_template(
        "dashboard.html",
        service_name=settings.service_name,
        version=settings.version,
        max_query_length=settings.max_query_length,
        refresh_seconds=settings.refresh_seconds,
    )


@routes.route("/health/live")
def health_live():
    settings = _runtime().settings
    return jsonify(
        {
            "status": "alive",
            "service": settings.service_name,
            "version": settings.version,
            "timestamp": _now(),
        }
    )


@routes.route("/health/ready")
def health_ready():
    runtime = _runtime()
    settings = runtime.settings
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
        runtime.prometheus.query(settings.status_query)
        runtime.alertmanager.active_alerts()
    except IntegrationUnavailable as exc:
        current_app.logger.warning(
            "readiness_check_failed",
            exc_info=exc,
            extra={"request_id": getattr(g, "request_id", None)},
        )
        return (
            jsonify(
                {
                    "status": "not_ready",
                    "reason": "Dependency health check failed",
                    "timestamp": _now(),
                }
            ),
            503,
        )
    return jsonify({"status": "ready", "timestamp": _now()})


@routes.route("/metrics")
def metrics():
    runtime = _runtime()
    return Response(
        runtime.metrics_registry.prometheus(runtime.settings.service_name),
        mimetype="text/plain; version=0.0.4",
    )


@routes.route("/api/status")
def api_status():
    runtime = _runtime()
    settings = runtime.settings
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
            "slo": runtime.metrics_registry.slo_snapshot(
                settings.slo_target, settings.slo_window_minutes
            ),
        }
    )


@routes.route("/api/incidents")
def api_incidents():
    settings = _runtime().settings
    incidents = _refresh_incidents()
    return jsonify(
        {
            "incidents": incidents,
            "total": len(incidents),
            "source": settings.incidents_url,
        }
    )


@routes.route("/api/alerts")
def api_alerts():
    settings = _runtime().settings
    alerts = _refresh_alerts()
    return jsonify(
        {"alerts": alerts, "total": len(alerts), "source": settings.alertmanager_url}
    )


@routes.route("/api/metrics")
def api_metrics():
    settings = _runtime().settings
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


@routes.route("/api/self-healing")
def api_self_healing():
    return jsonify(_refresh_actions())


@routes.route("/api/query", methods=["POST"])
def api_query():
    runtime = _runtime()
    payload = validate_json_object(request.get_json(silent=True))
    query = validate_query(payload, runtime.settings.max_query_length)
    context = _build_context()
    result = runtime.model.answer(query, context)
    runtime.audit_log.record(
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
            "policy": runtime.security_policy.__dict__,
        }
    )


@routes.route("/api/log-events")
def api_log_events():
    settings = _runtime().settings
    logs = _refresh_logs()
    return jsonify(
        {"log_events": logs, "total": len(logs), "source": settings.logs_url}
    )


@routes.route("/api/health-heatmap")
def api_health_heatmap():
    settings = _runtime().settings
    metrics_data = _refresh_metrics()
    return jsonify(
        {
            "components": metrics_data,
            "timestamp": _now(),
            "source": settings.prometheus_url,
        }
    )


@routes.route("/api/historical-trends")
def api_historical_trends():
    settings = _runtime().settings
    samples = _require_prometheus(settings.metrics_query)
    return jsonify(
        {"samples": samples, "source": settings.prometheus_url, "timestamp": _now()}
    )


@routes.route("/api/anomaly-timeline")
def api_anomaly_timeline():
    anomalies = _require_prometheus(_runtime().settings.anomalies_query)
    actions = _refresh_actions()
    return jsonify({"anomalies": anomalies, "actions": actions, "timestamp": _now()})


@routes.route("/api/ai-recommendations")
def api_ai_recommendations():
    return jsonify(_refresh_insights("recommendations"))


@routes.route("/api/rca-insights")
def api_rca_insights():
    return jsonify(_refresh_insights("rca"))


@routes.route("/api/suppress-alert", methods=["POST"])
def api_suppress_alert():
    runtime = _runtime()
    payload = validate_json_object(request.get_json(silent=True))
    alert_id = payload.get("alert_id")
    duration = payload.get("duration")
    comment = payload.get("comment")
    if not isinstance(alert_id, str) or not alert_id.strip():
        raise RequestValidationError("alert_id must be a non-empty string")
    is_integer_duration = isinstance(duration, int) and not isinstance(duration, bool)
    if not is_integer_duration or not 1 <= duration <= 10080:
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
    result = runtime.alertmanager.create_silence(
        matchers, duration, comment, runtime.settings.service_name
    )
    runtime.audit_log.record(
        "alert_suppressed",
        g.request_id,
        alert_id=alert_id,
        duration_minutes=duration,
        silence_id=result.get("silence_id"),
    )
    return jsonify({"status": "suppressed", "alert_id": alert_id, **result})


@routes.route("/api/grouped-incidents")
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


@routes.route("/api/ml-insights")
def api_ml_insights():
    return jsonify(_refresh_insights("ml"))


@routes.route("/api/performance-metrics")
def api_performance_metrics():
    settings = _runtime().settings
    return jsonify(
        {
            "samples": _refresh_metrics(),
            "source": settings.prometheus_url,
            "timestamp": _now(),
        }
    )


@routes.route("/api/self-healing-timeline")
def api_self_healing_timeline():
    return jsonify(_refresh_actions())


@routes.route("/api/set-thresholds", methods=["POST"])
def api_set_thresholds():
    runtime = _runtime()
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
        runtime.settings.thresholds_url,
        "Threshold service",
        method="POST",
        payload=payload,
    )
    runtime.audit_log.record("thresholds_updated", g.request_id, fields=list(payload))
    return jsonify(result)


@routes.route("/api/slo")
def api_slo():
    runtime = _runtime()
    return jsonify(
        runtime.metrics_registry.slo_snapshot(
            runtime.settings.slo_target, runtime.settings.slo_window_minutes
        )
    )


@routes.route("/api/audit")
def api_audit():
    try:
        limit = int(request.args.get("limit", "100"))
    except ValueError as exc:
        raise RequestValidationError("limit must be an integer") from exc
    return jsonify({"events": _runtime().audit_log.snapshot(limit)})


def create_app(
    settings: Settings | None = None,
    *,
    dependencies: DashboardDependencies | None = None,
) -> Flask:
    """Create an independently configured Flask application.

    Supplying ``settings`` and fake clients through ``dependencies`` keeps route
    tests isolated from process environment variables and live upstream services.
    The environment is read only when callers omit ``settings``.
    """
    app_settings = settings if settings is not None else Settings.from_env()
    clients = dependencies or DashboardDependencies()
    runtime = DashboardRuntime(
        settings=app_settings,
        prometheus=(
            clients.prometheus
            if clients.prometheus is not None
            else PrometheusAdapter(app_settings)
        ),
        alertmanager=(
            clients.alertmanager
            if clients.alertmanager is not None
            else AlertmanagerAdapter(app_settings)
        ),
        model=(
            clients.model if clients.model is not None else ModelAdapter(app_settings)
        ),
        http=clients.http if clients.http is not None else requests.Session(),
        metrics_registry=MetricsRegistry(
            max_samples=app_settings.event_store_max_entries
        ),
        rate_limiter=SlidingWindowRateLimiter(app_settings.rate_limit_per_minute),
        audit_log=AuditLog(app_settings.audit_log_max_entries),
        state_store=BoundedStore(app_settings.event_store_max_entries),
        security_policy=SecurityPolicy(input_max_length=app_settings.max_query_length),
    )

    application = Flask(__name__)
    application.config["MAX_CONTENT_LENGTH"] = app_settings.max_query_length + 4096
    application.extensions["aiops"] = runtime
    application.register_blueprint(routes)

    @application.before_request
    def before_request() -> None:
        request_id = request.headers.get("X-Request-ID")
        if isinstance(request_id, str):
            request_id = "".join(
                ch for ch in request_id if ch.isalnum() or ch in ("-", "_")
            )
        g.request_id = request_id or new_request_id()
        g.started_at = time.perf_counter()
        if request.path.startswith("/api") or request.path == "/metrics":
            if not runtime.rate_limiter.allow(request_key(request)):
                runtime.audit_log.record(
                    "rate_limit_denied", g.request_id, path=request.path
                )
                raise RateLimitExceeded("Request rate limit exceeded")
            authorize(request, app_settings)

    @application.after_request
    def after_request(response: Response) -> Response:
        request_id = getattr(g, "request_id", new_request_id())
        started_at = getattr(g, "started_at", time.perf_counter())
        runtime.metrics_registry.observe(
            request.method,
            request.path,
            response.status_code,
            time.perf_counter() - started_at,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Cache-Control"] = (
            "no-store" if request.path.startswith("/api") else "no-cache"
        )
        origin = request.headers.get("Origin")
        if origin and origin in app_settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    @application.errorhandler(RequestValidationError)
    def handle_validation_error(error: RequestValidationError):
        return _error(str(error), 400, "invalid_request")

    @application.errorhandler(AuthenticationError)
    def handle_authentication_error(error: AuthenticationError):
        return _error(str(error), 401, "authentication_required")

    @application.errorhandler(RateLimitExceeded)
    def handle_rate_limit_error(error: RateLimitExceeded):
        return _error(str(error), 429, "rate_limited")

    @application.errorhandler(IntegrationUnavailable)
    def handle_integration_error(error: IntegrationUnavailable):
        current_app.logger.warning(
            "integration_unavailable",
            extra={"request_id": getattr(g, "request_id", None)},
        )
        return _error(str(error), 503, "integration_unavailable")

    @application.errorhandler(413)
    def handle_payload_too_large(_error):
        return _error(
            "Request payload exceeds the configured limit", 413, "payload_too_large"
        )

    @application.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        current_app.logger.exception(
            "unhandled_request_error",
            extra={"request_id": getattr(g, "request_id", None)},
        )
        return _error("Unexpected service error", 500, "internal_error")

    return application


class LazyWSGIApplication:
    """WSGI-callable production entry point that defers environment loading."""

    def __init__(self) -> None:
        self._application: Flask | None = None
        self._lock = threading.Lock()

    def _get_application(self) -> Flask:
        if self._application is None:
            with self._lock:
                if self._application is None:
                    settings = Settings.from_env()
                    configure_logging(settings.log_level)
                    self._application = create_app(settings)
        return self._application

    def __call__(self, environ: dict[str, Any], start_response: Any) -> Any:
        return self._get_application()(environ, start_response)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_application(), name)


# Gunicorn and other WSGI servers can continue to target ``web_dashboard:app``.
# Configuration is validated when the WSGI callable is first used, not on import.
app = LazyWSGIApplication()


def process_query(query: str) -> dict[str, Any]:
    """Compatibility helper that always delegates to the configured model."""
    application = app._get_application()
    with application.app_context():
        runtime = _runtime()
        clean_query = validate_query(
            {"query": query}, runtime.settings.max_query_length
        )
        return runtime.model.answer(clean_query, _build_context())


def run_dashboard() -> None:
    """Run the local development server using environment-based settings."""
    application = app._get_application()
    settings = cast(DashboardRuntime, application.extensions["aiops"]).settings
    application.run(
        host=settings.host,
        port=settings.port,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    run_dashboard()
