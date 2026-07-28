"""verificaciones_extracto: StatementVerifier verdicts per ingestion

Revision ID: 0003_verificaciones_extracto
Revises: 0002_usuarios
Create Date: 2026-07-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_verificaciones_extracto"
down_revision: Union[str, None] = "0002_usuarios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# create_type=False: created/dropped explicitly below (matches 0001/0002).
resultado_verificacion = postgresql.ENUM(
    "OK",
    "DISCREPANCIA",
    "NO_VERIFICABLE",
    "ERROR",
    name="resultado_verificacion",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    resultado_verificacion.create(bind, checkfirst=True)

    op.create_table(
        "verificaciones_extracto",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("banco", sa.String(), nullable=False),
        sa.Column("resultado", resultado_verificacion, nullable=False),
        sa.Column(
            "filas_emitidas", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "filas_candidatas", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("insertados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("omitidos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "hallazgos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("hash_extracto", sa.String(64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "revisado_por_llm",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("modelo_llm", sa.String(), nullable=True),
        sa.Column(
            "revision_llm", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verificaciones_extracto_created_at",
        "verificaciones_extracto",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_verificaciones_extracto_created_at",
        table_name="verificaciones_extracto",
    )
    op.drop_table("verificaciones_extracto")

    bind = op.get_bind()
    resultado_verificacion.drop(bind, checkfirst=True)
