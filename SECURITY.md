# Security policy

## Supported versions

Security fixes are applied to the latest version on the `main` branch.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's private
security advisory flow for this repository and include the affected component,
reproduction steps, and potential impact. Do not include real credentials or private
data. You should receive an acknowledgement within five business days.

## Threat model

The primary untrusted inputs are user questions and model-generated SQL. External model
responses, example text, and database content are also treated as untrusted at their
boundaries. The application protects a fixed analytics database; it is not designed to
accept arbitrary database paths, arbitrary SQL, or privileged database credentials.

## Trust boundaries and controls

- **Prompt injection:** user and data context are delimited as untrusted content.
  Model output is never authorized by the prompt alone.
- **SQL injection and generated writes:** SQLGlot parses one statement and enforces a
  read-only AST, table allowlist, system-catalog restrictions, and row limit.
- **Database permissions:** SQLite is opened using a read-only URI, query-only mode,
  trusted-schema restrictions, and a fail-closed authorizer.
- **Secrets:** provider keys are loaded only at runtime, masked by configuration
  wrappers, ignored by Git, and excluded from Docker.
- **Provider privacy:** Gemini mode sends a question, schema context, selected examples,
  and bounded result context to Google. Operators are responsible for provider-policy
  compliance.
- **Errors and logs:** public errors expose safe categories, not stack traces, local
  paths, prompts, result rows, credentials, or raw provider metadata.

Defense in depth is not a substitute for least-privilege database credentials,
provider data-governance review, monitoring, and human review in a production system.
