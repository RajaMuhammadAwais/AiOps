# Contributing to AiOps

Thank you for contributing. Please read `ARCHITECTURE.md`, `OPERATIONS.md`, and `SECURITY.md` before changing integration, authentication, audit, or deployment behavior.

## Development setup

Use Python 3.12 or a newer version compatible with the project metadata:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Required checks

Run the same checks used by CI before opening a pull request:

```bash
python -m compileall -q web_dashboard.py src tests
black --check web_dashboard.py src/platform src/monitoring/log_monitor.py tests
flake8 web_dashboard.py src/platform src/monitoring/log_monitor.py --max-line-length=100 --extend-ignore=E203
mypy src/platform
python -m pytest --cov=src --cov-report=term-missing tests/
git diff --check
```

## Pull requests

Keep pull requests focused, explain operational and security impact, and include tests for new behavior and negative paths. Do not include secrets, real production URLs, fabricated telemetry, or generated operational data. Changes to authentication, authorization, integration validation, audit behavior, or CI permissions require explicit explanation in the pull request.

All pull requests must pass required CI and security checks and receive review from the owners listed in `.github/CODEOWNERS`.
