# GDPR Compliance Pack

This document defines the minimum GDPR controls for enterprise deployments of RAG Finland Enterprise.

## 1. Roles

- Customer: Data Controller
- RAG Finland Enterprise operator: Data Processor
- Sub-processors: OpenAI (if enabled), infrastructure provider (UpCloud)

## 2. Data Categories

- uploaded business documents
- user prompts and generated answers
- authentication metadata (username, role, API key usage)
- audit records (`audit_logs`, `usage_events`)

## 3. Processing Purposes

- enterprise document retrieval and Q&A
- access control and security monitoring
- operational troubleshooting and SLA reporting

## 4. Legal Basis

- Article 6(1)(b): contract performance
- Article 6(1)(f): legitimate interest for security logs

## 5. Technical Controls

- JWT authentication and role-based access control
- per-collection permissions
- API key lifecycle with quotas and revocation
- immutable audit trail for admin/data mutations
- encrypted transport via TLS (nginx reverse proxy)
- EU-only hosting option (UpCloud Finland)

## 6. Retention and Deletion

- chat history retention configurable per tenant
- audit logs retained 12 months by default
- customer can request erasure workflows per collection
- API key and user deactivation is immediate (`is_active=false`)

## 7. Data Subject Rights Workflow

1. Customer submits request with user identifier or document scope.
2. Admin exports matching records from `chat_messages`, `audit_logs`, `usage_events`.
3. For erasure requests, delete user content and invalidate associated API keys.
4. Provide completion report to customer in 30 days maximum.

## 8. Breach Notification Workflow

- detect incident via logs/metrics alerts
- contain impacted credentials (rotate secrets, revoke keys)
- preserve forensic logs
- notify affected controller without undue delay (target <24h)
- support controller Article 33 reporting obligations

## 9. Required Artifacts for Procurement

- signed DPA (`docs/DPA_TEMPLATE.md`)
- list of active subprocessors
- evidence of EU region deployment
- security questionnaire answers (access controls, encryption, logging)
