# Architecture

RAG Finland Enterprise is a full-stack RAG application for governed enterprise knowledge bases. It is designed around source-grounded answers, multilingual retrieval, administrative controls, and deployment paths for local Docker, EU cloud, and on-prem environments.

## System Context

```mermaid
flowchart LR
    User["Employee or reviewer"] --> Frontend["React/Vite frontend"]
    Admin["Admin or operator"] --> Frontend
    Frontend --> API["FastAPI backend"]
    API --> Auth["JWT, API keys, RBAC, OIDC-ready controls"]
    API --> DB["PostgreSQL + pgvector"]
    API --> LLM["OpenAI-compatible LLM provider"]
    API --> Embed["Embedding provider"]
    API --> Metrics["Structured logs, audit logs, Prometheus metrics"]
    Sources["Documents and connector sources"] --> Ingestion["Ingestion pipeline"]
    Ingestion --> DB
```

## Ingestion And Retrieval Flow

```mermaid
flowchart TD
    Upload["Upload PDF, DOCX, TXT, Markdown, or CSV"] --> Parse["Parse and normalize text"]
    Connector["Connector import: Confluence, SharePoint-style, generic HTTPS"] --> Parse
    Parse --> Chunk["Chunk with document, page, source URL, freshness, and ACL metadata"]
    Chunk --> Embed["Generate embeddings"]
    Embed --> Store["Store chunks and vectors in pgvector"]
    Store --> Eval["Seed or promote eval cases"]
    Question["User question"] --> Detect["Detect language and retrieval mode"]
    Detect --> Retrieve["Vector + lexical retrieval with Finnish stemming fallback"]
    Retrieve --> Rerank["Hybrid relevance and source confidence scoring"]
    Rerank --> Answer["LLM answer constrained by retrieved context"]
    Answer --> Cite["Return citations, confidence, freshness, and review signal"]
```

## Runtime Request Path

```mermaid
sequenceDiagram
    participant User
    participant UI as React UI
    participant API as FastAPI
    participant DB as Postgres/pgvector
    participant LLM as LLM provider

    User->>UI: Ask a question
    UI->>API: POST /v1/chat or /v1/chat/stream
    API->>API: Authenticate and enforce collection access
    API->>DB: Retrieve candidate chunks
    API->>API: Apply language-specific lexical fallback and scoring
    API->>LLM: Generate grounded answer from retrieved context
    LLM-->>API: Answer text
    API->>DB: Store chat, usage, audit, and review signals
    API-->>UI: Stream answer, citations, and confidence metadata
    UI-->>User: Show answer with source evidence and feedback controls
```

## Security And Governance Boundaries

```mermaid
flowchart TB
    Request["API request"] --> Authn["Authentication"]
    Authn --> Authz["RBAC and collection scope"]
    Authz --> Quota["Quota and usage controls"]
    Quota --> Action["Chat, admin, connector, or eval action"]
    Action --> Audit["Audit log and request ID"]
    Action --> SourceACL["Source ACL and freshness metadata"]
    SourceACL --> Retrieval["Permission-aware retrieval"]
    Retrieval --> Review["Answer review center and eval promotion"]
```

## Operational Surfaces

- **Chat workbench:** source-grounded answering with citations, answer modes, confidence, feedback, and evidence export.
- **Documents:** collection and source management for indexed evidence.
- **Admin:** users, API keys, quotas, connectors, source freshness, and ingestion jobs.
- **Review Center:** flagged-answer triage and promotion into retrieval eval cases.
- **Launch Center:** demo seed, readiness checks, connector coverage, eval scheduling, and deploy checklist.
- **Analytics:** usage, language demand, collection adoption, source confidence, feedback, and quota posture.

## Deployment Shape

The default local stack runs React, FastAPI, and PostgreSQL/pgvector through Docker Compose. Optional overlays add TLS, Prometheus, and air-gapped/on-prem packaging. Free demo deployment is documented for Vercel, Render, and Neon; production guidance favors paid EU-region infrastructure or on-prem deployment.
