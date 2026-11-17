# AiOps Operations Contract

## Purpose and trust boundary

The service is a thin operational control plane. It is trusted to authenticate API keys or configured gateway assertions, enforce route scopes, validate and bound request bodies, correlate requests, expose service metrics, and delegate external calls through configured adapters. It is not trusted to invent telemetry, decide that a dependency is healthy without checking it, execute autonomous remediation, or retain durable audit history in process memory.

> A missing or unavailable source is an operational failure, not a reason to return a plausible-looking value.

Prometheus and Alertmanager are the first-party operational sources. The incident, log, action, insight, and threshold URLs are service-to-service boundaries owned by the deployment. The schemas below are the contract this application accepts; they do not claim to describe an uninspected deployment-owned provider. The assistant is an external model boundary and receives only the context assembled from configured sources. Tool execution and remediation approval remain outside this repository.

## Required source contracts

| Upstream | Request | Accepted response contract |
|---|---|---|
| Prometheus (`AIOPS_PROMETHEUS_URL`) | `GET /api/v1/query?query=<PromQL>`; expressions come from `AIOPS_STATUS_QUERY`, `AIOPS_METRICS_QUERY`, or `AIOPS_ANOMALIES_QUERY`. | JSON object with `status: "success"`, `data.resultType: "vector"`, and `data.result` as a list. Every item must contain a `metric` string-to-string object and a `value` pair of finite numeric timestamp and finite decimal-string sample. An empty vector is valid; a malformed item rejects the whole response. The app returns normalized `name`, `value`, `timestamp`, and `labels`. |
| Alertmanager (`AIOPS_ALERTMANAGER_URL`) | `GET /api/v2/alerts` with active, non-silenced, non-inhibited filters; `POST /api/v2/silences` with `matchers`, `startsAt`, `endsAt`, `createdBy`, and `comment`. | The alerts response is a list of objects. Each item requires a non-empty `fingerprint`, label and annotation string maps, receiver objects with string names, timezone-aware `startsAt`, `updatedAt`, and `endsAt`, `labels.alertname`, and `status.state` in `unprocessed`, `active`, or `suppressed` plus string lists `silencedBy`, `inhibitedBy`, and `mutedBy`. A silence response requires a non-empty string `silenceID`. |
| Incidents (`AIOPS_INCIDENTS_URL`) | `GET` the configured endpoint. | Object with `incidents` as a list of JSON objects. Item fields are opaque and deployment-owned; non-object members are rejected. |
| Logs (`AIOPS_LOGS_URL`) | `GET` the configured endpoint. | Object with `log_events` as a list of JSON objects. Item fields are opaque and deployment-owned; non-object members are rejected. |
| Actions (`AIOPS_ACTIONS_URL`) | `GET` the configured endpoint. | JSON object representing the current action/remediation state. Nested fields are opaque and deployment-owned; no local command is executed. |
| Insights (`AIOPS_INSIGHTS_URL`) | `GET` the configured endpoint with `kind=recommendations`, `kind=rca`, or `kind=ml`. | JSON object. Nested fields are opaque and deployment-owned. |
| Thresholds (`AIOPS_THRESHOLDS_URL`) | `POST` a JSON object containing exactly `cpu`, `mem`, and `disk`; each is a finite number strictly between `0` and `100`. | Successful response must be a JSON object. The application does not infer or fabricate an upstream result. |
| Model (`AIOPS_LLM_URL`, `AIOPS_LLM_MODEL`) | OpenAI-compatible JSON request; optional `AIOPS_LLM_API_KEY` is sent as a Bearer credential. | JSON object containing either a non-empty `choices[0].message.content` string or a non-empty `output_text` string. |

### Authentication and transport

Each operational upstream has an independent `AIOPS_<UPSTREAM>_AUTH_TYPE` setting: `none` (the backward-compatible default), `bearer`, or `basic`. Bearer credentials use `AIOPS_<UPSTREAM>_BEARER_TOKEN`; Basic credentials use both `AIOPS_<UPSTREAM>_USERNAME` and `AIOPS_<UPSTREAM>_PASSWORD`. A secret provided with `AUTH_TYPE=none`, incomplete Basic credentials, or mixed credential modes fail configuration rather than being silently ignored. The supported names are `PROMETHEUS`, `ALERTMANAGER`, `INCIDENTS`, `LOGS`, `ACTIONS`, `INSIGHTS`, and `THRESHOLDS`. Use a deployment-owned authenticated proxy for other schemes; do not put credentials in endpoint URLs.

`AIOPS_<UPSTREAM>_TIMEOUT_SECONDS` and `AIOPS_<UPSTREAM>_VERIFY_TLS` override the per-request timeout and TLS verification for that source. Otherwise they inherit the existing `AIOPS_PROMETHEUS_TIMEOUT_SECONDS` and `AIOPS_VERIFY_TLS` settings. Timeouts are bounded to 1–60 seconds. TLS verification should remain enabled in production. The model endpoint uses the shared timeout/TLS settings and its existing Bearer API key.

Upstream credentials and configured endpoint URLs are read from injected environment/secret-manager values and excluded from settings representations; credentials are never included in API results or upstream error text. API `source` fields are stable integration labels, not configured URLs; startup also rejects URL userinfo and recognized secret query parameters. Missing configuration, network/timeout failure, HTTP error (including upstream authentication failure), invalid JSON, or a schema violation maps to the same structured `503 integration_unavailable` response. Client request validation remains `400`; gateway authentication/authorization retains its own `401`/`403` mapping. Valid empty lists are returned as empty lists. Invalid records are rejected as a whole rather than filtered, and a failed refresh never returns a previous cached sample as if it were current.

## Health and reliability semantics

`/health/live` answers whether the Python process can serve HTTP. `/health/ready` checks that the Prometheus and Alertmanager contracts are configured and reachable. A 200 liveness result must not be interpreted as dependency health. The `/api/status` response includes configured status samples, active alert and incident counts where their sources are configured, and an SLO snapshot labeled with its source.

`/metrics` exposes bounded-label request counters and fixed-bucket latency histograms. Route labels use Flask route templates, not raw request paths; methods and scopes are normalized to bounded values. The process-local exporter resets on restart, while Prometheus can aggregate scraped series across instances and handle counter resets with `increase()`.

The request-availability SLI counts final `2xx`/`3xx` API responses as good events. Its denominator includes `2xx`/`3xx`, `429`, and `5xx` responses; other `4xx` responses are excluded as caller errors. An empty window returns `measurement_state: "no_data"` with `null` availability. Development/test uses a bounded, process-local diagnostic only. Production requires `AIOPS_PROMETHEUS_URL`, calculates counts with `sum(increase(...[AIOPS_SLO_WINDOW_MINUTES]))`, and returns `503` rather than falling back to local samples when Prometheus is unavailable. Configure Prometheus to scrape every application instance directly and retain data for at least the SLO window. The deployment owns Prometheus storage durability, retention, and alerting policy; the endpoint alone is not compliance evidence.

## Security controls

`/api/*` and `/metrics` accept `X-AiOps-API-Key` or a bearer token when `AIOPS_API_KEY` is configured; this credential grants `aiops:read` only. A trusted gateway may instead authenticate a same-origin browser session and forward the server-side `AIOPS_GATEWAY_TOKEN` with `X-AiOps-Principal` and space-separated `X-AiOps-Scopes` claims. The gateway must remove client-supplied copies of those headers and set them only from verified identity/session data. `aiops:alerts:silence` authorizes only alert suppression; `aiops:thresholds:write` authorizes only threshold updates. Outside production, no configured credentials permit anonymous reads only; production still requires an API key of at least 24 characters. `/health/live` and `/health/ready` are public; the root dashboard shell is public unless the gateway protects it. Gateway-authenticated unsafe methods require an exact `Origin` in `AIOPS_ALLOWED_ORIGINS` as CSRF protection. CORS is not authentication. The service also applies a process-local sliding-window limiter, bounds the assistant query, redacts common secret patterns in selected audit details, and returns a request identifier on every response.

The browser dashboard assigns source values with `textContent`, does not interpret source payloads as HTML, and uses same-origin credentials without sending a shared API key. Never embed the service key or gateway token in client-side code. The app enforces explicit scopes and records the authenticated principal for its two write routes, but does not itself create a separate approval record. The model adapter sends the assembled context and user question; local environment variables, request headers, and audit records are not part of that context.

The in-process audit log is bounded and is not a durable compliance store. Deployments must ship structured service logs and audit events to an access-controlled retention system before enabling sensitive write operations in production.

## Deployment rules

Secrets must be supplied by the deployment secret manager. The repository must not contain live credentials, endpoint-specific bearer tokens, or source fixtures. TLS verification remains enabled by default; disabling it requires an explicit deployment decision and should be limited to controlled test environments.

The service should run behind an identity-aware gateway, with network policy restricting outbound connections to configured source systems and the model gateway. Store `AIOPS_GATEWAY_TOKEN` only in the gateway and app secret manager; restrict direct app access, configure exact browser origins, and have the gateway overwrite the identity/scope headers after session authentication. The gateway remains responsible for organization identity, request limits, approval records, and durable audit retention. For production SLOs, ensure Prometheus scrapes every app instance rather than a load-balanced address. Readiness checks Prometheus and Alertmanager; separately smoke-test each optional integration that the release intends to use.

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
