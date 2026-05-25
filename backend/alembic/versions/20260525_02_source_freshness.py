"""source freshness registry

Revision ID: 20260525_02
Revises: 20260525_01
Create Date: 2026-05-25 22:10:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260525_02"
down_revision = "20260525_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_sources (
            id SERIAL PRIMARY KEY,
            collection VARCHAR(100) NOT NULL,
            document_name VARCHAR(255) NOT NULL,
            source_url TEXT NOT NULL DEFAULT '',
            connector VARCHAR(32) NOT NULL DEFAULT 'upload',
            sync_status VARCHAR(24) NOT NULL DEFAULT 'synced',
            freshness_status VARCHAR(24) NOT NULL DEFAULT 'fresh',
            last_synced_at TIMESTAMP WITHOUT TIME ZONE,
            source_updated_at TIMESTAMP WITHOUT TIME ZONE,
            next_sync_at TIMESTAMP WITHOUT TIME ZONE,
            stale_after_days INTEGER NOT NULL DEFAULT 90,
            sync_interval_hours INTEGER NOT NULL DEFAULT 24,
            last_sync_error TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            CONSTRAINT uq_document_sources_collection_document UNIQUE (collection, document_name)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sources_collection ON document_sources (collection);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sources_document_name ON document_sources (document_name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sources_sync_status ON document_sources (sync_status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sources_freshness_status ON document_sources (freshness_status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sources_collection_freshness ON document_sources (collection, freshness_status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sources_sync_status_next_sync ON document_sources (sync_status, next_sync_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_sources_source_url ON document_sources (source_url);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_sources_source_url;")
    op.execute("DROP INDEX IF EXISTS ix_document_sources_sync_status_next_sync;")
    op.execute("DROP INDEX IF EXISTS ix_document_sources_collection_freshness;")
    op.execute("DROP INDEX IF EXISTS ix_document_sources_freshness_status;")
    op.execute("DROP INDEX IF EXISTS ix_document_sources_sync_status;")
    op.execute("DROP INDEX IF EXISTS ix_document_sources_document_name;")
    op.execute("DROP INDEX IF EXISTS ix_document_sources_collection;")
    op.execute("DROP TABLE IF EXISTS document_sources;")
