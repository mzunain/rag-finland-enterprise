from __future__ import annotations

import logging
import uuid
from typing import Literal

import json

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sse_starlette.sse import EventSourceResponse
from langdetect import detect
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from sqlalchemy import func as sa_func

from .db import ChatMessage, Collection, DocumentChunk, IngestionJob, SessionLocal, init_db
from .finnish import finnish_search_text, stem_overlap_ratio
from .ingestion import chunk_pages, extract_text

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Finland Enterprise MVP")

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    init_db()


class ChatRequest(BaseModel):
    question: str
    collection: str = "HR-docs"
    session_id: str = ""


class ChatResponse(BaseModel):
    answer: str
    language: Literal["fi", "en"]
    citations: list[dict]
    session_id: str = ""


@app.get("/health")
def health():
    return {"status": "ok"}


class CollectionCreate(BaseModel):
    name: str
    description: str = ""


@app.get("/admin/collections")
def collections(db: Session = Depends(get_db)):
    rows = db.query(Collection).order_by(Collection.name).all()
    return {
        "collections": [r.name for r in rows],
        "details": [
            {"name": r.name, "description": r.description, "created_at": str(r.created_at) if r.created_at else None}
            for r in rows
        ],
    }


@app.post("/admin/collections")
def create_collection(payload: CollectionCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Collection name is required")
    existing = db.query(Collection).filter(Collection.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Collection '{name}' already exists")
    coll = Collection(name=name, description=payload.description)
    db.add(coll)
    db.commit()
    logger.info("Collection created: %s", name)
    return {"name": name, "description": payload.description}


@app.delete("/admin/collections/{name}")
def delete_collection(name: str, db: Session = Depends(get_db)):
    coll = db.query(Collection).filter(Collection.name == name).first()
    if not coll:
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")
    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.collection == name).delete()
    db.query(IngestionJob).filter(IngestionJob.collection == name).delete()
    db.delete(coll)
    db.commit()
    logger.info("Collection deleted: %s (%d chunks removed)", name, chunk_count)
    return {"deleted": name, "chunks_removed": chunk_count}


@app.get("/admin/jobs")
def jobs(db: Session = Depends(get_db)):
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
def list_documents(collection: str = "HR-docs", db: Session = Depends(get_db)):
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
def delete_document(document_name: str, collection: str = "HR-docs", db: Session = Depends(get_db)):
    count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.collection == collection, DocumentChunk.document_name == document_name)
        .delete()
    )
    db.query(IngestionJob).filter(
        IngestionJob.collection == collection, IngestionJob.document_name == document_name
    ).delete()
    db.commit()
    logger.info("Deleted document: %s from %s (%d chunks)", document_name, collection, count)
    return {"deleted": document_name, "chunks_removed": count}


@app.get("/admin/documents/{document_name}/chunks")
def document_chunks(
    document_name: str, collection: str = "HR-docs", page: int = 1, db: Session = Depends(get_db)
):
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
def admin_stats(db: Session = Depends(get_db)):
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
def analytics(db: Session = Depends(get_db)):
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
def chat_sessions(db: Session = Depends(get_db)):
    subq = (
        db.query(
            ChatMessage.session_id,
            sa_func.min(ChatMessage.content).label("first_message"),
            sa_func.count(ChatMessage.id).label("message_count"),
            sa_func.max(ChatMessage.created_at).label("last_active"),
            sa_func.min(ChatMessage.collection).label("collection"),
        )
        .filter(ChatMessage.role == "user")
        .group_by(ChatMessage.session_id)
        .order_by(sa_func.max(ChatMessage.created_at).desc())
        .limit(30)
        .all()
    )
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
def chat_history(session_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
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
def delete_session(session_id: str, db: Session = Depends(get_db)):
    count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
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
async def upload_document(
    file: UploadFile = File(...),
    collection: str = Form("HR-docs"),
    db: Session = Depends(get_db),
):
    content = await file.read()
    logger.info("Upload started: %s -> collection=%s (%d bytes)", file.filename, collection, len(content))
    job = IngestionJob(document_name=file.filename, collection=collection, status="processing")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        pages = extract_text(file.filename, content)
        chunks = chunk_pages(pages)
        embeddings = OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)

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
        db.commit()
        logger.info("Upload completed: %s -> %d chunks", file.filename, len(chunks))
        return {"job_id": job.id, "chunks": len(chunks), "status": "completed"}
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        db.commit()
        logger.error("Upload failed: %s -> %s", file.filename, exc)
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {exc}") from exc


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    session_id = payload.session_id or uuid.uuid4().hex[:16]
    logger.info("Chat query: session=%s collection=%s question_len=%d", session_id, payload.collection, len(question))

    try:
        lang = detect(question)
    except Exception:
        lang = "en"
    language: Literal["fi", "en"] = "fi" if lang == "fi" else "en"

    top_rows = []
    try:
        embeddings = OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
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

        rows = db.execute(sql, {"query_vector": q_emb, "collection": payload.collection}).mappings().all()

        ranked = []
        for r in rows:
            lexical_boost = 0.0
            if language == "fi":
                lexical_boost = 0.20 * stem_overlap_ratio(question, r["search_text"] or "")
            ranked.append({**r, "score": float(r["vector_score"]) + lexical_boost})

        ranked.sort(key=lambda x: x["score"], reverse=True)
        top_rows = ranked[:5]
    except Exception:
        if language == "fi":
            top_rows = _lexical_fallback_rows(db, payload.collection, question)

    if not top_rows:
        msg = (
            "En löytänyt tietoa valitusta kokoelmasta." if language == "fi" else "I couldn't find relevant information in that collection."
        )
        db.add(ChatMessage(session_id=session_id, role="user", content=question, language=language, collection=payload.collection))
        db.add(ChatMessage(session_id=session_id, role="assistant", content=msg, language=language, collection=payload.collection, citations_json=[]))
        db.commit()
        return ChatResponse(answer=msg, language=language, citations=[], session_id=session_id)

    context = "\n\n".join([f"[{r['document_name']} p.{r['page']}] {r['content']}" for r in top_rows])
    sys_fi = "Vastaa suomeksi käyttäjän kysymykseen käyttäen vain annettua kontekstia."
    sys_en = "Answer in English using only the provided context."
    prompt = (
        f"System: {sys_fi if language == 'fi' else sys_en}\n"
        f"Question: {question}\n"
        f"Context:\n{context}\n"
        "Include concise answer and mention if policy details are missing."
    )

    llm = ChatOpenAI(model=settings.model_name, api_key=settings.openai_api_key, temperature=0)
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
    db.add(ChatMessage(session_id=session_id, role="assistant", content=result.content, language=language, collection=payload.collection, citations_json=citations))
    db.commit()

    return ChatResponse(answer=result.content, language=language, citations=citations, session_id=session_id)


def _retrieve_context(question: str, collection: str, language: str, db: Session):
    """Shared retrieval logic for both sync and streaming chat."""
    top_rows = []
    try:
        embeddings = OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
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
        rows = db.execute(sql, {"query_vector": q_emb, "collection": collection}).mappings().all()
        ranked = []
        for r in rows:
            lexical_boost = 0.0
            if language == "fi":
                lexical_boost = 0.20 * stem_overlap_ratio(question, r["search_text"] or "")
            ranked.append({**r, "score": float(r["vector_score"]) + lexical_boost})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        top_rows = ranked[:5]
    except Exception:
        if language == "fi":
            top_rows = _lexical_fallback_rows(db, collection, question)
    return top_rows


@app.post("/chat/stream")
async def chat_stream(request: Request, payload: ChatRequest, db: Session = Depends(get_db)):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    session_id = payload.session_id or uuid.uuid4().hex[:16]
    logger.info("Stream chat: session=%s collection=%s", session_id, payload.collection)

    try:
        lang = detect(question)
    except Exception:
        lang = "en"
    language: Literal["fi", "en"] = "fi" if lang == "fi" else "en"

    top_rows = _retrieve_context(question, payload.collection, language, db)

    citations = [
        {"document": r["document_name"], "page": r["page"], "relevance": round(float(r["score"]), 4), "chunk_id": r["id"]}
        for r in top_rows
    ]

    if not top_rows:
        msg = "En löytänyt tietoa valitusta kokoelmasta." if language == "fi" else "I couldn't find relevant information in that collection."
        db.add(ChatMessage(session_id=session_id, role="user", content=question, language=language, collection=payload.collection))
        db.add(ChatMessage(session_id=session_id, role="assistant", content=msg, language=language, collection=payload.collection, citations_json=[]))
        db.commit()

        async def no_results_gen():
            yield {"event": "metadata", "data": json.dumps({"session_id": session_id, "language": language, "citations": []})}
            yield {"event": "token", "data": msg}
            yield {"event": "done", "data": ""}

        return EventSourceResponse(no_results_gen())

    context = "\n\n".join([f"[{r['document_name']} p.{r['page']}] {r['content']}" for r in top_rows])
    sys_msg = "Vastaa suomeksi käyttäjän kysymykseen käyttäen vain annettua kontekstia." if language == "fi" else "Answer in English using only the provided context."
    prompt = f"System: {sys_msg}\nQuestion: {question}\nContext:\n{context}\nInclude concise answer and mention if policy details are missing."

    async def stream_gen():
        yield {"event": "metadata", "data": json.dumps({"session_id": session_id, "language": language, "citations": citations})}
        full_text = ""
        llm = ChatOpenAI(model=settings.model_name, api_key=settings.openai_api_key, temperature=0, streaming=True)
        async for chunk in llm.astream(prompt):
            if await request.is_disconnected():
                break
            token = chunk.content
            if token:
                full_text += token
                yield {"event": "token", "data": token}
        db.add(ChatMessage(session_id=session_id, role="user", content=question, language=language, collection=payload.collection))
        db.add(ChatMessage(session_id=session_id, role="assistant", content=full_text, language=language, collection=payload.collection, citations_json=citations))
        db.commit()
        yield {"event": "done", "data": ""}

    return EventSourceResponse(stream_gen())
