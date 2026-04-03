# PR Archive

This file tracks self-reviewed PRs merged with squash strategy for portfolio visibility.

## PR-0001
- **Title:** feat(mvp): bootstrap bilingual RAG MVP stack
- **Type:** Squash merge
- **Summary:** FastAPI backend, React frontend, pgvector storage, ingestion pipeline, Finnish stemming, Docker Compose, CI scaffold.
- **Review Notes:** Added migration safety for `search_text` and parser error handling.

## PR-0002
- **Title:** fix(finnish): harden Finnish retrieval with normalization and lexical fallback
- **Type:** Squash merge
- **Summary:** Added Finnish character normalization, lexical fallback when embeddings fail, and expanded Finnish query tests.
- **Review Notes:** Verified code hygiene checks and documented fallback behavior.
