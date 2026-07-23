"""Pydantic DTOs for MovimientoBancario (bank statement rows)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EstadoMovimiento


class MovimientoBancarioParsed(BaseModel):
    """Internal DTO: one normalized row emitted by a bank parser strategy.

    The ingestion service (Phase 3) computes ``hash_idempotencia`` from these
    fields before persisting, so the hash is intentionally absent here.
    """

    banco_origen: str
    fecha_movimiento: datetime
    monto_real: Decimal = Field(..., max_digits=12, decimal_places=2)
    saldo_posterior: Decimal = Field(..., max_digits=12, decimal_places=2)
    numero_referencia: str | None = None
    descripcion_concepto: str


class MovimientoBancarioRead(BaseModel):
    """Output DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    banco_origen: str
    fecha_movimiento: datetime
    monto_real: Decimal
    saldo_posterior: Decimal
    numero_referencia: str | None
    descripcion_concepto: str
    hash_idempotencia: str
    estado_movimiento: EstadoMovimiento
    created_at: datetime
