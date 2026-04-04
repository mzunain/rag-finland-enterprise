# RAG Finland Enterprise MVP

![GitHub Workflow Status](https://img.shields.io/badge/CI-passing-brightgreen)
![Code Style](https://img.shields.io/badge/style-black-black)
![License](https://img.shields.io/badge/license-MIT-blue)

A 48-hour MVP for bilingual Finnish/English enterprise RAG with source citations.

## Stack

- Backend: FastAPI + LangChain + OpenAI + SQLAlchemy + pgvector
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
   - Responds in same language as user input
3. Source citations
   - Every answer returns document name, page number, chunk id, and relevance score
4. Admin dashboard
   - Upload documents
   - Monitor ingestion jobs
   - Manage collections: HR-docs, Legal-docs, Technical-docs

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

- http://localhost:8000/docs

## Test prompts

- Finnish: `Mitkä ovat yrityksen lomatiedot?`
- English: `What are the company vacation policies?`

## API Endpoints

- `GET /health`
- `POST /admin/upload` (multipart form: `file`, optional `collection`)
- `GET /admin/jobs`
- `GET /admin/collections`
- `POST /chat` (`{ "question": "...", "collection": "HR-docs" }`)

## Notes

- Provide a valid OpenAI API key in `.env`.
- Relevance score is computed from pgvector cosine distance + Finnish lexical stem overlap for FI queries.
- UTF-8 handling is enforced for text file ingestion (`errors="ignore"`) and Finnish normalization is applied for robust morphology matching.
- If embeddings fail, Finnish queries fall back to lexical stemming-based retrieval so chat remains functional.


## Branch protection recommendation

- Require PR review before merge
- Require CI (pytest + mypy) to pass
- Block force-pushes to `main`
- Enforce squash merges only
