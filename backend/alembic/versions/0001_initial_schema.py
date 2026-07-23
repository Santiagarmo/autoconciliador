"""initial schema: pedidos, pagos_declarados, movimientos_bancarios, conciliaciones

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# create_type=False: we create/drop these types explicitly in upgrade/downgrade,
# so create_table must not try to emit CREATE TYPE again (would duplicate).
estado_pedido = postgresql.ENUM(
    "PENDIENTE_PAGO",
    "EN_VERIFICACION",
    "LISTO_PARA_DESPACHO",
    "ALERTA_PAGO",
    "DESPACHADO",
    "CANCELADO",
    name="estado_pedido",
    create_type=False,
)
estado_pago = postgresql.ENUM(
    "REGISTRADO",
    "CONCILIADO",
    "RECHAZADO",
    "ALERTA_NO_ENCONTRADO",
    name="estado_pago",
    create_type=False,
)
estado_movimiento = postgresql.ENUM(
    "DISPONIBLE",
    "CONCILIADO",
    "NO_OPERATIVO",
    name="estado_movimiento",
    create_type=False,
)
tipo_conciliacion = postgresql.ENUM(
    "AUTOMATICA",
    "MANUAL_AUDITOR",
    name="tipo_conciliacion",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    estado_pedido.create(bind, checkfirst=True)
    estado_pago.create(bind, checkfirst=True)
    estado_movimiento.create(bind, checkfirst=True)
    tipo_conciliacion.create(bind, checkfirst=True)

    op.create_table(
        "pedidos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("codigo_pedido", sa.String(), nullable=False),
        sa.Column("cliente_whatsapp", sa.String(), nullable=False),
        sa.Column("monto_total", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "estado_pedido",
            estado_pedido,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "monto_total > 0", name="ck_pedidos_monto_total_positivo"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pedidos_codigo_pedido", "pedidos", ["codigo_pedido"], unique=True
    )

    op.create_table(
        "pagos_declarados",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pedido_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("banco_destino", sa.String(), nullable=False),
        sa.Column("monto_declarado", sa.Numeric(12, 2), nullable=False),
        sa.Column("numero_referencia", sa.String(), nullable=False),
        sa.Column("ultimos_4_digitos", sa.String(4), nullable=True),
        sa.Column("estado_pago", estado_pago, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "monto_declarado > 0", name="ck_pagos_monto_declarado_positivo"
        ),
        sa.ForeignKeyConstraint(
            ["pedido_id"], ["pedidos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "banco_destino", "numero_referencia", name="uq_banco_referencia"
        ),
    )
    op.create_index(
        "ix_pagos_declarados_pedido_id", "pagos_declarados", ["pedido_id"]
    )

    op.create_table(
        "movimientos_bancarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("banco_origen", sa.String(), nullable=False),
        sa.Column(
            "fecha_movimiento", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column("monto_real", sa.Numeric(12, 2), nullable=False),
        sa.Column("saldo_posterior", sa.Numeric(12, 2), nullable=False),
        sa.Column("numero_referencia", sa.String(), nullable=True),
        sa.Column("descripcion_concepto", sa.Text(), nullable=False),
        sa.Column("hash_idempotencia", sa.String(64), nullable=False),
        sa.Column("estado_movimiento", estado_movimiento, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hash_idempotencia", name="uq_movimientos_hash_idempotencia"
        ),
    )

    op.create_table(
        "conciliaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pago_declarado_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "movimiento_bancario_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("tipo_conciliacion", tipo_conciliacion, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pago_declarado_id"], ["pagos_declarados.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["movimiento_bancario_id"],
            ["movimientos_bancarios.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pago_declarado_id", name="uq_conciliaciones_pago_declarado_id"
        ),
        sa.UniqueConstraint(
            "movimiento_bancario_id",
            name="uq_conciliaciones_movimiento_bancario_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("conciliaciones")
    op.drop_table("movimientos_bancarios")
    op.drop_index("ix_pagos_declarados_pedido_id", table_name="pagos_declarados")
    op.drop_table("pagos_declarados")
    op.drop_index("ix_pedidos_codigo_pedido", table_name="pedidos")
    op.drop_table("pedidos")

    bind = op.get_bind()
    tipo_conciliacion.drop(bind, checkfirst=True)
    estado_movimiento.drop(bind, checkfirst=True)
    estado_pago.drop(bind, checkfirst=True)
    estado_pedido.drop(bind, checkfirst=True)
