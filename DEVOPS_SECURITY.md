# DevOps and Security Baseline

This repository uses GitHub Actions for pull-request validation, tagged release packaging, and recurring security analysis. Deployment is intentionally not included because the service depends on deployment-owned upstream systems, identity, secrets, network policy, and durable audit infrastructure.

## Automated controls

The `AIOps CI/CD` workflow compiles the Python sources, checks formatting, runs flake8 and mypy, executes the test suite with coverage, validates whitespace, builds Python distributions, and publishes a GitHub release only for an explicitly pushed `v*.*.*` tag. It does not modify or push source files on `main`.

The `Security` workflow runs CodeQL for Python and JavaScript, reviews dependency changes in pull requests, scans repository history for secrets with Gitleaks, and publishes a CycloneDX SBOM for pushes to `main` and version tags. Dependabot monitors Python, npm, and GitHub Actions dependencies.

## Required repository settings

For the strongest enforcement, configure `main` as a protected branch and require the CI, CodeQL, dependency-review, and secret-scan checks before merge. Require pull requests, dismiss stale approvals, restrict force pushes, and enable the repository's native secret scanning and push protection when available.

Configure GitHub's private vulnerability reporting and repository security contact. Review the `SECURITY.md` policy and keep the `CODEOWNERS` entries aligned with the active maintainers.

## Deployment boundary

Before production exposure, provide an identity-aware gateway, managed secret injection, TLS verification, network policy, centralized logs, durable access-controlled audit storage, shared rate limiting for multiple replicas, and monitored liveness/readiness checks. These controls cannot be safely inferred or provisioned by repository CI.
