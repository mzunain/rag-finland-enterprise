"""answer review center

Revision ID: 20260525_01
Revises: 20260415_02
Create Date: 2026-05-25 21:40:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260525_01"
down_revision = "20260415_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS answer_reviews (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL DEFAULT '',
            collection VARCHAR(100) NOT NULL,
            question TEXT NOT NULL DEFAULT '',
            answer_excerpt TEXT NOT NULL DEFAULT '',
            rating VARCHAR(24) NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            language VARCHAR(5),
            citation_count INTEGER NOT NULL DEFAULT 0,
            source_confidence DOUBLE PRECISION,
            confidence_label VARCHAR(24),
            answer_quality_json JSON DEFAULT '{}'::json,
            status VARCHAR(24) NOT NULL DEFAULT 'open',
            reviewer_note TEXT NOT NULL DEFAULT '',
            created_by VARCHAR(64) NOT NULL,
            resolved_by VARCHAR(64),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            resolved_at TIMESTAMP WITHOUT TIME ZONE
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_session_id ON answer_reviews (session_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_collection ON answer_reviews (collection);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_rating ON answer_reviews (rating);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_status ON answer_reviews (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_created_by ON answer_reviews (created_by);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_status_created_at ON answer_reviews (status, created_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_collection_status ON answer_reviews (collection, status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_rating_created_at ON answer_reviews (rating, created_at);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_rating_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_collection_status;")
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_status_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_created_by;")
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_status;")
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_rating;")
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_collection;")
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_session_id;")
    op.execute("DROP TABLE IF EXISTS answer_reviews;")
