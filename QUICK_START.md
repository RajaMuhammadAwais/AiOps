# Quick start

AiOps is an integration-backed operations dashboard. It does not create sample telemetry, fabricate incidents, invent model responses, or execute local remediation actions. Without configured upstreams, the dashboard can be opened locally, while readiness and data-dependent API routes correctly report that integrations are unavailable.

## Run locally

Requirements: Python 3.12 or newer in the supported 3.x range, Bash, and package-index access for the first dependency install.

```bash
git clone https://github.com/RajaMuhammadAwais/AiOps.git
cd AiOps
cp .env.example .env
```

Edit `.env` and supply the required identity, logging, network-bind, port, TLS, and bounded-limit values described in the [Configuration section](README.md#configuration). For local-only access, set `AIOPS_HOST` to a loopback address. Leave optional upstream values empty unless you have real systems and approved values to provide.

Then run:

```bash
./scripts/run-local.sh
```

The launcher creates `.venv` if needed, installs only the dashboard and dotenv-loader dependencies from `requirements-local.txt`, loads `.env` without overriding values already exported in the process environment, and starts the dashboard. It does not set configuration defaults. Do not expose the development server to a public or untrusted network.

## Verify local behavior

Open the HTTP address printed by Flask using the host and port you configured. You can also request `/health/live` and `/health/ready` from a second terminal; substitute the actual `AIOPS_HOST` and `AIOPS_PORT` values from your `.env` rather than assuming a port or bind address.

A 503 from readiness is correct when required real integrations are absent or unreachable. The liveness endpoint only reports that the process is serving HTTP; it does not establish upstream health. No demo records are generated to make the dashboard look populated.

## Run tests and checks

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m compileall -q web_dashboard.py src tests
python -m unittest discover -s tests -v
```

`requirements-dev.txt` installs the dashboard runtime plus test and lint tools. `requirements.txt` remains the broader dependency set for the repository's optional analytics and integration modules.

## Production boundary

`./scripts/run-local.sh` uses Flask's development server and is for local development only. Flask's official deployment guidance requires a dedicated WSGI server or hosting platform outside local development. The repository includes Gunicorn in its full dependency set; a deployment can run the WSGI application with an approved server, for example:

```bash
gunicorn --bind "${AIOPS_HOST}:${AIOPS_PORT}" web_dashboard:app
```

Production also needs real, reachable integrations, deployment-managed secrets, TLS, an identity-aware ingress, shared rate limiting when running multiple workers, and durable audit/log handling. The default `web_dashboard:app` has no injected audit sink and therefore rejects mutation requests; a deployment that enables writes must use a custom WSGI factory with a verified, access-controlled sink. Do not treat a successful local liveness check or the in-process audit view as production readiness.

## Research basis

The local launcher keeps model behavior and operational data behind explicit integrations. This follows the repository's fail-closed integration contract; it does not establish that a configured model is safe. NIST describes its Generative AI Profile as a voluntary resource for incorporating trustworthiness into AI system design, development, use, and evaluation. OWASP's prompt-injection guidance describes residual risk and recommends constrained behavior, least privilege, human approval for high-risk actions, and adversarial testing. Flask distinguishes local development from production serving.

- [NIST AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
- [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [Flask deployment guidance](https://flask.palletsprojects.com/en/stable/deploying/)
- [OPERATIONS.md](OPERATIONS.md) describes integration contracts and trust boundaries.
