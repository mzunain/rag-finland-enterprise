"""review to evaluation cases

Revision ID: 20260525_03
Revises: 20260525_02
Create Date: 2026-05-25 22:45:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260525_03"
down_revision = "20260525_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE answer_reviews ADD COLUMN IF NOT EXISTS citations_json JSON DEFAULT '[]'::json;")
    op.execute("ALTER TABLE answer_reviews ADD COLUMN IF NOT EXISTS promoted_eval_case_id VARCHAR(100);")
    op.execute("ALTER TABLE answer_reviews ADD COLUMN IF NOT EXISTS promoted_to_eval_at TIMESTAMP WITHOUT TIME ZONE;")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluation_cases (
            id SERIAL PRIMARY KEY,
            case_id VARCHAR(100) NOT NULL UNIQUE,
            review_id INTEGER,
            language VARCHAR(5) NOT NULL DEFAULT 'en',
            collection VARCHAR(100) NOT NULL,
            question TEXT NOT NULL,
            expectation VARCHAR(24) NOT NULL DEFAULT 'answer',
            required_citations_json JSON DEFAULT '[]'::json,
            notes_json JSON DEFAULT '{}'::json,
            status VARCHAR(24) NOT NULL DEFAULT 'active',
            created_by VARCHAR(64) NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_answer_reviews_promoted_eval_case_id ON answer_reviews (promoted_eval_case_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_cases_case_id ON evaluation_cases (case_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_cases_review_id ON evaluation_cases (review_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_cases_collection ON evaluation_cases (collection);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_cases_status ON evaluation_cases (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_cases_collection_status ON evaluation_cases (collection, status);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evaluation_cases_collection_status;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_cases_status;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_cases_collection;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_cases_review_id;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_cases_case_id;")
    op.execute("DROP INDEX IF EXISTS ix_answer_reviews_promoted_eval_case_id;")
    op.execute("DROP TABLE IF EXISTS evaluation_cases;")
    op.execute("ALTER TABLE answer_reviews DROP COLUMN IF EXISTS promoted_to_eval_at;")
    op.execute("ALTER TABLE answer_reviews DROP COLUMN IF EXISTS promoted_eval_case_id;")
    op.execute("ALTER TABLE answer_reviews DROP COLUMN IF EXISTS citations_json;")
