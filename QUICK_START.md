# Quick start

This service is an integration-backed operations dashboard. It does not create sample telemetry, fabricate incidents, invent model responses, or execute local remediation actions without an explicitly configured external service.

## Install

```bash
git clone https://github.com/RajaMuhammadAwais/AiOps.git
cd AiOps
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure deployment inputs

Set the required identity and bind values before importing or starting the service:

```bash
export AIOPS_ENV="${AIOPS_ENV:?set deployment environment}"
export AIOPS_SERVICE_NAME="${AIOPS_SERVICE_NAME:?set service identity}"
export AIOPS_VERSION="${AIOPS_VERSION:?set immutable build identifier}"
export AIOPS_HOST="${AIOPS_HOST:?set bind address}"
export AIOPS_PORT="${AIOPS_PORT:?set service port}"
export AIOPS_LOG_LEVEL="${AIOPS_LOG_LEVEL:?set log level}"
export AIOPS_VERIFY_TLS="${AIOPS_VERIFY_TLS:?set TLS policy}"
export AIOPS_PROMETHEUS_TIMEOUT_SECONDS="${AIOPS_PROMETHEUS_TIMEOUT_SECONDS:?set upstream timeout}"
export AIOPS_MAX_QUERY_LENGTH="${AIOPS_MAX_QUERY_LENGTH:?set query limit}"
export AIOPS_RATE_LIMIT_PER_MINUTE="${AIOPS_RATE_LIMIT_PER_MINUTE:?set rate limit}"
export AIOPS_AUDIT_LOG_MAX_ENTRIES="${AIOPS_AUDIT_LOG_MAX_ENTRIES:?set audit capacity}"
export AIOPS_EVENT_STORE_MAX_ENTRIES="${AIOPS_EVENT_STORE_MAX_ENTRIES:?set event capacity}"
export AIOPS_SLO_TARGET="${AIOPS_SLO_TARGET:?set SLO target}"
export AIOPS_SLO_WINDOW_MINUTES="${AIOPS_SLO_WINDOW_MINUTES:?set SLO window}"
export AIOPS_REFRESH_SECONDS="${AIOPS_REFRESH_SECONDS:?set refresh interval}"
```

Configure at least one real telemetry or incident source. Prometheus is the normal metrics source; Alertmanager is the normal alert source:

```bash
export AIOPS_PROMETHEUS_URL="${AIOPS_PROMETHEUS_URL:?set the real Prometheus endpoint}"
export AIOPS_ALERTMANAGER_URL="${AIOPS_ALERTMANAGER_URL:-}"
export AIOPS_VERIFY_TLS=true
```

For authenticated deployments, provide a secret through the process environment or secret manager. Do not commit it:

```bash
export AIOPS_API_KEY='<secret-managed-value>'
```

Optional integrations are configured only when the corresponding real service exists: `AIOPS_INCIDENTS_URL`, `AIOPS_LOGS_URL`, `AIOPS_ACTIONS_URL`, `AIOPS_INSIGHTS_URL`, `AIOPS_THRESHOLDS_URL`, `AIOPS_LLM_URL`, `AIOPS_LLM_API_KEY`, and `AIOPS_LLM_MODEL`.

## Validate configuration and start

```bash
python -c 'from src.platform.config import Settings; Settings.from_env(); print("configuration valid")'
python web_dashboard.py
```

The liveness endpoint is `GET /health/live`. The readiness endpoint is `GET /health/ready`; it returns an unavailable response until the configured upstream integration can be reached. This prevents the service from reporting readiness without real data sources.

## Verify the deployment

```bash
curl -fsS http://127.0.0.1:${AIOPS_PORT}/health/live
curl -i http://127.0.0.1:${AIOPS_PORT}/health/ready
```

Use the dashboard only after readiness succeeds. Query parameters, incident content, and model output are rendered as text, not HTML. Every request receives a correlation identifier for log tracing.

## Run repository checks

```bash
python -m compileall -q web_dashboard.py src tests
python -m unittest discover -s tests -p 'test_operational_foundations.py' -v
```

Operational deployment, security boundaries, integration response contracts, and rollout rules are documented in [OPERATIONS.md](OPERATIONS.md) and [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).
