# RAG Finland Enterprise

[![CI](https://github.com/mzunain/rag-finland-enterprise/actions/workflows/ci.yml/badge.svg)](https://github.com/mzunain/rag-finland-enterprise/actions/workflows/ci.yml)
[![Retrieval Evaluation](https://github.com/mzunain/rag-finland-enterprise/actions/workflows/retrieval-eval.yml/badge.svg)](https://github.com/mzunain/rag-finland-enterprise/actions/workflows/retrieval-eval.yml)
[![Release](https://img.shields.io/github/v/release/mzunain/rag-finland-enterprise)](https://github.com/mzunain/rag-finland-enterprise/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Enterprise-ready RAG application for global company knowledge bases, with strong Finnish, English, and Swedish language support. It includes document ingestion, pgvector retrieval, source citations, role-based access, audit logging, analytics, and deployment paths for local Docker, EU/on-prem environments, and free demo hosting.

## Product Screens

Screenshots show the local app with demo-style data.

| Chat workbench | Launch Center |
| --- | --- |
| ![Chat workbench showing governed collections, answer modes, and source-grounded prompts](docs/assets/screenshots/chat-workbench.png) | ![Launch Center showing readiness, connector coverage, eval schedule, and deploy gate](docs/assets/screenshots/launch-center.png) |

| Review Center | Analytics |
| --- | --- |
| ![Review Center showing flagged answers, live retrieval evals, and promoted cases](docs/assets/screenshots/review-center.png) | ![Analytics dashboard showing answer reliability, language demand, and governance signals](docs/assets/screenshots/analytics-dashboard.png) |

## Quick Start

Prerequisite: Docker Desktop or another Docker Compose-compatible runtime.

```bash
./run
```

This is the beginner path. The script creates `.env` if it does not exist, generates a local JWT secret, builds the stack, waits for health checks, and starts:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/v1/health
- API docs: http://localhost:8000/docs

Default local login:

```text
username: admin
password: change-admin-password
```

Set `OPENAI_API_KEY` in `.env` before using embeddings or chat with the default OpenAI provider. The app can still boot without it for UI, docs, auth, and health checks.

After sign-in, open the Launch tab and click `Seed demo workspace` to load demo corpus, eval cases, and review signals for a polished walkthrough.

Default local ports are `FRONTEND_PORT=5173`, `BACKEND_PORT=8000`, and `POSTGRES_PORT=55432`. Change them in `.env` if any are already in use.

## Common Commands

```bash
./run                 # start the full app
./run status          # show containers and health URLs
./run logs            # follow Docker logs
./run logs backend    # follow one service
./run stop            # stop containers
./run clean           # stop containers and remove volumes
./run eval            # run deterministic retrieval eval gate
./run test            # backend tests, eval gate, type check, frontend build, compose validation when Docker is available
./run doctor          # check local tools
```

`make run`, `make test`, `make logs`, and `make clean` are thin wrappers around the same script. Manual Docker command:

```bash
cp .env.example .env
docker compose up --build -d
```

Only `./run` needs Docker for normal app startup. `./run test` also uses local Python and Node.js when available; if Docker Compose is missing, it still runs backend tests, mypy, retrieval evals, and the frontend build, then skips only Compose validation.

## Stack

- Backend: FastAPI, SQLAlchemy, LangChain, OpenAI-compatible LLM providers
- Database: PostgreSQL with pgvector
- Frontend: React, Vite, Tailwind, React Query
- Auth and controls: JWT, API keys, RBAC, OIDC support, quotas, audit logs
- Operations: Docker Compose, Prometheus metrics, TLS reverse proxy option, air-gapped package option

## Architecture

```mermaid
flowchart LR
    Frontend["React/Vite frontend"] --> API["FastAPI API"]
    API --> Auth["JWT, API keys, RBAC"]
    API --> DB["PostgreSQL + pgvector"]
    API --> LLM["OpenAI-compatible LLM"]
    API --> Eval["Review Center + eval gate"]
    Sources["Documents and connector sources"] --> Ingestion["Parse, chunk, embed"]
    Ingestion --> DB
    DB --> Retrieval["Vector + lexical retrieval"]
    Retrieval --> API
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system, ingestion, request-path, and governance diagrams.

## Implemented

- Upload and parse PDF, DOCX, TXT, Markdown, and CSV files.
- Chunk documents, generate embeddings, and store vectors in Postgres/pgvector.
- Ask questions in Finnish, Swedish, or English and receive answers in the same language.
- Return citations with document name, page, chunk id, and relevance score.
- Improve Finnish retrieval with stemming, compound decomposition, and lexical fallback.
- Manage collections, documents, users, API keys, quotas, usage, and analytics from the UI.
- Import connector sources through Confluence/SharePoint-style fetch endpoints.
- Use the Launch Center to seed demo data, inspect readiness, compare connector coverage, schedule eval runs, and walk a production deploy checklist.
- Run Launch Center eval schedules automatically in the backend, with pass/fail history and the next due time visible in the UI.
- Run OpenAI, local OpenAI-compatible models, or sovereignty mode for local providers.
- Emit request IDs, structured logs, metrics, and audit events.

For a fuller status and competitor comparison, see [docs/PRODUCT_AUDIT.md](docs/PRODUCT_AUDIT.md).

## Testing

One command:

```bash
./run test
```

Backend only:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
PYTHONPATH=. ../.venv/bin/python -m pytest -q tests --ignore=tests/integration
PYTHONPATH=. ../.venv/bin/mypy
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```

PostgreSQL integration tests run in CI against `pgvector/pgvector:pg16`. Locally, set:

```bash
RUN_INTEGRATION_TESTS=1
INTEGRATION_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:55432/rag
```

## Retrieval Scorecard

Deterministic seeded eval gate, last verified 2026-06-06:

| Metric | Result | Threshold |
| --- | ---: | ---: |
| Cases passed | 5/5 | 100% |
| Case pass rate | 100% | 100% |
| Citation recall | 100% | 100% |
| Grounded-answer accuracy | 100% | 100% |
| No-answer accuracy | 100% | 100% |
| Missing predictions | 0 | 0 |

This is a regression baseline for known golden cases, not a production accuracy claim. See [docs/EVAL_SCORECARD.md](docs/EVAL_SCORECARD.md) for language/collection coverage and reproduction steps.

## CI Pipeline

GitHub Actions runs:

- backend unit tests
- deterministic retrieval evaluation gate
- PostgreSQL/pgvector integration smoke test
- focused mypy checks
- frontend production build
- frontend dependency audit
- Docker image builds
- Compose and deployment manifest validation

The separate `Retrieval Evaluation` workflow also runs the deterministic retrieval gate every day at 04:17 UTC and can be launched manually from GitHub Actions. This catches citation recall, no-answer, grounded-answer, and multilingual retrieval drift even when no code is being pushed.

The Launch Center also has an in-app eval scheduler. Enable it from the Launch tab to run promoted eval cases automatically inside the backend process. It checks for due work every `EVAL_SCHEDULER_POLL_SECONDS` seconds, records pass/fail status, and advances `next_run_at` after each due run.

The focused mypy target intentionally covers non-ORM modules first. The current SQLAlchemy models use classic declarative mappings, which produce noisy static typing errors until they are migrated to SQLAlchemy `Mapped[...]` models.

## API

Versioned endpoints are served under `/v1`. Legacy unversioned paths remain available for compatibility.

- `GET /v1/health`
- `GET /v1/health/deep`
- `GET /v1/metrics`
- `POST /v1/auth/token`
- `GET /v1/auth/me`
- `POST /v1/admin/upload`
- `GET /v1/admin/jobs`
- `GET /v1/admin/collections`
- `GET /v1/admin/documents`
- `GET /v1/admin/users`
- `POST /v1/admin/users`
- `GET /v1/admin/api-keys`
- `POST /v1/admin/api-keys`
- `GET /v1/admin/usage`
- `GET /v1/admin/ai/providers`
- `GET /v1/admin/reviews`
- `PATCH /v1/admin/reviews/{review_id}`
- `POST /v1/admin/reviews/{review_id}/promote-eval`
- `GET /v1/admin/eval-cases`
- `GET /v1/admin/eval-cases/export`
- `POST /v1/admin/eval-runs`
- `GET /v1/admin/eval-runs`
- `GET /v1/admin/launch/readiness`
- `POST /v1/admin/launch/demo-seed`
- `GET /v1/admin/launch/connectors`
- `GET /v1/admin/launch/deploy-checklist`
- `GET /v1/admin/launch/eval-schedule`
- `PATCH /v1/admin/launch/eval-schedule`
- `POST /v1/admin/launch/eval-schedule/run-due`
- `POST /v1/admin/connectors/import`
- `POST /v1/chat`
- `POST /v1/chat/stream`

Example token request:

```bash
curl -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=change-admin-password"
```

## Free Demo Deployment

Recommended free stack:

- Frontend: Vercel Hobby
- Backend: Render Free Web Service
- Database: Neon Free Postgres with pgvector

Use:

- [frontend/vercel.json](frontend/vercel.json) for the Vite SPA
- [render.yaml](render.yaml) for the backend Docker service
- [docs/DEPLOYMENT_FREE.md](docs/DEPLOYMENT_FREE.md) for the full walkthrough

Free tiers are good for demos and portfolio review. For real enterprise use, move to paid EU-region infrastructure or the on-prem deployment package.

## Production And Enterprise Runbooks

- [UpCloud EU deployment](docs/UPCLOUD_EU_DEPLOYMENT.md)
- [Free deployment](docs/DEPLOYMENT_FREE.md)
- [GDPR compliance](docs/GDPR_COMPLIANCE.md)
- [DPA template](docs/DPA_TEMPLATE.md)
- [SOC 2 readiness](docs/SOC2_READINESS.md)
- [EU AI Act notes](docs/EU_AI_ACT_COMPLIANCE.md)
- [On-prem and air-gapped deployment](deploy/onprem/README.md)

Optional local modes:

```bash
# TLS reverse proxy
docker compose -f docker-compose.yml -f docker-compose.tls.yml up --build

# Observability
docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d

# Air-gapped/on-prem profile
docker compose -f deploy/onprem/docker-compose.airgapped.yml up -d
```

## Engineering Workflow

- Use feature branches such as `feature/free-deploy-docs` or `fix/auth-token-handling`.
- Keep commit messages plain and specific, for example `Add one-command local startup`.
- Open PRs with What, Why, and Testing notes.
- Require CI to pass before merge.
- Prefer squash merge for clean project history.

## Community And Security

- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

## License

MIT
