# Installation guide

## Scope

AiOps is a web service that reads operational data from configured upstream systems. Installation does not provision Prometheus, Alertmanager, an incident system, a log system, an action executor, or a model endpoint. Those systems remain owned by the deployment environment and must be reachable before readiness is considered successful.

## Prerequisites

Use a supported Python version listed in `pyproject.toml`. Install the operating-system packages required by the selected Python dependencies and ensure the process identity can read its secret source. In production, place secrets in a managed secret store or injected environment rather than a repository file.

## Source installation

```bash
git clone https://github.com/RajaMuhammadAwais/AiOps.git
cd AiOps
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Required environment

The identity, bind, logging, TLS, request-limit, audit-capacity, event-capacity, SLO, refresh, and port settings are mandatory for every process start:

| Variable | Meaning |
|---|---|
| `AIOPS_ENV` | `development`, `test`, `staging`, or `production` |
| `AIOPS_SERVICE_NAME` | Deployment identity used in logs and telemetry |
| `AIOPS_VERSION` | Immutable build or release identifier |
| `AIOPS_HOST` | Explicit bind address |

At least one of `AIOPS_PROMETHEUS_URL` or `AIOPS_ALERTMANAGER_URL` must be configured for operational readiness. `AIOPS_VERIFY_TLS`, `AIOPS_PROMETHEUS_TIMEOUT_SECONDS`, `AIOPS_MAX_QUERY_LENGTH`, `AIOPS_RATE_LIMIT_PER_MINUTE`, `AIOPS_AUDIT_LOG_MAX_ENTRIES`, `AIOPS_EVENT_STORE_MAX_ENTRIES`, `AIOPS_SLO_TARGET`, `AIOPS_SLO_WINDOW_MINUTES`, `AIOPS_REFRESH_SECONDS`, and `AIOPS_LOG_LEVEL` must be supplied explicitly and are range-checked. Production also requires an `AIOPS_API_KEY` with sufficient entropy.

Optional service endpoints are configured through `AIOPS_INCIDENTS_URL`, `AIOPS_LOGS_URL`, `AIOPS_ACTIONS_URL`, `AIOPS_INSIGHTS_URL`, `AIOPS_THRESHOLDS_URL`, and `AIOPS_LLM_URL`. The model adapter additionally accepts `AIOPS_LLM_API_KEY` and `AIOPS_LLM_MODEL`. A missing optional integration makes only its dependent capability unavailable; it never produces a substitute response.

## Configuration validation

Validate the exact process environment before starting a service:

```bash
python -c 'from src.platform.config import Settings; Settings.from_env(); print("configuration valid")'
```

The configuration parser rejects invalid booleans, ranges, wildcard origins, weak production API keys, missing service identity, missing bind address, and malformed numeric limits. Runtime limits such as query length, rate limit, audit capacity, event capacity, SLO target, and refresh interval are supplied through the corresponding `AIOPS_*` variables.

## Start and health checks

```bash
python web_dashboard.py
curl -fsS http://${AIOPS_HOST}:${AIOPS_PORT}/health/live
curl -i http://${AIOPS_HOST}:${AIOPS_PORT}/health/ready
```

`/health/live` only indicates that the process is running. `/health/ready` checks the configured upstream contract and returns an unavailable response when the service cannot provide real operational data. Route failures include a correlation identifier so operators can trace the request through structured logs.

## Reverse proxy and TLS

Terminate external TLS at an approved ingress or reverse proxy, restrict access to the dashboard and API paths, and forward the request identifier when one is already present. Configure `AIOPS_ALLOWED_ORIGINS` with an explicit comma-separated origin list; wildcard origins are rejected. Keep upstream certificate verification enabled unless a documented trust exception exists.

## Release and rollback

Build the package from a clean checkout, record the immutable version in `AIOPS_VERSION`, run the repository checks, and publish only the generated distribution artifacts from a tag-gated release workflow. Roll back by redeploying the previous immutable artifact and restoring the previous configuration revision. Do not change source files or generate operational data during rollback.

## Operational references

See [OPERATIONS.md](OPERATIONS.md) for integration response schemas, security boundaries, audit behavior, and readiness rules. See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for deployment topology and rollout verification. See [QUICK_START.md](QUICK_START.md) for the shortest local procedure.
