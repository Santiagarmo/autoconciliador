"""Pydantic DTOs for Conciliacion (reconciliation audit records)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import TipoConciliacion


class ConciliacionCreate(BaseModel):
    """Internal DTO built by the reconciliation engine (Phase 3)."""

    pago_declarado_id: UUID
    movimiento_bancario_id: UUID
    tipo_conciliacion: TipoConciliacion = TipoConciliacion.AUTOMATICA


class ConciliacionRead(BaseModel):
    """Output DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pago_declarado_id: UUID
    movimiento_bancario_id: UUID
    tipo_conciliacion: TipoConciliacion
    created_at: datetime


class ReconSummaryRead(BaseModel):
    """Result of a reconciliation run."""

    model_config = ConfigDict(from_attributes=True)

    conciliados: int
