"""usuarios: authentication table with role enum (Phase 4)

Revision ID: 0002_usuarios
Revises: 0001_initial
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_usuarios"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# create_type=False: created/dropped explicitly below so create_table won't
# emit a duplicate CREATE TYPE (matches 0001_initial_schema convention).
rol_usuario = postgresql.ENUM(
    "ASESOR",
    "AUDITOR",
    name="rol_usuario",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    rol_usuario.create(bind, checkfirst=True)

    op.create_table(
        "usuarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("rol", rol_usuario, nullable=False),
        sa.Column(
            "activo",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")

    bind = op.get_bind()
    rol_usuario.drop(bind, checkfirst=True)
