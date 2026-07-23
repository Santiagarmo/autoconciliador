"""MovimientoBancario: the source of truth parsed from the bank PDF."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base, TimestampMixin
from app.domain.enums import EstadoMovimiento


class MovimientoBancario(Base, TimestampMixin):
    __tablename__ = "movimientos_bancarios"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    banco_origen: Mapped[str] = mapped_column(String, nullable=False)
    fecha_movimiento: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    monto_real: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    saldo_posterior: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    numero_referencia: Mapped[str | None] = mapped_column(String, nullable=True)
    descripcion_concepto: Mapped[str] = mapped_column(Text, nullable=False)
    # SHA256(fecha + monto + saldo_posterior + descripcion_limpia); guarantees
    # idempotent PDF re-ingestion. Computed in the ingestion service (Phase 3).
    hash_idempotencia: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    estado_movimiento: Mapped[EstadoMovimiento] = mapped_column(
        SAEnum(EstadoMovimiento, name="estado_movimiento"),
        nullable=False,
        default=EstadoMovimiento.DISPONIBLE,
    )
