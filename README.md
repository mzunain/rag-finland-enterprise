# rag-finland-enterprise

> Bilingual Finnish/English RAG system for enterprise knowledge bases — making internal documents instantly searchable.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Stack](https://img.shields.io/badge/stack-Next.js%20%2B%20Node.js%20%2B%20Qdrant-black)
![Language](https://img.shields.io/badge/language-Finnish%20%2F%20English-brightgreen)
![Status](https://img.shields.io/badge/status-active-brightgreen)

## The Problem

Finnish corporations like OP Bank, Kone, and Wärtsilä have thousands of internal documents — manuals, SOPs, contracts, HR policies — that employees cannot search effectively. Existing RAG tools either don’t support Finnish, or require expensive custom integration work.

I built this to change that.

## Key Differentiator: Finnish Language Support

Most RAG solutions are English-only. This system is built from the ground up to handle Finnish morphology — agglutinative word forms, case inflections, and compound words that break standard embedding models.

## Features

- **Document upload** — PDF, DOCX, TXT, CSV support with automatic chunking
- **Bilingual search** — query in Finnish or English, get relevant results regardless of document language
- **Source citation** — every answer references the exact document and page number
- **Department-level access control** — employees only see documents they’re authorized for
- **Conversation memory** — multi-turn Q&A with context retention
- **On-premise option** — can run fully local for GDPR/data residency requirements

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui |
| Backend | Node.js, Express, TypeScript |
| Embeddings | OpenAI text-embedding-3-large + Finnish fine-tuned model |
| Vector DB | Qdrant (self-hosted) or Pinecone |
| LLM | GPT-4o / Azure OpenAI / local Mistral |
| Auth | NextAuth.js with role-based access |
| Storage | AWS S3 / Azure Blob / MinIO |

## Who This Is For

Any Finnish corporation with document-heavy workflows: OP Bank, Kone, Wärtsilä, Stora Enso, or Finnish government agencies managing large knowledge bases.

## Project Structure

```
rag-finland-enterprise/
├── frontend/          # Next.js chat + document management UI
├── backend/           # Node.js RAG pipeline
│   ├── ingestion/     # Document processing and chunking
│   ├── retrieval/     # Vector search and reranking
│   └── generation/    # LLM response generation
├── models/            # Finnish NLP model configs
└── docker-compose.yml
```

## Getting Started

```bash
git clone https://github.com/mzulqarnain118/rag-finland-enterprise
cd rag-finland-enterprise
npm install
cp .env.example .env  # add your API keys
npm run dev
```

## Roadmap

- [x] Repository setup and architecture design
- [ ] Document ingestion pipeline (PDF/DOCX/TXT)
- [ ] Finnish language embedding integration
- [ ] Qdrant vector store setup
- [ ] Chat UI with source citations
- [ ] Role-based access control
- [ ] Bilingual query handling
- [ ] On-premise deployment guide
- [ ] Live demo

## License

MIT — see [LICENSE](LICENSE)
