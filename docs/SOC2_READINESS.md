# SOC 2 Type II Readiness Checklist

This checklist tracks controls required before entering a formal SOC 2 Type II audit window.

## Security

- [x] JWT authentication and role-based authorization
- [x] API key lifecycle with revocation
- [x] Structured audit logs for privileged actions
- [x] Rate limiting and upload limits
- [ ] Quarterly secret rotation evidence retained
- [ ] Formal vulnerability management policy signed

## Availability

- [x] Deep health checks and metrics endpoint
- [x] Observability stack profile (Prometheus + Grafana)
- [ ] Incident response tabletop exercises (quarterly)
- [ ] SLA/SLO definitions approved

## Confidentiality

- [x] TLS deployment profile (`docker-compose.tls.yml`)
- [x] EU-residency runbook
- [x] On-prem / air-gapped deployment profile
- [ ] Encryption-at-rest key management SOP

## Processing Integrity

- [x] Alembic migrations for controlled schema changes
- [x] Automated tests in CI pipeline
- [ ] Change management evidence mapped to ticket IDs

## Privacy

- [x] GDPR compliance pack and DPA template
- [ ] Data retention policy signed by legal
- [ ] DSAR workflow test evidence

## Evidence Folder Structure (recommended)

- `evidence/access-control/`
- `evidence/change-management/`
- `evidence/incident-response/`
- `evidence/vendor-management/`
- `evidence/backup-restore/`

Maintain dated screenshots/log exports per quarter for Type II period evidence.
