"""phase2 hardening baseline

Revision ID: 20260415_01
Revises:
Create Date: 2026-04-15 18:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260415_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            actor_username VARCHAR(64) NOT NULL,
            actor_role VARCHAR(16) NOT NULL,
            action VARCHAR(80) NOT NULL,
            resource_type VARCHAR(80) NOT NULL,
            resource_id VARCHAR(255),
            collection VARCHAR(100),
            request_id VARCHAR(64),
            metadata_json JSON DEFAULT '{}'::json,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_text TEXT DEFAULT '';")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_collection_document_name "
        "ON document_chunks (collection, document_name);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_collection_created_at "
        "ON document_chunks (collection, created_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_collection_status_created_at "
        "ON ingestion_jobs (collection, status, created_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_messages_session_created_at "
        "ON chat_messages (session_id, created_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_messages_collection_created_at "
        "ON chat_messages (collection, created_at);"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action_created_at ON audit_logs (action, created_at);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_created_at ON audit_logs (actor_username, created_at);"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_request_id ON audit_logs (request_id);")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_ivfflat "
        "ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat;")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_request_id;")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_actor_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_action_created_at;")
    op.execute("DROP TABLE IF EXISTS audit_logs;")

