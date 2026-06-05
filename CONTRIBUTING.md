# Contributing

Thanks for helping improve RAG Finland Enterprise. This project aims to be a practical, enterprise-ready RAG application for multilingual knowledge bases, so contributions should keep security, reliability, and maintainability in view.

## Getting Started

1. Fork the repository or create a feature branch from `main`.
2. Install Docker Desktop or another Docker Compose-compatible runtime.
3. Start the app:

```bash
./run
```

4. Sign in locally with:

```text
username: admin
password: change-admin-password
```

Set `OPENAI_API_KEY` in `.env` before testing embeddings or chat with the default OpenAI provider. The app can still boot without it for UI, auth, health checks, and docs.

## Development Workflow

- Use focused branches such as `feature/sharepoint-connector` or `fix/citation-ranking`.
- Keep commits small, plain, and specific.
- Follow the existing FastAPI, SQLAlchemy, React, Vite, and Tailwind patterns already in the repo.
- Avoid committing secrets, `.env` files, deployment credentials, or exported customer data.
- Add or update tests when changing backend behavior, retrieval logic, auth, ingestion, connectors, or user-facing workflows.

## Testing

Run the full local check when possible:

```bash
./run test
```

Backend-only checks:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
PYTHONPATH=. ../.venv/bin/python -m pytest -q tests --ignore=tests/integration
PYTHONPATH=. ../.venv/bin/mypy
```

Frontend build:

```bash
cd frontend
npm ci
npm run build
```

PostgreSQL integration tests require a local pgvector database and these environment variables:

```bash
RUN_INTEGRATION_TESTS=1
INTEGRATION_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:55432/rag
```

## Pull Requests

Each pull request should include:

- What changed.
- Why it changed.
- How it was tested.
- Any deployment, migration, security, or data-handling impact.

Prefer squash merge after CI passes.

## Security

Do not open public issues for suspected vulnerabilities. Report security-sensitive findings privately to the repository owner with enough detail to reproduce the issue.

## Releases

Update `CHANGELOG.md` for user-visible changes. Releases should use semantic version tags such as `v1.0.0` and include concise notes for operators and reviewers.
