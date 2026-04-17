from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors import fetch_connector_document, sanitize_document_name


def test_sanitize_document_name_fallback_and_extension():
    assert sanitize_document_name("", fallback="fallback") == "fallback.txt"
    assert sanitize_document_name("Confluence policy page") == "Confluence-policy-page.txt"


def test_fetch_connector_document_html():
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html><head><title>HR Policy</title></head><body><h1>Annual Leave</h1></body></html>"
    mock_response.raise_for_status = MagicMock()

    with patch("app.connectors.httpx.Client") as client_cls:
        client_instance = client_cls.return_value.__enter__.return_value
        client_instance.get.return_value = mock_response

        doc = fetch_connector_document("confluence", "https://example.com/page", access_token="token")

    assert "HR-Policy" in doc.title
    assert "Annual Leave" in doc.content
    assert doc.metadata["connector"] == "confluence"


def test_fetch_connector_document_confluence_json():
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {
        "title": "Tietoturvakäytäntö",
        "body": {"storage": {"value": "<p>Salasanat pitää vaihtaa 90 päivän välein.</p>"}},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("app.connectors.httpx.Client") as client_cls:
        client_instance = client_cls.return_value.__enter__.return_value
        client_instance.get.return_value = mock_response

        doc = fetch_connector_document("confluence", "https://confluence.example.com/rest/api/content/123")

    assert doc.title.endswith(".txt")
    assert "Salasanat" in doc.content


def test_fetch_connector_document_empty_content_raises():
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/plain"}
    mock_response.text = "   "
    mock_response.raise_for_status = MagicMock()

    with patch("app.connectors.httpx.Client") as client_cls:
        client_instance = client_cls.return_value.__enter__.return_value
        client_instance.get.return_value = mock_response

        with pytest.raises(ValueError, match="empty content"):
            fetch_connector_document("generic", "https://example.com/empty")
