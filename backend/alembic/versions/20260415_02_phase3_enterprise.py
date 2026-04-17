"""phase3 enterprise access and quota tables

Revision ID: 20260415_02
Revises: 20260415_01
Create Date: 2026-04-15 20:30:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260415_02"
down_revision = "20260415_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_accounts (
            id SERIAL PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255),
            role VARCHAR(16) NOT NULL DEFAULT 'viewer',
            auth_provider VARCHAR(32) NOT NULL DEFAULT 'local',
            external_subject VARCHAR(255),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            monthly_quota INTEGER NOT NULL DEFAULT 10000,
            used_this_month INTEGER NOT NULL DEFAULT 0,
            quota_reset_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            last_login_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS collection_permissions (
            id SERIAL PRIMARY KEY,
            username VARCHAR(64) NOT NULL,
            collection VARCHAR(100) NOT NULL,
            can_read BOOLEAN NOT NULL DEFAULT TRUE,
            can_write BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            CONSTRAINT uq_collection_permissions_user_collection UNIQUE (username, collection)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            owner_username VARCHAR(64) NOT NULL,
            name VARCHAR(100) NOT NULL,
            key_prefix VARCHAR(24) NOT NULL,
            key_hash VARCHAR(128) NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            monthly_quota INTEGER NOT NULL DEFAULT 5000,
            used_this_month INTEGER NOT NULL DEFAULT 0,
            quota_reset_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            last_used_at TIMESTAMP WITHOUT TIME ZONE,
            expires_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_events (
            id SERIAL PRIMARY KEY,
            actor_username VARCHAR(64) NOT NULL,
            api_key_id INTEGER,
            event_type VARCHAR(64) NOT NULL,
            units INTEGER NOT NULL DEFAULT 1,
            metadata_json JSON DEFAULT '{}'::json,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_user_accounts_role_active ON user_accounts (role, is_active);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_accounts_external_subject ON user_accounts (external_subject);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_collection_permissions_collection_write ON collection_permissions (collection, can_write);"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_owner_active ON api_keys (owner_username, is_active);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_key_hash ON api_keys (key_hash);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_usage_events_actor_created_at ON usage_events (actor_username, created_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_usage_events_event_created_at ON usage_events (event_type, created_at);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_usage_events_event_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_usage_events_actor_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_api_keys_key_hash;")
    op.execute("DROP INDEX IF EXISTS ix_api_keys_owner_active;")
    op.execute("DROP INDEX IF EXISTS ix_collection_permissions_collection_write;")
    op.execute("DROP INDEX IF EXISTS ix_user_accounts_external_subject;")
    op.execute("DROP INDEX IF EXISTS ix_user_accounts_role_active;")

    op.execute("DROP TABLE IF EXISTS usage_events;")
    op.execute("DROP TABLE IF EXISTS api_keys;")
    op.execute("DROP TABLE IF EXISTS collection_permissions;")
    op.execute("DROP TABLE IF EXISTS user_accounts;")
