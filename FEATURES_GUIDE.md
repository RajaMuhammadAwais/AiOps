# Features guide

## Dashboard and API

The Flask service exposes a browser dashboard and JSON endpoints for operational status, metrics, anomalies, incidents, insights, actions, thresholds, and assistant requests. The API validates input length and types, applies request authentication when configured, rate-limits clients, attaches correlation identifiers, and records bounded audit events.

The browser client receives data from the API and inserts values using text nodes. It does not interpolate operational or user-controlled content as HTML. Refresh cadence, query limits, allowed origins, and other runtime controls are deployment settings.

## Observability

The service emits structured request logs with request identifiers, route labels, status codes, and latency. The metrics surface is compatible with Prometheus-style scraping when the deployment exposes it. Availability and SLO calculations operate on recorded request observations; they do not report fabricated health values when no observations exist.

OpenTelemetry-compatible telemetry should be collected by the deployment boundary and associated with the service identity in `AIOPS_SERVICE_NAME` and immutable `AIOPS_VERSION` values. Upstream telemetry remains the source of truth for metrics, alerts, logs, and traces.

## Integration adapters

The adapter layer provides bounded HTTP clients for Prometheus, Alertmanager, incident systems, log systems, action executors, insight systems, threshold systems, and external model endpoints. Each adapter validates response shape and converts connection, HTTP, JSON, and schema failures into an unavailable result. Missing endpoints are explicit configuration errors, not invitations to fall back to local values.

| Capability | Configuration | Source of truth | Unavailable behavior |
|---|---|---|---|
| Metrics and status | `AIOPS_PROMETHEUS_URL` | Prometheus query response | Readiness or route reports integration unavailable |
| Alerts | `AIOPS_ALERTMANAGER_URL` | Alertmanager response | Alert route reports integration unavailable |
| Incidents | `AIOPS_INCIDENTS_URL` | Incident service response | Incident route reports integration unavailable |
| Logs | `AIOPS_LOGS_URL` | Log service response | Log route reports integration unavailable |
| Actions | `AIOPS_ACTIONS_URL` | Approved action executor | Action is refused without executor |
| Insights | `AIOPS_INSIGHTS_URL` | Insight service response | Insight route reports integration unavailable |
| Thresholds | `AIOPS_THRESHOLDS_URL` | Threshold policy service | Threshold mutation is refused without policy service |
| Assistant | `AIOPS_LLM_URL` | Configured model endpoint | Assistant route reports integration unavailable |

## Automation boundaries

Incident orchestration accepts policy supplied by the caller or a policy service and dispatches approved actions to `AIOPS_ACTIONS_URL`. It does not contain default remediation actions, local shell execution, invented execution results, or hidden retry policy. Deployment coordination similarly requires a deployment executor and a risk-advisor endpoint; absent integrations return a structured unavailable result.

## Predictive analytics

Predictive training requires explicitly supplied feature columns and a `failure_label` column for supervised failure prediction. Capacity thresholds are injected through deployment policy. Service correlation is calculated only from supplied numeric values and returns an unavailable correlation when aligned observations are insufficient or constant. Model evaluation returns an unavailable value when cross-validation cannot be performed rather than a made-up score.

## Security controls

Production requires a sufficiently strong API key. CORS origins are explicit, request bodies and query strings are bounded, sensitive headers and values are redacted in audit records, and state stores are bounded and thread-safe. The CI workflow checks for executable fixture markers, unsafe DOM APIs, source compilation failures, and packaging failures.

## What the service does not do

The repository does not seed operational records, invent telemetry, generate a local incident stream, pretend that a deployment succeeded, create synthetic model labels, or claim readiness when upstream systems are unavailable. These boundaries are deliberate so operators can distinguish real observations from missing integrations.
