# AiOps Operations Contract

## Purpose and trust boundary

The service is a thin operational control plane. It is trusted to authenticate requests when an API key is configured, validate and bound request bodies, correlate requests, expose service metrics, and delegate external calls through configured adapters. It is not trusted to invent telemetry, decide that a dependency is healthy without checking it, execute autonomous remediation, or retain durable audit history in process memory.

> A missing or unavailable source is an operational failure, not a reason to return a plausible-looking value.

Prometheus and Alertmanager are the first-party operational sources. The incident, log, action, insight, and threshold URLs are service-to-service boundaries owned by the deployment. The assistant is an external model boundary and receives only the context assembled from configured sources. Tool execution and remediation approval remain outside this repository.

## Required source contracts

| Variable | Expected contract | Read/write |
|---|---|---|
| `AIOPS_PROMETHEUS_URL` | Prometheus base URL exposing `/api/v1/query` | Read |
| `AIOPS_STATUS_QUERY` | PromQL expression for dependency status | Read |
| `AIOPS_METRICS_QUERY` | PromQL expression for dashboard metrics | Read |
| `AIOPS_ANOMALIES_QUERY` | PromQL expression for anomaly series | Read |
| `AIOPS_ALERTMANAGER_URL` | Alertmanager base URL exposing `/api/v2/alerts` and `/api/v2/silences` | Read/write |
| `AIOPS_INCIDENTS_URL` | JSON endpoint returning `{ "incidents": [...] }` | Read |
| `AIOPS_LOGS_URL` | JSON endpoint returning `{ "log_events": [...] }` | Read |
| `AIOPS_ACTIONS_URL` | JSON endpoint returning the current remediation state | Read |
| `AIOPS_INSIGHTS_URL` | JSON endpoint supporting `kind=recommendations`, `kind=rca`, and `kind=ml` | Read |
| `AIOPS_THRESHOLDS_URL` | JSON endpoint accepting the exact `cpu`, `mem`, and `disk` fields | Write |
| `AIOPS_LLM_URL` | OpenAI-compatible chat or response endpoint | Read/write request |
| `AIOPS_LLM_MODEL` | Deployment-owned model identifier | Read |

Every adapter validates the response shape and converts connection, HTTP, JSON, and schema failures into `integration_unavailable`. The application does not silently use a local fixture, random value, stale sample, or placeholder response.

## Health and reliability semantics

`/health/live` answers whether the Python process can serve HTTP. `/health/ready` checks that the Prometheus and Alertmanager contracts are configured and reachable. A 200 liveness result must not be interpreted as dependency health. The `/api/status` response includes the configured status samples, active alert and incident counts where their sources are configured, and the locally observed request SLO snapshot.

The `/metrics` endpoint exposes request counters and bounded latency samples in Prometheus text format. The `/api/slo` endpoint reports the configured objective, request count, error count, observed availability, budget remaining, budget consumed, and burn rate over the configured window. A production deployment should replace the process-local sample window with durable telemetry aggregation before using it for paging or compliance evidence.

## Security controls

API routes are protected by `X-AiOps-API-Key` or a bearer token whenever `AIOPS_API_KEY` is configured. Production startup requires an API key of at least 24 characters and an explicit CORS origin list. The service applies a process-local sliding-window limiter, bounds the assistant query, redacts common secret patterns in audit details, and returns a request identifier on every response.

The browser dashboard assigns source values with `textContent` and does not interpret source payloads as HTML. The assistant policy metadata states that autonomous actions are disabled and human approval is required. The model adapter sends only the assembled context and user question; it does not expose local environment variables, request headers, or audit records to the model.

The in-process audit log is bounded and is not a durable compliance store. Deployments must ship structured service logs and audit events to an access-controlled retention system before enabling sensitive write operations in production.

## Deployment rules

Secrets must be supplied by the deployment secret manager. The repository must not contain live credentials, endpoint-specific bearer tokens, or source fixtures. TLS verification remains enabled by default; disabling it requires an explicit deployment decision and should be limited to controlled test environments.

The service should run behind an identity-aware gateway, with network policy restricting outbound connections to the configured source systems and model gateway. The gateway should enforce organization-level identity, authorization scopes, request body limits, and durable audit retention. A release should be promoted only after readiness succeeds against the intended telemetry and alerting systems.

## Migration sequence

First, configure Prometheus, Alertmanager, service URLs, and the model gateway in a non-production environment. Second, verify the source schemas, readiness behavior, request correlation, alert-silence approval path, and structured log shipping. Third, configure a durable audit sink and gateway authorization. Fourth, set the service SLO target and alert on error-budget burn. Finally, enable write routes for approved operators and keep autonomous remediation disabled until a separate executor has explicit policy, approval, rollback, and audit controls.

## Research basis

The request, metric, and log model is aligned with OpenTelemetry’s observability primer [1]. The SLO and error-budget model is based on Google SRE guidance [2]. AI risk and governance boundaries use the NIST Generative AI Profile [3] and OWASP GenAI security guidance [4]. CI workflow hardening and artifact integrity should follow GitHub’s secure-use guidance and SLSA build requirements [5] [6].

## References

[1]: https://opentelemetry.io/docs/concepts/observability-primer/ "OpenTelemetry Observability Primer"
[2]: https://sre.google/workbook/implementing-slos/ "Google SRE Workbook: Implementing SLOs"
[3]: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence "NIST AI RMF Generative AI Profile"
[4]: https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/ "OWASP GenAI LLM Top 10 2026"
[5]: https://docs.github.com/en/actions/reference/security/secure-use "GitHub Actions Secure Use Reference"
[6]: https://slsa.dev/spec/v1.2/build-requirements "SLSA v1.2 Build Requirements"
