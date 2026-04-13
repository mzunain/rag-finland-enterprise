# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **UI overhaul** — professional enterprise design: Slack-style chat, drag-upload admin, collection tabs, collapsible citations (PR #14)
- **Swedish language support** — trilingual UI (EN/FI/SV) with ~50 Swedish translation keys, backend Swedish detection and prompts (PR #13)
- **Analytics dashboard** with usage stats, language breakdown, collection usage, and recent queries (PR #11)
- **SSE streaming** for real-time token-by-token chat responses (PR #10)
- **Accessibility** with ARIA labels, skip navigation, focus-visible styles, and screen reader support (PR #9)
- **Bilingual UI** (Finnish/English) with ~100 translation keys and persistent language switcher (PR #8)
- **Dynamic collections** CRUD — create, list, and delete collections via API and admin UI (PR #7)
- **Chat history** with persistent sessions, conversation sidebar, and message bubble UI (PR #6)
- **Document management** — list, delete, and inspect chunks per collection with stats (PR #5)
- **Frontend architecture** — React component hierarchy with routing, error boundaries, and API layer (PR #4)
- **Backend test suite** — 47 tests covering API endpoints, ingestion pipeline, and Finnish stemmer (PR #3)
- **Security hardening** — DOMPurify XSS fix, configurable CORS, structured logging, expanded .gitignore (PR #2)
- Finnish stemming utilities using Snowball stemmer for improved Finnish query handling
- Hybrid reranking for Finnish chat requests with stem-overlap lexical boost
- CI workflow running pytest and mypy checks
