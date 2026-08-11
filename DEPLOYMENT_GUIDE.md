# AiOps Deployment Guide

## Deployment stance

Run the service as a stateless web process behind an identity-aware gateway. The service reads operational state from configured Prometheus, Alertmanager, incident, log, action, insight, threshold, and model endpoints. It does not start from local source fixtures and it does not treat an unreachable dependency as healthy.

## Required configuration

Production startup requires `AIOPS_ENV`, `AIOPS_SERVICE_NAME`, `AIOPS_VERSION`, `AIOPS_HOST`, `AIOPS_PORT`, and `AIOPS_API_KEY`. Readiness requires `AIOPS_PROMETHEUS_URL`, `AIOPS_ALERTMANAGER_URL`, and `AIOPS_STATUS_QUERY`. Dashboard capabilities require the corresponding service URLs and PromQL expressions described in `README.md` and `OPERATIONS.md`.

Secrets must be injected through the deployment secret manager. Do not place API keys, model credentials, database credentials, or bearer tokens in a committed environment file. Keep TLS verification enabled unless a controlled test environment explicitly requires another policy.

## Process execution

Install the repository’s declared requirements and run behind a production WSGI server. The development Flask server is intended only for local integration checks.

```bash
python3 -m pip install -r requirements.txt
gunicorn --workers 2 --bind "$AIOPS_HOST:$AIOPS_PORT" web_dashboard:app
```

The process should receive termination signals from the orchestrator and be restarted only after a liveness failure or an explicit rollout decision. The gateway should enforce identity, authorization scopes, request size, and durable audit retention.

## Health checks

Use `/health/live` as the process liveness check. Use `/health/ready` as the dependency readiness check. The service should not receive production traffic until readiness succeeds against the intended Prometheus and Alertmanager instances. Scrape `/metrics` from a trusted monitoring network and route error-budget burn to the on-call system.

## Network policy

Permit outbound traffic only to the configured telemetry, alerting, service, and model endpoints. Permit inbound traffic only from the gateway and monitoring network. Restrict administrative write routes to an operator scope at the gateway; the application’s API key is a defense-in-depth control, not a substitute for identity-aware authorization.

## Release validation

Before promotion, run Python compilation, deterministic foundation tests, formatting, type checks where dependencies are available, and a scan for executable fixture or synthetic-data paths. Verify that a missing dependency returns `503 integration_unavailable`, a malformed query returns `400 invalid_request`, every response contains `X-Request-ID`, and the dashboard contains no `innerHTML` assignment.

## Data retention and audit

The process-local audit buffer and latency sample window are bounded convenience buffers. Export structured logs and audit events to a durable access-controlled sink before treating them as compliance evidence. Persist incidents, silences, thresholds, remediation approvals, and model evaluation records in their owning services.

## Research basis

The deployment model follows OpenTelemetry’s telemetry concepts [1], Google SRE’s SLO practice [2], NIST AI risk-management guidance [3], OWASP GenAI security guidance [4], GitHub Actions secure-use guidance [5], and SLSA build requirements [6].

## References

[1]: https://opentelemetry.io/docs/concepts/observability-primer/ "OpenTelemetry Observability Primer"
[2]: https://sre.google/workbook/implementing-slos/ "Google SRE Workbook: Implementing SLOs"
[3]: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence "NIST AI RMF Generative AI Profile"
[4]: https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/ "OWASP GenAI LLM Top 10 2026"
[5]: https://docs.github.com/en/actions/reference/security/secure-use "GitHub Actions Secure Use Reference"
[6]: https://slsa.dev/spec/v1.2/build-requirements "SLSA v1.2 Build Requirements"
