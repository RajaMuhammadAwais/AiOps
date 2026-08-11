# Operational AiOps Upgrade Plan

## Objective

Refactor the Flask dashboard into an integration-backed AiOps control plane that never invents operational records. The implementation focuses on secure configuration, API protection, request correlation, bounded state management, explicit health semantics, SLO and error-budget visibility, safe assistant query handling, audit trails, and hardened CI/CD.

## Research-to-change mapping

| Research requirement | Current repository gap | Planned change | Priority |
|---|---|---|---|
| NIST AI RMF: trustworthy design, development, use, and evaluation | Assistant requests lacked explicit policy boundaries and auditability | Delegate to a configured model endpoint, bound inputs, fingerprint queries, expose model metadata, and record audit events | P0 |
| OpenTelemetry: correlated traces, metrics, and logs | Request correlation and service telemetry were incomplete | Add request correlation, structured logs, Prometheus-compatible service metrics, and health/readiness endpoints | P0 |
| OWASP GenAI: protect LLM/tool interfaces and sensitive data | Query endpoint accepted arbitrary JSON and the browser rendered source data unsafely | Validate and bound queries, keep the model behind a configured adapter, return safe JSON, use DOM text assignment, and log policy decisions | P0 |
| Google SRE: SLOs, SLIs, and error budgets | No user-impact reliability indicators or error-budget view | Add configurable availability/latency SLO calculations and an API endpoint exposing SLO state | P1 |
| GitHub Actions secure use: least privilege and action hygiene | Workflow has implicit token permissions, mutable third-party action references, and PR-side effects | Add explicit permissions, safer job conditions, pinned reusable actions where practical, dependency/security checks, and artifact attestation | P0 |
| SLSA v1.2: provenance and isolated artifact production | Build job creates artifacts without provenance/verification | Add release provenance/attestation step and document the trust boundary | P1 |

## Implementation boundary

The repository does not contain a durable database schema, identity provider, or remediation executor. Those remain explicit integration boundaries. The dashboard now uses Prometheus, Alertmanager, service URLs, and an external model endpoint when configured, and it fails closed with `503 integration_unavailable` when a required source is absent or unhealthy.

## Files expected in this increment

- `src/platform/config.py`: environment-driven settings and validation.
- `src/platform/security.py`: API-key authorization, request limits, redaction, safe response helpers, and audit event creation.
- `src/platform/observability.py`: request IDs, structured logging, Prometheus metrics, and health/SLO calculations.
- `src/platform/integrations.py`: Prometheus, Alertmanager, service, and external model adapters.
- `web_dashboard.py`: integrate the operational foundation, validate inputs, provide health/readiness/metrics/SLO/audit routes, and remove unsafe direct HTML interpolation from the frontend.
- `tests/test_operational_foundations.py`: standard-library unit tests for configuration, security, bounded state, SLO calculations, and integration failure behavior.
- `.github/workflows/ci-cd.yaml`: least-privilege and security-oriented CI improvements.
- `OPERATIONS.md`: deployment contract, trust boundary, SLO model, assistant safety boundary, and migration roadmap.
- `README.md`: updated claims and production-mode setup instructions.

## Definition of done

The service must compile, helper tests must run without external services, the Flask test client must exercise public health routes and explicit integration failures, unsafe query inputs must be rejected, health semantics must distinguish liveness from readiness, and no dashboard content may use user-controlled `innerHTML`. CI must run deterministic quality and security checks with explicit permissions. Documentation must separate implemented controls from external integration contracts.
