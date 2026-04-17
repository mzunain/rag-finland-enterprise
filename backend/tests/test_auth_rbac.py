from __future__ import annotations


def test_login_success(client):
    resp = client.post("/auth/token", data={"username": "admin", "password": "change-admin-password"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_failure(client):
    resp = client.post("/auth/token", data={"username": "admin", "password": "wrong-password"})
    assert resp.status_code == 401


def test_protected_endpoint_requires_auth(client):
    resp = client.get("/admin/collections", headers={"Authorization": ""})
    assert resp.status_code == 401


def test_viewer_can_read_allowed_collection(client, mock_db_session, viewer_headers):
    mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/admin/documents?collection=HR-docs", headers=viewer_headers)
    assert resp.status_code == 200


def test_viewer_blocked_from_disallowed_collection(client, viewer_headers):
    resp = client.get("/admin/documents?collection=Legal-docs", headers=viewer_headers)
    assert resp.status_code == 403


def test_viewer_cannot_create_collection(client, viewer_headers):
    resp = client.post("/admin/collections", json={"name": "Finance-docs"}, headers=viewer_headers)
    assert resp.status_code == 403
