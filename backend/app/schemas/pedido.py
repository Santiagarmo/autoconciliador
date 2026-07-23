"""Pydantic DTOs for Pedido."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EstadoPedido


class PedidoBase(BaseModel):
    codigo_pedido: str = Field(..., examples=["PED-1042"])
    cliente_whatsapp: str
    monto_total: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)


class PedidoCreate(PedidoBase):
    """Input DTO to register an order."""


class PedidoUpdate(BaseModel):
    """Partial update DTO (state transitions are driven by services)."""

    cliente_whatsapp: str | None = None
    estado_pedido: EstadoPedido | None = None


class PedidoRead(PedidoBase):
    """Output DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    estado_pedido: EstadoPedido
    created_at: datetime
    updated_at: datetime
