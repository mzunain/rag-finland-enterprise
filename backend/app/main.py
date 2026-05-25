import logging
import secrets
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path as FilePath
from typing import Annotated, Literal
from urllib.parse import urlparse

import json

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Path, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import OpenAI, OpenAIError
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, Field, StringConstraints
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func as sa_func
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth_utils import hash_api_key, hash_password, month_window_start, utc_now, verify_password
from .config import settings
from .connectors import fetch_connector_document
from .db import (
    ApiKey,
    AuditLog,
    AnswerReview,
    ChatMessage,
    Collection,
    CollectionPermission,
    DocumentChunk,
    DocumentSource,
    EvaluationCase,
    EvaluationRun,
    IngestionJob,
    LaunchSetting,
    SessionLocal,
    UsageEvent,
    UserAccount,
    init_db,
)
from .evaluation import evaluate_retrieval
from .finnish import finnish_search_text, stem_overlap_ratio
from .ingestion import chunk_pages, extract_text
from .logging_utils import configure_logging, request_id_ctx
from .security import (
    CurrentUser,
    authenticate_user,
    create_access_token,
    ensure_collection_access,
    get_current_user,
    require_admin,
)

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.auth_required and settings.jwt_secret_key == "change-me-in-production":
        logger.warning("JWT_SECRET_KEY is using the default placeholder; set a secure value before deployment")
    yield


app = FastAPI(
    title="RAG Finland Enterprise MVP",
    version="1.0.0",
    servers=[{"url": settings.api_version_prefix, "description": "Versioned API root"}],
    lifespan=lifespan,
)
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.default_rate_limit])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

http_requests_total = Counter(
    "rag_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
chat_requests_total = Counter(
    "rag_chat_requests_total",
    "Total chat requests",
    ["mode", "status"],
)
ingestion_uploaded_bytes_total = Counter(
    "rag_ingestion_uploaded_bytes_total",
    "Total uploaded bytes for ingestion",
)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_version_prefix_middleware(request: Request, call_next):
    version_prefix = settings.api_version_prefix.rstrip("/")
    path = request.scope.get("path", "")
    if version_prefix and path.startswith(f"{version_prefix}/"):
        request.scope["path"] = path[len(version_prefix) :]
    elif version_prefix and path == version_prefix:
        request.scope["path"] = "/"
    return await call_next(request)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    token = request_id_ctx.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request.error",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        raise
    finally:
        request_id_ctx.reset(token)

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request.completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    http_requests_total.labels(
        method=request.method,
        path=request.url.path,
        status_code=str(response.status_code),
    ).inc()
    return response


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TurkuNLPEmbeddings:
    def __init__(self, endpoint: str, api_key: str = "", timeout_seconds: int = 20):
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _embed(self, texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"texts": texts}
        response = httpx.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        body = response.json()
        embeddings = body.get("embeddings") if isinstance(body, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ValueError("TurkuNLP embedding response must include one embedding per input text")
        parsed: list[list[float]] = []
        for item in embeddings:
            if not isinstance(item, list):
                raise ValueError("Embedding vector must be a list")
            parsed.append([float(value) for value in item])
        return parsed

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]


def _resolved_llm_provider(language: str) -> str:
    provider = settings.llm_provider.lower()
    if settings.data_sovereignty_mode and provider == "openai":
        return "local"
    if provider == "auto":
        return "local" if language == "fi" else "openai"
    return provider


def _resolved_embedding_provider(language: str) -> str:
    provider = settings.embedding_provider.lower()
    if settings.data_sovereignty_mode and provider == "openai":
        if settings.turkunlp_embedding_url:
            return "turkunlp"
        return "local"
    if provider == "auto":
        if language == "fi" and settings.turkunlp_embedding_url:
            return "turkunlp"
        return "openai"
    return provider


def _build_chat_llm(language: str, *, streaming: bool = False) -> ChatOpenAI:
    provider = _resolved_llm_provider(language)
    if provider in {"local", "poro", "viking"}:
        model_name = settings.local_llm_model_fi if language == "fi" else settings.local_llm_model_default
        return ChatOpenAI(
            model=model_name,
            api_key=settings.local_provider_api_key,
            base_url=settings.local_llm_base_url,
            temperature=0,
            streaming=streaming,
        )
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        temperature=0,
        streaming=streaming,
    )


def _build_embeddings(language: str):
    provider = _resolved_embedding_provider(language)
    if provider == "turkunlp":
        if not settings.turkunlp_embedding_url:
            logger.warning("TURKUNLP_EMBEDDING_URL not configured, falling back to OpenAI embeddings")
        else:
            return TurkuNLPEmbeddings(
                endpoint=settings.turkunlp_embedding_url,
                api_key=settings.turkunlp_embedding_api_key,
                timeout_seconds=settings.connector_fetch_timeout_seconds,
            )
    if provider == "local":
        return OpenAIEmbeddings(
            model=settings.local_embedding_model,
            api_key=settings.local_provider_api_key,
            base_url=settings.local_embedding_base_url,
        )
    return OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)


def _validate_connector_source_domain(source_url: str) -> None:
    raw_allowed = [item.strip().lower() for item in settings.connector_allowed_domains.split(",") if item.strip()]
    if not raw_allowed:
        return
    hostname = (urlparse(source_url).hostname or "").lower()
    if not hostname:
        raise HTTPException(status_code=400, detail=f"Invalid connector source URL: {source_url}")
    if hostname not in raw_allowed:
        raise HTTPException(status_code=400, detail=f"Connector source domain '{hostname}' is not allowlisted")


def _list_str(value) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _normalize_source_acl(raw_acl=None) -> dict:
    if raw_acl is None:
        return {"mode": "public", "allowed_users": [], "allowed_groups": []}
    if hasattr(raw_acl, "model_dump"):
        raw_acl = raw_acl.model_dump()
    if not isinstance(raw_acl, dict):
        return {"mode": "public", "allowed_users": [], "allowed_groups": []}

    allowed_users = sorted(set(_list_str(raw_acl.get("allowed_users")) or _list_str(raw_acl.get("allowedUsers"))))
    allowed_groups = sorted(set(_list_str(raw_acl.get("allowed_groups")) or _list_str(raw_acl.get("allowedGroups"))))
    requested_mode = raw_acl.get("mode")
    mode = "restricted" if allowed_users or allowed_groups or requested_mode == "restricted" else "public"
    return {"mode": mode, "allowed_users": allowed_users, "allowed_groups": allowed_groups}


def _source_acl_for_import(payload, source_url: str, connector_metadata: dict) -> dict:
    raw_acl = None
    if payload.source_acls:
        raw_acl = payload.source_acls.get(source_url)
    if raw_acl is None and isinstance(connector_metadata, dict):
        raw_acl = connector_metadata.get("source_acl")
    if raw_acl is None:
        raw_acl = payload.default_acl
    return _normalize_source_acl(raw_acl)


def _source_acl_summary(source_acl: dict) -> dict:
    return {
        "source_acl_mode": source_acl.get("mode", "public"),
        "source_acl_users": len(source_acl.get("allowed_users") or []),
        "source_acl_groups": len(source_acl.get("allowed_groups") or []),
    }


def _reset_quota_window(row) -> None:
    month_start = month_window_start()
    if row.quota_reset_at is None or row.quota_reset_at < month_start:
        row.used_this_month = 0
        row.quota_reset_at = month_start


def _consume_user_quota(db: Session, current_user: CurrentUser, *, units: int = 1) -> None:
    if not settings.db_auth_enabled or units <= 0 or current_user.auth_provider == "api_key":
        return
    user = (
        db.query(UserAccount)
        .filter(UserAccount.username == current_user.username, UserAccount.is_active.is_(True))
        .first()
    )
    if not isinstance(user, UserAccount):
        return
    if not user:
        return
    _reset_quota_window(user)
    if user.used_this_month + units > user.monthly_quota:
        raise HTTPException(status_code=429, detail="User monthly quota exceeded")
    user.used_this_month += units


def _track_usage(
    db: Session,
    *,
    current_user: CurrentUser,
    event_type: str,
    units: int = 1,
    metadata: dict | None = None,
) -> None:
    db.add(
        UsageEvent(
            actor_username=current_user.username,
            api_key_id=current_user.api_key_id,
            event_type=event_type,
            units=units,
            metadata_json=metadata or {},
        )
    )


def _source_confidence(citations: list[dict]) -> float:
    if not citations:
        return 0.0
    scores = []
    for citation in citations:
        try:
            scores.append(max(0.0, min(1.0, float(citation.get("relevance", 0.0)))))
        except (TypeError, ValueError):
            scores.append(0.0)
    return round(sum(scores) / max(1, len(scores)), 4)


def _citation_freshness_counts(citations: list[dict]) -> dict:
    stale = sum(1 for citation in citations if citation.get("source_freshness") == "stale")
    aging = sum(1 for citation in citations if citation.get("source_freshness") == "aging")
    failed = sum(1 for citation in citations if citation.get("source_freshness") == "failed")
    return {
        "stale_source_citations": stale,
        "aging_source_citations": aging,
        "failed_source_citations": failed,
        "stale_source_answer": stale > 0 or failed > 0,
    }


def _answer_quality(outcome: Literal["grounded", "no_context"], citations: list[dict]) -> dict:
    citation_count = len(citations)
    source_confidence = _source_confidence(citations)
    if outcome == "no_context":
        confidence_label = "no_context"
    elif source_confidence >= 0.55:
        confidence_label = "high"
    elif source_confidence >= 0.35:
        confidence_label = "medium"
    else:
        confidence_label = "low"
    return {
        "outcome": outcome,
        "grounded": outcome == "grounded" and citation_count > 0,
        "citation_count": citation_count,
        "source_confidence": source_confidence,
        "confidence_label": confidence_label,
    }


def _quality_usage_metadata(*, collection: str, language: str, quality: dict) -> dict:
    return {
        "collection": collection,
        "language": language,
        "outcome": quality["outcome"],
        "grounded": quality["grounded"],
        "citations": quality["citation_count"],
        "citation_count": quality["citation_count"],
        "source_confidence": quality["source_confidence"],
        "confidence_label": quality["confidence_label"],
        "answer_quality_version": 1,
    }


def _percent(part: int | float, whole: int | float) -> int:
    if not whole:
        return 0
    return round((part / whole) * 100)


def _quality_event_metadata(event) -> dict:
    metadata = getattr(event, "metadata_json", {}) or {}
    if not isinstance(metadata, dict):
        return {}
    citation_count = metadata.get("citation_count", metadata.get("citations", 0))
    try:
        citation_count = int(citation_count or 0)
    except (TypeError, ValueError):
        citation_count = 0
    try:
        source_confidence = float(metadata.get("source_confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        source_confidence = 0.0
    outcome = metadata.get("outcome")
    if outcome not in {"grounded", "no_context"}:
        outcome = "grounded" if citation_count > 0 else "no_context"
    collection = str(metadata.get("collection") or "unknown")
    return {
        "collection": collection,
        "outcome": outcome,
        "citation_count": citation_count,
        "source_confidence": max(0.0, min(1.0, source_confidence)),
        "stale_source_answer": bool(metadata.get("stale_source_answer")),
    }


def _build_answer_quality_summary(events) -> dict:
    rows = [_quality_event_metadata(event) for event in events]
    rows = [row for row in rows if row]
    total = len(rows)
    grounded = sum(1 for row in rows if row["outcome"] == "grounded" and row["citation_count"] > 0)
    no_context = sum(1 for row in rows if row["outcome"] == "no_context")
    low_confidence = sum(
        1
        for row in rows
        if row["outcome"] == "grounded" and row["citation_count"] > 0 and row["source_confidence"] < 0.35
    )
    stale_source_answers = sum(1 for row in rows if row.get("stale_source_answer"))
    citation_total = sum(row["citation_count"] for row in rows)
    confidence_total = sum(row["source_confidence"] for row in rows)

    by_collection: dict[str, dict] = {}
    for row in rows:
        bucket = by_collection.setdefault(
            row["collection"],
            {
                "collection": row["collection"],
                "total": 0,
                "grounded": 0,
                "no_context": 0,
                "citation_total": 0,
                "confidence_total": 0.0,
                "stale_source_answers": 0,
            },
        )
        bucket["total"] += 1
        bucket["citation_total"] += row["citation_count"]
        bucket["confidence_total"] += row["source_confidence"]
        if row["outcome"] == "grounded" and row["citation_count"] > 0:
            bucket["grounded"] += 1
        if row["outcome"] == "no_context":
            bucket["no_context"] += 1
        if row.get("stale_source_answer"):
            bucket["stale_source_answers"] += 1

    collection_rows = []
    for bucket in by_collection.values():
        total_bucket = bucket["total"]
        collection_rows.append(
            {
                "collection": bucket["collection"],
                "total": total_bucket,
                "grounded": bucket["grounded"],
                "no_context": bucket["no_context"],
                "grounded_rate": _percent(bucket["grounded"], total_bucket),
                "no_context_rate": _percent(bucket["no_context"], total_bucket),
                "average_citations": round(bucket["citation_total"] / total_bucket, 2) if total_bucket else 0,
                "average_source_confidence": round(bucket["confidence_total"] / total_bucket, 4) if total_bucket else 0,
                "stale_source_answers": bucket["stale_source_answers"],
                "stale_source_rate": _percent(bucket["stale_source_answers"], total_bucket),
            }
        )
    collection_rows.sort(key=lambda item: (item["grounded_rate"], item["total"]), reverse=True)

    return {
        "total_chat_events": total,
        "grounded_answers": grounded,
        "no_context_answers": no_context,
        "grounded_rate": _percent(grounded, total),
        "no_context_rate": _percent(no_context, total),
        "low_confidence_answers": low_confidence,
        "low_confidence_rate": _percent(low_confidence, total),
        "average_citations": round(citation_total / total, 2) if total else 0,
        "average_source_confidence": round(confidence_total / total, 4) if total else 0,
        "stale_source_answers": stale_source_answers,
        "stale_source_rate": _percent(stale_source_answers, total),
        "by_collection": collection_rows,
        "window": "last_5000_chat_events",
    }


def _feedback_event_metadata(event) -> dict:
    metadata = getattr(event, "metadata_json", {}) or {}
    if not isinstance(metadata, dict):
        return {}
    rating = str(metadata.get("rating") or "").strip()
    if rating not in {"helpful", "not_helpful", "needs_review"}:
        return {}
    collection = str(metadata.get("collection") or "unknown")
    return {
        "collection": collection,
        "rating": rating,
    }


def _build_feedback_summary(events) -> dict:
    rows = [_feedback_event_metadata(event) for event in events]
    rows = [row for row in rows if row]
    total = len(rows)
    helpful = sum(1 for row in rows if row["rating"] == "helpful")
    not_helpful = sum(1 for row in rows if row["rating"] == "not_helpful")
    needs_review = sum(1 for row in rows if row["rating"] == "needs_review")

    by_collection: dict[str, dict] = {}
    for row in rows:
        bucket = by_collection.setdefault(
            row["collection"],
            {"collection": row["collection"], "total": 0, "helpful": 0, "not_helpful": 0, "needs_review": 0},
        )
        bucket["total"] += 1
        bucket[row["rating"]] += 1

    collection_rows = []
    for bucket in by_collection.values():
        total_bucket = bucket["total"]
        collection_rows.append(
            {
                **bucket,
                "helpful_rate": _percent(bucket["helpful"], total_bucket),
                "review_rate": _percent(bucket["not_helpful"] + bucket["needs_review"], total_bucket),
            }
        )
    collection_rows.sort(key=lambda item: (item["review_rate"], item["total"]), reverse=True)

    return {
        "total_feedback": total,
        "helpful": helpful,
        "not_helpful": not_helpful,
        "needs_review": needs_review,
        "helpful_rate": _percent(helpful, total),
        "review_rate": _percent(not_helpful + needs_review, total),
        "by_collection": collection_rows,
        "window": "last_5000_feedback_events",
    }


def _safe_float(value) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _source_freshness_status(source: DocumentSource, now: datetime | None = None) -> str:
    if source.sync_status == "failed":
        return "failed"
    current = now or utc_now()
    basis = source.source_updated_at or source.last_synced_at
    if not basis:
        return "unknown"
    age_days = max(0, (current - basis).days)
    if age_days >= source.stale_after_days:
        return "stale"
    if age_days >= settings.source_aging_after_days:
        return "aging"
    return "fresh"


def _next_sync_at(now: datetime | None = None, interval_hours: int | None = None) -> datetime:
    current = now or utc_now()
    hours = interval_hours or settings.source_sync_interval_hours
    return current + timedelta(hours=hours)


def _upsert_document_source(
    db: Session,
    *,
    collection: str,
    document_name: str,
    connector: str,
    source_url: str = "",
    source_updated_at: datetime | None = None,
    sync_status: str = "synced",
    last_sync_error: str = "",
) -> DocumentSource:
    now = utc_now()
    source = (
        db.query(DocumentSource)
        .filter(DocumentSource.collection == collection, DocumentSource.document_name == document_name)
        .first()
    )
    if not isinstance(source, DocumentSource):
        source = None
    if not source:
        source = DocumentSource(collection=collection, document_name=document_name, created_at=now)
        db.add(source)
    source.connector = connector
    source.source_url = source_url or ""
    source.sync_status = sync_status
    source.last_synced_at = now if sync_status == "synced" else source.last_synced_at
    source.source_updated_at = source_updated_at or source.source_updated_at or (now if connector == "upload" else None)
    source.sync_interval_hours = settings.source_sync_interval_hours
    source.stale_after_days = settings.source_stale_after_days
    source.next_sync_at = _next_sync_at(now, source.sync_interval_hours) if source.source_url else None
    source.last_sync_error = last_sync_error
    source.updated_at = now
    source.freshness_status = _source_freshness_status(source, now)
    return source


def _source_payload(source: DocumentSource) -> dict:
    source.freshness_status = _source_freshness_status(source)
    return {
        "id": source.id,
        "collection": source.collection,
        "document_name": source.document_name,
        "source_url": source.source_url,
        "connector": source.connector,
        "sync_status": source.sync_status,
        "freshness_status": source.freshness_status,
        "last_synced_at": str(source.last_synced_at) if source.last_synced_at else None,
        "source_updated_at": str(source.source_updated_at) if source.source_updated_at else None,
        "next_sync_at": str(source.next_sync_at) if source.next_sync_at else None,
        "stale_after_days": source.stale_after_days,
        "sync_interval_hours": source.sync_interval_hours,
        "last_sync_error": source.last_sync_error,
        "created_at": str(source.created_at) if source.created_at else None,
        "updated_at": str(source.updated_at) if source.updated_at else None,
    }


def _source_summary(sources: list[DocumentSource]) -> dict:
    counts = {"fresh": 0, "aging": 0, "stale": 0, "failed": 0, "unknown": 0}
    due = 0
    now = utc_now()
    for source in sources:
        status = _source_freshness_status(source, now)
        source.freshness_status = status
        counts[status] = counts.get(status, 0) + 1
        if source.source_url and source.next_sync_at and source.next_sync_at <= now:
            due += 1
    return {"total_sources": len(sources), "due_for_sync": due, **counts}


def _answer_review_payload(row) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "collection": row.collection,
        "question": row.question,
        "answer_excerpt": row.answer_excerpt,
        "rating": row.rating,
        "reason": row.reason,
        "language": row.language,
        "citation_count": row.citation_count,
        "citations": getattr(row, "citations_json", None) or [],
        "source_confidence": row.source_confidence,
        "confidence_label": row.confidence_label,
        "answer_quality": row.answer_quality_json or {},
        "status": row.status,
        "reviewer_note": row.reviewer_note,
        "created_by": row.created_by,
        "resolved_by": row.resolved_by,
        "promoted_eval_case_id": getattr(row, "promoted_eval_case_id", None),
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
        "resolved_at": str(row.resolved_at) if row.resolved_at else None,
        "promoted_to_eval_at": str(row.promoted_to_eval_at) if getattr(row, "promoted_to_eval_at", None) else None,
    }


def _required_citations_from_review(review: AnswerReview) -> list[dict]:
    citations = getattr(review, "citations_json", None) or []
    required = []
    for citation in citations:
        if not isinstance(citation, dict) or not citation.get("document"):
            continue
        item = {"document": citation.get("document")}
        if citation.get("page") not in (None, ""):
            item["page"] = citation.get("page")
        if citation.get("chunk_id"):
            item["chunk_id"] = citation.get("chunk_id")
        required.append(item)
    return required


def _eval_case_id_for_review(review: AnswerReview) -> str:
    return f"review-{review.id}"


def _build_eval_case_from_review(review: AnswerReview, current_user: CurrentUser) -> EvaluationCase:
    case_id = _eval_case_id_for_review(review)
    return EvaluationCase(
        case_id=case_id,
        review_id=review.id,
        language=review.language or "en",
        collection=review.collection,
        question=review.question,
        expectation="answer",
        required_citations_json=_required_citations_from_review(review),
        notes_json={
            "source": "answer_review",
            "review_id": review.id,
            "rating": review.rating,
            "reason": review.reason,
            "answer_excerpt": review.answer_excerpt,
            "reviewer_note": review.reviewer_note,
            "source_confidence": review.source_confidence,
            "confidence_label": review.confidence_label,
        },
        status="active",
        created_by=current_user.username,
    )


def _eval_case_payload(row: EvaluationCase) -> dict:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "review_id": row.review_id,
        "language": row.language,
        "collection": row.collection,
        "question": row.question,
        "expectation": row.expectation,
        "required_citations": row.required_citations_json or [],
        "notes": row.notes_json or {},
        "status": row.status,
        "created_by": row.created_by,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def _golden_case_payload(row: EvaluationCase) -> dict:
    payload = {
        "id": row.case_id,
        "language": row.language,
        "collection": row.collection,
        "question": row.question,
        "expectation": row.expectation,
        "required_citations": row.required_citations_json or [],
    }
    notes = row.notes_json or {}
    if notes:
        payload["notes"] = notes
    return payload


def _prediction_for_eval_case(row: EvaluationCase, current_user: CurrentUser, db: Session) -> dict:
    language = row.language or "en"
    top_rows = _retrieve_context(row.question, row.collection, language, current_user, db)
    source_by_document = _source_freshness_by_document(db, row.collection, top_rows)
    citations = [_citation_from_retrieval_row(item, source_by_document) for item in top_rows]
    return {
        "case_id": row.case_id,
        "outcome": "grounded" if citations else "no_context",
        "citations": citations,
        "retriever": "live_retrieval",
    }


def _run_promoted_eval_cases(rows: list[EvaluationCase], current_user: CurrentUser, db: Session) -> dict:
    cases = [_golden_case_payload(row) for row in rows]
    predictions = [_prediction_for_eval_case(row, current_user, db) for row in rows]
    report = evaluate_retrieval(cases, predictions)
    report["predictions"] = predictions
    return report


def _eval_run_payload(row: EvaluationRun) -> dict:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "collection": row.collection,
        "status": row.status,
        "total_cases": row.total_cases,
        "passed_cases": row.passed_cases,
        "case_pass_rate": row.case_pass_rate,
        "citation_recall": row.citation_recall,
        "grounded_accuracy": row.grounded_accuracy,
        "no_answer_accuracy": row.no_answer_accuracy,
        "passed": row.passed,
        "report": row.report_json or {},
        "created_by": row.created_by,
        "started_at": str(row.started_at) if row.started_at else None,
        "completed_at": str(row.completed_at) if row.completed_at else None,
    }


def _eval_run_summary(rows: list[EvaluationRun]) -> dict:
    latest = rows[0] if rows else None
    trend_rows = list(reversed(rows[:10]))
    return {
        "total": len(rows),
        "latest": _eval_run_payload(latest) if latest else None,
        "passing_runs": sum(1 for row in rows if row.passed),
        "best_case_pass_rate": max((row.case_pass_rate for row in rows), default=0.0),
        "trend": [
            {
                "run_id": row.run_id,
                "case_pass_rate": row.case_pass_rate,
                "citation_recall": row.citation_recall,
                "passed": row.passed,
                "started_at": str(row.started_at) if row.started_at else None,
            }
            for row in trend_rows
        ],
    }


EVAL_SCHEDULE_SETTING_KEY = "eval_schedule"
DEMO_SEED_SESSION_ID = "demo-launch-seed"


def _count_model(db: Session, model, *filters) -> int:
    try:
        query = db.query(model)
        for condition in filters:
            query = query.filter(condition)
        return int(query.count() or 0)
    except (TypeError, ValueError, SQLAlchemyError, AttributeError):
        return 0


def _launch_status(status: str, title: str, detail: str, action: str, owner: str = "Admin") -> dict:
    return {"status": status, "title": title, "detail": detail, "action": action, "owner": owner}


def _launch_score(checks: list[dict]) -> int:
    if not checks:
        return 0
    weights = {"ok": 1.0, "warning": 0.5, "error": 0.0}
    return round((sum(weights.get(item.get("status"), 0.0) for item in checks) / len(checks)) * 100)


def _default_admin_password_active(db: Session) -> bool:
    try:
        row = db.query(UserAccount).filter(UserAccount.username == "admin", UserAccount.is_active.is_(True)).first()
        if isinstance(row, UserAccount) and row.password_hash:
            return verify_password("change-admin-password", row.password_hash)
    except (SQLAlchemyError, AttributeError, TypeError, ValueError):
        pass

    try:
        raw_users = json.loads(settings.auth_users_json)
    except json.JSONDecodeError:
        return False
    if not isinstance(raw_users, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("username") == "admin"
        and item.get("password") == "change-admin-password"
        for item in raw_users
    )


def _provider_ready() -> bool:
    if settings.data_sovereignty_mode:
        return True
    providers = {settings.llm_provider.lower(), settings.embedding_provider.lower()}
    if "openai" in providers and settings.openai_api_key:
        return True
    return bool(providers.intersection({"local", "turkunlp", "auto"}))


def _launch_readiness_payload(db: Session) -> dict:
    source_rows = []
    try:
        source_rows = db.query(DocumentSource).limit(5000).all()
    except (SQLAlchemyError, AttributeError, TypeError):
        source_rows = []
    source_summary = _source_summary(source_rows)
    metrics = {
        "users": _count_model(db, UserAccount),
        "sources": _count_model(db, DocumentSource),
        "chunks": _count_model(db, DocumentChunk),
        "open_reviews": _count_model(db, AnswerReview, AnswerReview.status == "open"),
        "active_eval_cases": _count_model(db, EvaluationCase, EvaluationCase.status == "active"),
        "eval_runs": _count_model(db, EvaluationRun),
    }
    default_password = _default_admin_password_active(db)
    jwt_rotated = settings.jwt_secret_key not in {"", "change-me-in-production", "replace-with-64-char-random-secret"}
    provider_ready = _provider_ready()
    demo_seeded = _count_model(db, EvaluationCase, EvaluationCase.case_id.like("seed-%")) > 0
    source_risk = (source_summary.get("stale", 0) or 0) + (source_summary.get("failed", 0) or 0)
    checks = [
        _launch_status(
            "warning" if default_password else "ok",
            "Admin password",
            "Default admin password is still accepted." if default_password else "Default admin password is not active.",
            "Rotate the admin password before external demos." if default_password else "No action needed.",
        ),
        _launch_status(
            "ok" if jwt_rotated else "error",
            "JWT secret",
            "A non-default JWT secret is configured." if jwt_rotated else "JWT secret is still a placeholder.",
            "Run ./run or set JWT_SECRET_KEY manually." if not jwt_rotated else "No action needed.",
        ),
        _launch_status(
            "ok" if provider_ready else "warning",
            "AI provider",
            "LLM and embedding provider settings look usable." if provider_ready else "No OpenAI key or local provider route is ready.",
            "Set OPENAI_API_KEY or configure local provider variables." if not provider_ready else "No action needed.",
        ),
        _launch_status(
            "ok" if demo_seeded else "warning",
            "Demo workspace",
            "Seeded demo docs and eval cases are available." if demo_seeded else "Demo data has not been loaded.",
            "Use Seed demo workspace in Launch Center." if not demo_seeded else "No action needed.",
        ),
        _launch_status(
            "ok" if metrics["active_eval_cases"] else "warning",
            "Eval coverage",
            f"{metrics['active_eval_cases']} active eval cases are available.",
            "Promote Review Center cases or seed demo evals." if not metrics["active_eval_cases"] else "Run evals after retrieval changes.",
        ),
        _launch_status(
            "ok" if source_risk == 0 else "warning",
            "Source freshness",
            f"{source_risk} stale or failed source records.",
            "Sync stale sources from Admin." if source_risk else "No action needed.",
        ),
    ]
    return {
        "score": _launch_score(checks),
        "checks": checks,
        "metrics": metrics,
        "source_freshness": source_summary,
        "generated_at": str(utc_now()),
    }


def _evals_dir() -> FilePath:
    return FilePath(__file__).resolve().parents[1] / "evals"


def _load_eval_fixture(name: str) -> dict:
    return json.loads((_evals_dir() / name).read_text(encoding="utf-8"))


def _seed_demo_workspace(db: Session, current_user: CurrentUser) -> dict:
    corpus = _load_eval_fixture("seed_corpus.json").get("chunks", [])
    cases = _load_eval_fixture("retrieval_golden.json").get("cases", [])
    now = utc_now()
    created = {"collections": 0, "chunks": 0, "sources": 0, "eval_cases": 0, "reviews": 0}

    collection_names = sorted(
        {str(item.get("collection") or "").strip() for item in [*corpus, *cases] if isinstance(item, dict) and item.get("collection")}
    )
    for name in collection_names:
        if not db.query(Collection).filter(Collection.name == name).first():
            db.add(Collection(name=name, description="Seeded demo collection"))
            created["collections"] += 1

    for index, item in enumerate(corpus):
        if not isinstance(item, dict):
            continue
        collection = str(item.get("collection") or "HR-docs")
        document = str(item.get("document") or "demo-document.txt")
        page = int(item.get("page") or 1)
        chunk_id = str(item.get("chunk_id") or item.get("id") or f"demo-{index}")
        existing = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.collection == collection,
                DocumentChunk.document_name == document,
                DocumentChunk.page == page,
                DocumentChunk.chunk_index == index,
            )
            .first()
        )
        if not existing:
            content = str(item.get("content") or "")
            title = str(item.get("title") or document)
            db.add(
                DocumentChunk(
                    collection=collection,
                    document_name=document,
                    page=page,
                    chunk_index=index,
                    content=content,
                    search_text=finnish_search_text(f"{title} {content}"),
                    metadata_json={"demo_seed": True, "chunk_id": chunk_id, "title": title},
                )
            )
            created["chunks"] += 1
        source = _upsert_document_source(
            db,
            collection=collection,
            document_name=document,
            connector="demo",
            source_url=f"demo://{collection}/{document}",
            source_updated_at=now,
        )
        if not getattr(source, "id", None):
            created["sources"] += 1

    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = f"seed-{item.get('id')}"
        if db.query(EvaluationCase).filter(EvaluationCase.case_id == case_id).first():
            continue
        db.add(
            EvaluationCase(
                case_id=case_id,
                review_id=None,
                language=item.get("language") or "en",
                collection=item.get("collection") or "HR-docs",
                question=item.get("question") or "",
                expectation=item.get("expectation") or "answer",
                required_citations_json=item.get("required_citations") or [],
                notes_json={"source": "demo_seed", "fixture_case_id": item.get("id")},
                status="active",
                created_by=current_user.username,
            )
        )
        created["eval_cases"] += 1

    existing_review = db.query(AnswerReview).filter(AnswerReview.session_id == DEMO_SEED_SESSION_ID).first()
    if not existing_review:
        db.add(
            AnswerReview(
                session_id=DEMO_SEED_SESSION_ID,
                collection="HR-docs",
                question="What is tomorrow's cafeteria menu?",
                answer_excerpt="I could not find relevant information in HR-docs.",
                rating="needs_review",
                reason="Demo review showing how weak answers become eval cases.",
                language="en",
                citation_count=0,
                citations_json=[],
                source_confidence=0.0,
                confidence_label="no_context",
                answer_quality_json={"outcome": "no_context", "demo_seed": True},
                status="open",
                created_by=current_user.username,
            )
        )
        created["reviews"] += 1

    return {"created": created, "total_created": sum(created.values())}


def _connector_catalog_payload() -> dict:
    connectors = [
        {
            "id": "confluence",
            "label": "Confluence",
            "status": "available",
            "coverage": "JSON page import, HTML body extraction, source ACL capture",
            "setup": "Use Admin connector import with a Confluence REST API URL and token.",
        },
        {
            "id": "sharepoint",
            "label": "SharePoint",
            "status": "available",
            "coverage": "Document JSON import, source ACL capture, freshness tracking",
            "setup": "Use Admin connector import with a SharePoint/Graph document URL and token.",
        },
        {
            "id": "generic-url",
            "label": "Generic URL",
            "status": "available",
            "coverage": "HTML, text, and JSON import with freshness metadata",
            "setup": "Allowlist domains with CONNECTOR_ALLOWED_DOMAINS for production.",
        },
        {
            "id": "google-drive",
            "label": "Google Drive",
            "status": "planned",
            "coverage": "OAuth app, Drive file picker, native Docs export, inherited ACLs",
            "setup": "Use the current generic URL import until native OAuth is configured.",
        },
        {
            "id": "jira",
            "label": "Jira",
            "status": "planned",
            "coverage": "Issue and project sync, comments, permissions, freshness webhooks",
            "setup": "Prioritize after M365/Drive because enterprise search value depends on tickets.",
        },
    ]
    return {
        "connectors": connectors,
        "available": sum(1 for item in connectors if item["status"] == "available"),
        "planned": sum(1 for item in connectors if item["status"] == "planned"),
    }


def _deploy_checklist_payload(db: Session) -> dict:
    jwt_rotated = settings.jwt_secret_key not in {"", "change-me-in-production", "replace-with-64-char-random-secret"}
    provider_ready = _provider_ready()
    eval_cases = _count_model(db, EvaluationCase, EvaluationCase.status == "active")
    items = [
        _launch_status("ok" if settings.auth_required else "error", "Auth required", "AUTH_REQUIRED is enabled.", "Keep enabled for demos and production."),
        _launch_status("ok" if jwt_rotated else "error", "JWT secret", "JWT secret is not a placeholder." if jwt_rotated else "JWT secret is still a placeholder.", "Set JWT_SECRET_KEY."),
        _launch_status("ok" if provider_ready else "warning", "Model provider", "Provider configuration is ready." if provider_ready else "Provider route is incomplete.", "Set OpenAI or local provider env vars."),
        _launch_status("ok" if settings.db_auth_enabled else "warning", "Database users", "DB-backed auth is enabled.", "Keep DB_AUTH_ENABLED=true."),
        _launch_status("ok" if settings.cors_origins else "warning", "CORS origins", f"CORS_ORIGINS={settings.cors_origins}", "Limit CORS to deployed frontend origins."),
        _launch_status("ok" if eval_cases else "warning", "Regression gate", f"{eval_cases} active eval cases.", "Seed demo cases or promote reviews."),
        _launch_status("ok" if settings.connector_allowed_domains else "warning", "Connector allowlist", "Connector domain allowlist is configured." if settings.connector_allowed_domains else "Connector domain allowlist is empty.", "Set CONNECTOR_ALLOWED_DOMAINS before production connector sync."),
    ]
    return {"score": _launch_score(items), "items": items, "generated_at": str(utc_now())}


def _default_eval_schedule() -> dict:
    return {
        "enabled": False,
        "interval_hours": 24,
        "collection": "",
        "alert_email": "",
        "next_run_at": None,
        "last_due_run_at": None,
        "last_status": "not_configured",
    }


def _get_launch_setting(db: Session, key: str) -> dict:
    try:
        row = db.query(LaunchSetting).filter(LaunchSetting.key == key).first()
    except (SQLAlchemyError, AttributeError, TypeError):
        return {}
    if not isinstance(row, LaunchSetting):
        return {}
    value = row.value_json or {}
    return value if isinstance(value, dict) else {}


def _save_launch_setting(db: Session, key: str, value: dict, current_user: CurrentUser) -> LaunchSetting:
    row = db.query(LaunchSetting).filter(LaunchSetting.key == key).first()
    if not isinstance(row, LaunchSetting):
        row = LaunchSetting(key=key, created_at=utc_now())
        db.add(row)
    row.value_json = value
    row.updated_by = current_user.username
    row.updated_at = utc_now()
    return row


def _eval_schedule_payload(db: Session) -> dict:
    return {**_default_eval_schedule(), **_get_launch_setting(db, EVAL_SCHEDULE_SETTING_KEY)}


def _parse_schedule_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _next_schedule_time(interval_hours: int, now: datetime | None = None) -> str:
    current = now or utc_now()
    return str(current + timedelta(hours=max(1, interval_hours)))


def _answer_review_summary(rows) -> dict:
    total = len(rows)
    open_rows = [row for row in rows if row.status == "open"]
    resolved_rows = [row for row in rows if row.status == "resolved"]
    dismissed_rows = [row for row in rows if row.status == "dismissed"]
    needs_review = [row for row in rows if row.rating in {"needs_review", "not_helpful"}]
    by_collection: dict[str, dict] = {}
    for row in rows:
        bucket = by_collection.setdefault(row.collection, {"collection": row.collection, "total": 0, "open": 0})
        bucket["total"] += 1
        if row.status == "open":
            bucket["open"] += 1
    collection_rows = sorted(by_collection.values(), key=lambda item: (item["open"], item["total"]), reverse=True)
    return {
        "total": total,
        "open": len(open_rows),
        "resolved": len(resolved_rows),
        "dismissed": len(dismissed_rows),
        "needs_review": len(needs_review),
        "resolution_rate": _percent(len(resolved_rows), total),
        "by_collection": collection_rows,
    }


def _replace_user_permissions(
    db: Session,
    *,
    username: str,
    collections: list[str],
    write_collections: list[str],
) -> None:
    db.query(CollectionPermission).filter(CollectionPermission.username == username).delete()
    normalized_collections = {c.strip() for c in collections if c and c.strip() and c.strip() != "*"}
    normalized_writes = {c.strip() for c in write_collections if c and c.strip() and c.strip() != "*"}
    for collection in sorted(normalized_collections | normalized_writes):
        db.add(
            CollectionPermission(
                username=username,
                collection=collection,
                can_read=True,
                can_write=collection in normalized_writes,
            )
        )


def _key_preview(prefix: str) -> str:
    if len(prefix) <= 8:
        return f"{prefix}****"
    return f"{prefix[:8]}****{prefix[-4:]}"


def _audit_log(
    db: Session,
    *,
    request: Request,
    current_user: CurrentUser,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    collection: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_username=current_user.username,
            actor_role=current_user.role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            collection=collection,
            request_id=getattr(request.state, "request_id", None),
            metadata_json=metadata or {},
        )
    )


CollectionName = Annotated[str, StringConstraints(min_length=2, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$")]
SessionId = Annotated[str, StringConstraints(max_length=64, pattern=r"^[A-Za-z0-9_-]*$")]
DocumentName = Annotated[str, StringConstraints(min_length=1, max_length=255)]
SourceAclPrincipal = Annotated[str, StringConstraints(min_length=1, max_length=255)]

class ChatRequest(BaseModel):
    question: Annotated[str, StringConstraints(max_length=4000)]
    collection: CollectionName = "HR-docs"
    session_id: SessionId = ""

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What is the annual leave policy?",
                "collection": "HR-docs",
                "session_id": "sess-finland-001",
            }
        }
    }


class ChatResponse(BaseModel):
    answer: str
    language: Literal["fi", "en", "sv"]
    citations: list[dict]
    session_id: str = ""
    answer_quality: dict = Field(default_factory=dict)


class ChatFeedbackRequest(BaseModel):
    session_id: SessionId = ""
    collection: CollectionName = "HR-docs"
    question: Annotated[str, StringConstraints(max_length=4000)] = ""
    answer_excerpt: Annotated[str, StringConstraints(max_length=1500)] = ""
    rating: Literal["helpful", "not_helpful", "needs_review"]
    reason: Annotated[str, StringConstraints(max_length=1000)] = ""
    language: Literal["fi", "en", "sv"] | None = None
    citation_count: int = Field(default=0, ge=0, le=50)
    citations: list[dict] = Field(default_factory=list, max_length=50)
    answer_quality: dict = Field(default_factory=dict)


class ReviewUpdateRequest(BaseModel):
    status: Literal["open", "resolved", "dismissed"]
    reviewer_note: Annotated[str, StringConstraints(max_length=2000)] = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-finland-backend"}


@app.get("/health/deep")
@limiter.limit(settings.default_rate_limit)
def deep_health(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    checks: dict[str, dict] = {}
    overall_status = "ok"
    http_status = 200

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except SQLAlchemyError as exc:
        checks["database"] = {"status": "error", "error": str(exc)}
        overall_status = "degraded"
        http_status = 503

    if settings.openai_api_key:
        try:
            client = OpenAI(api_key=settings.openai_api_key, timeout=settings.health_openai_timeout_seconds)
            models = client.models.list()
            model_id = None
            for model in models.data[:1]:
                model_id = model.id
            checks["openai"] = {"status": "ok", "model_probe": model_id}
        except (OpenAIError, RuntimeError, ValueError) as exc:
            checks["openai"] = {"status": "error", "error": str(exc)}
            overall_status = "degraded"
            http_status = 503
    else:
        checks["openai"] = {"status": "skipped", "reason": "OPENAI_API_KEY not configured"}

    payload = {
        "status": overall_status,
        "checks": checks,
        "request_id": getattr(request.state, "request_id", None),
    }
    if http_status != 200:
        return JSONResponse(status_code=http_status, content=payload)
    return payload


@app.get("/metrics")
@limiter.limit(settings.default_rate_limit)
def metrics(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
):
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/ai/providers")
@limiter.limit(settings.default_rate_limit)
def ai_provider_status(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
):
    return {
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "data_sovereignty_mode": settings.data_sovereignty_mode,
        "local_llm_base_url": settings.local_llm_base_url,
        "local_llm_model_default": settings.local_llm_model_default,
        "local_llm_model_fi": settings.local_llm_model_fi,
        "local_embedding_base_url": settings.local_embedding_base_url,
        "local_embedding_model": settings.local_embedding_model,
        "turkunlp_embedding_configured": bool(settings.turkunlp_embedding_url),
    }


@app.post("/auth/token", response_model=TokenResponse)
@limiter.limit(settings.auth_rate_limit)
def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    user = authenticate_user(form_data.username, form_data.password, db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token, ttl = create_access_token(user)
    db.commit()
    return TokenResponse(access_token=access_token, expires_in=ttl)


@app.get("/auth/me")
def auth_me(current_user: Annotated[CurrentUser, Depends(get_current_user)]):
    return {
        "username": current_user.username,
        "role": current_user.role,
        "collections": sorted(current_user.collections),
        "permissions": current_user.collection_permissions,
        "source_groups": sorted(current_user.source_groups),
        "auth_provider": current_user.auth_provider,
        "api_version": settings.api_version_prefix.strip("/") or "v1",
    }


class CollectionCreate(BaseModel):
    name: CollectionName
    description: Annotated[str, StringConstraints(max_length=1000)] = ""

    model_config = {
        "json_schema_extra": {
            "example": {"name": "Finance-docs", "description": "Quarterly and annual finance policies"}
        }
    }


class UserCreate(BaseModel):
    username: Annotated[str, StringConstraints(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")]
    password: Annotated[str, StringConstraints(min_length=10, max_length=128)]
    role: Literal["admin", "editor", "viewer"] = "viewer"
    collections: list[CollectionName] = []
    write_collections: list[CollectionName] = []
    monthly_quota: int = Field(default=settings.default_user_quota_per_month, ge=100, le=5_000_000)
    is_active: bool = True


class UserUpdate(BaseModel):
    password: Annotated[str | None, StringConstraints(min_length=10, max_length=128)] = None
    role: Literal["admin", "editor", "viewer"] | None = None
    collections: list[CollectionName] | None = None
    write_collections: list[CollectionName] | None = None
    monthly_quota: int | None = None
    is_active: bool | None = None


class ApiKeyCreate(BaseModel):
    owner_username: Annotated[str, StringConstraints(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")]
    name: Annotated[str, StringConstraints(min_length=3, max_length=100)]
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
    monthly_quota: int = Field(default=settings.default_api_key_quota_per_month, ge=100, le=5_000_000)


class SourceAcl(BaseModel):
    mode: Literal["public", "restricted"] = "restricted"
    allowed_users: list[SourceAclPrincipal] = Field(default_factory=list, max_length=500)
    allowed_groups: list[SourceAclPrincipal] = Field(default_factory=list, max_length=500)


class ConnectorImportRequest(BaseModel):
    connector: Literal["confluence", "sharepoint", "generic"] = "generic"
    collection: CollectionName = "HR-docs"
    source_urls: list[Annotated[str, StringConstraints(min_length=10, max_length=2000)]]
    access_token: Annotated[str | None, StringConstraints(max_length=4096)] = None
    default_acl: SourceAcl | None = None
    source_acls: dict[Annotated[str, StringConstraints(min_length=10, max_length=2000)], SourceAcl] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "connector": "confluence",
                "collection": "Technical-docs",
                "source_urls": [
                    "https://wiki.example.com/rest/api/content/12345?expand=body.storage,title"
                ],
                "source_acls": {
                    "https://wiki.example.com/rest/api/content/12345?expand=body.storage,title": {
                        "allowed_users": ["legal.owner@example.com"],
                        "allowed_groups": ["legal-team"],
                    }
                },
            }
        }
    }


def _serialize_user(db: Session, user_row: UserAccount) -> dict:
    permission_rows = (
        db.query(CollectionPermission)
        .filter(CollectionPermission.username == user_row.username)
        .order_by(CollectionPermission.collection)
        .all()
    )
    permissions = [
        {
            "collection": row.collection,
            "can_read": bool(row.can_read),
            "can_write": bool(row.can_write),
        }
        for row in permission_rows
    ]
    return {
        "username": user_row.username,
        "role": user_row.role,
        "auth_provider": user_row.auth_provider,
        "is_active": bool(user_row.is_active),
        "monthly_quota": user_row.monthly_quota,
        "used_this_month": user_row.used_this_month,
        "quota_reset_at": str(user_row.quota_reset_at) if user_row.quota_reset_at else None,
        "permissions": permissions,
        "created_at": str(user_row.created_at) if user_row.created_at else None,
        "last_login_at": str(user_row.last_login_at) if user_row.last_login_at else None,
    }


@app.get("/admin/users")
@limiter.limit(settings.default_rate_limit)
def list_users(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    rows = db.query(UserAccount).order_by(UserAccount.username).all()
    return {"users": [_serialize_user(db, row) for row in rows]}


@app.post("/admin/users")
@limiter.limit(settings.default_rate_limit)
def create_user(
    request: Request,
    payload: UserCreate,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    existing = db.query(UserAccount).filter(UserAccount.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"User '{payload.username}' already exists")

    if payload.role != "admin" and not payload.collections and not payload.write_collections:
        raise HTTPException(status_code=400, detail="Non-admin users must have at least one collection permission")

    user_row = UserAccount(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        auth_provider="local",
        is_active=payload.is_active,
        monthly_quota=payload.monthly_quota,
        quota_reset_at=month_window_start(),
    )
    db.add(user_row)
    if payload.role != "admin":
        _replace_user_permissions(
            db,
            username=payload.username,
            collections=payload.collections,
            write_collections=payload.write_collections,
        )
    else:
        db.query(CollectionPermission).filter(CollectionPermission.username == payload.username).delete()

    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="user.create",
        resource_type="user",
        resource_id=payload.username,
        metadata={"role": payload.role, "collections": payload.collections, "write_collections": payload.write_collections},
    )
    db.commit()
    return {"user": _serialize_user(db, user_row)}


@app.patch("/admin/users/{username}")
@limiter.limit(settings.default_rate_limit)
def update_user(
    request: Request,
    username: Annotated[str, Path(..., description="Username")],
    payload: UserUpdate,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    user_row = db.query(UserAccount).filter(UserAccount.username == username).first()
    if not user_row:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    if payload.password:
        user_row.password_hash = hash_password(payload.password)
    if payload.role:
        user_row.role = payload.role
    if payload.monthly_quota is not None:
        if payload.monthly_quota < 100 or payload.monthly_quota > 5_000_000:
            raise HTTPException(status_code=400, detail="monthly_quota must be between 100 and 5000000")
        user_row.monthly_quota = payload.monthly_quota
    if payload.is_active is not None:
        user_row.is_active = payload.is_active

    if payload.role == "admin" or user_row.role == "admin":
        db.query(CollectionPermission).filter(CollectionPermission.username == username).delete()
    elif payload.collections is not None or payload.write_collections is not None:
        current_perms = (
            db.query(CollectionPermission)
            .filter(CollectionPermission.username == username)
            .order_by(CollectionPermission.collection)
            .all()
        )
        current_collections = [row.collection for row in current_perms if row.can_read or row.can_write]
        current_write_collections = [row.collection for row in current_perms if row.can_write]
        _replace_user_permissions(
            db,
            username=username,
            collections=payload.collections if payload.collections is not None else current_collections,
            write_collections=payload.write_collections if payload.write_collections is not None else current_write_collections,
        )

    if user_row.role != "admin":
        perm_count = db.query(sa_func.count(CollectionPermission.id)).filter(CollectionPermission.username == username).scalar()
        if not perm_count:
            raise HTTPException(status_code=400, detail="Non-admin users must have at least one collection permission")

    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="user.update",
        resource_type="user",
        resource_id=username,
        metadata={
            "role": payload.role,
            "is_active": payload.is_active,
            "monthly_quota": payload.monthly_quota,
            "collections_updated": payload.collections is not None or payload.write_collections is not None,
        },
    )
    db.commit()
    return {"user": _serialize_user(db, user_row)}


@app.delete("/admin/users/{username}")
@limiter.limit(settings.default_rate_limit)
def disable_user(
    request: Request,
    username: Annotated[str, Path(..., description="Username")],
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot deactivate the currently authenticated admin user")

    user_row = db.query(UserAccount).filter(UserAccount.username == username).first()
    if not user_row:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    user_row.is_active = False
    db.query(ApiKey).filter(ApiKey.owner_username == username).update({"is_active": False})
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="user.deactivate",
        resource_type="user",
        resource_id=username,
    )
    db.commit()
    return {"disabled": username}


@app.get("/admin/api-keys")
@limiter.limit(settings.default_rate_limit)
def list_api_keys(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    rows = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
    return {
        "api_keys": [
            {
                "id": row.id,
                "owner_username": row.owner_username,
                "name": row.name,
                "key_preview": _key_preview(row.key_prefix),
                "is_active": bool(row.is_active),
                "monthly_quota": row.monthly_quota,
                "used_this_month": row.used_this_month,
                "quota_reset_at": str(row.quota_reset_at) if row.quota_reset_at else None,
                "last_used_at": str(row.last_used_at) if row.last_used_at else None,
                "expires_at": str(row.expires_at) if row.expires_at else None,
                "created_at": str(row.created_at) if row.created_at else None,
            }
            for row in rows
        ]
    }


@app.post("/admin/api-keys")
@limiter.limit(settings.default_rate_limit)
def create_api_key(
    request: Request,
    payload: ApiKeyCreate,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    user_row = (
        db.query(UserAccount)
        .filter(UserAccount.username == payload.owner_username, UserAccount.is_active.is_(True))
        .first()
    )
    if not user_row:
        raise HTTPException(status_code=404, detail=f"Active user '{payload.owner_username}' not found")

    raw_key = f"{settings.api_key_prefix}{secrets.token_urlsafe(32)}"
    now = utc_now()
    expires_at = None
    if payload.expires_in_days:
        expires_at = now + timedelta(days=payload.expires_in_days)
    api_key = ApiKey(
        owner_username=payload.owner_username,
        name=payload.name,
        key_prefix=raw_key[:16],
        key_hash=hash_api_key(raw_key),
        monthly_quota=payload.monthly_quota,
        quota_reset_at=month_window_start(),
        expires_at=expires_at,
    )
    db.add(api_key)
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="apikey.create",
        resource_type="api_key",
        resource_id=payload.name,
        metadata={"owner_username": payload.owner_username, "monthly_quota": payload.monthly_quota},
    )
    db.commit()
    db.refresh(api_key)
    return {
        "id": api_key.id,
        "owner_username": api_key.owner_username,
        "name": api_key.name,
        "api_key": raw_key,
        "expires_at": str(api_key.expires_at) if api_key.expires_at else None,
        "monthly_quota": api_key.monthly_quota,
    }


@app.delete("/admin/api-keys/{key_id}")
@limiter.limit(settings.default_rate_limit)
def revoke_api_key(
    request: Request,
    key_id: Annotated[int, Path(..., ge=1)],
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    key_row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key_row:
        raise HTTPException(status_code=404, detail=f"API key '{key_id}' not found")
    key_row.is_active = False
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="apikey.revoke",
        resource_type="api_key",
        resource_id=str(key_id),
        metadata={"owner_username": key_row.owner_username},
    )
    db.commit()
    return {"revoked": key_id}


@app.get("/admin/usage")
@limiter.limit(settings.default_rate_limit)
def usage_dashboard(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    users = db.query(UserAccount).order_by(UserAccount.username).all()
    api_keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
    events = (
        db.query(UsageEvent.event_type, sa_func.count(UsageEvent.id).label("count"), sa_func.sum(UsageEvent.units).label("units"))
        .group_by(UsageEvent.event_type)
        .order_by(sa_func.count(UsageEvent.id).desc())
        .all()
    )
    return {
        "users": [
            {
                "username": user.username,
                "used_this_month": user.used_this_month,
                "monthly_quota": user.monthly_quota,
                "is_active": bool(user.is_active),
                "quota_reset_at": str(user.quota_reset_at) if user.quota_reset_at else None,
            }
            for user in users
        ],
        "api_keys": [
            {
                "id": key.id,
                "owner_username": key.owner_username,
                "name": key.name,
                "is_active": bool(key.is_active),
                "used_this_month": key.used_this_month,
                "monthly_quota": key.monthly_quota,
                "quota_reset_at": str(key.quota_reset_at) if key.quota_reset_at else None,
            }
            for key in api_keys
        ],
        "events": [{"event_type": row.event_type, "count": row.count, "units": row.units or 0} for row in events],
    }


@app.post("/admin/connectors/import")
@limiter.limit(settings.upload_rate_limit)
def import_from_connectors(
    request: Request,
    payload: ConnectorImportRequest,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    if not payload.source_urls:
        raise HTTPException(status_code=400, detail="At least one source URL is required")
    if len(payload.source_urls) > settings.connector_max_sources_per_import:
        raise HTTPException(
            status_code=400,
            detail=f"Connector import limit exceeded ({settings.connector_max_sources_per_import} sources max)",
        )

    imported: list[dict] = []
    failed: list[dict] = []

    for source_url in payload.source_urls:
        _consume_user_quota(db, current_user, units=1)
        _validate_connector_source_domain(source_url)

        job: IngestionJob | None = None
        try:
            connector_doc = fetch_connector_document(
                payload.connector,
                source_url,
                access_token=payload.access_token,
                timeout_seconds=settings.connector_fetch_timeout_seconds,
            )
            text = connector_doc.content.strip()
            if not text:
                raise ValueError("Connector source returned empty text")

            job = IngestionJob(document_name=connector_doc.title, collection=payload.collection, status="processing")
            db.add(job)
            db.commit()
            db.refresh(job)

            chunks = chunk_pages([(1, text)])
            if not chunks:
                raise ValueError("Connector source produced no chunks")

            source_acl = _source_acl_for_import(payload, source_url, connector_doc.metadata)
            source_acl_summary = _source_acl_summary(source_acl)
            language_hint = _detect_language(text[:1500])
            embeddings = _build_embeddings(language_hint)
            vectors = embeddings.embed_documents([chunk["content"] for chunk in chunks])

            for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                db.add(
                    DocumentChunk(
                        collection=payload.collection,
                        document_name=connector_doc.title,
                        page=chunk["page"],
                        chunk_index=idx,
                        content=chunk["content"],
                        metadata_json={
                            **connector_doc.metadata,
                            "source_url": source_url,
                            "connector": payload.connector,
                            "source_acl": source_acl,
                        },
                        search_text=finnish_search_text(chunk["content"]),
                        embedding=vec,
                    )
                )
            document_source = _upsert_document_source(
                db,
                collection=payload.collection,
                document_name=connector_doc.title,
                connector=payload.connector,
                source_url=source_url,
                source_updated_at=_parse_http_datetime(connector_doc.metadata.get("http_last_modified")),
            )

            job.status = "completed"
            job.chunks_created = len(chunks)
            _audit_log(
                db,
                request=request,
                current_user=current_user,
                action="connector.import.completed",
                resource_type="document",
                resource_id=connector_doc.title,
                collection=payload.collection,
                metadata={
                    "connector": payload.connector,
                    "source_url": source_url,
                    "freshness_status": document_source.freshness_status,
                    "chunks_created": len(chunks),
                    **source_acl_summary,
                },
            )
            _track_usage(
                db,
                current_user=current_user,
                event_type="connector.import",
                metadata={
                    "connector": payload.connector,
                    "source_url": source_url,
                    "freshness_status": document_source.freshness_status,
                    "chunks_created": len(chunks),
                    **source_acl_summary,
                },
            )
            db.commit()
            imported.append(
                {
                    "source_url": source_url,
                    "document_name": connector_doc.title,
                    "source_id": document_source.id,
                    "freshness_status": document_source.freshness_status,
                    "chunks_created": len(chunks),
                    "job_id": job.id,
                    **source_acl_summary,
                }
            )
        except (httpx.HTTPError, SQLAlchemyError, RuntimeError, TypeError, ValueError) as exc:
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
                _audit_log(
                    db,
                    request=request,
                    current_user=current_user,
                    action="connector.import.failed",
                    resource_type="document",
                    resource_id=job.document_name,
                    collection=payload.collection,
                    metadata={"connector": payload.connector, "source_url": source_url, "error": str(exc)},
                )
                db.commit()
            else:
                db.rollback()
                existing_source = (
                    db.query(DocumentSource)
                    .filter(DocumentSource.collection == payload.collection, DocumentSource.source_url == source_url)
                    .first()
                )
                if existing_source:
                    existing_source.sync_status = "failed"
                    existing_source.freshness_status = "failed"
                    existing_source.last_sync_error = str(exc)
                    existing_source.updated_at = utc_now()
                    db.commit()
            failed.append({"source_url": source_url, "error": str(exc)})

    return {
        "connector": payload.connector,
        "collection": payload.collection,
        "imported": imported,
        "failed": failed,
    }


def _sync_document_source_record(
    *,
    db: Session,
    request: Request,
    current_user: CurrentUser,
    source: DocumentSource,
) -> dict:
    if not source.source_url or source.connector == "upload":
        raise HTTPException(status_code=400, detail="Only connector-backed sources can be synced")

    _validate_connector_source_domain(source.source_url)
    _consume_user_quota(db, current_user, units=1)
    source.sync_status = "syncing"
    source.updated_at = utc_now()
    db.flush()

    job: IngestionJob | None = None
    try:
        connector_doc = fetch_connector_document(
            source.connector,
            source.source_url,
            timeout_seconds=settings.connector_fetch_timeout_seconds,
        )
        text = connector_doc.content.strip()
        if not text:
            raise ValueError("Connector source returned empty text")

        previous_chunk = (
            db.query(DocumentChunk.metadata_json)
            .filter(DocumentChunk.collection == source.collection, DocumentChunk.document_name == source.document_name)
            .first()
        )
        previous_metadata = {}
        if previous_chunk is not None:
            previous_metadata = getattr(previous_chunk, "metadata_json", None)
            if previous_metadata is None:
                try:
                    previous_metadata = previous_chunk[0]
                except (TypeError, IndexError, KeyError):
                    previous_metadata = {}
            previous_metadata = previous_metadata or {}
        source_acl = _normalize_source_acl(
            connector_doc.metadata.get("source_acl") if isinstance(connector_doc.metadata, dict) else None
        )
        if source_acl["mode"] == "public" and isinstance(previous_metadata, dict):
            source_acl = _normalize_source_acl(previous_metadata.get("source_acl"))

        chunks = chunk_pages([(1, text)])
        if not chunks:
            raise ValueError("Connector source produced no chunks")

        language_hint = _detect_language(text[:1500])
        embeddings = _build_embeddings(language_hint)
        vectors = embeddings.embed_documents([chunk["content"] for chunk in chunks])

        job = IngestionJob(document_name=source.document_name, collection=source.collection, status="processing")
        db.add(job)
        db.flush()
        db.query(DocumentChunk).filter(
            DocumentChunk.collection == source.collection,
            DocumentChunk.document_name == source.document_name,
        ).delete()

        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            db.add(
                DocumentChunk(
                    collection=source.collection,
                    document_name=source.document_name,
                    page=chunk["page"],
                    chunk_index=idx,
                    content=chunk["content"],
                    metadata_json={
                        **connector_doc.metadata,
                        "source_url": source.source_url,
                        "connector": source.connector,
                        "source_acl": source_acl,
                    },
                    search_text=finnish_search_text(chunk["content"]),
                    embedding=vec,
                )
            )

        source.source_updated_at = _parse_http_datetime(connector_doc.metadata.get("http_last_modified")) or source.source_updated_at
        source.sync_status = "synced"
        source.last_synced_at = utc_now()
        source.next_sync_at = _next_sync_at(source.last_synced_at, source.sync_interval_hours)
        source.last_sync_error = ""
        source.updated_at = source.last_synced_at
        source.freshness_status = _source_freshness_status(source, source.last_synced_at)
        job.status = "completed"
        job.chunks_created = len(chunks)
        _audit_log(
            db,
            request=request,
            current_user=current_user,
            action="source.sync.completed",
            resource_type="document_source",
            resource_id=str(source.id),
            collection=source.collection,
            metadata={"document_name": source.document_name, "source_url": source.source_url, "chunks_created": len(chunks)},
        )
        _track_usage(
            db,
            current_user=current_user,
            event_type="source.sync",
            metadata={"collection": source.collection, "document_name": source.document_name, "source_url": source.source_url, "chunks_created": len(chunks)},
        )
        db.commit()
        return {"source": _source_payload(source), "job_id": job.id, "chunks_created": len(chunks)}
    except (httpx.HTTPError, SQLAlchemyError, RuntimeError, TypeError, ValueError) as exc:
        if job is not None:
            job.status = "failed"
            job.error = str(exc)
        source.sync_status = "failed"
        source.freshness_status = "failed"
        source.last_sync_error = str(exc)
        source.updated_at = utc_now()
        _audit_log(
            db,
            request=request,
            current_user=current_user,
            action="source.sync.failed",
            resource_type="document_source",
            resource_id=str(source.id),
            collection=source.collection,
            metadata={"document_name": source.document_name, "source_url": source.source_url, "error": str(exc)},
        )
        db.commit()
        raise HTTPException(status_code=400, detail=f"Source sync failed: {exc}") from exc


@app.get("/admin/sources")
@limiter.limit(settings.default_rate_limit)
def list_sources(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
    collection: str = Query("", max_length=100),
    freshness: Literal["fresh", "aging", "stale", "failed", "unknown", "all"] = "all",
    limit: int = Query(100, ge=1, le=500),
):
    query = db.query(DocumentSource)
    if collection:
        query = query.filter(DocumentSource.collection == collection)
    rows = query.order_by(DocumentSource.updated_at.desc()).limit(limit).all()
    for row in rows:
        row.freshness_status = _source_freshness_status(row)
    db.commit()
    filtered_rows = rows if freshness == "all" else [row for row in rows if row.freshness_status == freshness]
    return {
        "sources": [_source_payload(row) for row in filtered_rows],
        "summary": _source_summary(rows),
    }


@app.post("/admin/sources/sync-due")
@limiter.limit(settings.upload_rate_limit)
def sync_due_sources(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
):
    now = utc_now()
    rows = (
        db.query(DocumentSource)
        .filter(DocumentSource.source_url != "", DocumentSource.next_sync_at.isnot(None), DocumentSource.next_sync_at <= now)
        .order_by(DocumentSource.next_sync_at.asc())
        .limit(limit)
        .all()
    )
    synced: list[dict] = []
    failed: list[dict] = []
    for source in rows:
        try:
            synced.append(_sync_document_source_record(db=db, request=request, current_user=current_user, source=source))
        except HTTPException as exc:
            failed.append({"source_id": source.id, "document_name": source.document_name, "error": exc.detail})
    return {"attempted": len(rows), "synced": synced, "failed": failed}


@app.post("/admin/sources/{source_id}/sync")
@limiter.limit(settings.upload_rate_limit)
def sync_source(
    request: Request,
    source_id: Annotated[int, Path(..., ge=1)],
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    source = db.query(DocumentSource).filter(DocumentSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _sync_document_source_record(db=db, request=request, current_user=current_user, source=source)


@app.get("/admin/collections")
@limiter.limit(settings.default_rate_limit)
def collections(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    rows = db.query(Collection).order_by(Collection.name).all()
    if not current_user.is_admin and "*" not in current_user.collections:
        rows = [r for r in rows if r.name in current_user.collections]
    return {
        "collections": [r.name for r in rows],
        "details": [
            {"name": r.name, "description": r.description, "created_at": str(r.created_at) if r.created_at else None}
            for r in rows
        ],
    }


@app.post("/admin/collections")
@limiter.limit(settings.default_rate_limit)
def create_collection(
    request: Request,
    payload: CollectionCreate,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    existing = db.query(Collection).filter(Collection.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Collection '{name}' already exists")
    coll = Collection(name=name, description=payload.description)
    db.add(coll)
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="collection.create",
        resource_type="collection",
        resource_id=name,
        collection=name,
        metadata={"description": payload.description},
    )
    db.commit()
    logger.info("Collection created: %s", name)
    return {"name": name, "description": payload.description}


@app.delete("/admin/collections/{name}")
@limiter.limit(settings.default_rate_limit)
def delete_collection(
    request: Request,
    name: Annotated[CollectionName, Path(..., description="Collection name")],
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    coll = db.query(Collection).filter(Collection.name == name).first()
    if not coll:
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")
    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.collection == name).delete()
    db.query(IngestionJob).filter(IngestionJob.collection == name).delete()
    db.delete(coll)
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="collection.delete",
        resource_type="collection",
        resource_id=name,
        collection=name,
        metadata={"chunks_removed": chunk_count},
    )
    db.commit()
    logger.info("Collection deleted: %s (%d chunks removed)", name, chunk_count)
    return {"deleted": name, "chunks_removed": chunk_count}


@app.get("/admin/jobs")
@limiter.limit(settings.default_rate_limit)
def jobs(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    rows = db.query(IngestionJob).order_by(IngestionJob.id.desc()).limit(30).all()
    return {
        "jobs": [
            {
                "id": r.id,
                "document_name": r.document_name,
                "collection": r.collection,
                "status": r.status,
                "chunks_created": r.chunks_created,
                "error": r.error,
            }
            for r in rows
        ]
    }




@app.get("/admin/documents")
@limiter.limit(settings.default_rate_limit)
def list_documents(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    collection: Annotated[CollectionName, Query()] = "HR-docs",
    db: Session = Depends(get_db),
):
    ensure_collection_access(current_user, collection)
    rows = (
        db.query(
            DocumentChunk.document_name,
            sa_func.count(DocumentChunk.id).label("chunk_count"),
            sa_func.max(DocumentChunk.page).label("max_page"),
            sa_func.min(DocumentChunk.created_at).label("created_at"),
        )
        .filter(DocumentChunk.collection == collection)
        .group_by(DocumentChunk.document_name)
        .order_by(sa_func.min(DocumentChunk.created_at).desc())
        .all()
    )
    document_names = [r.document_name for r in rows]
    source_rows = []
    if document_names:
        source_rows = (
            db.query(DocumentSource)
            .filter(DocumentSource.collection == collection, DocumentSource.document_name.in_(document_names))
            .all()
        )
    source_by_document = {row.document_name: _source_payload(row) for row in source_rows}
    return {
        "documents": [
            {
                "document_name": r.document_name,
                "chunk_count": r.chunk_count,
                "pages": r.max_page,
                "created_at": str(r.created_at) if r.created_at else None,
                "source": source_by_document.get(r.document_name),
            }
            for r in rows
        ]
    }


@app.delete("/admin/documents/{document_name}")
@limiter.limit(settings.default_rate_limit)
def delete_document(
    request: Request,
    document_name: Annotated[DocumentName, Path(..., description="Document file name")],
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    collection: Annotated[CollectionName, Query()] = "HR-docs",
    db: Session = Depends(get_db),
):
    count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.collection == collection, DocumentChunk.document_name == document_name)
        .delete()
    )
    db.query(IngestionJob).filter(
        IngestionJob.collection == collection, IngestionJob.document_name == document_name
    ).delete()
    db.query(DocumentSource).filter(
        DocumentSource.collection == collection, DocumentSource.document_name == document_name
    ).delete()
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="document.delete",
        resource_type="document",
        resource_id=document_name,
        collection=collection,
        metadata={"chunks_removed": count},
    )
    db.commit()
    logger.info("Deleted document: %s from %s (%d chunks)", document_name, collection, count)
    return {"deleted": document_name, "chunks_removed": count}


@app.get("/admin/documents/{document_name}/chunks")
@limiter.limit(settings.default_rate_limit)
def document_chunks(
    request: Request,
    document_name: Annotated[DocumentName, Path(..., description="Document file name")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    collection: Annotated[CollectionName, Query()] = "HR-docs",
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    db: Session = Depends(get_db),
):
    ensure_collection_access(current_user, collection)
    per_page = 20
    offset = (page - 1) * per_page
    total = (
        db.query(sa_func.count(DocumentChunk.id))
        .filter(DocumentChunk.collection == collection, DocumentChunk.document_name == document_name)
        .scalar()
    )
    rows = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.collection == collection, DocumentChunk.document_name == document_name)
        .order_by(DocumentChunk.page, DocumentChunk.chunk_index)
        .offset(offset)
        .limit(per_page)
        .all()
    )
    return {
        "document_name": document_name,
        "collection": collection,
        "total_chunks": total,
        "page": page,
        "per_page": per_page,
        "chunks": [
            {
                "id": r.id,
                "page": r.page,
                "chunk_index": r.chunk_index,
                "content": r.content[:300],
                "content_length": len(r.content),
            }
            for r in rows
        ],
    }


@app.get("/admin/stats")
@limiter.limit(settings.default_rate_limit)
def admin_stats(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    total_docs = db.query(sa_func.count(sa_func.distinct(DocumentChunk.document_name))).scalar()
    total_chunks = db.query(sa_func.count(DocumentChunk.id)).scalar()
    collection_stats = (
        db.query(
            DocumentChunk.collection,
            sa_func.count(sa_func.distinct(DocumentChunk.document_name)).label("documents"),
            sa_func.count(DocumentChunk.id).label("chunks"),
        )
        .group_by(DocumentChunk.collection)
        .all()
    )
    source_rows = db.query(DocumentSource).limit(5000).all()
    return {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "source_freshness": _source_summary(source_rows),
        "collections": [
            {"name": r.collection, "documents": r.documents, "chunks": r.chunks}
            for r in collection_stats
        ],
    }


@app.get("/admin/analytics")
@limiter.limit(settings.default_rate_limit)
def analytics(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    total_messages = db.query(sa_func.count(ChatMessage.id)).scalar()
    total_sessions = db.query(sa_func.count(sa_func.distinct(ChatMessage.session_id))).scalar()
    user_messages = db.query(sa_func.count(ChatMessage.id)).filter(ChatMessage.role == "user").scalar()

    lang_breakdown = (
        db.query(ChatMessage.language, sa_func.count(ChatMessage.id).label("count"))
        .filter(ChatMessage.role == "user")
        .group_by(ChatMessage.language)
        .all()
    )

    collection_usage = (
        db.query(ChatMessage.collection, sa_func.count(ChatMessage.id).label("queries"))
        .filter(ChatMessage.role == "user")
        .group_by(ChatMessage.collection)
        .order_by(sa_func.count(ChatMessage.id).desc())
        .all()
    )

    recent_queries = (
        db.query(ChatMessage.content, ChatMessage.language, ChatMessage.collection, ChatMessage.created_at)
        .filter(ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
        .all()
    )

    total_docs = db.query(sa_func.count(sa_func.distinct(DocumentChunk.document_name))).scalar()
    total_chunks = db.query(sa_func.count(DocumentChunk.id)).scalar()
    quality_events = (
        db.query(UsageEvent.metadata_json)
        .filter(UsageEvent.event_type.in_(["chat.query", "chat.stream.query"]))
        .order_by(UsageEvent.created_at.desc())
        .limit(5000)
        .all()
    )
    answer_quality = _build_answer_quality_summary(quality_events)
    feedback_events = (
        db.query(UsageEvent.metadata_json)
        .filter(UsageEvent.event_type == "chat.feedback")
        .order_by(UsageEvent.created_at.desc())
        .limit(5000)
        .all()
    )
    answer_feedback = _build_feedback_summary(feedback_events)

    return {
        "total_messages": total_messages,
        "total_sessions": total_sessions,
        "user_queries": user_messages,
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "answer_quality": answer_quality,
        "answer_feedback": answer_feedback,
        "language_breakdown": [{"language": r.language, "count": r.count} for r in lang_breakdown],
        "collection_usage": [{"collection": r.collection, "queries": r.queries} for r in collection_usage],
        "recent_queries": [
            {
                "content": r.content[:100],
                "language": r.language,
                "collection": r.collection,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in recent_queries
        ],
    }


@app.get("/admin/reviews")
@limiter.limit(settings.default_rate_limit)
def admin_reviews(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
    status_filter: Literal["open", "resolved", "dismissed", "all"] = Query("open", alias="status"),
    collection: str = Query("", max_length=100),
    rating: Literal["helpful", "not_helpful", "needs_review", "all"] = "all",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = db.query(AnswerReview)
    if status_filter != "all":
        query = query.filter(AnswerReview.status == status_filter)
    if collection:
        query = query.filter(AnswerReview.collection == collection)
    if rating != "all":
        query = query.filter(AnswerReview.rating == rating)

    total = query.count()
    summary_rows = query.order_by(AnswerReview.created_at.desc()).limit(5000).all()
    rows = query.order_by(AnswerReview.created_at.desc()).offset(offset).limit(limit).all()
    summary = _answer_review_summary(summary_rows)
    summary["total_matching"] = total
    return {
        "reviews": [_answer_review_payload(row) for row in rows],
        "summary": summary,
        "pagination": {"limit": limit, "offset": offset, "total": total},
    }


@app.patch("/admin/reviews/{review_id}")
@limiter.limit(settings.default_rate_limit)
def update_review(
    request: Request,
    review_id: Annotated[int, Path(..., ge=1)],
    payload: ReviewUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    row = db.query(AnswerReview).filter(AnswerReview.id == review_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")

    row.status = payload.status
    row.reviewer_note = payload.reviewer_note
    row.updated_at = utc_now()
    if payload.status in {"resolved", "dismissed"}:
        row.resolved_by = current_user.username
        row.resolved_at = row.resolved_at or utc_now()
    else:
        row.resolved_by = None
        row.resolved_at = None

    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="answer_review.update",
        resource_type="answer_review",
        resource_id=str(review_id),
        collection=row.collection,
        metadata={"status": payload.status, "reviewer_note": payload.reviewer_note[:500]},
    )
    db.commit()
    return {"review": _answer_review_payload(row)}


@app.post("/admin/reviews/{review_id}/promote-eval")
@limiter.limit(settings.default_rate_limit)
def promote_review_to_eval_case(
    request: Request,
    review_id: Annotated[int, Path(..., ge=1)],
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    review = db.query(AnswerReview).filter(AnswerReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    case_id = _eval_case_id_for_review(review)
    existing = db.query(EvaluationCase).filter(EvaluationCase.case_id == case_id).first()
    if existing:
        eval_case = existing
    else:
        eval_case = _build_eval_case_from_review(review, current_user)
        db.add(eval_case)

    review.promoted_eval_case_id = case_id
    review.promoted_to_eval_at = review.promoted_to_eval_at or utc_now()
    review.updated_at = utc_now()
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="answer_review.promote_eval",
        resource_type="evaluation_case",
        resource_id=case_id,
        collection=review.collection,
        metadata={"review_id": review.id, "required_citations": len(_required_citations_from_review(review))},
    )
    _track_usage(
        db,
        current_user=current_user,
        event_type="evaluation_case.promoted",
        metadata={"case_id": case_id, "review_id": review.id, "collection": review.collection},
    )
    db.commit()
    return {"eval_case": _eval_case_payload(eval_case), "review": _answer_review_payload(review)}


@app.get("/admin/eval-cases")
@limiter.limit(settings.default_rate_limit)
def list_eval_cases(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
    collection: str = Query("", max_length=100),
    status_filter: Literal["active", "archived", "all"] = Query("active", alias="status"),
    limit: int = Query(100, ge=1, le=500),
):
    query = db.query(EvaluationCase)
    if collection:
        query = query.filter(EvaluationCase.collection == collection)
    if status_filter != "all":
        query = query.filter(EvaluationCase.status == status_filter)
    rows = query.order_by(EvaluationCase.created_at.desc()).limit(limit).all()
    return {
        "cases": [_eval_case_payload(row) for row in rows],
        "summary": {
            "total": len(rows),
            "with_required_citations": sum(1 for row in rows if row.required_citations_json),
            "by_collection": sorted(
                [
                    {"collection": value, "count": sum(1 for row in rows if row.collection == value)}
                    for value in {row.collection for row in rows}
                ],
                key=lambda item: item["count"],
                reverse=True,
            ),
        },
    }


@app.get("/admin/eval-cases/export")
@limiter.limit(settings.default_rate_limit)
def export_eval_cases(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
    collection: str = Query("", max_length=100),
):
    query = db.query(EvaluationCase).filter(EvaluationCase.status == "active")
    if collection:
        query = query.filter(EvaluationCase.collection == collection)
    rows = query.order_by(EvaluationCase.created_at.asc()).all()
    return {
        "version": 1,
        "description": "Promoted answer review cases for retrieval evaluation.",
        "cases": [_golden_case_payload(row) for row in rows],
    }


@app.post("/admin/eval-runs")
@limiter.limit(settings.default_rate_limit)
def run_eval_cases(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
    collection: str = Query("", max_length=100),
    limit: int = Query(50, ge=1, le=100),
):
    query = db.query(EvaluationCase).filter(EvaluationCase.status == "active")
    if collection:
        query = query.filter(EvaluationCase.collection == collection)
    rows = query.order_by(EvaluationCase.created_at.asc()).limit(limit).all()
    if not rows:
        raise HTTPException(status_code=400, detail="No active evaluation cases found")

    report = _run_promoted_eval_cases(rows, current_user, db)
    summary = report.get("summary", {})
    started_at = utc_now()
    run = EvaluationRun(
        run_id=f"eval-{uuid.uuid4().hex[:12]}",
        collection=collection or "all",
        status="completed",
        total_cases=int(summary.get("total_cases", 0) or 0),
        passed_cases=int(summary.get("passed_cases", 0) or 0),
        case_pass_rate=float(summary.get("case_pass_rate", 0.0) or 0.0),
        citation_recall=float(summary.get("citation_recall", 0.0) or 0.0),
        grounded_accuracy=float(summary.get("grounded_accuracy", 0.0) or 0.0),
        no_answer_accuracy=float(summary.get("no_answer_accuracy", 0.0) or 0.0),
        passed=bool(report.get("passed")),
        report_json=report,
        created_by=current_user.username,
        started_at=started_at,
        completed_at=utc_now(),
    )
    db.add(run)
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="evaluation_run.create",
        resource_type="evaluation_run",
        resource_id=run.run_id,
        collection=collection or None,
        metadata={
            "total_cases": run.total_cases,
            "passed_cases": run.passed_cases,
            "case_pass_rate": run.case_pass_rate,
            "citation_recall": run.citation_recall,
            "passed": run.passed,
        },
    )
    _track_usage(
        db,
        current_user=current_user,
        event_type="evaluation_run.completed",
        metadata={
            "run_id": run.run_id,
            "collection": run.collection,
            "total_cases": run.total_cases,
            "passed_cases": run.passed_cases,
            "case_pass_rate": run.case_pass_rate,
            "passed": run.passed,
        },
    )
    db.commit()
    return {"run": _eval_run_payload(run)}


@app.get("/admin/eval-runs")
@limiter.limit(settings.default_rate_limit)
def list_eval_runs(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    db: Session = Depends(get_db),
    collection: str = Query("", max_length=100),
    status_filter: Literal["completed", "failed", "all"] = Query("all", alias="status"),
    limit: int = Query(20, ge=1, le=100),
):
    query = db.query(EvaluationRun)
    if collection:
        query = query.filter(EvaluationRun.collection == collection)
    if status_filter != "all":
        query = query.filter(EvaluationRun.status == status_filter)
    rows = query.order_by(EvaluationRun.started_at.desc()).limit(limit).all()
    return {
        "runs": [_eval_run_payload(row) for row in rows],
        "summary": _eval_run_summary(rows),
    }


@app.get("/chat/sessions")
@limiter.limit(settings.default_rate_limit)
def chat_sessions(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    query = db.query(
        ChatMessage.session_id,
        sa_func.min(ChatMessage.content).label("first_message"),
        sa_func.count(ChatMessage.id).label("message_count"),
        sa_func.max(ChatMessage.created_at).label("last_active"),
        sa_func.min(ChatMessage.collection).label("collection"),
    ).filter(ChatMessage.role == "user")
    if not current_user.is_admin and "*" not in current_user.collections:
        query = query.filter(ChatMessage.collection.in_(sorted(current_user.collections)))
    subq = query.group_by(ChatMessage.session_id).order_by(sa_func.max(ChatMessage.created_at).desc()).limit(30).all()
    return {
        "sessions": [
            {
                "session_id": r.session_id,
                "preview": (r.first_message or "")[:80],
                "message_count": r.message_count,
                "last_active": str(r.last_active) if r.last_active else None,
                "collection": r.collection,
            }
            for r in subq
        ]
    }


@app.get("/chat/history/{session_id}")
@limiter.limit(settings.default_rate_limit)
def chat_history(
    request: Request,
    session_id: Annotated[SessionId, Path(..., description="Chat session identifier")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
    if not current_user.is_admin and "*" not in current_user.collections:
        query = query.filter(ChatMessage.collection.in_(sorted(current_user.collections)))
    rows = query.order_by(ChatMessage.created_at).all()
    messages = []
    for r in rows:
        citations = r.citations_json or []
        messages.append(
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "language": r.language,
                "collection": r.collection,
                "citations": citations,
                "answer_quality": _answer_quality("grounded" if citations else "no_context", citations) if r.role == "assistant" else {},
                "created_at": str(r.created_at) if r.created_at else None,
            }
        )
    return {"session_id": session_id, "messages": messages}


@app.post("/chat/feedback")
@limiter.limit(settings.default_rate_limit)
def chat_feedback(
    request: Request,
    payload: ChatFeedbackRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    quality = payload.answer_quality if isinstance(payload.answer_quality, dict) else {}
    review_status = "resolved" if payload.rating == "helpful" else "open"
    source_confidence = _safe_float(quality.get("source_confidence"))
    metadata = {
        "session_id": payload.session_id,
        "collection": payload.collection,
        "question": payload.question[:500],
        "answer_excerpt": payload.answer_excerpt[:500],
        "rating": payload.rating,
        "reason": payload.reason[:500],
        "language": payload.language,
        "citation_count": payload.citation_count,
        "citations": payload.citations,
        "source_confidence": source_confidence,
        "confidence_label": quality.get("confidence_label"),
        "outcome": quality.get("outcome"),
        "feedback_version": 1,
    }
    _track_usage(db, current_user=current_user, event_type="chat.feedback", metadata=metadata)
    db.add(
        AnswerReview(
            session_id=payload.session_id,
            collection=payload.collection,
            question=payload.question[:4000],
            answer_excerpt=payload.answer_excerpt[:1500],
            rating=payload.rating,
            reason=payload.reason[:1000],
            language=payload.language,
            citation_count=payload.citation_count,
            citations_json=payload.citations,
            source_confidence=source_confidence,
            confidence_label=quality.get("confidence_label"),
            answer_quality_json=quality,
            status=review_status,
            created_by=current_user.username,
            resolved_by=current_user.username if review_status == "resolved" else None,
            resolved_at=utc_now() if review_status == "resolved" else None,
        )
    )
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="chat.feedback",
        resource_type="chat_session",
        resource_id=payload.session_id or None,
        collection=payload.collection,
        metadata={"rating": payload.rating, "reason": payload.reason[:500]},
    )
    db.commit()
    return {"recorded": True, "rating": payload.rating}


@app.delete("/chat/sessions/{session_id}")
@limiter.limit(settings.default_rate_limit)
def delete_session(
    request: Request,
    session_id: Annotated[SessionId, Path(..., description="Chat session identifier")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
    if not current_user.is_admin and "*" not in current_user.collections:
        query = query.filter(ChatMessage.collection.in_(sorted(current_user.collections)))
    count = query.delete()
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="chat.session.delete",
        resource_type="chat_session",
        resource_id=session_id,
        metadata={"messages_removed": count},
    )
    db.commit()
    return {"deleted_session": session_id, "messages_removed": count}


def _row_metadata(row) -> dict:
    if hasattr(row, "get"):
        metadata = row.get("metadata_json") or {}
    else:
        metadata = getattr(row, "metadata_json", {}) or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    return metadata if isinstance(metadata, dict) else {}


def _source_acl_allows(metadata: dict, current_user: CurrentUser) -> bool:
    if current_user.is_admin:
        return True
    source_acl = _normalize_source_acl(metadata.get("source_acl"))
    if source_acl["mode"] == "public":
        return True

    allowed_users = {item.lower() for item in source_acl.get("allowed_users", [])}
    allowed_groups = {item.lower() for item in source_acl.get("allowed_groups", [])}
    username = current_user.username.lower()
    user_groups = {item.lower() for item in current_user.source_groups}

    if username in allowed_users:
        return True
    if allowed_groups and user_groups.intersection(allowed_groups):
        return True
    return False


def _filter_rows_by_source_acl(rows, current_user: CurrentUser) -> list:
    return [row for row in rows if _source_acl_allows(_row_metadata(row), current_user)]


def _source_freshness_by_document(db: Session, collection: str, rows: list[dict]) -> dict[str, dict]:
    document_names = sorted({str(row.get("document_name") or "") for row in rows if row.get("document_name")})
    if not document_names:
        return {}
    sources = (
        db.query(DocumentSource)
        .filter(DocumentSource.collection == collection, DocumentSource.document_name.in_(document_names))
        .all()
    )
    return {source.document_name: _source_payload(source) for source in sources}


def _citation_from_retrieval_row(row: dict, source_by_document: dict[str, dict]) -> dict:
    source = source_by_document.get(row["document_name"]) or {}
    citation = {
        "document": row["document_name"],
        "page": row["page"],
        "relevance": round(float(row["score"]), 4),
        "chunk_id": row["id"],
    }
    if source:
        citation.update(
            {
                "source_freshness": source.get("freshness_status"),
                "source_sync_status": source.get("sync_status"),
                "last_synced_at": source.get("last_synced_at"),
                "source_updated_at": source.get("source_updated_at"),
            }
        )
    return citation


def _lexical_fallback_rows(db: Session, collection: str, question: str, current_user: CurrentUser):
    rows = (
        db.query(
            DocumentChunk.id,
            DocumentChunk.document_name,
            DocumentChunk.page,
            DocumentChunk.content,
            DocumentChunk.search_text,
            DocumentChunk.metadata_json,
        )
        .filter(DocumentChunk.collection == collection)
        .limit(250)
        .all()
    )
    ranked = []
    for r in _filter_rows_by_source_acl(rows, current_user):
        score = stem_overlap_ratio(question, r.search_text or "")
        ranked.append({
            "id": r.id,
            "document_name": r.document_name,
            "page": r.page,
            "content": r.content,
            "search_text": r.search_text or "",
            "metadata_json": r.metadata_json or {},
            "vector_score": 0.0,
            "score": score,
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:5]


@app.post("/admin/upload")
@limiter.limit(settings.upload_rate_limit)
async def upload_document(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    file: UploadFile = File(...),
    collection: Annotated[CollectionName, Form()] = "HR-docs",
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")
    if len(file.filename) > 255:
        raise HTTPException(status_code=400, detail="File name exceeds 255 characters")

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum allowed size is {settings.max_upload_size_mb}MB",
        )
    _consume_user_quota(db, current_user, units=1)
    _track_usage(
        db,
        current_user=current_user,
        event_type="document.upload.requested",
        metadata={"collection": collection, "filename": file.filename, "bytes": len(content)},
    )
    ingestion_uploaded_bytes_total.inc(len(content))
    logger.info("Upload started: %s -> collection=%s (%d bytes)", file.filename, collection, len(content))
    job = IngestionJob(document_name=file.filename, collection=collection, status="processing")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        pages = extract_text(file.filename, content)
        chunks = chunk_pages(pages)
        language_hint = _detect_language(" ".join(chunk["content"] for chunk in chunks[:3])[:1500]) if chunks else "en"
        embeddings = _build_embeddings(language_hint)

        vectors = embeddings.embed_documents([c["content"] for c in chunks])

        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            db.add(
                DocumentChunk(
                    collection=collection,
                    document_name=file.filename,
                    page=chunk["page"],
                    chunk_index=idx,
                    content=chunk["content"],
                    metadata_json={"page": chunk["page"]},
                    search_text=finnish_search_text(chunk["content"]),
                    embedding=vec,
                )
            )

        job.status = "completed"
        job.chunks_created = len(chunks)
        document_source = _upsert_document_source(
            db,
            collection=collection,
            document_name=file.filename,
            connector="upload",
            source_url="",
            source_updated_at=utc_now(),
        )
        _audit_log(
            db,
            request=request,
            current_user=current_user,
            action="document.upload.completed",
            resource_type="document",
            resource_id=file.filename,
            collection=collection,
            metadata={"job_id": job.id, "chunks_created": len(chunks), "bytes": len(content), "freshness_status": document_source.freshness_status},
        )
        _track_usage(
            db,
            current_user=current_user,
            event_type="document.upload.completed",
            metadata={"collection": collection, "filename": file.filename, "chunks_created": len(chunks), "freshness_status": document_source.freshness_status},
        )
        db.commit()
        logger.info("Upload completed: %s -> %d chunks", file.filename, len(chunks))
        return {"job_id": job.id, "chunks": len(chunks), "status": "completed"}
    except (ValueError, TypeError, SQLAlchemyError, RuntimeError, httpx.HTTPError) as exc:
        job.status = "failed"
        job.error = str(exc)
        _audit_log(
            db,
            request=request,
            current_user=current_user,
            action="document.upload.failed",
            resource_type="document",
            resource_id=file.filename,
            collection=collection,
            metadata={"error": str(exc), "job_id": job.id},
        )
        _track_usage(
            db,
            current_user=current_user,
            event_type="document.upload.failed",
            metadata={"collection": collection, "filename": file.filename, "error": str(exc)},
        )
        db.commit()
        logger.error("Upload failed: %s -> %s", file.filename, exc)
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {exc}") from exc


def _detect_language(question: str) -> Literal["fi", "en", "sv"]:
    try:
        lang = detect(question)
    except (LangDetectException, ValueError):
        lang = "en"
    return "fi" if lang == "fi" else ("sv" if lang == "sv" else "en")


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.chat_rate_limit)
def chat(
    request: Request,
    payload: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    ensure_collection_access(current_user, payload.collection)
    _consume_user_quota(db, current_user, units=1)

    session_id = payload.session_id or uuid.uuid4().hex[:16]
    logger.info("Chat query: session=%s collection=%s question_len=%d", session_id, payload.collection, len(question))
    language = _detect_language(question)

    top_rows = _retrieve_context(question, payload.collection, language, current_user, db)
    if not top_rows:
        quality = _answer_quality("no_context", [])
        _no_info = {
            "fi": "En löytänyt tietoa valitusta kokoelmasta.",
            "sv": "Jag kunde inte hitta relevant information i den samlingen.",
            "en": "I couldn't find relevant information in that collection.",
        }
        msg = _no_info.get(language, _no_info["en"])
        db.add(ChatMessage(session_id=session_id, role="user", content=question, language=language, collection=payload.collection))
        db.add(
            ChatMessage(
                session_id=session_id,
                role="assistant",
                content=msg,
                language=language,
                collection=payload.collection,
                citations_json=[],
            )
        )
        _audit_log(
            db,
            request=request,
            current_user=current_user,
            action="chat.message.create",
            resource_type="chat_session",
            resource_id=session_id,
            collection=payload.collection,
            metadata={"question_len": len(question), "citations": quality["citation_count"], **quality},
        )
        usage_metadata = _quality_usage_metadata(collection=payload.collection, language=language, quality=quality)
        usage_metadata["question_len"] = len(question)
        _track_usage(
            db,
            current_user=current_user,
            event_type="chat.query",
            metadata=usage_metadata,
        )
        db.commit()
        chat_requests_total.labels(mode="sync", status="no_context").inc()
        return ChatResponse(answer=msg, language=language, citations=[], session_id=session_id, answer_quality=quality)

    context = "\n\n".join([f"[{r['document_name']} p.{r['page']}] {r['content']}" for r in top_rows])
    _sys_prompts = {
        "fi": "Vastaa suomeksi käyttäjän kysymykseen käyttäen vain annettua kontekstia.",
        "sv": "Svara på svenska på användarens fråga med enbart den angivna kontexten.",
        "en": "Answer in English using only the provided context.",
    }
    sys_prompt = _sys_prompts.get(language, _sys_prompts["en"])
    prompt = (
        f"System: {sys_prompt}\n"
        f"Question: {question}\n"
        f"Context:\n{context}\n"
        "Include concise answer and mention if policy details are missing."
    )

    llm = _build_chat_llm(language, streaming=False)
    result = llm.invoke(prompt)
    source_by_document = _source_freshness_by_document(db, payload.collection, top_rows)
    citations = [_citation_from_retrieval_row(r, source_by_document) for r in top_rows]
    quality = _answer_quality("grounded", citations)

    db.add(ChatMessage(session_id=session_id, role="user", content=question, language=language, collection=payload.collection))
    db.add(
        ChatMessage(
            session_id=session_id,
            role="assistant",
            content=result.content,
            language=language,
            collection=payload.collection,
            citations_json=citations,
        )
    )
    _audit_log(
        db,
        request=request,
        current_user=current_user,
        action="chat.message.create",
        resource_type="chat_session",
        resource_id=session_id,
        collection=payload.collection,
        metadata={"question_len": len(question), "citations": quality["citation_count"], **quality},
    )
    usage_metadata = _quality_usage_metadata(collection=payload.collection, language=language, quality=quality)
    usage_metadata["question_len"] = len(question)
    usage_metadata.update(_citation_freshness_counts(citations))
    _track_usage(
        db,
        current_user=current_user,
        event_type="chat.query",
        metadata=usage_metadata,
    )
    db.commit()
    chat_requests_total.labels(mode="sync", status="ok").inc()
    return ChatResponse(answer=result.content, language=language, citations=citations, session_id=session_id, answer_quality=quality)


def _retrieve_context(question: str, collection: str, language: str, current_user: CurrentUser, db: Session):
    """Shared retrieval logic for both sync and streaming chat."""
    top_rows = []
    try:
        embeddings = _build_embeddings(language)
        q_emb = embeddings.embed_query(question)
        sql = text(
            """
            SELECT id, document_name, page, content, search_text, metadata_json,
                   1 - (embedding <=> :query_vector) AS vector_score
            FROM document_chunks
            WHERE collection = :collection
            ORDER BY embedding <=> :query_vector
            LIMIT 50
            """
        )
        q_vec_str = str(q_emb)
        rows = db.execute(sql, {"query_vector": q_vec_str, "collection": collection}).mappings().all()
        ranked = []
        for r in _filter_rows_by_source_acl(rows, current_user):
            lexical_boost = 0.0
            if language == "fi":
                lexical_boost = 0.20 * stem_overlap_ratio(question, r["search_text"] or "")
            ranked.append({**r, "score": float(r["vector_score"]) + lexical_boost})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        top_rows = ranked[:5]
    except (SQLAlchemyError, ValueError, TypeError, RuntimeError, httpx.HTTPError):
        logger.error("Vector search failed: %s", traceback.format_exc())
        if language == "fi":
            top_rows = _lexical_fallback_rows(db, collection, question, current_user)
    return top_rows


@app.post("/chat/stream")
@limiter.limit(settings.chat_rate_limit)
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    ensure_collection_access(current_user, payload.collection)
    _consume_user_quota(db, current_user, units=1)

    session_id = payload.session_id or uuid.uuid4().hex[:16]
    logger.info("Stream chat: session=%s collection=%s", session_id, payload.collection)
    language = _detect_language(question)

    top_rows = _retrieve_context(question, payload.collection, language, current_user, db)

    source_by_document = _source_freshness_by_document(db, payload.collection, top_rows)
    citations = [_citation_from_retrieval_row(r, source_by_document) for r in top_rows]

    if not top_rows:
        quality = _answer_quality("no_context", [])
        _no_info = {
            "fi": "En löytänyt tietoa valitusta kokoelmasta.",
            "sv": "Jag kunde inte hitta relevant information i den samlingen.",
            "en": "I couldn't find relevant information in that collection.",
        }
        msg = _no_info.get(language, _no_info["en"])
        db.add(ChatMessage(session_id=session_id, role="user", content=question, language=language, collection=payload.collection))
        db.add(ChatMessage(session_id=session_id, role="assistant", content=msg, language=language, collection=payload.collection, citations_json=[]))
        _audit_log(
            db,
            request=request,
            current_user=current_user,
            action="chat.message.stream.create",
            resource_type="chat_session",
            resource_id=session_id,
            collection=payload.collection,
            metadata={"question_len": len(question), "citations": quality["citation_count"], **quality},
        )
        usage_metadata = _quality_usage_metadata(collection=payload.collection, language=language, quality=quality)
        usage_metadata["question_len"] = len(question)
        usage_metadata.update(_citation_freshness_counts(citations))
        _track_usage(
            db,
            current_user=current_user,
            event_type="chat.stream.query",
            metadata=usage_metadata,
        )
        db.commit()
        chat_requests_total.labels(mode="stream", status="no_context").inc()

        async def no_results_gen():
            yield {
                "event": "metadata",
                "data": json.dumps({"session_id": session_id, "language": language, "citations": [], "answer_quality": quality}),
            }
            yield {"event": "token", "data": msg}
            yield {"event": "done", "data": ""}

        return EventSourceResponse(no_results_gen())

    quality = _answer_quality("grounded", citations)

    context = "\n\n".join([f"[{r['document_name']} p.{r['page']}] {r['content']}" for r in top_rows])
    _sys_prompts_stream = {
        "fi": "Vastaa suomeksi käyttäjän kysymykseen käyttäen vain annettua kontekstia.",
        "sv": "Svara på svenska på användarens fråga med enbart den angivna kontexten.",
        "en": "Answer in English using only the provided context.",
    }
    sys_msg = _sys_prompts_stream.get(language, _sys_prompts_stream["en"])
    prompt = f"System: {sys_msg}\nQuestion: {question}\nContext:\n{context}\nInclude concise answer and mention if policy details are missing."

    async def stream_gen():
        yield {
            "event": "metadata",
            "data": json.dumps({"session_id": session_id, "language": language, "citations": citations, "answer_quality": quality}),
        }
        full_text = ""
        llm = _build_chat_llm(language, streaming=True)
        async for chunk in llm.astream(prompt):
            if await request.is_disconnected():
                break
            token = chunk.content
            if token:
                full_text += token
                yield {"event": "token", "data": token}
        db.add(ChatMessage(session_id=session_id, role="user", content=question, language=language, collection=payload.collection))
        db.add(ChatMessage(session_id=session_id, role="assistant", content=full_text, language=language, collection=payload.collection, citations_json=citations))
        _audit_log(
            db,
            request=request,
            current_user=current_user,
            action="chat.message.stream.create",
            resource_type="chat_session",
            resource_id=session_id,
            collection=payload.collection,
            metadata={"question_len": len(question), "citations": quality["citation_count"], **quality},
        )
        usage_metadata = _quality_usage_metadata(collection=payload.collection, language=language, quality=quality)
        usage_metadata["question_len"] = len(question)
        _track_usage(
            db,
            current_user=current_user,
            event_type="chat.stream.query",
            metadata=usage_metadata,
        )
        db.commit()
        chat_requests_total.labels(mode="stream", status="ok").inc()
        yield {"event": "done", "data": ""}

    return EventSourceResponse(stream_gen())
