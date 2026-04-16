"""Add DEFAULT gen_random_uuid() to chunks.id

Revision ID: 0001_chunks_id_default
Revises:
Create Date: 2026-04-16

Without this default, any INSERT into the chunks table that omits the id
column fails with a NotNullViolation.  The SQLAlchemy model already sets
default=uuid.uuid4 at the ORM level, but raw SQL inserts (e.g. from arlc
indexing scripts or bulk loaders) bypass the ORM and hit the constraint.
"""

from __future__ import annotations

revision = "0001_chunks_id_default"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    op.execute("ALTER TABLE chunks ALTER COLUMN id SET DEFAULT gen_random_uuid();")


def downgrade() -> None:
    from alembic import op

    op.execute("ALTER TABLE chunks ALTER COLUMN id DROP DEFAULT;")
