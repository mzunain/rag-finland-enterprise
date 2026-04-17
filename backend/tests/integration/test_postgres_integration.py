from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 and INTEGRATION_DATABASE_URL to run PostgreSQL integration tests",
)


def _engine():
    database_url = os.getenv("INTEGRATION_DATABASE_URL")
    if not database_url:
        pytest.skip("INTEGRATION_DATABASE_URL is not set")
    return create_engine(database_url)


def test_postgres_connection_and_tables_exist():
    engine = _engine()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar() == 1

    inspector = inspect(engine)
    expected_tables = {
        "document_chunks",
        "ingestion_jobs",
        "collections",
        "chat_messages",
        "audit_logs",
        "user_accounts",
        "collection_permissions",
        "api_keys",
        "usage_events",
    }
    existing = set(inspector.get_table_names())
    missing = expected_tables - existing
    assert not missing, f"Missing expected tables: {sorted(missing)}"
