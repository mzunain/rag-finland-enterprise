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

## PR-0003 (GH #2)
- **Title:** feat(security): harden project with XSS fix, CORS config, and logging
- **Type:** Squash merge
- **Summary:** Added DOMPurify for XSS prevention, configurable CORS origins, structured logging, comprehensive .gitignore, and fixed broken Finnish stemmer tests.
- **Review Notes:** Security-first hardening pass before feature development begins.

## PR-0004 (GH #3)
- **Title:** feat(tests): comprehensive backend test suite (29 tests)
- **Type:** Squash merge
- **Summary:** 12 API endpoint tests, 10 ingestion pipeline tests, shared fixtures with mocked DB and TestClient. No real DB or OpenAI calls.
- **Review Notes:** Establishes confidence for safe refactoring. All mocked.

## PR-0005 (GH #4)
- **Title:** feat(frontend): component architecture with routing and error boundaries
- **Type:** Squash merge
- **Summary:** Split 120-line monolith into 7 modules. Added react-router-dom, ErrorBoundary, centralized API layer. Chat + Admin pages.
- **Review Notes:** Clean separation of concerns. All existing functionality preserved.

## PR-0006 (GH #5)
- **Title:** feat(documents): document management with CRUD, chunk viewer, and stats
- **Type:** Squash merge
- **Summary:** 4 new API endpoints for document listing, deletion, chunk inspection, and collection stats. New Documents page with browse/delete/inspect UI.
- **Review Notes:** Cascading delete verified. Paginated chunk viewer works with large docs.

## PR-0007 (GH #6)
- **Title:** feat(chat): persistent chat history with session management
- **Type:** Squash merge
- **Summary:** ChatMessage model, session-based conversation persistence, 3 history endpoints, conversational bubble UI with sidebar.
- **Review Notes:** Session ID auto-generated if not provided, preserved if given. History loads correctly.

## PR-0008 (GH #7)
- **Title:** feat(collections): database-backed CRUD replacing hardcoded collections
- **Type:** Squash merge
- **Summary:** Collection model with seed defaults, create/list/delete endpoints, admin UI for collection management.
- **Review Notes:** Duplicate name check (409), empty name check (400), 404 on delete non-existent.

## PR-0009 (GH #8)
- **Title:** feat(i18n): bilingual Finnish/English UI with language switcher
- **Type:** Squash merge
- **Summary:** ~100 translation keys for both languages, LangContext provider, EN/FI toggle in header, localStorage persistence.
- **Review Notes:** All visible strings translated. Verified by switching to FI mode.

## PR-0010 (GH #9)
- **Title:** feat(a11y): accessibility with ARIA labels, skip nav, and focus management
- **Type:** Squash merge
- **Summary:** Skip-to-content link, dynamic html lang, ARIA roles/labels on all interactive elements, focus-visible styles.
- **Review Notes:** Tab navigation, screen reader announcements via aria-live, language toggle radio group semantics.

## PR-0011 (GH #10)
- **Title:** feat(streaming): SSE streaming for real-time chat responses
- **Type:** Squash merge
- **Summary:** POST /chat/stream with SSE events (metadata, token, done). Frontend streams tokens into chat bubble. Shared retrieval logic.
- **Review Notes:** Client disconnect handled. Full message persisted after stream completes.

## PR-0012 (GH #11)
- **Title:** feat(analytics): usage analytics dashboard with language and collection stats
- **Type:** Squash merge
- **Summary:** Analytics endpoint with session/query counts, language breakdown, collection usage, recent queries. Frontend with stat cards and CSS bar charts.
- **Review Notes:** Zero external charting dependencies. Auto-refreshes every 15s.

## PR-0013 (GH #13)
- **Title:** feat(i18n): trilingual Swedish language support
- **Type:** Squash merge
- **Summary:** Complete Swedish (sv) translations (~50 keys), backend language detection for Swedish queries, dedicated Swedish system prompts, EN/FI/SV header toggle, pgvector query parameter fix.
- **Review Notes:** Swedish detected correctly via langdetect. Answers in Swedish with citations. All 48 tests pass.
