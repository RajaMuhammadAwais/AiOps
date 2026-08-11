# AiOps Operations Platform

[![Observability: OpenTelemetry](https://img.shields.io/badge/Observability-OpenTelemetry-425CC7?logo=opentelemetry&logoColor=white)](https://opentelemetry.io/docs/concepts/observability-primer/)
[![AI Governance: NIST AI RMF](https://img.shields.io/badge/AI%20Governance-NIST%20AI%20RMF-1f4e79)](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
[![GenAI Security: OWASP](https://img.shields.io/badge/GenAI%20Security-OWASP-000000?logo=owasp&logoColor=white)](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/)
[![Build Integrity: SLSA](https://img.shields.io/badge/Build%20Integrity-SLSA-6f42c1)](https://slsa.dev/spec/v1.2/build-requirements)

AiOps is a **real-integration operations control plane**. It presents a Flask web dashboard and JSON API over configured operational systems such as Prometheus, Alertmanager, incident services, log services, action services, threshold services, insight services, and an OpenAI-compatible model endpoint.

The central design rule is simple:

> AiOps must never invent telemetry, incidents, alerts, remediation results, model output, or configuration values. If a required upstream system is unavailable or returns an invalid response, the dependent request fails explicitly.

This repository is intended for teams that need a lightweight operational interface while keeping source-of-truth data, identity, authorization, durable storage, and deployment ownership in the surrounding platform.

## Why this project exists

Operations data is usually distributed across monitoring, alerting, incident management, logs, change systems, remediation systems, and analysis tools. AiOps provides one consistent interface for reading that data, correlating a request across the service, and exposing a small set of validated mutation paths.

It is useful when you need to:

| Need | What AiOps provides |
|---|---|
| A single operational view | A dashboard and API over configured upstream systems. |
| Trustworthy integration behavior | Explicit `503 integration_unavailable` responses instead of fabricated fallback data. |
| Safer model-assisted analysis | A model adapter that receives the configured operational context and is instructed to state uncertainty when context is insufficient. |
| Controlled writes | Validated alert-suppression and threshold-update routes that call configured upstream services. |
| Basic request accountability | Request IDs, bounded rate limiting, authentication support, secret redaction, structured logging, and a bounded in-process audit view. |
| Deployment visibility | Liveness, readiness, Prometheus-compatible service metrics, SLO calculations, and explicit configuration validation. |

## What AiOps is—and is not

AiOps is a **control-plane component**, not a replacement for the systems that own operational truth.

| AiOps is | AiOps is not |
|---|---|
| A dashboard and API composition layer. | A Prometheus or Alertmanager replacement. |
| An integration client for configured upstream data. | An incident database or durable event store. |
| A bounded interface for model-assisted operational questions. | A general autonomous agent or unrestricted shell executor. |
| A place to validate request shape and refuse unsafe or unavailable operations. | A substitute for an identity-aware gateway, service mesh, policy engine, or secret manager. |
| A foundation for adding durable audit sinks and policy-controlled automation. | A claim that in-process state survives restart or is suitable for regulated retention. |

The current `/api/audit` endpoint exposes the legacy bounded in-memory audit log used by the web application. The newer typed audit-event contract in `src/platform/audit.py` defines a storage-neutral event format and `AuditSink` interface, but it is **not yet wired into the production mutation routes**. Until a deployment supplies and integration-tests a durable, access-controlled sink, audit data must be treated as process-local diagnostic state.

## Architecture

```text
Browser or API client
        |
        | HTTPS and identity-aware gateway recommended
        v
+-----------------------------+
| Flask dashboard/API         |
| - request IDs               |
| - authentication            |
| - rate limiting             |
| - validation and redaction  |
| - health and SLO endpoints  |
+-----------------------------+
        |
        +--> PrometheusAdapter ----> Prometheus HTTP API
        +--> AlertmanagerAdapter --> Alertmanager HTTP API
        +--> External JSON clients -> incidents/logs/actions/insights/thresholds
        +--> ModelAdapter ----------> configured OpenAI-compatible endpoint
        +--> bounded local state and metrics
        +--> bounded in-process audit view
```

The service creates no upstream system and does not seed local records. The installer creates a Python virtual environment and installs declared dependencies only; it does not provision telemetry, databases, queues, model services, or operational data.

## Integration contracts

The following values are deployment-supplied. URLs are treated as upstream service endpoints; secrets must come from a secret manager or injected environment, never from committed files.

| Capability | Required upstream configuration | Expected response or behavior |
|---|---|---|
| Readiness and status | `AIOPS_PROMETHEUS_URL`, `AIOPS_STATUS_QUERY`, `AIOPS_ALERTMANAGER_URL` | Prometheus must return a successful `/api/v1/query` response with `data.result`; Alertmanager must return a JSON list from `/api/v2/alerts`. |
| Metrics | `AIOPS_PROMETHEUS_URL`, `AIOPS_METRICS_QUERY` | The adapter normalizes Prometheus samples into metric name, numeric value, timestamp, and labels. |
| Anomalies | `AIOPS_ANOMALIES_QUERY` with Prometheus configured | The expression is queried through the same Prometheus adapter. |
| Active alerts | `AIOPS_ALERTMANAGER_URL` | The adapter reads active, non-silenced, non-inhibited alerts from `/api/v2/alerts`. |
| Alert suppression | `AIOPS_ALERTMANAGER_URL` | The service validates the alert and duration, then creates a silence through `/api/v2/silences`. |
| Incidents | `AIOPS_INCIDENTS_URL` | The endpoint must return an object containing an `incidents` list. |
| Logs | `AIOPS_LOGS_URL` | The endpoint must return an object containing a `log_events` list. |
| Actions and remediation state | `AIOPS_ACTIONS_URL` | The endpoint must return a JSON object. AiOps does not execute arbitrary local commands. |
| Insights and RCA | `AIOPS_INSIGHTS_URL` | The endpoint is queried with `?kind=recommendations`, `?kind=rca`, or `?kind=ml`. |
| Threshold persistence | `AIOPS_THRESHOLDS_URL` | The service accepts exactly `cpu`, `mem`, and `disk`, each as a number greater than `0` and less than `100`, then sends the object to the configured service. |
| Assistant | `AIOPS_LLM_URL`, `AIOPS_LLM_MODEL`, optional `AIOPS_LLM_API_KEY` | The endpoint must return either `choices[0].message.content` or a non-empty `output_text` string. |

A missing integration affects only the routes that depend on it. The service returns a structured `503` error instead of substituting an empty or synthetic success response.

## Requirements

The packaging metadata declares **Python `>=3.12,<4.0`**. Use Python 3.12 or a newer compatible version. The repository contains both `requirements.txt` and `pyproject.toml`; the supplied installer follows `requirements.txt`.

The runtime requires network access from the service process to each configured upstream. Production deployments should also provide a managed secret source, an approved ingress or reverse proxy, centralized logs, and a durable audit destination before enabling sensitive operational workflows.

## Installation

### Option A: supplied installer

Run the installer from the repository root. Replace the destination placeholder with a deployment-owned path.

```bash
./install_aiops.sh --install-dir /path/to/aiops-install --python python3.12
```

The installer copies the checkout, creates `.venv`, installs `requirements.txt`, validates the deployment environment, and compiles the application. It does not create upstream services or operational records.

### Option B: manual virtual environment

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Before starting the service, validate the exact environment that the process will use:

```bash
python -c 'from src.platform.config import Settings; Settings.from_env(); print("configuration valid")'
```

## Configuration

Configuration is deliberately strict. The service exits with a configuration error when required deployment values are missing, malformed, outside their allowed range, or unsafe for the selected environment.

### Required for every process

```bash
export AIOPS_ENV="development"                 # development, test, staging, production, or prod
export AIOPS_SERVICE_NAME="<deployment-service-name>"
export AIOPS_VERSION="<immutable-build-or-release-id>"
export AIOPS_LOG_LEVEL="INFO"                  # DEBUG, INFO, WARNING, ERROR, or CRITICAL
export AIOPS_PROMETHEUS_TIMEOUT_SECONDS="<1-60>"
export AIOPS_VERIFY_TLS="true"                 # true/false, yes/no, on/off, or 1/0
export AIOPS_MAX_QUERY_LENGTH="<32-10000>"
export AIOPS_RATE_LIMIT_PER_MINUTE="<1-10000>"
export AIOPS_AUDIT_LOG_MAX_ENTRIES="<100-100000>"
export AIOPS_EVENT_STORE_MAX_ENTRIES="<100-100000>"
export AIOPS_SLO_TARGET="<90-100>"
export AIOPS_SLO_WINDOW_MINUTES="<5-10080>"
export AIOPS_REFRESH_SECONDS="<5-3600>"
export AIOPS_HOST="<explicit-bind-address>"
export AIOPS_PORT="<1-65535>"
```

### Required for readiness

`/health/ready` requires all three of the following values and a successful upstream check:

```bash
export AIOPS_PROMETHEUS_URL="<prometheus-base-url>"
export AIOPS_STATUS_QUERY="<deployment-owned-promql-expression>"
export AIOPS_ALERTMANAGER_URL="<alertmanager-base-url>"
```

The adapters append `/api/v1/query` to the Prometheus base URL and `/api/v2/alerts` or `/api/v2/silences` to the Alertmanager base URL. Supply base URLs that match the actual deployment routing.

### Authentication and browser origins

```bash
export AIOPS_API_KEY="<secret-injected-by-secret-manager>"
export AIOPS_ALLOWED_ORIGINS="<https-origin-1>,<https-origin-2>"
```

`AIOPS_API_KEY` is optional outside production. When set, API and metrics requests must include either `X-AiOps-API-Key` or `Authorization: Bearer <key>`. Production requires an API key of at least 24 characters. `AIOPS_ALLOWED_ORIGINS` is optional; when set, it must contain explicit origins and may not contain `*`.

### Optional integrations

```bash
export AIOPS_METRICS_QUERY="<deployment-owned-promql-expression>"
export AIOPS_ANOMALIES_QUERY="<deployment-owned-promql-expression>"
export AIOPS_INCIDENTS_URL="<incident-json-endpoint>"
export AIOPS_LOGS_URL="<log-json-endpoint>"
export AIOPS_ACTIONS_URL="<action-state-json-endpoint>"
export AIOPS_INSIGHTS_URL="<insight-json-endpoint>"
export AIOPS_THRESHOLDS_URL="<threshold-write-endpoint>"
export AIOPS_LLM_URL="<openai-compatible-chat-endpoint>"
export AIOPS_LLM_API_KEY="<secret-if-required-by-model-endpoint>"
export AIOPS_LLM_MODEL="<deployment-model-identifier>"
```

The angle-bracket values above are configuration placeholders, not defaults. Do not copy credentials, production URLs, PromQL expressions, or tokens into the repository.

## Starting the service

```bash
. .venv/bin/activate
python web_dashboard.py
```

For a production deployment, run the process under an approved process manager or container supervisor and place it behind an identity-aware ingress or service mesh. External TLS termination, network policy, secret injection, centralized logging, and durable audit retention belong to the deployment platform.

## Health and observability

| Endpoint | Visibility | Meaning |
|---|---|---|
| `/health/live` | Public | The Python process is running and can return an HTTP response. It does not prove upstream availability. |
| `/health/ready` | Public | Prometheus and Alertmanager configuration and connectivity satisfy the readiness contract. Returns `503` when requirements are missing or upstream checks fail. |
| `/metrics` | Protected when `AIOPS_API_KEY` is configured | Prometheus-compatible request count, latency, status, and SLO-related service metrics. |
| `X-Request-ID` | Response header | Every response receives a request identifier; a caller-provided identifier is preserved. |

The rate limiter is thread-safe but process-local and keyed by the direct peer address. When deploying multiple workers or replicas, enforce the authoritative rate limit at the gateway or use a shared limiter. Do not assume the in-process limiter is a cluster-wide security control.

## API reference

All `/api/*` routes are rate-limited. When authentication is enabled, they require the configured API key. Errors use this shape:

```json
{
  "error": {
    "code": "integration_unavailable",
    "message": "..."
  },
  "request_id": "..."
}
```

### Read routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/status` | Reads the configured status query and returns current samples, active alert/incident counts, and an SLO snapshot. |
| `GET` | `/api/incidents` | Reads the configured incident service. |
| `GET` | `/api/alerts` | Reads active alerts from Alertmanager. |
| `GET` | `/api/metrics` | Reads the configured metrics query and optional anomaly query. |
| `GET` | `/api/log-events` | Reads the configured log service. |
| `GET` | `/api/health-heatmap` | Returns configured metric samples as dashboard component data. |
| `GET` | `/api/historical-trends` | Reads the configured metrics query for trend data. |
| `GET` | `/api/anomaly-timeline` | Reads the anomaly query and configured action-state service. |
| `GET` | `/api/ai-recommendations` | Reads the insight service with `kind=recommendations`. |
| `GET` | `/api/rca-insights` | Reads the insight service with `kind=rca`. |
| `GET` | `/api/grouped-incidents` | Groups configured incidents by affected service. |
| `GET` | `/api/ml-insights` | Reads the insight service with `kind=ml`. |
| `GET` | `/api/performance-metrics` | Reads the configured metrics query. |
| `GET` | `/api/self-healing` | Reads action/remediation state from the configured action service. |
| `GET` | `/api/self-healing-timeline` | Reads action/remediation state for the timeline view. |
| `GET` | `/api/slo` | Returns the configured SLO target and observed service metrics. |
| `GET` | `/api/audit?limit=100` | Returns up to the bounded in-process audit entries; the limit is clamped to `1..1000`. |

### Write and analysis routes

#### Ask the configured model

```bash
curl -fsS \
  -H "Authorization: Bearer ${AIOPS_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "http://${AIOPS_HOST}:${AIOPS_PORT}/api/query" \
  -d '{"query":"Summarize the current operational evidence and state what is unknown."}'
```

The service validates that `query` is a non-empty string within `AIOPS_MAX_QUERY_LENGTH`. It sends the configured model the query and the currently configured metric, alert, and incident context. The service records a non-reversible query fingerprint rather than the raw query in its legacy in-process audit entry.

#### Suppress an active Alertmanager alert

```bash
curl -fsS \
  -H "Authorization: Bearer ${AIOPS_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "http://${AIOPS_HOST}:${AIOPS_PORT}/api/suppress-alert" \
  -d '{
    "alert_id":"<active-alert-fingerprint>",
    "duration":60,
    "comment":"<operator-approved reason>"
  }'
```

The alert must exist in the current active Alertmanager response. `duration` is an integer from `1` to `10080` minutes, and `comment` must be non-empty. The service then creates an Alertmanager silence and records the operation in the bounded audit log.

#### Set thresholds through the configured threshold service

```bash
curl -fsS \
  -H "Authorization: Bearer ${AIOPS_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "http://${AIOPS_HOST}:${AIOPS_PORT}/api/set-thresholds" \
  -d '{"cpu":80,"mem":80,"disk":85}'
```

The payload must contain exactly `cpu`, `mem`, and `disk`. Each value must be numeric, must not be a boolean, and must be greater than `0` and less than `100`. The configured threshold service is the source of persistence; AiOps does not persist these values locally.

## Failure behavior and security boundaries

The service is intentionally conservative around missing or untrusted inputs.

| Condition | Response or behavior |
|---|---|
| Missing required configuration | Process startup fails with a configuration error. |
| Missing required readiness integration | `/health/ready` returns `503` with the missing setting names. |
| Upstream timeout, HTTP failure, invalid JSON, or invalid response shape | Dependent route returns `503 integration_unavailable`. |
| Invalid JSON body or field type | Route returns `400 invalid_request`. |
| Missing or incorrect API key when authentication is enabled | Route returns `401 authentication_required`. |
| Request budget exceeded | Route returns `429 rate_limited`. |
| Payload above the configured maximum | Route returns `413 payload_too_large`. |
| Common bearer, API-key, password, and secret patterns in audit details | Values are redacted before recording. |
| Browser origin not explicitly allowed | No permissive wildcard CORS header is emitted. |
| Unexpected exception | The service logs the correlation ID and returns a generic `500 internal_error`. |

The code sets response hardening headers including `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive `Permissions-Policy`, and no-store caching for API responses. The browser template renders source data with DOM text assignment rather than interpreting upstream values as HTML.

These controls are a baseline, not a complete security architecture. Production deployments should still use identity-aware ingress, centralized authorization, network policy, managed secrets, TLS verification, dependency scanning, durable audit storage, and a controlled policy/action executor before enabling sensitive remediation workflows.

## Operational deployment checklist

Before exposing AiOps to operators, verify the following in the deployment environment:

1. The configured upstream URLs are reachable from the service network and return the documented response shapes.
2. `AIOPS_VERIFY_TLS=true` is used unless a documented trust exception exists.
3. A secret manager injects `AIOPS_API_KEY` and any model credential; no secret is stored in Git.
4. Production has an identity-aware gateway or service mesh in front of the Flask process.
5. `AIOPS_ALLOWED_ORIGINS` contains only the required browser origins, or browser access is disabled.
6. The gateway applies shared rate limiting when more than one worker or replica is deployed.
7. Logs and audit events are exported to a durable, access-controlled platform. The in-process audit log is bounded and is lost on restart.
8. Liveness and readiness are monitored separately, and readiness failures are connected to deployment rollback or traffic removal.
9. The immutable build identifier is set in `AIOPS_VERSION` and is recorded in release metadata.
10. The model endpoint is approved for the operational data classification being sent in `metadata.context`.

## Repository map

```text
web_dashboard.py             Flask API, health probes, dashboard composition, and route wiring
src/platform/config.py       strict environment configuration and range validation
src/platform/security.py     authentication, rate limiting, validation, redaction, and legacy audit log
src/platform/audit.py        versioned audit-event contract and storage-neutral AuditSink protocol
src/platform/integrations.py Prometheus, Alertmanager, external JSON, and model adapters
src/platform/observability.py request metrics, structured logging, and SLO calculations
src/platform/state.py         bounded in-process state store
src/monitoring/               monitoring components and integration hooks
src/observability/             tracing components
src/intelligence/              model and forecasting components
src/ml/                        analytics and detection components
templates/dashboard.html      integration-backed browser interface
tests/                         contract and operational tests
install_aiops.sh               integration-only installer
OPERATIONS.md                  deployment and trust-boundary contract
```

## Development and validation

Create the environment and install the declared dependencies before running checks:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the core validation suite:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
black --check web_dashboard.py src tests
flake8 src/platform tests
mypy src/platform
 git diff --check
```

The HTTP smoke test requires a running service and real configured upstream systems. Unit and contract tests should not be interpreted as proof that a deployment’s Prometheus, Alertmanager, incident, log, action, threshold, insight, or model endpoint is reachable. Those dependencies require a deployment-level integration test.

When adding code, preserve these repository rules:

- Do not add synthetic operational records or fabricated fallback responses.
- Do not add hidden runtime defaults for security, limits, endpoints, or policy.
- Do not execute arbitrary local commands from an HTTP request.
- Do not place credentials, production URLs, or operational query expressions in Git.
- Keep external response validation explicit and return integration errors when trust cannot be established.
- Add tests for negative paths, especially missing configuration, malformed upstream payloads, authorization failures, and unavailable integrations.

## Research basis

The request-correlation and telemetry model is aligned with the OpenTelemetry observability model, which treats telemetry as a combination of signals such as traces, metrics, and logs [1]. The future GenAI/tool-observability direction is informed by the OpenTelemetry GenAI semantic-conventions work [2]. Governance and risk language follows the NIST Generative AI Risk Management Profile [3], while threat-boundary decisions for model and agent interactions are informed by OWASP GenAI guidance [4] [5]. SLO and error-budget concepts follow established SRE practice [6] and the OpenSLO specification [7]. Authorization, workload identity, tool interoperability, and delivery integrity are future extension points informed by OpenFGA, SPIFFE, MCP, GitHub secure-use guidance, and SLSA [8] [9] [10] [11] [12].

These references explain the design direction; they do not mean that every listed future control has already been implemented in this repository. The implementation status is defined by the source files, tests, and operational documents in this checkout.

## License

See `LICENSE.md`.

## References

[1]: https://opentelemetry.io/docs/concepts/observability-primer/ "OpenTelemetry Observability Primer"

[2]: https://github.com/open-telemetry/semantic-conventions-genai "OpenTelemetry GenAI Semantic Conventions"

[3]: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence "NIST AI RMF Generative AI Profile"

[4]: https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/ "OWASP GenAI LLM Top 10"

[5]: https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/ "OWASP Agentic AI Threats and Mitigations"

[6]: https://sre.google/workbook/implementing-slos/ "Google SRE Workbook: Implementing SLOs"

[7]: https://openslo.com/ "OpenSLO"

[8]: https://openfga.dev/docs/fga "OpenFGA Fine-Grained Authorization"

[9]: https://spiffe.io/docs/latest/spiffe-about/overview/ "SPIFFE Overview"

[10]: https://modelcontextprotocol.io/specification/2026-07-28 "Model Context Protocol Specification"

[11]: https://docs.github.com/en/actions/reference/security/secure-use "GitHub Actions Secure Use Reference"

[12]: https://slsa.dev/spec/v1.2/build-requirements "SLSA v1.2 Build Requirements"
