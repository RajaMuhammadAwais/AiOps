# AiOps Operations Platform

AiOps is an integration-backed operations interface for teams that need a single API and dashboard over telemetry, alerting, incidents, operational logs, remediation workflows, and externally hosted analysis. It does not generate or invent operational records. When a source is not configured or cannot be reached, the API returns an explicit integration error and the readiness probe remains unsuccessful.

## Operating model

The web layer is intentionally a thin control plane. Prometheus supplies query results and metric samples; Alertmanager supplies active alerts and silence operations; incident, log, action, and insight services supply their respective records; and the assistant delegates to a configured OpenAI-compatible model endpoint. Durable identity, authorization policy, and audit retention should be provided by the deployment gateway and centralized logging platform.

| Capability | Source contract | API behavior when absent |
|---|---|---|
| Status and metrics | Prometheus URL plus query expressions | `503 integration_unavailable` |
| Alerts and alert silencing | Alertmanager API | `503 integration_unavailable` |
| Incidents | `AIOPS_INCIDENTS_URL` returning `{ "incidents": [] }` | `503 integration_unavailable` |
| Logs | `AIOPS_LOGS_URL` returning `{ "log_events": [] }` | `503 integration_unavailable` |
| Remediation state | `AIOPS_ACTIONS_URL` returning a JSON object | `503 integration_unavailable` |
| Recommendations and RCA | `AIOPS_INSIGHTS_URL` supporting `?kind=` | `503 integration_unavailable` |
| Assistant | `AIOPS_LLM_URL` and `AIOPS_LLM_MODEL` | `503 integration_unavailable` |
| Threshold persistence | `AIOPS_THRESHOLDS_URL` accepting a JSON object | `503 integration_unavailable` |

## Configuration

The service requires the following variables and refuses to start if they are missing:

```bash
export AIOPS_ENV="${AIOPS_ENV:?set deployment environment}"
export AIOPS_SERVICE_NAME="${AIOPS_SERVICE_NAME:?set service identity}"
export AIOPS_VERSION="${AIOPS_VERSION:?set immutable build identifier}"
export AIOPS_HOST="${AIOPS_HOST:?set bind address}"
export AIOPS_PORT="${AIOPS_PORT:?set service port}"
export AIOPS_API_KEY="${AIOPS_API_KEY:?inject from secret management}"
export AIOPS_ALLOWED_ORIGINS="${AIOPS_ALLOWED_ORIGINS:?set explicit browser origins}"
export AIOPS_PROMETHEUS_URL="${AIOPS_PROMETHEUS_URL:-}"
export AIOPS_ALERTMANAGER_URL="${AIOPS_ALERTMANAGER_URL:-}"
export AIOPS_STATUS_QUERY="${AIOPS_STATUS_QUERY:-}"
export AIOPS_METRICS_QUERY="${AIOPS_METRICS_QUERY:-}"
export AIOPS_ANOMALIES_QUERY="${AIOPS_ANOMALIES_QUERY:-}"
export AIOPS_LLM_URL="${AIOPS_LLM_URL:-}"
export AIOPS_LLM_API_KEY="${AIOPS_LLM_API_KEY:-}"
export AIOPS_LLM_MODEL="${AIOPS_LLM_MODEL:-}"
export AIOPS_INCIDENTS_URL="${AIOPS_INCIDENTS_URL:-}"
export AIOPS_LOGS_URL="${AIOPS_LOGS_URL:-}"
export AIOPS_ACTIONS_URL="${AIOPS_ACTIONS_URL:-}"
export AIOPS_INSIGHTS_URL="${AIOPS_INSIGHTS_URL:-}"
export AIOPS_THRESHOLDS_URL="${AIOPS_THRESHOLDS_URL:-}"
```

The remaining `AIOPS_*` settings control request limits, TLS verification, SLO window, refresh interval, and structured logging. Their accepted ranges are defined in `src/platform/config.py`. Secrets must be injected by a secret manager or deployment environment; they must not be committed to the repository.

## Run

Install the dependency set and start the service with the deployment environment loaded:

```bash
python3 -m pip install -r requirements.txt
python3 web_dashboard.py
```

The live probe is `/health/live`; the dependency probe is `/health/ready`; Prometheus-compatible service metrics are exposed at `/metrics`. API requests require `X-AiOps-API-Key` or `Authorization: Bearer <key>` when `AIOPS_API_KEY` is configured.

## API surface

The read APIs include `/api/status`, `/api/incidents`, `/api/alerts`, `/api/metrics`, `/api/log-events`, `/api/health-heatmap`, `/api/historical-trends`, `/api/anomaly-timeline`, `/api/ai-recommendations`, `/api/rca-insights`, `/api/grouped-incidents`, `/api/ml-insights`, `/api/performance-metrics`, `/api/self-healing`, and `/api/self-healing-timeline`. The controlled write APIs are `/api/query`, `/api/suppress-alert`, and `/api/set-thresholds`. Operational reliability and audit endpoints are `/api/slo` and `/api/audit`.

All API responses include a request identifier through the `X-Request-ID` response header. Query input is bounded and the service records only a fingerprint in the in-process audit log. The dashboard uses DOM text assignment rather than interpreting source data as HTML.

## Repository map

```text
web_dashboard.py             Flask API and dashboard composition
src/platform/                configuration, adapters, security, state, observability
src/monitoring/              monitoring components and integration hooks
src/observability/            tracing components
src/intelligence/             model and forecasting components
src/ml/                       analytics and detection components
src/alerting/                 alert lifecycle and action definitions
templates/dashboard.html     integration-backed browser UI
.github/workflows/            quality, security, and release automation
OPERATIONS.md                deployment, trust-boundary, and migration contract
```

## Validation

Run syntax compilation and the standard-library foundation tests with the same environment variables used by the deployment:

```bash
python3 -m compileall -q .
python3 -m unittest discover -s tests -v
```

The repository’s HTTP smoke script is intentionally separate from unit tests because it requires a running service and configured external systems.

## Research basis

The platform’s request correlation and telemetry model follows the OpenTelemetry observability model [1]. Its SLO and error-budget endpoint follows Google SRE’s SLO practice [2]. AI input handling and tool-boundary decisions are informed by the NIST Generative AI Profile [3] and the OWASP GenAI security guidance [4]. CI provenance and artifact controls follow GitHub’s secure-use guidance and SLSA build requirements [5] [6].

## License

See `LICENSE.md`.

## References

[1]: https://opentelemetry.io/docs/concepts/observability-primer/ "OpenTelemetry Observability Primer"
[2]: https://sre.google/workbook/implementing-slos/ "Google SRE Workbook: Implementing SLOs"
[3]: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence "NIST AI RMF Generative AI Profile"
[4]: https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/ "OWASP GenAI LLM Top 10 2026"
[5]: https://docs.github.com/en/actions/reference/security/secure-use "GitHub Actions Secure Use Reference"
[6]: https://slsa.dev/spec/v1.2/build-requirements "SLSA v1.2 Build Requirements"
