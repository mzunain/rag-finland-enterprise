from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_chat_sessions_empty(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []

    resp = client.get("/chat/sessions")
    assert resp.status_code == 200
    assert resp.json()["sessions"] == []


def test_chat_sessions_with_data(client, mock_db_session):
    row = MagicMock()
    row.session_id = "abc123"
    row.first_message = "What is the leave policy?"
    row.message_count = 4
    row.last_active = "2025-01-15 10:00:00"
    row.collection = "HR-docs"
    mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [row]

    resp = client.get("/chat/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "abc123"
    assert sessions[0]["message_count"] == 4


def test_chat_history_returns_messages(client, mock_db_session):
    msg1 = MagicMock()
    msg1.id = 1
    msg1.role = "user"
    msg1.content = "Hello"
    msg1.language = "en"
    msg1.collection = "HR-docs"
    msg1.citations_json = []
    msg1.created_at = "2025-01-15 10:00:00"

    msg2 = MagicMock()
    msg2.id = 2
    msg2.role = "assistant"
    msg2.content = "Hi there"
    msg2.language = "en"
    msg2.collection = "HR-docs"
    msg2.citations_json = []
    msg2.created_at = "2025-01-15 10:00:01"

    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg1, msg2]

    resp = client.get("/chat/history/abc123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "abc123"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["answer_quality"]["outcome"] == "no_context"


def test_delete_session(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.delete.return_value = 6
    mock_db_session.commit = MagicMock()

    resp = client.delete("/chat/sessions/abc123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted_session"] == "abc123"
    assert data["messages_removed"] == 6


def test_chat_feedback_records_usage_and_audit(client, mock_db_session):
    from app.db import AnswerReview, AuditLog, UsageEvent

    resp = client.post(
        "/chat/feedback",
        json={
            "session_id": "abc123",
            "collection": "HR-docs",
            "question": "How many leave days?",
            "answer_excerpt": "Employees receive 25 annual leave days.",
            "rating": "needs_review",
            "reason": "Need HR to verify this policy version.",
            "language": "en",
            "citation_count": 1,
            "citations": [{"document": "HR-policy.pdf", "page": 2, "chunk_id": 12}],
            "answer_quality": {"outcome": "grounded", "source_confidence": 0.92, "confidence_label": "high"},
        },
    )

    assert resp.status_code == 200
    assert resp.json() == {"recorded": True, "rating": "needs_review"}
    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    usage = next(item for item in added if isinstance(item, UsageEvent))
    audit = next(item for item in added if isinstance(item, AuditLog))
    review = next(item for item in added if isinstance(item, AnswerReview))
    assert usage.event_type == "chat.feedback"
    assert usage.metadata_json["rating"] == "needs_review"
    assert review.status == "open"
    assert review.rating == "needs_review"
    assert review.collection == "HR-docs"
    assert review.citations_json == [{"document": "HR-policy.pdf", "page": 2, "chunk_id": 12}]
    assert audit.action == "chat.feedback"
    assert audit.collection == "HR-docs"
    mock_db_session.commit.assert_called()


@patch("app.main.ChatOpenAI")
@patch("app.main.OpenAIEmbeddings")
def test_chat_returns_session_id(mock_embeddings_cls, mock_llm_cls, client, mock_db_session):
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.0] * 1536
    mock_embeddings_cls.return_value = mock_embeddings
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = []

    resp = client.post("/chat", json={"question": "What is leave policy?", "collection": "HR-docs"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


@patch("app.main.ChatOpenAI")
@patch("app.main.OpenAIEmbeddings")
def test_chat_preserves_session_id(mock_embeddings_cls, mock_llm_cls, client, mock_db_session):
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.0] * 1536
    mock_embeddings_cls.return_value = mock_embeddings
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = []

    resp = client.post("/chat", json={"question": "Test?", "collection": "HR-docs", "session_id": "my-session-42"})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "my-session-42"
