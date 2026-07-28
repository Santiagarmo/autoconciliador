"""Pydantic DTO for VerificacionExtracto (read-only, API output)."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import ResultadoVerificacion


class VerificacionExtractoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    banco: str
    resultado: ResultadoVerificacion
    filas_emitidas: int
    filas_candidatas: int
    insertados: int
    omitidos: int
    hallazgos: list[dict[str, Any]]
    hash_extracto: str | None
    error: str | None
    revisado_por_llm: bool
    modelo_llm: str | None
    revision_llm: dict[str, Any] | None
    created_at: datetime
