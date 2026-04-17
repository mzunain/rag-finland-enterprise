from __future__ import annotations


def test_v1_health_alias(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_v1_auth_me_alias(client):
    resp = client.get("/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["api_version"] == "v1"


def test_admin_users_list_empty(client, mock_db_session):
    mock_db_session.query.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    assert resp.json() == {"users": []}


def test_admin_create_user_requires_collection_for_non_admin(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    resp = client.post(
        "/admin/users",
        json={
            "username": "analyst",
            "password": "very-secure-password",
            "role": "viewer",
            "collections": [],
            "write_collections": [],
        },
    )
    assert resp.status_code == 400


def test_admin_create_api_key_missing_user(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    resp = client.post(
        "/admin/api-keys",
        json={
            "owner_username": "missing-user",
            "name": "integration-key",
            "monthly_quota": 1000,
        },
    )
    assert resp.status_code == 404
