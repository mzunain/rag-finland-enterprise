# UpCloud EU Deployment Runbook (Finland)

This runbook describes a production deployment in UpCloud Finnish data centers (Helsinki `fi-hel1` or Tampere `fi-tre1`) for enterprise customers that require EU residency.

## 1. Architecture

- `app` VM group (backend + frontend containers)
- `db` managed PostgreSQL with pgvector extension
- `edge` VM (nginx TLS termination)
- `monitoring` VM (Prometheus + Grafana)
- private VPC network between all nodes

## 2. Region and Residency Controls

- Provision all compute and storage in Finland only (`fi-hel1`/`fi-tre1`).
- Disable snapshots/backup replication to non-EU zones.
- Store object backups only in EU object storage buckets.
- Enforce private network access for PostgreSQL (`allowlist` app subnet only).

## 3. Provisioning Checklist

1. Create UpCloud private network per customer environment.
2. Provision Ubuntu LTS VMs with dedicated service accounts.
3. Install Docker + Compose plugin.
4. Deploy project using:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml -f docker-compose.observability.yml up -d --build
```

5. Configure DNS + TLS certificates for customer domain.
6. Run migrations:

```bash
cd backend
alembic upgrade head
```

## 4. Security Baseline

- `AUTH_REQUIRED=true`
- rotate `JWT_SECRET_KEY` per environment
- rotate OpenAI and OIDC secrets every 90 days
- disable public DB access
- run containers as non-root (already enforced in Dockerfiles)
- ship structured logs to SIEM (json format is default)

## 5. Backups and DR

- PostgreSQL PITR enabled with daily retention policy
- nightly encrypted off-site backup in EU storage
- quarterly restore test (staging)
- RPO target: 15 minutes
- RTO target: 2 hours

## 6. Customer Acceptance Evidence

For enterprise security reviews, provide:

- deployment manifest with Finnish region IDs
- network diagram showing private DB access
- latest backup restore report
- copy of `docs/GDPR_COMPLIANCE.md`
- audit log sample from `audit_logs` table
