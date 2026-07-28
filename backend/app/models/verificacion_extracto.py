"""VerificacionExtracto: durable verdict of StatementVerifier (+ future
StatementReviewer) for one statement ingestion.

Exists because the ingestion background task (``_ingest_and_reconcile``)
otherwise has nowhere to put its outcome: it returns ``None`` and only logs,
so a detected discrepancy — or an outright exception — is invisible to any
human unless they go read server logs. One row per ingestion attempt gives
both a queryable verdict and, on failure, a durable error record.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Enum as SAEnum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.domain.enums import ResultadoVerificacion


class VerificacionExtracto(Base, TimestampMixin):
    __tablename__ = "verificaciones_extracto"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    banco: Mapped[str] = mapped_column(String, nullable=False)
    resultado: Mapped[ResultadoVerificacion] = mapped_column(
        SAEnum(ResultadoVerificacion, name="resultado_verificacion"),
        nullable=False,
    )
    filas_emitidas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filas_candidatas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    insertados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    omitidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Serialized list[Hallazgo] (see app.services.statement_verifier). A
    # child table here would be over-engineering at this volume/maturity.
    hallazgos: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    # sha256(pdf_bytes) — ties re-ingestions of the same file together.
    # Null when the parser was fed a path instead of bytes.
    hash_extracto: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Exception text + traceback when the background ingestion task itself
    # blew up (parse error, corrupt PDF, DB error) — resultado=ERROR.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Tier 2 (LLM reviewer) columns — present from day 1, unused until
    # a StatementReviewer implementation is wired in (see llm_reviewer.py).
    revisado_por_llm: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    modelo_llm: Mapped[str | None] = mapped_column(String, nullable=True)
    revision_llm: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
