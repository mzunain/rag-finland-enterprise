# Product Audit and Competitor Comparison

Reviewed on 2026-05-25.

## What Is Done

- FastAPI backend with versioned `/v1` API, health checks, request IDs, rate limits, structured logs, and Prometheus metrics.
- PostgreSQL + pgvector retrieval with document chunking, citations, page numbers, and relevance scores.
- PDF, DOCX, TXT, Markdown, and CSV ingestion.
- Finnish/English language detection, Finnish stemming, compound decomposition, and lexical fallback for Finnish queries.
- React admin UI for chat, document management, collections, users, API keys, usage, and analytics.
- Local Docker Compose stack for frontend, backend, and pgvector Postgres.
- Enterprise controls: JWT auth, role-based collection access, API keys, quotas, audit logs, OIDC support, and connector import endpoint.
- Deployment material for TLS, observability, on-prem, air-gapped packaging, GDPR, SOC 2 readiness, DPA, and EU AI Act notes.

## What Was Missing

- One-command onboarding from a clean checkout.
- Honest CI that also validates frontend, Docker, deployment manifests, and pgvector integration.
- Free cloud deployment path for a public demo.
- Clear product positioning against current enterprise RAG/search tools.
- A README structure that separates quick local setup from enterprise runbooks.

## Competitor Baseline

| Competitor | Current strengths | Gap for this repo | Practical response |
| --- | --- | --- | --- |
| Glean | Large connector catalog, source permissions, single-tenant options, data sovereignty regions, AI governance. | This repo has only starter connector import and no broad connector marketplace. | Stay focused on Finnish/EU sovereignty, add Microsoft 365/Google Drive/Jira connectors next, and keep permission-aware retrieval as a must-have. |
| Microsoft 365 Copilot | Native Microsoft Graph grounding, M365 permissions, retention, labels, audit, enterprise data protection. | Cannot beat Microsoft inside pure M365 estates. | Position as vendor-neutral, self-hostable, Finnish-first, and useful when data spans non-Microsoft or regulated systems. |
| Gemini Enterprise | Google-native agent platform, Google/M365/business app connectors, centralized governance, EU/US data residency controls. | This repo lacks no-code agent creation and marketplace-style agent workflows. | Add workflow/action APIs only after retrieval evaluation and permissions are strong. |
| Onyx | Open-source/self-hostable enterprise AI search with connectors and permission sync in enterprise edition. | Similar self-hostable story, but Onyx has a broader connector surface. | Differentiate through Finnish language quality, EU compliance pack, air-gapped deployment, and simpler enterprise MVP setup. |
| Azure AI Search / Vertex AI Search | Managed search infrastructure, enterprise cloud networking, managed scale. | They reduce ops effort for cloud-native teams. | Keep this repo portable: Docker, pgvector, local LLM mode, and clean migration path to managed search if needed. |

Sources used:

- Glean security and connectors: https://www.glean.com/security, https://docs.glean.com/connectors/about
- Microsoft Copilot enterprise data protection and connectors: https://learn.microsoft.com/en-us/copilot/microsoft-365/enterprise-data-protection, https://learn.microsoft.com/en-ie/microsoft-365-copilot/extensibility/overview-copilot-connector
- Gemini Enterprise connectors and compliance controls: https://cloud.google.com/gemini-enterprise, https://cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores, https://cloud.google.com/gemini/enterprise/docs/compliance-security-controls
- Onyx connectors: https://docs.onyx.app/admin/connectors, https://docs.onyx.app/overview/core_features/connectors

## Priority Roadmap

1. Retrieval evaluation harness: golden Finnish/English question sets, answer faithfulness checks, citation recall, and regression thresholds in CI.
2. Permission-aware connectors: Microsoft Graph/SharePoint, Google Drive, Confluence, Jira, and filesystem/S3 imports with source ACL preservation.
3. Admin onboarding: first-run setup screen to rotate the default admin password and validate OpenAI/local model settings.
4. Data governance: PII detection before indexing, retention policies per collection, and export/delete workflows for GDPR requests.
5. Observability: dashboard for retrieval latency, answer fallback rate, no-citation answers, failed ingestion jobs, and token cost.
6. Deployment hardening: paid EU production profile with managed Postgres backups, object storage for original files, and SSO enforced by default.
