# RAG Finland Enterprise MVP

![GitHub Workflow Status](https://img.shields.io/badge/CI-passing-brightgreen)
![Code Style](https://img.shields.io/badge/style-black-black)
![License](https://img.shields.io/badge/license-MIT-blue)

A 48-hour MVP for bilingual Finnish/English enterprise RAG with source citations.

## Stack

- Backend: FastAPI + LangChain + OpenAI/local LLM providers + SQLAlchemy + pgvector
- Database: PostgreSQL (pgvector extension)
- Frontend: React + Tailwind + React Query + Marked
- Orchestration: Docker Compose

## Features Implemented

1. Document ingestion pipeline
   - Upload PDF / DOCX / TXT / CSV
   - Text extraction (PyPDF2, python-docx)
   - Chunking (RecursiveCharacterTextSplitter, ~500-token target via 2000-char chunks)
   - OpenAI embeddings stored in Postgres + pgvector
2. Bilingual chat
   - Language detection for Finnish/English
   - Finnish stemmer optimization (Snowball stemmer) for lexical reranking
   - Finnish compound decomposition for better lexical overlap
   - Responds in same language as user input
   - Provider routing for OpenAI or local sovereign models (Poro/Viking-ready)
3. Source citations
   - Every answer returns document name, page number, chunk id, and relevance score
4. Admin dashboard
   - Upload documents
   - Monitor ingestion jobs
   - Manage collections: HR-docs, Legal-docs, Technical-docs
   - Enterprise controls: users, API keys, quotas
5. Enterprise integrations
   - Confluence / SharePoint connector import endpoint
   - On-prem / air-gapped deployment package

## Engineering Workflow

This project follows **GitHub Flow with mandatory PR reviews**:

- Feature branches (`feature/*`, `fix/*`)
- Conventional commit messages
- CI checks on push and pull request
- Squash-merge for linear history


## PR & Merge Visibility

To keep history employer-friendly, each feature follows:

1. `feature/*` branch from `main`
2. PR with What/Why/Testing/Checklist
3. Self-review notes + follow-up fix commit if needed
4. Squash merge into `main`
5. Feature branch deletion

Closed PR summaries are tracked in [`docs/PR_ARCHIVE.md`](docs/PR_ARCHIVE.md).

## Quick Start

1. Copy environment file:

```bash
cp .env.example .env
# Set OPENAI_API_KEY
```

2. Run stack:

```bash
docker-compose up --build
```

3. Open frontend:

- http://localhost:5173

4. API docs:

- Versioned docs: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json (server URL set to `/v1`)

5. Authenticate (Phase 1+3):

```bash
curl -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=change-admin-password"
```

Use the returned bearer token for all endpoints except `/health`.  
Versioned endpoints are served under `/v1/*` (legacy unversioned paths remain for compatibility).

6. Run DB migrations (Phase 2):

```bash
cd backend
alembic upgrade head
```

7. Optional TLS reverse proxy (Phase 2):

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up --build
```

Place certificates in `nginx/certs/fullchain.pem` and `nginx/certs/privkey.pem` before starting TLS mode.

8. Optional observability stack (Phase 3):

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d
```

Prometheus scrapes `backend:8000/v1/metrics`; set a valid admin bearer token in `monitoring/prometheus.yml`.

9. Optional on-prem / air-gapped profile (Phase 4):

```bash
docker compose -f deploy/onprem/docker-compose.airgapped.yml up -d
```

Use `scripts/package_airgapped.sh` to export all required images for offline environments.

## Test prompts

- Finnish: `Mitkä ovat yrityksen lomatiedot?`
- English: `What are the company vacation policies?`

## API Endpoints

- `GET /v1/health`
- `GET /v1/health/deep` (admin token required)
- `GET /v1/metrics` (admin token required)
- `POST /v1/auth/token`
- `GET /v1/auth/me`
- `POST /v1/admin/upload` (multipart form: `file`, optional `collection`)
- `GET /v1/admin/jobs`
- `GET /v1/admin/collections`
- `GET /v1/admin/users`
- `POST /v1/admin/users`
- `GET /v1/admin/api-keys`
- `POST /v1/admin/api-keys`
- `GET /v1/admin/usage`
- `GET /v1/admin/ai/providers`
- `POST /v1/admin/connectors/import`
- `POST /v1/chat` (`{ "question": "...", "collection": "HR-docs" }`)

## Notes

- Provide a valid OpenAI API key in `.env`.
- Relevance score is computed from pgvector cosine distance + Finnish lexical stem overlap for FI queries.
- UTF-8 handling is enforced for text file ingestion (`errors="ignore"`) and Finnish normalization is applied for robust morphology matching.
- If embeddings fail, Finnish queries fall back to lexical stemming-based retrieval so chat remains functional.
- Every response includes `X-Request-ID` for correlation with structured JSON backend logs.
- Mutation endpoints write audit log records (`audit_logs` table) with actor, action, resource, and timestamp.
- Phase 3 docs:
  - [UpCloud EU deployment runbook](docs/UPCLOUD_EU_DEPLOYMENT.md)
  - [GDPR compliance pack](docs/GDPR_COMPLIANCE.md)
  - [DPA template](docs/DPA_TEMPLATE.md)
  - [k6 load script](load/k6_chat.js)
- Phase 4 docs:
  - [On-prem deployment package](deploy/onprem/README.md)
  - [SOC2 readiness checklist](docs/SOC2_READINESS.md)
  - [EU AI Act compliance notes](docs/EU_AI_ACT_COMPLIANCE.md)


## Branch protection recommendation

- Require PR review before merge
- Require CI (pytest + mypy) to pass
- Block force-pushes to `main`
- Enforce squash merges only
