#!/usr/bin/env bash
set -euo pipefail

mkdir -p dist

images=(
  rag-finland-backend:latest
  rag-finland-frontend:latest
  pgvector/pgvector:pg16
  ollama/ollama:0.6.6
)

# Build app images locally (tags used by air-gapped compose file)
docker build -t rag-finland-backend:latest backend
docker build -t rag-finland-frontend:latest frontend

docker save "${images[@]}" | gzip > dist/airgapped-images.tar.gz

echo "Created dist/airgapped-images.tar.gz"
