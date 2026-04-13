from __future__ import annotations

from unittest.mock import MagicMock


def test_list_documents_empty(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []

    resp = client.get("/admin/documents?collection=HR-docs")
    assert resp.status_code == 200
    assert resp.json()["documents"] == []


def test_list_documents_with_results(client, mock_db_session):
    row = MagicMock()
    row.document_name = "policy.pdf"
    row.chunk_count = 12
    row.max_page = 5
    row.created_at = "2025-01-15 10:00:00"
    mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [row]

    resp = client.get("/admin/documents?collection=HR-docs")
    assert resp.status_code == 200
    docs = resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["document_name"] == "policy.pdf"
    assert docs[0]["chunk_count"] == 12


def test_delete_document(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.delete.return_value = 5
    mock_db_session.commit = MagicMock()

    resp = client.delete("/admin/documents/test.pdf?collection=HR-docs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] == "test.pdf"
    assert data["chunks_removed"] == 5


def test_document_chunks_empty(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    mock_db_session.query.return_value.filter.return_value.scalar.return_value = 0

    resp = client.get("/admin/documents/test.pdf/chunks?collection=HR-docs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_chunks"] == 0
    assert data["chunks"] == []


def test_stats_endpoint(client, mock_db_session):
    mock_db_session.query.return_value.scalar.return_value = 0
    mock_db_session.query.return_value.group_by.return_value.all.return_value = []

    resp = client.get("/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_documents" in data
    assert "total_chunks" in data
    assert "collections" in data
