from __future__ import annotations

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
    with patch("app.main.init_db"):
        from app.main import app, get_db

        def _override_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = _override_db
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()
