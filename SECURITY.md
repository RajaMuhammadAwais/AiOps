# Security Policy

## Supported versions

Security fixes are developed against the latest commit on `main`.

| Version or branch | Security support |
| --- | --- |
| `main` | Supported |
| Tagged releases | Supported only when the release notes explicitly identify the release as supported |
| Other branches and untagged historical commits | Not supported |

If you are unsure whether a deployment is affected, report the issue against the commit or release that you tested.

## Reporting a vulnerability

Please do **not** report security vulnerabilities in a public GitHub issue, discussion, pull request, or social-media post.

### Preferred method: GitHub private vulnerability reporting

If private vulnerability reporting is enabled for this repository, use the repository's **Security** tab and select **Report a vulnerability**. This creates a private report that can be reviewed and handled as a draft security advisory.

Private vulnerability reporting is a GitHub repository feature separate from this file. If the option is not available, use the fallback process below. Repository maintainers should enable private vulnerability reporting in the repository security settings when the feature is available.

### Fallback method

If private reporting is unavailable, open a public issue that contains only the following request, without vulnerability details, exploit code, credentials, personal data, or affected operational endpoints:

> I need a private security contact for a potential vulnerability. No sensitive details are included here.

A maintainer will provide a private reporting channel. Do not include technical details until that private channel has been established.

## What to include in a private report

Provide enough information for the maintainers to reproduce and assess the issue:

- A concise summary and the affected component.
- The affected version, commit, branch, or deployment configuration.
- Security impact and realistic attack conditions.
- Reproduction steps or a proof of concept that does not access real user or production data.
- Logs, screenshots, or traces with secrets and personal data removed.
- Any suggested mitigation or patch.
- Your preferred credit or attribution, if the issue is confirmed and disclosed.

Please do not include live credentials, API keys, customer information, production URLs, or destructive payloads. If a credential may have been exposed, report that fact promptly and rotate or revoke it immediately through the appropriate secret-management process.

## Response and coordinated disclosure

Maintainers will acknowledge receipt as soon as practical, investigate the report confidentially, and communicate the next steps with the reporter. The reporter may be asked to help verify impact, affected versions, or the proposed fix.

The maintainers will aim to develop and validate a remediation before public disclosure. When appropriate, the fix will be identified in release notes and a GitHub repository security advisory may be published so users can understand the impact and update safely. Disclosure timing will be coordinated with the reporter and may be delayed when users need time to apply a fix.

Please do not publicly disclose the vulnerability or publish a proof of concept while remediation is in progress. If a report has received no meaningful response after reasonable private follow-up, the reporter should state their intended disclosure timeline when contacting the maintainers again.

There is no bug-bounty or financial reward program for this repository unless a separate written program is announced.

## Security expectations for contributors

Never commit credentials, tokens, production URLs, customer data, or operational query expressions. Treat model output and upstream integration data as untrusted input. Use the repository's CI checks, CodeQL analysis, secret scanning, dependency review, and Dependabot updates before merging changes.

## References

This policy follows GitHub's guidance for [adding a security policy](https://docs.github.com/code-security/getting-started/adding-a-security-policy-to-your-repository), [private vulnerability reporting](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability), and [coordinated disclosure](https://docs.github.com/en/enterprise-cloud@latest/code-security/concepts/vulnerability-reporting-and-management/coordinated-disclosure).
