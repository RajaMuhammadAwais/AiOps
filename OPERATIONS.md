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

`/health/live` answers whether the Python process can serve HTTP. `/health/ready` checks that the Prometheus and Alertmanager contracts are configured and reachable. A 200 liveness result must not be interpreted as dependency health. The `/api/status` response includes the configured status samples, active alert and incident counts where their sources are configured, and the locally observed request SLO snapshot.

The `/metrics` endpoint exposes request counters plus duration sum and retained sample count in Prometheus text format. `/api/slo` calculates a snapshot from the same bounded, process-local request window. It counts status codes `>=500` as errors, so 4xx and 429 responses count as available. These values are not durable or shared across workers. Define and validate user-facing SLIs, then use durable telemetry aggregation before relying on SLOs for paging or compliance evidence.

## Security controls

`/api/*` and `/metrics` accept `X-AiOps-API-Key` or a bearer token when `AIOPS_API_KEY` is configured; this credential grants `aiops:read` only. A trusted gateway may instead authenticate a same-origin browser session and forward the server-side `AIOPS_GATEWAY_TOKEN` with `X-AiOps-Principal` and space-separated `X-AiOps-Scopes` claims. The gateway must remove client-supplied copies of those headers and set them only from verified identity/session data. `aiops:alerts:silence` authorizes only alert suppression; `aiops:thresholds:write` authorizes only threshold updates. Outside production, no configured credentials permit anonymous reads only; production still requires an API key of at least 24 characters. `/health/live` and `/health/ready` are public; the root dashboard shell is public unless the gateway protects it. Gateway-authenticated unsafe methods require an exact `Origin` in `AIOPS_ALLOWED_ORIGINS` as CSRF protection. CORS is not authentication. The service also applies a process-local sliding-window limiter, bounds the assistant query, redacts common secret patterns in selected audit details, and returns a request identifier on every response.

The browser dashboard assigns source values with `textContent`, does not interpret source payloads as HTML, and uses same-origin credentials without sending a shared API key. Never embed the service key or gateway token in client-side code. The app enforces explicit scopes and records the authenticated principal for its two write routes, but does not itself create a separate approval record. The model adapter sends the assembled context and user question; local environment variables, request headers, and audit records are not part of that context.

The in-process audit log is bounded and is not a durable compliance store. Deployments must ship structured service logs and audit events to an access-controlled retention system before enabling sensitive write operations in production.

## Deployment rules

Secrets must be supplied by the deployment secret manager. The repository must not contain live credentials, endpoint-specific bearer tokens, or source fixtures. TLS verification remains enabled by default; disabling it requires an explicit deployment decision and should be limited to controlled test environments.

The service should run behind an identity-aware gateway, with network policy restricting outbound connections to configured source systems and the model gateway. Store `AIOPS_GATEWAY_TOKEN` only in the gateway and app secret manager; restrict direct app access, configure exact browser origins, and have the gateway overwrite the identity/scope headers after session authentication. The gateway remains responsible for organization identity, request limits, approval records, and durable audit retention. Readiness checks only Prometheus and Alertmanager; separately smoke-test each optional integration that the release intends to use.

## Migration sequence

First, configure Prometheus, Alertmanager, service URLs, and the model gateway in a non-production environment. Second, verify the source schemas, readiness behavior, request correlation, alert-silence approval path, and structured log shipping. Third, configure a durable audit sink and gateway authorization. Fourth, set the service SLO target and alert on error-budget burn. Finally, enable write routes for approved operators and keep autonomous remediation disabled until a separate executor has explicit policy, approval, rollback, and audit controls.

## Research basis

The request, metric, and log model is aligned with OpenTelemetry’s observability primer [1]. The SLO and error-budget model is based on Google SRE guidance [2]. AI risk and governance boundaries use the NIST Generative AI Profile [3] and OWASP GenAI security guidance [4]. CI workflow hardening and artifact integrity should follow GitHub’s secure-use guidance and SLSA build requirements [5] [6].

## References

[1]: https://opentelemetry.io/docs/concepts/observability-primer/ "OpenTelemetry Observability Primer"
[2]: https://sre.google/workbook/implementing-slos/ "Google SRE Workbook: Implementing SLOs"
[3]: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence "NIST AI RMF Generative AI Profile"
[4]: https://genai.owasp.org/llmrisk/llm01-prompt-injection/ "OWASP LLM01:2025 Prompt Injection"
[5]: https://docs.github.com/en/actions/reference/security/secure-use "GitHub Actions Secure Use Reference"
[6]: https://slsa.dev/spec/v1.2/build-requirements "SLSA v1.2 Build Requirements"
