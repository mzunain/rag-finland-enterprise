import logging
import secrets
import time
import traceback
import uuid
from datetime import timedelta
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

from .auth_utils import hash_api_key, hash_password, month_window_start, utc_now
from .config import settings
from .connectors import fetch_connector_document
from .db import (
    ApiKey,
    AuditLog,
    ChatMessage,
    Collection,
    CollectionPermission,
    DocumentChunk,
    IngestionJob,
    SessionLocal,
    UsageEvent,
    UserAccount,
    init_db,
)
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

app = FastAPI(
    title="RAG Finland Enterprise MVP",
    version="1.0.0",
    servers=[{"url": settings.api_version_prefix, "description": "Versioned API root"}],
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


@app.on_event("startup")
def on_startup():
    init_db()
    if settings.auth_required and settings.jwt_secret_key == "change-me-in-production":
        logger.warning("JWT_SECRET_KEY is using the default placeholder; set a secure value before deployment")


CollectionName = Annotated[str, StringConstraints(min_length=2, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$")]
SessionId = Annotated[str, StringConstraints(max_length=64, pattern=r"^[A-Za-z0-9_-]*$")]
DocumentName = Annotated[str, StringConstraints(min_length=1, max_length=255)]

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


class ConnectorImportRequest(BaseModel):
    connector: Literal["confluence", "sharepoint", "generic"] = "generic"
    collection: CollectionName = "HR-docs"
    source_urls: list[Annotated[str, StringConstraints(min_length=10, max_length=2000)]]
    access_token: Annotated[str | None, StringConstraints(max_length=4096)] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "connector": "confluence",
                "collection": "Technical-docs",
                "source_urls": [
                    "https://wiki.example.com/rest/api/content/12345?expand=body.storage,title"
                ],
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
                        metadata_json={**connector_doc.metadata, "source_url": source_url, "connector": payload.connector},
                        search_text=finnish_search_text(chunk["content"]),
                        embedding=vec,
                    )
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
                metadata={"connector": payload.connector, "source_url": source_url, "chunks_created": len(chunks)},
            )
            _track_usage(
                db,
                current_user=current_user,
                event_type="connector.import",
                metadata={"connector": payload.connector, "source_url": source_url, "chunks_created": len(chunks)},
            )
            db.commit()
            imported.append(
                {
                    "source_url": source_url,
                    "document_name": connector_doc.title,
                    "chunks_created": len(chunks),
                    "job_id": job.id,
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
            failed.append({"source_url": source_url, "error": str(exc)})

    return {
        "connector": payload.connector,
        "collection": payload.collection,
        "imported": imported,
        "failed": failed,
    }


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
    return {
        "documents": [
            {
                "document_name": r.document_name,
                "chunk_count": r.chunk_count,
                "pages": r.max_page,
                "created_at": str(r.created_at) if r.created_at else None,
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
    return {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
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

    return {
        "total_messages": total_messages,
        "total_sessions": total_sessions,
        "user_queries": user_messages,
        "total_documents": total_docs,
        "total_chunks": total_chunks,
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
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "language": r.language,
                "collection": r.collection,
                "citations": r.citations_json or [],
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ],
    }


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


def _lexical_fallback_rows(db: Session, collection: str, question: str):
    rows = (
        db.query(DocumentChunk.id, DocumentChunk.document_name, DocumentChunk.page, DocumentChunk.content, DocumentChunk.search_text)
        .filter(DocumentChunk.collection == collection)
        .limit(250)
        .all()
    )
    ranked = []
    for r in rows:
        score = stem_overlap_ratio(question, r.search_text or "")
        ranked.append({
            "id": r.id,
            "document_name": r.document_name,
            "page": r.page,
            "content": r.content,
            "search_text": r.search_text or "",
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
        _audit_log(
            db,
            request=request,
            current_user=current_user,
            action="document.upload.completed",
            resource_type="document",
            resource_id=file.filename,
            collection=collection,
            metadata={"job_id": job.id, "chunks_created": len(chunks), "bytes": len(content)},
        )
        _track_usage(
            db,
            current_user=current_user,
            event_type="document.upload.completed",
            metadata={"collection": collection, "filename": file.filename, "chunks_created": len(chunks)},
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

    top_rows = _retrieve_context(question, payload.collection, language, db)
    if not top_rows:
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
            metadata={"question_len": len(question), "citations": 0},
        )
        _track_usage(
            db,
            current_user=current_user,
            event_type="chat.query",
            metadata={"collection": payload.collection, "language": language, "citations": 0},
        )
        db.commit()
        chat_requests_total.labels(mode="sync", status="no_context").inc()
        return ChatResponse(answer=msg, language=language, citations=[], session_id=session_id)

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
    citations = [
        {
            "document": r["document_name"],
            "page": r["page"],
            "relevance": round(float(r["score"]), 4),
            "chunk_id": r["id"],
        }
        for r in top_rows
    ]

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
        metadata={"question_len": len(question), "citations": len(citations)},
    )
    _track_usage(
        db,
        current_user=current_user,
        event_type="chat.query",
        metadata={"collection": payload.collection, "language": language, "citations": len(citations)},
    )
    db.commit()
    chat_requests_total.labels(mode="sync", status="ok").inc()
    return ChatResponse(answer=result.content, language=language, citations=citations, session_id=session_id)


def _retrieve_context(question: str, collection: str, language: str, db: Session):
    """Shared retrieval logic for both sync and streaming chat."""
    top_rows = []
    try:
        embeddings = _build_embeddings(language)
        q_emb = embeddings.embed_query(question)
        sql = text(
            """
            SELECT id, document_name, page, content, search_text,
                   1 - (embedding <=> :query_vector) AS vector_score
            FROM document_chunks
            WHERE collection = :collection
            ORDER BY embedding <=> :query_vector
            LIMIT 12
            """
        )
        q_vec_str = str(q_emb)
        rows = db.execute(sql, {"query_vector": q_vec_str, "collection": collection}).mappings().all()
        ranked = []
        for r in rows:
            lexical_boost = 0.0
            if language == "fi":
                lexical_boost = 0.20 * stem_overlap_ratio(question, r["search_text"] or "")
            ranked.append({**r, "score": float(r["vector_score"]) + lexical_boost})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        top_rows = ranked[:5]
    except (SQLAlchemyError, ValueError, TypeError, RuntimeError, httpx.HTTPError):
        logger.error("Vector search failed: %s", traceback.format_exc())
        if language == "fi":
            top_rows = _lexical_fallback_rows(db, collection, question)
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

    top_rows = _retrieve_context(question, payload.collection, language, db)

    citations = [
        {"document": r["document_name"], "page": r["page"], "relevance": round(float(r["score"]), 4), "chunk_id": r["id"]}
        for r in top_rows
    ]

    if not top_rows:
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
            metadata={"question_len": len(question), "citations": 0},
        )
        _track_usage(
            db,
            current_user=current_user,
            event_type="chat.stream.query",
            metadata={"collection": payload.collection, "language": language, "citations": 0},
        )
        db.commit()
        chat_requests_total.labels(mode="stream", status="no_context").inc()

        async def no_results_gen():
            yield {"event": "metadata", "data": json.dumps({"session_id": session_id, "language": language, "citations": []})}
            yield {"event": "token", "data": msg}
            yield {"event": "done", "data": ""}

        return EventSourceResponse(no_results_gen())

    context = "\n\n".join([f"[{r['document_name']} p.{r['page']}] {r['content']}" for r in top_rows])
    _sys_prompts_stream = {
        "fi": "Vastaa suomeksi käyttäjän kysymykseen käyttäen vain annettua kontekstia.",
        "sv": "Svara på svenska på användarens fråga med enbart den angivna kontexten.",
        "en": "Answer in English using only the provided context.",
    }
    sys_msg = _sys_prompts_stream.get(language, _sys_prompts_stream["en"])
    prompt = f"System: {sys_msg}\nQuestion: {question}\nContext:\n{context}\nInclude concise answer and mention if policy details are missing."

    async def stream_gen():
        yield {"event": "metadata", "data": json.dumps({"session_id": session_id, "language": language, "citations": citations})}
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
            metadata={"question_len": len(question), "citations": len(citations)},
        )
        _track_usage(
            db,
            current_user=current_user,
            event_type="chat.stream.query",
            metadata={"collection": payload.collection, "language": language, "citations": len(citations)},
        )
        db.commit()
        chat_requests_total.labels(mode="stream", status="ok").inc()
        yield {"event": "done", "data": ""}

    return EventSourceResponse(stream_gen())
