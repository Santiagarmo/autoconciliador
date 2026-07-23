"""Pydantic DTOs for PagoDeclarado (advisor's declared payment)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EstadoPago


class PagoDeclaradoBase(BaseModel):
    banco_destino: str = Field(..., examples=["NEQUI", "BANCOLOMBIA"])
    monto_declarado: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    numero_referencia: str
    ultimos_4_digitos: str | None = Field(default=None, max_length=4)


class PagoDeclaradoCreate(PagoDeclaradoBase):
    """Input DTO: advisor registers the receipt against an order."""

    pedido_id: UUID


class PagoDeclaradoRead(PagoDeclaradoBase):
    """Output DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pedido_id: UUID
    estado_pago: EstadoPago
    created_at: datetime
