name: CI or security check failure
description: Report a reproducible failure in CI, CodeQL, dependency review, or security scanning
title: "[CI]: "
labels: ["bug", "needs-triage"]
assignees: []
body:
  - type: input
    id: workflow
    attributes:
      label: Workflow or check
      placeholder: e.g. AIOps CI/CD / CodeQL / Secret scan
    validations:
      required: true
  - type: input
    id: run
    attributes:
      label: Run URL
      description: Link to the failed GitHub Actions run.
    validations:
      required: true
  - type: textarea
    id: details
    attributes:
      label: Failure details
      description: Include the relevant error and reproduction context. Do not include secrets.
    validations:
      required: true
