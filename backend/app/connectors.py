from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlparse

import httpx

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass
class ConnectorDocument:
    source_url: str
    title: str
    content: str
    metadata: dict


def sanitize_document_name(value: str, fallback: str = "connector-document") -> str:
    text = (value or "").strip()
    if not text:
        text = fallback
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")
    if not text:
        text = fallback
    if len(text) > 180:
        text = text[:180].rstrip("-")
    if "." not in text:
        text = f"{text}.txt"
    return text


def _strip_html(value: str) -> str:
    text = _TAG_RE.sub(" ", value)
    text = unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _extract_title_from_html(html_text: str) -> str:
    match = _TITLE_RE.search(html_text)
    if match:
        return _strip_html(match.group(1))
    return ""


def _safe_json_get(data: dict, path: list[str]) -> str:
    node = data
    for key in path:
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return ""
    return node if isinstance(node, str) else ""


def _string_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _extract_acl_from_json(payload: dict) -> dict:
    candidates = [
        payload.get("source_acl"),
        payload.get("acl"),
        payload.get("permissions"),
        payload.get("restrictions"),
    ]
    acl_source = next((item for item in candidates if isinstance(item, dict)), {})
    if not isinstance(acl_source, dict):
        acl_source = {}

    users = (
        _string_list(acl_source.get("allowed_users"))
        or _string_list(acl_source.get("allowedUsers"))
        or _string_list(acl_source.get("users"))
    )
    groups = (
        _string_list(acl_source.get("allowed_groups"))
        or _string_list(acl_source.get("allowedGroups"))
        or _string_list(acl_source.get("groups"))
    )

    if not users and not groups:
        return {}
    return {"allowed_users": sorted(set(users)), "allowed_groups": sorted(set(groups))}


def _normalize_document(connector: str, source_url: str, response: httpx.Response) -> ConnectorDocument:
    content_type = (response.headers.get("content-type") or "").lower()
    transport_metadata = {
        key: value
        for key, value in {
            "http_last_modified": response.headers.get("last-modified"),
            "http_etag": response.headers.get("etag"),
        }.items()
        if value
    }

    if "application/json" in content_type:
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Connector response JSON must be an object")

        if connector == "confluence":
            title = _safe_json_get(payload, ["title"]) or "confluence-page"
            html_body = _safe_json_get(payload, ["body", "storage", "value"])
            body = _strip_html(html_body) if html_body else _strip_html(str(payload))
            acl = _extract_acl_from_json(payload)
            return ConnectorDocument(
                source_url=source_url,
                title=sanitize_document_name(title, fallback="confluence-page.txt"),
                content=body,
                metadata={"connector": "confluence", "raw_title": title, **transport_metadata, **({"source_acl": acl} if acl else {})},
            )

        if connector == "sharepoint":
            title = _safe_json_get(payload, ["name"]) or _safe_json_get(payload, ["title"]) or "sharepoint-document"
            body = _safe_json_get(payload, ["content"]) or _safe_json_get(payload, ["body"]) or _strip_html(str(payload))
            acl = _extract_acl_from_json(payload)
            return ConnectorDocument(
                source_url=source_url,
                title=sanitize_document_name(title, fallback="sharepoint-document.txt"),
                content=body,
                metadata={"connector": "sharepoint", "raw_title": title, **transport_metadata, **({"source_acl": acl} if acl else {})},
            )

        title = _safe_json_get(payload, ["title"]) or "connector-json"
        body = _safe_json_get(payload, ["content"]) or _safe_json_get(payload, ["body"]) or _strip_html(str(payload))
        acl = _extract_acl_from_json(payload)
        return ConnectorDocument(
            source_url=source_url,
            title=sanitize_document_name(title, fallback="connector-json.txt"),
            content=body,
            metadata={"connector": connector, "raw_title": title, **transport_metadata, **({"source_acl": acl} if acl else {})},
        )

    raw_text = response.text
    if "text/html" in content_type or "<html" in raw_text.lower():
        title = _extract_title_from_html(raw_text) or urlparse(source_url).path.rsplit("/", 1)[-1] or connector
        content = _strip_html(raw_text)
    else:
        title = urlparse(source_url).path.rsplit("/", 1)[-1] or connector
        content = raw_text.strip()

    return ConnectorDocument(
        source_url=source_url,
        title=sanitize_document_name(title, fallback=f"{connector}-document.txt"),
        content=content,
        metadata={"connector": connector, "content_type": content_type, **transport_metadata},
    )


def fetch_connector_document(
    connector: str,
    source_url: str,
    *,
    access_token: str | None = None,
    timeout_seconds: int = 20,
) -> ConnectorDocument:
    headers = {"User-Agent": "rag-finland-enterprise/1.0"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(source_url, headers=headers)
    response.raise_for_status()

    document = _normalize_document(connector, source_url, response)
    if not document.content:
        raise ValueError(f"Connector source '{source_url}' returned empty content")
    return document
