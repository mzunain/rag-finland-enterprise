from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def test_ai_provider_status_endpoint(client):
    resp = client.get("/admin/ai/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm_provider" in data
    assert "embedding_provider" in data


def test_connector_import_enforces_source_limit(client, monkeypatch):
    monkeypatch.setattr("app.main.settings.connector_max_sources_per_import", 1)

    resp = client.post(
        "/admin/connectors/import",
        json={
            "connector": "generic",
            "collection": "HR-docs",
            "source_urls": [
                "https://example.com/a",
                "https://example.com/b",
            ],
        },
    )
    assert resp.status_code == 400


@patch("app.main.fetch_connector_document")
@patch("app.main.OpenAIEmbeddings")
def test_connector_import_success(mock_embeddings_cls, mock_fetch, client, mock_db_session):
    mock_fetch.return_value = SimpleNamespace(
        source_url="https://example.com/policy",
        title="policy-import.txt",
        content="Tietoturvakäytäntö vaatii vahvan salasanan.",
        metadata={"connector": "generic"},
    )

    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents.return_value = [[0.0] * 1536]
    mock_embeddings_cls.return_value = mock_embeddings

    def _refresh(job):
        setattr(job, "id", 99)

    mock_db_session.refresh.side_effect = _refresh

    resp = client.post(
        "/admin/connectors/import",
        json={
            "connector": "generic",
            "collection": "HR-docs",
            "source_urls": ["https://example.com/policy"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["imported"]) == 1
    assert data["imported"][0]["job_id"] == 99
