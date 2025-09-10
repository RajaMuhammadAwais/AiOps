name: Bug report
description: File a bug report to help us improve
title: "[Bug]: "
labels: ["bug"]
assignees: []

body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to fill out this bug report!

  - type: checkboxes
    id: checks
    attributes:
      label: Checks
      options:
        - label: I have searched existing issues
          required: true
        - label: I can reproduce this with the latest commit on main
          required: true

  - type: input
    id: version
    attributes:
      label: Version info
      description: Output of `python --version` and any relevant package versions
      placeholder: e.g. Python 3.12.6, Flask 3.1.1
    validations:
      required: false

  - type: textarea
    id: description
    attributes:
      label: Describe the bug
      description: A clear and concise description of what the bug is.
      placeholder: Tell us what you see!
    validations:
      required: true

  - type: textarea
    id: reproduction
    attributes:
      label: Steps to reproduce
      description: How can we reproduce the behavior?
      placeholder: |
        1. Run ...
        2. With config ...
        3. See error ...
      render: bash
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
      description: What did you expect to happen?
    validations:
      required: true

  - type: textarea
    id: logs
    attributes:
      label: Relevant log output
      description: Please copy and paste any relevant log output. This will be automatically formatted as code.
      render: shell
    validations:
      required: false

  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: OS, Python version, how installed (pip/poetry), cloud/local, etc.
    validations:
      required: false