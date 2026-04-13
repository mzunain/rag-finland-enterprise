from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_collections(client, mock_db_session):
    row = MagicMock()
    row.name = "HR-docs"
    row.description = ""
    row.created_at = None
    mock_db_session.query.return_value.order_by.return_value.all.return_value = [row]

    resp = client.get("/admin/collections")
    assert resp.status_code == 200
    data = resp.json()
    assert "HR-docs" in data["collections"]
    assert "details" in data


def test_jobs_empty(client):
    resp = client.get("/admin/jobs")
    assert resp.status_code == 200
    assert resp.json() == {"jobs": []}


def test_jobs_returns_list(client, mock_db_session):
    mock_job = MagicMock()
    mock_job.id = 1
    mock_job.document_name = "test.pdf"
    mock_job.collection = "HR-docs"
    mock_job.status = "completed"
    mock_job.chunks_created = 5
    mock_job.error = None
    mock_db_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]

    resp = client.get("/admin/jobs")
    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["document_name"] == "test.pdf"
    assert jobs[0]["status"] == "completed"
    assert jobs[0]["chunks_created"] == 5


def test_chat_empty_question(client):
    resp = client.post("/chat", json={"question": "", "collection": "HR-docs"})
    assert resp.status_code == 400


def test_chat_whitespace_question(client):
    resp = client.post("/chat", json={"question": "   ", "collection": "HR-docs"})
    assert resp.status_code == 400


@patch("app.main.ChatOpenAI")
@patch("app.main.OpenAIEmbeddings")
def test_chat_no_results_english(mock_embeddings_cls, mock_llm_cls, client, mock_db_session):
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.0] * 1536
    mock_embeddings_cls.return_value = mock_embeddings
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = []

    resp = client.post("/chat", json={"question": "What is the leave policy?", "collection": "HR-docs"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "en"
    assert data["citations"] == []
    assert "couldn't find" in data["answer"].lower() or "information" in data["answer"].lower()


@patch("app.main.ChatOpenAI")
@patch("app.main.OpenAIEmbeddings")
def test_chat_with_results(mock_embeddings_cls, mock_llm_cls, client, mock_db_session):
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.0] * 1536
    mock_embeddings_cls.return_value = mock_embeddings

    mock_row = {
        "id": 1,
        "document_name": "policy.pdf",
        "page": 2,
        "content": "Annual leave is 25 days.",
        "search_text": "",
        "vector_score": 0.85,
    }
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = [mock_row]

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="You get 25 days of annual leave.")
    mock_llm_cls.return_value = mock_llm

    resp = client.post("/chat", json={"question": "What is the leave policy?", "collection": "HR-docs"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "en"
    assert len(data["citations"]) == 1
    assert data["citations"][0]["document"] == "policy.pdf"
    assert data["citations"][0]["page"] == 2
    assert "25 days" in data["answer"]


@patch("app.main.ChatOpenAI")
@patch("app.main.OpenAIEmbeddings")
def test_chat_finnish_detected(mock_embeddings_cls, mock_llm_cls, client, mock_db_session):
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.0] * 1536
    mock_embeddings_cls.return_value = mock_embeddings
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = []

    resp = client.post("/chat", json={"question": "Mitkä ovat yrityksen lomatiedot?", "collection": "HR-docs"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "fi"


@patch("app.main.OpenAIEmbeddings")
def test_chat_embedding_failure_finnish_fallback(mock_embeddings_cls, client, mock_db_session):
    mock_embeddings_cls.return_value.embed_query.side_effect = Exception("API error")
    mock_db_session.query.return_value.filter.return_value.limit.return_value.all.return_value = []

    resp = client.post("/chat", json={"question": "Mitkä ovat yrityksen lomatiedot?", "collection": "HR-docs"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "fi"


@patch("app.main.ChatOpenAI")
@patch("app.main.OpenAIEmbeddings")
def test_chat_swedish_detected(mock_embeddings_cls, mock_llm_cls, client, mock_db_session):
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.0] * 1536
    mock_embeddings_cls.return_value = mock_embeddings
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = []

    resp = client.post("/chat", json={"question": "Hur många semesterdagar har anställda?", "collection": "HR-docs"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "sv"
    assert "hitta" in data["answer"].lower() or "information" in data["answer"].lower()


@patch("app.main.OpenAIEmbeddings")
def test_upload_unsupported_file_type(mock_embeddings_cls, client, mock_db_session):
    mock_db_session.add = MagicMock()
    mock_db_session.commit = MagicMock()
    mock_db_session.refresh = MagicMock(side_effect=lambda obj: setattr(obj, "id", 1))

    resp = client.post(
        "/admin/upload",
        files={"file": ("test.xyz", b"some content", "application/octet-stream")},
        data={"collection": "HR-docs"},
    )
    assert resp.status_code == 400


@patch("app.main.OpenAIEmbeddings")
def test_upload_txt_success(mock_embeddings_cls, client, mock_db_session):
    mock_db_session.add = MagicMock()
    mock_db_session.commit = MagicMock()
    mock_db_session.refresh = MagicMock(side_effect=lambda obj: setattr(obj, "id", 1))

    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents.return_value = [[0.0] * 1536]
    mock_embeddings_cls.return_value = mock_embeddings

    resp = client.post(
        "/admin/upload",
        files={"file": ("test.txt", b"Hello world from a test document.", "text/plain")},
        data={"collection": "HR-docs"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["chunks"] >= 1
