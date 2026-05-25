from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.security import CurrentUser


def _user(username="viewer", groups=None):
    return CurrentUser(
        username=username,
        role="viewer",
        collections={"HR-docs"},
        collection_permissions={"HR-docs": "read"},
        source_groups=set(groups or []),
    )


def test_retrieve_context_filters_restricted_source_acl_rows(mock_db_session):
    from app.main import _retrieve_context

    rows = [
        {
            "id": 1,
            "document_name": "executive.txt",
            "page": 1,
            "content": "Executive only.",
            "search_text": "",
            "metadata_json": {"source_acl": {"mode": "restricted", "allowed_users": ["owner@example.com"]}},
            "vector_score": 0.99,
        },
        {
            "id": 2,
            "document_name": "viewer.txt",
            "page": 1,
            "content": "Viewer allowed.",
            "search_text": "",
            "metadata_json": {"source_acl": {"mode": "restricted", "allowed_users": ["viewer"]}},
            "vector_score": 0.8,
        },
        {
            "id": 3,
            "document_name": "public.txt",
            "page": 1,
            "content": "Public policy.",
            "search_text": "",
            "metadata_json": {},
            "vector_score": 0.5,
        },
    ]
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = rows
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.0] * 1536

    with patch("app.main._build_embeddings", return_value=mock_embeddings):
        result = _retrieve_context("policy", "HR-docs", "en", _user(), mock_db_session)

    assert [row["document_name"] for row in result] == ["viewer.txt", "public.txt"]


def test_retrieve_context_allows_matching_source_group(mock_db_session):
    from app.main import _retrieve_context

    rows = [
        {
            "id": 1,
            "document_name": "legal.txt",
            "page": 1,
            "content": "Legal team only.",
            "search_text": "",
            "metadata_json": {"source_acl": {"mode": "restricted", "allowed_groups": ["legal-team"]}},
            "vector_score": 0.7,
        }
    ]
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = rows
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.0] * 1536

    with patch("app.main._build_embeddings", return_value=mock_embeddings):
        result = _retrieve_context("legal", "HR-docs", "en", _user(groups=["legal-team"]), mock_db_session)

    assert len(result) == 1
    assert result[0]["document_name"] == "legal.txt"


def test_source_acl_for_import_prefers_per_source_payload_acl():
    from app.main import ConnectorImportRequest, _source_acl_for_import

    source_url = "https://wiki.example.com/rest/api/content/12345"
    payload = ConnectorImportRequest(
        connector="confluence",
        collection="HR-docs",
        source_urls=[source_url],
        default_acl={"allowed_groups": ["everyone"]},
        source_acls={source_url: {"allowed_users": ["owner@example.com"]}},
    )

    acl = _source_acl_for_import(payload, source_url, {"source_acl": {"allowed_groups": ["source-team"]}})

    assert acl == {
        "mode": "restricted",
        "allowed_users": ["owner@example.com"],
        "allowed_groups": [],
    }
