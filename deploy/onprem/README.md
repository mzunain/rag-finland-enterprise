# On-Prem / Air-Gapped Deployment

This package provides an offline-first deployment profile for regulated customers.

## Included

- `docker-compose.airgapped.yml` with:
  - local PostgreSQL + pgvector
  - local model gateway (Ollama)
  - backend in sovereignty mode (`LLM_PROVIDER=local`, `EMBEDDING_PROVIDER=local`)
  - frontend pointing to `/v1` API

## Build artifacts before transfer

Run from connected build environment:

```bash
./scripts/package_airgapped.sh
```

The script exports Docker images to `dist/airgapped-images.tar.gz`.

## Import on isolated environment

```bash
docker load -i dist/airgapped-images.tar.gz
docker compose -f deploy/onprem/docker-compose.airgapped.yml up -d
```

## Hardening checklist

- Replace default DB credentials
- Set strong `JWT_SECRET_KEY`
- Restrict host firewall to trusted networks
- Store exported images in signed artifact repository
- Run `alembic upgrade head` after first startup
