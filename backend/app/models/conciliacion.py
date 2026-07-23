"""Conciliacion: bridge / audit log linking one payment to one bank movement."""
from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.domain.enums import TipoConciliacion


class Conciliacion(Base, TimestampMixin):
    __tablename__ = "conciliaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # UNIQUE FKs: each payment and each movement can be reconciled exactly once.
    pago_declarado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pagos_declarados.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    movimiento_bancario_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("movimientos_bancarios.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    tipo_conciliacion: Mapped[TipoConciliacion] = mapped_column(
        SAEnum(TipoConciliacion, name="tipo_conciliacion"),
        nullable=False,
        default=TipoConciliacion.AUTOMATICA,
    )
