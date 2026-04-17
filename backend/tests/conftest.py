from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def mock_db_session():
    session = MagicMock()
    session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    session.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    session.execute.return_value.mappings.return_value.all.return_value = []
    return session


@pytest.fixture()
def client(mock_db_session):
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    with patch("app.main.init_db"):
        from app.main import app, get_db
        from app.security import authenticate_user, create_access_token

        def _override_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = _override_db
        with TestClient(app) as c:
            user = authenticate_user("admin", "change-admin-password")
            assert user is not None
            token, _ = create_access_token(user)
            c.headers.update({"Authorization": f"Bearer {token}"})
            yield c
        app.dependency_overrides.clear()


@pytest.fixture()
def viewer_headers(client):
    from app.security import authenticate_user, create_access_token

    user = authenticate_user("viewer", "change-viewer-password")
    assert user is not None
    token, _ = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}
