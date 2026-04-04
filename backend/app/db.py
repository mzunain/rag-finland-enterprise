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


def init_db() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_text TEXT DEFAULT '';")
