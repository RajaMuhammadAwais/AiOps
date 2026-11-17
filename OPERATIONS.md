# AiOps Operations Contract

## Purpose and trust boundary

The service is a thin operational control plane. It is trusted to authenticate API keys or configured gateway assertions, enforce route scopes, validate and bound request bodies, correlate requests, expose service metrics, and delegate external calls through configured adapters. It is not trusted to invent telemetry, decide that a dependency is healthy without checking it, execute autonomous remediation, or retain durable audit history in process memory.

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

Response validation is endpoint-specific, not a uniform guarantee across every configured service. Typed clients enforce their defined response checks; generic JSON endpoints do not yet share versioned schemas or equivalent validation. Some malformed payloads may not map uniformly to the documented unavailable response. Add contract tests for each actual upstream before relying on its route. The application does not silently use a local fixture, random value, stale sample, or placeholder response.

## Health and reliability semantics

`/health/live` answers whether the Python process can serve HTTP. `/health/ready` checks that the Prometheus and Alertmanager contracts are configured and reachable. A 200 liveness result must not be interpreted as dependency health. The `/api/status` response includes configured status samples, active alert and incident counts where their sources are configured, and an SLO snapshot labeled with its source.

`/metrics` exposes bounded-label request counters and fixed-bucket latency histograms. Route labels use Flask route templates, not raw request paths; methods and scopes are normalized to bounded values. The process-local exporter resets on restart, while Prometheus can aggregate scraped series across instances and handle counter resets with `increase()`.

The request-availability SLI counts final `2xx`/`3xx` API responses as good events. Its denominator includes `2xx`/`3xx`, `429`, and `5xx` responses; other `4xx` responses are excluded as caller errors. An empty window returns `measurement_state: "no_data"` with `null` availability. Development/test uses a bounded, process-local diagnostic only. Production requires `AIOPS_PROMETHEUS_URL`, calculates counts with `sum(increase(...[AIOPS_SLO_WINDOW_MINUTES]))`, and returns `503` rather than falling back to local samples when Prometheus is unavailable. Configure Prometheus to scrape every application instance directly and retain data for at least the SLO window. The deployment owns Prometheus storage durability, retention, and alerting policy; the endpoint alone is not compliance evidence.

## Security controls

`/api/*` and `/metrics` accept `X-AiOps-API-Key` or a bearer token when `AIOPS_API_KEY` is configured; this credential grants `aiops:read` only. A trusted gateway may instead authenticate a same-origin browser session and forward the server-side `AIOPS_GATEWAY_TOKEN` with `X-AiOps-Principal` and space-separated `X-AiOps-Scopes` claims. The gateway must remove client-supplied copies of those headers and set them only from verified identity/session data. `aiops:alerts:silence` authorizes only alert suppression; `aiops:thresholds:write` authorizes only threshold updates. Outside production, no configured credentials permit anonymous reads only; production still requires an API key of at least 24 characters. `/health/live` and `/health/ready` are public; the root dashboard shell is public unless the gateway protects it. Gateway-authenticated unsafe methods require an exact `Origin` in `AIOPS_ALLOWED_ORIGINS` as CSRF protection. CORS is not authentication. The service also applies a process-local sliding-window limiter, bounds the assistant query, redacts common secret patterns in selected audit details, and returns a request identifier on every response.

The browser dashboard assigns source values with `textContent`, does not interpret source payloads as HTML, and uses same-origin credentials without sending a shared API key. Never embed the service key or gateway token in client-side code. The app enforces explicit scopes, verifies one-time approval through the configured approval service, and records the authenticated principal for its two write routes. The model adapter sends the assembled context and user question; local environment variables, request headers, and audit records are not part of that context.

The `/api/audit` view is a bounded in-process diagnostic log, not a durable compliance store. Separately, both mutation routes append versioned `AuditEvent` records through the storage-neutral `AuditSink` protocol. The repository supplies no storage vendor or sink implementation: deployment code must inject an access-controlled implementation through `DashboardDependencies.audit_sink` and verify its durability, retention, permissions, and outage behavior. The default `web_dashboard:app` WSGI target has no sink and therefore rejects writes; deployments enabling writes must use a custom WSGI factory that injects the sink.

## Mutation audit and failure policy

Each mutation event includes schema version, UTC timestamp, request ID, authenticated actor (or `unauthenticated` for an unauthenticated denial), environment, explicit `tenant: "not-configured"` sentinel, action, target, phase, and outcome. Alert comments, threshold values, raw request bodies, approval credentials, and assistant prompts are excluded. The sink's `append` must provide bounded completion, access control, and the durability guarantee the deployment relies on; a successful call only proves what that implementation promises.

| Condition | Behavior |
|---|---|
| No sink or the initial attempt-event append fails | Return `503 audit_sink_unavailable` with `operation_outcome: "not_started"`; do not contact the approval service or issue the mutation request. |
| Approval is rejected or unavailable | Append a terminal `rejected` or `not_executed` event. If accepted by the sink, preserve the normal `403` or `503` response; a terminal append failure returns `503 audit_sink_unavailable` and `operation_outcome: "not_started"`. |
| Mutation upstream fails after the request may have been sent | Append outcome `unknown`, since the remote service may have applied the operation despite a lost/error response. Preserve the upstream `503` if that audit append succeeds; otherwise return `503 audit_sink_unavailable` with `operation_outcome: "unknown"`. |
| Mutation succeeds but the terminal audit append fails | Return `503 audit_sink_unavailable` with `operation_outcome: "succeeded"`; reconcile the external state before retrying to avoid a duplicate operation. |
| Authentication, authorization, CSRF, rate-limit, or request-validation denial | Append a minimal denial event best-effort when a sink is configured. A sink failure never changes the denial response; with no sink, only a safe non-durable service log is available. |

The write-ahead attempt event allows operators to identify unfinished operations after a process crash; it is not transactional with the external provider. Do not infer that a returned `503` means no side effect occurred unless `operation_outcome` is `not_started`.

## Deployment rules

Secrets must be supplied by the deployment secret manager. The repository must not contain live credentials, endpoint-specific bearer tokens, or source fixtures. TLS verification remains enabled by default; disabling it requires an explicit deployment decision and should be limited to controlled test environments.

The service should run behind an identity-aware gateway, with network policy restricting outbound connections to configured source systems and the model gateway. Store `AIOPS_GATEWAY_TOKEN` only in the gateway and app secret manager; restrict direct app access, configure exact browser origins, and have the gateway overwrite the identity/scope headers after session authentication. The deployment owns organization identity and shared request limits; the configured approval service owns one-time approval records, and the injected audit sink owns durable audit retention. For production SLOs, ensure Prometheus scrapes every app instance rather than a load-balanced address. Readiness checks Prometheus and Alertmanager; separately smoke-test each optional integration that the release intends to use.

## Migration sequence

First, configure Prometheus, Alertmanager, service URLs, and the model gateway in a non-production environment. Second, verify source schemas, readiness behavior, request correlation, and structured log shipping. Third, configure and fault-test the durable audit sink, gateway authorization, and approval service, then exercise the approved mutation path in non-production. Fourth, set the service SLO target and alert on error-budget burn. Finally, enable write routes for approved operators and keep autonomous remediation disabled until a separate executor has explicit policy, approval, rollback, and audit controls.

## Research basis

The request, metric, and log model is aligned with OpenTelemetry’s observability primer [1]. The SLO and error-budget model is based on Google SRE guidance [2]. AI risk and governance boundaries use the NIST Generative AI Profile [3] and OWASP GenAI security guidance [4]. CI workflow hardening and artifact integrity should follow GitHub’s secure-use guidance and SLSA build requirements [5] [6].

## References

[1]: https://opentelemetry.io/docs/concepts/observability-primer/ "OpenTelemetry Observability Primer"
[2]: https://sre.google/workbook/implementing-slos/ "Google SRE Workbook: Implementing SLOs"
[3]: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence "NIST AI RMF Generative AI Profile"
[4]: https://genai.owasp.org/llmrisk/llm01-prompt-injection/ "OWASP LLM01:2025 Prompt Injection"
[5]: https://docs.github.com/en/actions/reference/security/secure-use "GitHub Actions Secure Use Reference"
[6]: https://slsa.dev/spec/v1.2/build-requirements "SLSA v1.2 Build Requirements"
