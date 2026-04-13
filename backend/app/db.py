from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, func

from .config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    collection = Column(String(100), index=True)
    document_name = Column(String(255), index=True)
    page = Column(Integer, default=1)
    chunk_index = Column(Integer)
    content = Column(Text)
    metadata_json = Column(JSON, default={})
    search_text = Column(Text, default="", index=True)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

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

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), index=True, nullable=False)
    role = Column(String(10), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    language = Column(String(5), default="en")
    collection = Column(String(100), default="HR-docs")
    citations_json = Column(JSON, default=[])
    created_at = Column(DateTime, server_default=func.now())


_DEFAULT_COLLECTIONS = [
    ("HR-docs", "Human resources policies and procedures"),
    ("Legal-docs", "Legal documents and compliance"),
    ("Technical-docs", "Technical documentation and guides"),
]


def init_db() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_text TEXT DEFAULT '';")
    session = SessionLocal()
    try:
        for name, desc in _DEFAULT_COLLECTIONS:
            if not session.query(Collection).filter(Collection.name == name).first():
                session.add(Collection(name=name, description=desc))
        session.commit()
    finally:
        session.close()
