from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.auth_utils import utc_now


def _source(**overrides):
    now = utc_now()
    data = {
        "id": 3,
        "collection": "HR-docs",
        "document_name": "policy.pdf",
        "source_url": "https://example.com/policy",
        "connector": "generic",
        "sync_status": "synced",
        "freshness_status": "fresh",
        "last_synced_at": now,
        "source_updated_at": now,
        "next_sync_at": now + timedelta(hours=24),
        "stale_after_days": 90,
        "sync_interval_hours": 24,
        "last_sync_error": "",
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_source_freshness_status_uses_age_and_failures(monkeypatch):
    from app.main import _source_freshness_status

    now = utc_now()
    monkeypatch.setattr("app.main.settings.source_aging_after_days", 30)

    assert _source_freshness_status(_source(source_updated_at=now - timedelta(days=5)), now) == "fresh"
    assert _source_freshness_status(_source(source_updated_at=now - timedelta(days=45)), now) == "aging"
    assert _source_freshness_status(_source(source_updated_at=now - timedelta(days=95)), now) == "stale"
    assert _source_freshness_status(_source(sync_status="failed"), now) == "failed"


def test_list_sources_returns_summary(client, mock_db_session):
    source = _source()
    query = MagicMock()
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [source]
    mock_db_session.query.return_value = query

    resp = client.get("/admin/sources")

    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"][0]["document_name"] == "policy.pdf"
    assert data["summary"]["total_sources"] == 1
    assert data["summary"]["fresh"] == 1


def test_sync_source_rejects_uploaded_sources(client, mock_db_session):
    source = _source(source_url="", connector="upload")
    mock_db_session.query.return_value.filter.return_value.first.return_value = source

    resp = client.post("/admin/sources/3/sync")

    assert resp.status_code == 400
    assert "connector-backed" in resp.json()["detail"]


@patch("app.main._build_embeddings")
@patch("app.main.fetch_connector_document")
def test_sync_source_refreshes_connector_chunks(mock_fetch, mock_embeddings, client, mock_db_session):
    from app.connectors import ConnectorDocument
    from app.db import DocumentChunk, IngestionJob

    source = _source()
    mock_db_session.query.return_value.filter.return_value.first.return_value = source
    mock_fetch.return_value = ConnectorDocument(
        source_url=source.source_url,
        title="policy.pdf",
        content="Annual leave is 25 days.",
        metadata={"connector": "generic", "http_last_modified": "Mon, 25 May 2026 10:00:00 GMT"},
    )
    mock_embeddings.return_value.embed_documents.return_value = [[0.0] * 1536]

    resp = client.post("/admin/sources/3/sync")

    assert resp.status_code == 200
    data = resp.json()
    assert data["chunks_created"] == 1
    assert data["source"]["sync_status"] == "synced"
    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    assert any(isinstance(item, IngestionJob) for item in added)
    assert any(isinstance(item, DocumentChunk) for item in added)
    mock_db_session.commit.assert_called()
