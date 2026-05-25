"""evaluation run history

Revision ID: 20260525_04
Revises: 20260525_03
Create Date: 2026-05-25 23:25:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260525_04"
down_revision = "20260525_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluation_runs (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(64) NOT NULL UNIQUE,
            collection VARCHAR(100) NOT NULL DEFAULT '',
            status VARCHAR(24) NOT NULL DEFAULT 'completed',
            total_cases INTEGER NOT NULL DEFAULT 0,
            passed_cases INTEGER NOT NULL DEFAULT 0,
            case_pass_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
            citation_recall DOUBLE PRECISION NOT NULL DEFAULT 0,
            grounded_accuracy DOUBLE PRECISION NOT NULL DEFAULT 0,
            no_answer_accuracy DOUBLE PRECISION NOT NULL DEFAULT 0,
            passed BOOLEAN NOT NULL DEFAULT FALSE,
            report_json JSON DEFAULT '{}'::json,
            created_by VARCHAR(64) NOT NULL,
            started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITHOUT TIME ZONE
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_runs_run_id ON evaluation_runs (run_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_runs_collection ON evaluation_runs (collection);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_runs_status ON evaluation_runs (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_runs_passed ON evaluation_runs (passed);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_runs_collection_started_at ON evaluation_runs (collection, started_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_runs_status_started_at ON evaluation_runs (status, started_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_evaluation_runs_passed_started_at ON evaluation_runs (passed, started_at);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evaluation_runs_passed_started_at;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_runs_status_started_at;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_runs_collection_started_at;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_runs_passed;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_runs_status;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_runs_collection;")
    op.execute("DROP INDEX IF EXISTS ix_evaluation_runs_run_id;")
    op.execute("DROP TABLE IF EXISTS evaluation_runs;")
