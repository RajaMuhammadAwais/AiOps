# Features guide

For the system diagram, request/data flows, developer setup, and production-readiness roadmap, see [ARCHITECTURE.md](ARCHITECTURE.md). This guide describes the current Flask dashboard/API path; other packages in the repository are not automatically part of that runtime path.

## Dashboard and API

`web_dashboard.py` serves the browser dashboard and JSON routes. Request hooks attach a request ID, rate-limit `/api/*` and `/metrics`, apply API-key authentication when configured, and record request metrics. Routes validate their own inputs and use configured upstreams rather than local sample data.

Read routes expose status, alerts, metrics, incidents, logs, insights, action state, SLO snapshots, and the bounded audit view. The explicit write routes create an Alertmanager silence for a currently active alert and forward validated `cpu`, `mem`, and `disk` threshold values to the configured threshold service. The Flask app does not expose a general autonomous action executor.

## Integration boundaries

Prometheus, Alertmanager, and model calls use typed clients in `src/platform/integrations.py`. Other operational JSON endpoints are called through shared request helpers in `web_dashboard.py`. Timeouts and TLS verification are configurable. The current client layer does not provide a common authentication contract for every upstream: Prometheus, Alertmanager, and generic JSON clients do not expose a general per-service credential setting.

Response validation is endpoint-specific. Do not assume every valid JSON payload is a valid integration response. Add a versioned schema, contract tests, and a deployment smoke test for each real service before relying on its route. Missing or unavailable upstream data must stay explicit; it must not be replaced with a plausible-looking fixture.

## Health and observability

`/health/live` checks only that the application process can answer HTTP. `/health/ready` checks the required Prometheus and Alertmanager dependencies; it does not check optional integrations such as the model or incident service.

Request metrics, the sliding-window limiter, and the web app's legacy `AuditLog` are process-local. `/metrics` exports request counters and duration sum/count over a bounded sample window. `/api/slo` reports a snapshot from that same process; it is not a durable or multi-replica SLO source. The JSON log formatter includes a request ID when present, but request route, HTTP status, and latency are not currently structured log fields. See [ARCHITECTURE.md](ARCHITECTURE.md) before using these values for paging or compliance evidence.

## Authentication, browser UI, and AI boundary

API and metrics paths accept `X-AiOps-API-Key` or a bearer token when `AIOPS_API_KEY` is configured. Authentication is optional outside production; production configuration requires a key of at least 24 characters. The dashboard JavaScript does not send this key, so a protected dashboard needs a reviewed same-origin browser session/proxy. Never embed a shared service key in browser code.

The assistant route sends the user question and selected configured operational context to the configured model endpoint. It does not provide the model a local shell or a general action tool. Model output is untrusted input: prompt wording is not a security boundary. Privileged writes require deterministic route scopes and a verified one-time approval from the configured approval service; the read-only Flask API key alone is not role-based authorization or an approval record.

## State and audit

`BoundedStore` is an in-memory utility; the dashboard writes refresh snapshots to it but its routes do not read those snapshots. It is not a persistent database or response cache. The legacy web `AuditLog` is bounded, in-memory, and diagnostic only. Mutation routes use the versioned `AuditEvent`/`AuditSink` contract when a deployment injects its own durable, access-controlled sink. No storage vendor or sink implementation is bundled. The default `web_dashboard:app` target has no sink and fails closed for writes; a deployment enabling writes must use a custom WSGI factory and inject the sink through `DashboardDependencies`.

The runtime has no shared limiter or distributed metrics aggregation, and the repository does not provide a durable sink implementation. Supply shared controls before scaling to multiple workers/replicas, and integration-test the deployment's sink for durable retained evidence and outage behavior.

## Repository modules outside the dashboard path

The repository also contains monitoring, observability, intelligence, and ML packages. A package being present does not mean that the Flask request path invokes it. When changing runtime behavior, trace imports and callers from `web_dashboard.py`, add route-level or integration tests, and update [ARCHITECTURE.md](ARCHITECTURE.md) so the documented flow stays accurate.
