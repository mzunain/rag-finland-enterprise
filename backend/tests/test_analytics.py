from __future__ import annotations

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
