# Free Deployment Runbook

Verified on 2026-05-25. This setup keeps the demo deployable without paid infrastructure, while still using the same Docker/Postgres shape as local development.

## Recommended Free Stack

| Layer | Platform | Why |
| --- | --- | --- |
| Frontend | Vercel Hobby | Free static Vite hosting, GitHub previews, CDN, automatic CI/CD. |
| Backend | Render Free Web Service | Runs the existing backend Dockerfile with a public HTTPS URL. Free services can sleep after idle periods. |
| Database | Neon Free Postgres | Managed Postgres with pgvector support for embeddings. |

Official references:

- Vercel pricing: https://vercel.com/pricing
- Render free web services: https://render.com/free
- Render free service sleep behavior: https://render.com/docs/faq
- Neon Postgres for AI and pgvector: https://neon.com/ai

## 1. Create Neon Postgres

1. Create a Neon project.
2. Open the SQL editor and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

3. Copy the pooled connection string.
4. Use the SQLAlchemy driver format in backend env vars:

```bash
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/dbname?sslmode=require
```

## 2. Deploy Backend on Render

1. In Render, create a new Blueprint from this repository.
2. Render will read `render.yaml` and create `rag-finland-backend`.
3. Set these environment variables:

```bash
DATABASE_URL=postgresql+psycopg2://...
OPENAI_API_KEY=sk-...
CORS_ORIGINS=https://your-vercel-domain.vercel.app
AUTH_USERS_JSON=[{"username":"admin","password":"replace-this-password","role":"admin","collections":["*"]}]
```

4. Deploy and verify:

```bash
curl https://your-render-service.onrender.com/v1/health
```

## 3. Deploy Frontend on Vercel

1. Import the repo in Vercel.
2. Set the project root directory to `frontend`.
3. Add the environment variable:

```bash
VITE_API_URL=https://your-render-service.onrender.com/v1
```

4. Deploy. `frontend/vercel.json` keeps React Router routes working on refresh.

## 4. GitHub Actions Pipeline

The CI workflow runs on pull requests and protected branches:

- backend unit tests
- PostgreSQL/pgvector integration smoke test
- focused mypy checks
- frontend production build
- frontend dependency audit
- Docker image builds
- Compose and deployment manifest validation

Do not add deploy steps until the required platform tokens are saved as GitHub Secrets. Vercel Git integration already creates preview deployments for frontend branches when the repo is connected.

## Production Notes

- Render Free is suitable for demos, not latency-sensitive production. Expect cold starts after idle time.
- Keep `AUTH_REQUIRED=true` outside local-only testing.
- Do not commit `.env`, `.vercel`, Render secrets, Neon connection strings, or OpenAI keys.
- For commercial use, move to paid tiers or an EU VPS/Kubernetes target, then reuse the Docker and on-prem runbooks already in this repo.
