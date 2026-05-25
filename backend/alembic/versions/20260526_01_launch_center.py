"""launch center settings

Revision ID: 20260526_01
Revises: 20260525_04
Create Date: 2026-05-26 09:30:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260526_01"
down_revision = "20260525_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS launch_settings (
            id SERIAL PRIMARY KEY,
            key VARCHAR(80) NOT NULL UNIQUE,
            value_json JSON DEFAULT '{}'::json,
            updated_by VARCHAR(64) NOT NULL DEFAULT 'system',
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_launch_settings_key ON launch_settings (key);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_launch_settings_key;")
    op.execute("DROP TABLE IF EXISTS launch_settings;")
