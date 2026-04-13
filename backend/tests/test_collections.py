from __future__ import annotations

from unittest.mock import MagicMock


def test_collections_list(client, mock_db_session):
    row = MagicMock()
    row.name = "HR-docs"
    row.description = "Human resources"
    row.created_at = None
    mock_db_session.query.return_value.order_by.return_value.all.return_value = [row]

    resp = client.get("/admin/collections")
    assert resp.status_code == 200
    data = resp.json()
    assert "HR-docs" in data["collections"]
    assert len(data["details"]) == 1
    assert data["details"][0]["description"] == "Human resources"


def test_create_collection(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    mock_db_session.add = MagicMock()
    mock_db_session.commit = MagicMock()

    resp = client.post("/admin/collections", json={"name": "Finance-docs", "description": "Financial records"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Finance-docs"


def test_create_collection_duplicate(client, mock_db_session):
    existing = MagicMock()
    mock_db_session.query.return_value.filter.return_value.first.return_value = existing

    resp = client.post("/admin/collections", json={"name": "HR-docs"})
    assert resp.status_code == 409


def test_create_collection_empty_name(client, mock_db_session):
    resp = client.post("/admin/collections", json={"name": "  "})
    assert resp.status_code == 400


def test_delete_collection(client, mock_db_session):
    coll = MagicMock()
    mock_db_session.query.return_value.filter.return_value.first.return_value = coll
    mock_db_session.query.return_value.filter.return_value.delete.return_value = 10
    mock_db_session.delete = MagicMock()
    mock_db_session.commit = MagicMock()

    resp = client.delete("/admin/collections/HR-docs")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == "HR-docs"


def test_delete_collection_not_found(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    resp = client.delete("/admin/collections/nonexistent")
    assert resp.status_code == 404
