## Summary

<!-- What changed and why? -->

## Validation

- [ ] `python -m compileall -q web_dashboard.py src tests`
- [ ] `black --check ...`
- [ ] `flake8 ...`
- [ ] `mypy src/platform`
- [ ] `python -m pytest --cov=src ...`
- [ ] `git diff --check`

## Security and operations

- [ ] No credentials, production URLs, or operational data were added.
- [ ] External responses remain explicitly validated.
- [ ] Authentication, authorization, rate limiting, audit, and secret-redaction behavior were considered.
- [ ] Deployment, rollback, migration, or configuration impact is documented.

## Testing notes

<!-- Describe important test cases, negative paths, or limitations. -->
