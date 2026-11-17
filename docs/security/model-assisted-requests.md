# Model-assisted request and approval boundary

The model is an untrusted, read-only analysis component. It has no tool definitions and cannot authorize or execute operational actions. Its text is returned as data only; the dashboard renders it as text rather than HTML. Never use a model response as an approval, command, or mutation payload.

## Data sent to the model

`POST /api/query` sends a bounded user query and a projected `operational_context` object. The projection is allowlisted in `ModelAdapter` and includes at most 25 items per section:

- `metrics`: `name`, numeric `value`, and `timestamp`.
- `alerts`: `name`, `severity`, `status`, `source`, `timestamp`, and `message`.
- `incidents`: `id`, `title`, `severity`, `status`, `created_at`, and `updated_at`.

Text values are limited to 500 characters and common credential patterns are redacted. Other upstream fields, including metric labels and incident descriptions, are excluded. The complete request is serialized as JSON and placed between escaped `<untrusted-request-json>` delimiters. The system message directs the model to treat both the user query and all operational values as untrusted data, not instructions. Delimiters and prompt instructions reduce risk but do not make prompt injection preventable; application-side controls remain authoritative.

The model request contains no local environment variables, inbound request headers, API keys used to authenticate the caller, or audit history. The model endpoint's own credential, if configured, is sent only as an outbound HTTP authorization header and never in the prompt body. The service accepts only a non-empty text string from `choices[0].message.content` or `output_text`, with an 8,000-character maximum. It does not execute model-generated commands or expose model output to an action executor.

## Mutating operations

`POST /api/suppress-alert` and `POST /api/set-thresholds` require both an authenticated gateway principal with the route's exact action scope and a separate, one-time human approval:

1. `aiops:alerts:silence` authorizes alert suppression; `aiops:thresholds:write` authorizes threshold changes. A shared `AIOPS_API_KEY` grants read access only.
2. The caller supplies `X-AiOps-Approval-ID` for a pending approval in the configured approval authority.
3. The authority atomically verifies and consumes the approval, bound to the exact action and SHA-256 fingerprint of the validated operation payload.

The service fails closed when approval verification is not configured. The approval authority must authenticate and authorize the named human approver, enforce approval expiry and one-time consumption, and retain its own durable approval record. AiOps independently records the approval ID, approver, action, timestamp, and payload fingerprint in its bounded audit log before attempting the external mutation. The authenticated gateway principal and approver are recorded separately. A model response cannot populate or satisfy any of these fields.

Configure these server-side settings through a secret manager:

- `AIOPS_APPROVAL_URL`: the approval authority's HTTPS verify-and-consume endpoint, without URL credentials, query, or fragment data.
- `AIOPS_APPROVAL_API_KEY`: credential for AiOps to call that endpoint, at least 24 characters.

The approval endpoint accepts a JSON `POST` body with `approval_id`, `action`, and `payload_sha256`. An accepted response must be a JSON object containing `status: "approved"`, `consumed: true`, the exact same `approval_id`, `action`, and `payload_sha256`, plus non-empty `approved_by` and timezone-qualified ISO-8601 `approved_at`. The authority must atomically reject reused, expired, unauthorized, or mismatched approvals. AiOps does not follow redirects when sending the approval credential. `AIOPS_APPROVAL_API_KEY` is never forwarded to the model.

Example write headers sent through the trusted gateway:

```http
X-AiOps-Gateway-Token: <server-side-gateway-secret>
X-AiOps-Principal: <authenticated-user>
X-AiOps-Scopes: aiops:alerts:silence
Origin: <configured-same-origin>
X-AiOps-Approval-ID: <approval-ticket-id>
```

The gateway must strip client-supplied identity headers and set them only after authenticating the user. Do not put approval secrets, production operational data, or real approval IDs in source control or tests.

## References

- [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) recommends separating untrusted external content, constraining model behavior, adversarial testing, and human approval for high-risk actions.
- [OWASP LLM05:2025 Improper Output Handling](https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/) recommends validating model output and encoding it for its display context before downstream use.
- [NIST AI RMF: Generative Artificial Intelligence Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) provides a lifecycle risk-management profile for generative AI systems.
