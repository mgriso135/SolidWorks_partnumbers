"""unique active external reference

Revision ID: 4e7b1c2a9d10
Revises: fac13fcea334
Create Date: 2026-10-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4e7b1c2a9d10"
down_revision: str | Sequence[str] | None = "fac13fcea334"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create a partial unique index for active external references."""
    op.create_index(
        "uq_items_tenant_external_ref_active",
        "items",
        ["tenant_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL AND status <> 'void'"),
        sqlite_where=sa.text("external_ref IS NOT NULL AND status <> 'void'"),
    )


def downgrade() -> None:
    """Drop the partial unique index."""
    op.drop_index("uq_items_tenant_external_ref_active", table_name="items")
