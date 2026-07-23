"""PagoDeclarado: what the advisor declares from the WhatsApp receipt."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.domain.enums import EstadoPago


class PagoDeclarado(Base, TimestampMixin):
    __tablename__ = "pagos_declarados"
    __table_args__ = (
        # Core anti-fraud rule: a receipt reference cannot be reused per bank.
        UniqueConstraint(
            "banco_destino", "numero_referencia", name="uq_banco_referencia"
        ),
        CheckConstraint(
            "monto_declarado > 0", name="ck_pagos_monto_declarado_positivo"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pedidos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    banco_destino: Mapped[str] = mapped_column(String, nullable=False)
    monto_declarado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    numero_referencia: Mapped[str] = mapped_column(String, nullable=False)
    ultimos_4_digitos: Mapped[str | None] = mapped_column(String(4), nullable=True)
    estado_pago: Mapped[EstadoPago] = mapped_column(
        SAEnum(EstadoPago, name="estado_pago"),
        nullable=False,
        default=EstadoPago.REGISTRADO,
    )
