"""Add partial unique index on conversation_messages(user_id, conversation_id, trace_id)

Revision ID: 0002_convmsg_trace_unique
Revises: 0001_chunks_id_default
Create Date: 2026-04-21

Prevents duplicate rows when save_turn() fires twice for the same query
(SSE reconnect, network retry, double-click). The partial index covers only
rows where trace_id IS NOT NULL, so legacy rows without a trace_id are
unaffected.
"""

from __future__ import annotations

revision = "0002_convmsg_trace_unique"
down_revision = "0001_chunks_id_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    op.execute(
        """
        CREATE UNIQUE INDEX ix_convmsg_user_conv_trace_uq
            ON conversation_messages (user_id, conversation_id, trace_id)
            WHERE trace_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    from alembic import op

    op.execute("DROP INDEX IF EXISTS ix_convmsg_user_conv_trace_uq;")
