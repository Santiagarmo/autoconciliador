"""Pedido: the order created by the advisor after a WhatsApp payment."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum as SAEnum, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base, TimestampMixin
from app.domain.enums import EstadoPedido


class Pedido(Base, TimestampMixin):
    __tablename__ = "pedidos"
    __table_args__ = (
        CheckConstraint("monto_total > 0", name="ck_pedidos_monto_total_positivo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    codigo_pedido: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    cliente_whatsapp: Mapped[str] = mapped_column(String, nullable=False)
    monto_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estado_pedido: Mapped[EstadoPedido] = mapped_column(
        SAEnum(EstadoPedido, name="estado_pedido"),
        nullable=False,
        default=EstadoPedido.PENDIENTE_PAGO,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
