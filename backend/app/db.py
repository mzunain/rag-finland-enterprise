import logging
import json

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, JSON, String, Text, UniqueConstraint, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector

from .auth_utils import hash_password, month_window_start
from .config import settings

logger = logging.getLogger(__name__)

_engine_kwargs = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(
        {
            "pool_size": settings.pool_size,
            "max_overflow": settings.max_overflow,
            "pool_timeout": settings.pool_timeout_seconds,
            "pool_recycle": settings.pool_recycle_seconds,
        }
    )

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_collection_document_name", "collection", "document_name"),
        Index("ix_document_chunks_collection_created_at", "collection", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    collection = Column(String(100), index=True)
    document_name = Column(String(255), index=True)
    page = Column(Integer, default=1)
    chunk_index = Column(Integer)
    content = Column(Text)
    metadata_json = Column(JSON, default=dict)
    search_text = Column(Text, default="", index=True)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index("ix_ingestion_jobs_collection_status_created_at", "collection", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    document_name = Column(String(255), index=True)
    collection = Column(String(100), index=True)
    status = Column(String(30), default="queued")
    chunks_created = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_created_at", "session_id", "created_at"),
        Index("ix_chat_messages_collection_created_at", "collection", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), index=True, nullable=False)
    role = Column(String(10), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    language = Column(String(5), default="en")
    collection = Column(String(100), default="HR-docs")
    citations_json = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
        Index("ix_audit_logs_actor_created_at", "actor_username", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    actor_username = Column(String(64), nullable=False, index=True)
    actor_role = Column(String(16), nullable=False)
    action = Column(String(80), nullable=False, index=True)
    resource_type = Column(String(80), nullable=False, index=True)
    resource_id = Column(String(255), nullable=True)
    collection = Column(String(100), nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())


class UserAccount(Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        Index("ix_user_accounts_role_active", "role", "is_active"),
    )

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(16), nullable=False, default="viewer")
    auth_provider = Column(String(32), nullable=False, default="local")
    external_subject = Column(String(255), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    monthly_quota = Column(Integer, nullable=False, default=settings.default_user_quota_per_month)
    used_this_month = Column(Integer, nullable=False, default=0)
    quota_reset_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CollectionPermission(Base):
    __tablename__ = "collection_permissions"
    __table_args__ = (
        UniqueConstraint("username", "collection", name="uq_collection_permissions_user_collection"),
        Index("ix_collection_permissions_collection_write", "collection", "can_write"),
    )

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    collection = Column(String(100), nullable=False, index=True)
    can_read = Column(Boolean, nullable=False, default=True)
    can_write = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_owner_active", "owner_username", "is_active"),
    )

    id = Column(Integer, primary_key=True)
    owner_username = Column(String(64), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    key_prefix = Column(String(24), nullable=False, index=True)
    key_hash = Column(String(128), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    monthly_quota = Column(Integer, nullable=False, default=settings.default_api_key_quota_per_month)
    used_this_month = Column(Integer, nullable=False, default=0)
    quota_reset_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_actor_created_at", "actor_username", "created_at"),
        Index("ix_usage_events_event_created_at", "event_type", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    actor_username = Column(String(64), nullable=False, index=True)
    api_key_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    units = Column(Integer, nullable=False, default=1)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())


class AnswerReview(Base):
    __tablename__ = "answer_reviews"
    __table_args__ = (
        Index("ix_answer_reviews_status_created_at", "status", "created_at"),
        Index("ix_answer_reviews_collection_status", "collection", "status"),
        Index("ix_answer_reviews_rating_created_at", "rating", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), index=True, nullable=False, default="")
    collection = Column(String(100), nullable=False, index=True)
    question = Column(Text, nullable=False, default="")
    answer_excerpt = Column(Text, nullable=False, default="")
    rating = Column(String(24), nullable=False, index=True)
    reason = Column(Text, nullable=False, default="")
    language = Column(String(5), nullable=True)
    citation_count = Column(Integer, nullable=False, default=0)
    citations_json = Column(JSON, default=list)
    source_confidence = Column(Float, nullable=True)
    confidence_label = Column(String(24), nullable=True)
    answer_quality_json = Column(JSON, default=dict)
    status = Column(String(24), nullable=False, default="open", index=True)
    reviewer_note = Column(Text, nullable=False, default="")
    created_by = Column(String(64), nullable=False, index=True)
    resolved_by = Column(String(64), nullable=True)
    promoted_eval_case_id = Column(String(100), nullable=True, index=True)
    promoted_to_eval_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime, nullable=True)


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_evaluation_cases_case_id"),
        Index("ix_evaluation_cases_collection_status", "collection", "status"),
        Index("ix_evaluation_cases_review_id", "review_id"),
    )

    id = Column(Integer, primary_key=True)
    case_id = Column(String(100), nullable=False, unique=True, index=True)
    review_id = Column(Integer, nullable=True, index=True)
    language = Column(String(5), nullable=False, default="en")
    collection = Column(String(100), nullable=False, index=True)
    question = Column(Text, nullable=False)
    expectation = Column(String(24), nullable=False, default="answer")
    required_citations_json = Column(JSON, default=list)
    notes_json = Column(JSON, default=dict)
    status = Column(String(24), nullable=False, default="active", index=True)
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_evaluation_runs_run_id"),
        Index("ix_evaluation_runs_collection_started_at", "collection", "started_at"),
        Index("ix_evaluation_runs_status_started_at", "status", "started_at"),
        Index("ix_evaluation_runs_passed_started_at", "passed", "started_at"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    collection = Column(String(100), nullable=False, default="", index=True)
    status = Column(String(24), nullable=False, default="completed", index=True)
    total_cases = Column(Integer, nullable=False, default=0)
    passed_cases = Column(Integer, nullable=False, default=0)
    case_pass_rate = Column(Float, nullable=False, default=0.0)
    citation_recall = Column(Float, nullable=False, default=0.0)
    grounded_accuracy = Column(Float, nullable=False, default=0.0)
    no_answer_accuracy = Column(Float, nullable=False, default=0.0)
    passed = Column(Boolean, nullable=False, default=False, index=True)
    report_json = Column(JSON, default=dict)
    created_by = Column(String(64), nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class DocumentSource(Base):
    __tablename__ = "document_sources"
    __table_args__ = (
        UniqueConstraint("collection", "document_name", name="uq_document_sources_collection_document"),
        Index("ix_document_sources_collection_freshness", "collection", "freshness_status"),
        Index("ix_document_sources_sync_status_next_sync", "sync_status", "next_sync_at"),
        Index("ix_document_sources_source_url", "source_url"),
    )

    id = Column(Integer, primary_key=True)
    collection = Column(String(100), nullable=False, index=True)
    document_name = Column(String(255), nullable=False, index=True)
    source_url = Column(Text, nullable=False, default="")
    connector = Column(String(32), nullable=False, default="upload")
    sync_status = Column(String(24), nullable=False, default="synced", index=True)
    freshness_status = Column(String(24), nullable=False, default="fresh", index=True)
    last_synced_at = Column(DateTime, nullable=True)
    source_updated_at = Column(DateTime, nullable=True)
    next_sync_at = Column(DateTime, nullable=True)
    stale_after_days = Column(Integer, nullable=False, default=settings.source_stale_after_days)
    sync_interval_hours = Column(Integer, nullable=False, default=settings.source_sync_interval_hours)
    last_sync_error = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


_DEFAULT_COLLECTIONS = [
    ("HR-docs", "Human resources policies and procedures"),
    ("Legal-docs", "Legal documents and compliance"),
    ("Technical-docs", "Technical documentation and guides"),
]


def _seed_default_users(session) -> None:
    if session.query(UserAccount).first():
        return

    try:
        raw_users = json.loads(settings.auth_users_json)
    except json.JSONDecodeError:
        logger.warning("Skipping bootstrap user seed: AUTH_USERS_JSON is invalid JSON")
        return
    if not isinstance(raw_users, list):
        logger.warning("Skipping bootstrap user seed: AUTH_USERS_JSON must be a list")
        return

    now = month_window_start()
    for entry in raw_users:
        if not isinstance(entry, dict):
            continue
        username = str(entry.get("username", "")).strip()
        password = str(entry.get("password", ""))
        role = str(entry.get("role", "viewer")).strip() or "viewer"
        collections = entry.get("collections", [])
        if not username or not password:
            continue

        session.add(
            UserAccount(
                username=username,
                password_hash=hash_password(password),
                role=role,
                auth_provider="local",
                monthly_quota=settings.default_user_quota_per_month,
                quota_reset_at=now,
            )
        )
        if role != "admin":
            for collection in collections if isinstance(collections, list) else []:
                if isinstance(collection, str) and collection:
                    session.add(
                        CollectionPermission(
                            username=username,
                            collection=collection,
                            can_read=True,
                            can_write=False,
                        )
                    )


def init_db() -> None:
    is_postgres = settings.database_url.startswith("postgresql")
    if is_postgres:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_text TEXT DEFAULT '';")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_collection_document_name ON document_chunks (collection, document_name);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_collection_created_at ON document_chunks (collection, created_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_collection_status_created_at ON ingestion_jobs (collection, status, created_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_session_created_at ON chat_messages (session_id, created_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_collection_created_at ON chat_messages (collection, created_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_answer_reviews_status_created_at ON answer_reviews (status, created_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_answer_reviews_collection_status ON answer_reviews (collection, status);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_answer_reviews_rating_created_at ON answer_reviews (rating, created_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_answer_reviews_promoted_eval_case_id ON answer_reviews (promoted_eval_case_id);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_evaluation_cases_collection_status ON evaluation_cases (collection, status);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_evaluation_cases_review_id ON evaluation_cases (review_id);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_evaluation_runs_collection_started_at ON evaluation_runs (collection, started_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_evaluation_runs_status_started_at ON evaluation_runs (status, started_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_evaluation_runs_passed_started_at ON evaluation_runs (passed, started_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_document_sources_collection_freshness ON document_sources (collection, freshness_status);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_document_sources_sync_status_next_sync ON document_sources (sync_status, next_sync_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_document_sources_source_url ON document_sources (source_url);"
        )
        if is_postgres:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_ivfflat ON document_chunks "
                f"USING ivfflat (embedding vector_cosine_ops) WITH (lists = {settings.ivfflat_lists});"
            )
            conn.exec_driver_sql("ANALYZE document_chunks;")

    session = SessionLocal()
    try:
        for name, desc in _DEFAULT_COLLECTIONS:
            if not session.query(Collection).filter(Collection.name == name).first():
                session.add(Collection(name=name, description=desc))
        _seed_default_users(session)
        session.commit()
    finally:
        session.close()
    logger.info(
        "Database initialized",
        extra={
            "database_url": settings.database_url,
            "pool_size": settings.pool_size,
            "max_overflow": settings.max_overflow,
            "ivfflat_lists": settings.ivfflat_lists,
        },
    )
