import logging
import json

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint, create_engine, func
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
