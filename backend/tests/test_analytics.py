from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def test_analytics_endpoint(client, mock_db_session):
    mock_db_session.query.return_value.scalar.return_value = 0
    mock_db_session.query.return_value.filter.return_value.scalar.return_value = 0
    mock_db_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    resp = client.get("/admin/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_messages" in data
    assert "total_sessions" in data
    assert "user_queries" in data
    assert "language_breakdown" in data
    assert "collection_usage" in data
    assert "recent_queries" in data
    assert data["answer_quality"]["grounded_rate"] == 0
    assert data["answer_quality"]["by_collection"] == []
    assert data["answer_feedback"]["total_feedback"] == 0


def test_answer_quality_summary_groups_grounded_and_no_context_events():
    from app.main import _build_answer_quality_summary

    events = [
        SimpleNamespace(
            metadata_json={
                "collection": "HR-docs",
                "outcome": "grounded",
                "citation_count": 3,
                "source_confidence": 0.72,
            }
        ),
        SimpleNamespace(
            metadata_json={
                "collection": "HR-docs",
                "outcome": "no_context",
                "citation_count": 0,
                "source_confidence": 0,
            }
        ),
        SimpleNamespace(
            metadata_json={
                "collection": "Legal-docs",
                "outcome": "grounded",
                "citation_count": 1,
                "source_confidence": 0.28,
            }
        ),
    ]

    summary = _build_answer_quality_summary(events)

    assert summary["total_chat_events"] == 3
    assert summary["grounded_answers"] == 2
    assert summary["no_context_answers"] == 1
    assert summary["grounded_rate"] == 67
    assert summary["no_context_rate"] == 33
    assert summary["low_confidence_answers"] == 1
    assert summary["average_citations"] == 1.33
    assert summary["by_collection"][0]["collection"] == "Legal-docs"
    assert summary["by_collection"][1]["collection"] == "HR-docs"


def test_feedback_summary_groups_review_signals_by_collection():
    from app.main import _build_feedback_summary

    events = [
        SimpleNamespace(metadata_json={"collection": "HR-docs", "rating": "helpful"}),
        SimpleNamespace(metadata_json={"collection": "HR-docs", "rating": "needs_review"}),
        SimpleNamespace(metadata_json={"collection": "Legal-docs", "rating": "not_helpful"}),
    ]

    summary = _build_feedback_summary(events)

    assert summary["total_feedback"] == 3
    assert summary["helpful"] == 1
    assert summary["needs_review"] == 1
    assert summary["not_helpful"] == 1
    assert summary["helpful_rate"] == 33
    assert summary["review_rate"] == 67
    assert summary["by_collection"][0]["collection"] == "Legal-docs"
    assert summary["by_collection"][0]["review_rate"] == 100
