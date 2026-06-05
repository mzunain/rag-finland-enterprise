# Security Policy

## Supported Versions

Security fixes are currently applied to the latest release and the `main` branch.

| Version | Supported |
| --- | --- |
| `v1.x` | Yes |
| `< v1.0.0` | No |

## Reporting a Vulnerability

Please do not open a public issue for a suspected vulnerability.

Report security-sensitive findings privately to the repository owner with:

- A short description of the issue and affected component.
- Reproduction steps or a proof of concept.
- Impact, including whether secrets, documents, user data, or administrative access are exposed.
- Any logs, screenshots, or request examples that help confirm the behavior.

The expected response target is:

- Initial acknowledgement: within 3 business days.
- Triage update: within 7 business days.
- Fix or mitigation plan: based on severity and exploitability.

## Scope

In scope:

- Authentication, authorization, RBAC, and API key handling.
- Document ingestion, parsing, and source access controls.
- Retrieval behavior that can expose unauthorized source material.
- Audit logging, quota enforcement, and admin endpoints.
- Docker, deployment, and reverse proxy configuration that changes security boundaries.

Out of scope:

- Vulnerabilities requiring access to a developer's local machine.
- Denial-of-service findings against free-tier demo deployments.
- Reports that only affect intentionally insecure local defaults such as `change-admin-password`.

## Operational Guidance

- Rotate the default admin password before any external demo.
- Keep `.env`, provider API keys, database URLs, customer documents, and exported datasets out of git.
- Use HTTPS and restricted `CORS_ORIGINS` for deployed environments.
- Prefer EU-region or on-prem infrastructure when processing regulated enterprise documents.
- Run `./run test` and the retrieval eval gate before releases.
