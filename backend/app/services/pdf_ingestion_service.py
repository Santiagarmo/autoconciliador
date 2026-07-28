"""PDFIngestionService — parse a bank statement and persist movements.

Applies the Strategy pattern (bank parser chosen via the factory) and hash
idempotency: every row gets a deterministic ``hash_idempotencia`` and a UNIQUE
constraint guarantees a re-ingested statement inserts nothing new. A duplicate
never halts processing — its row is rolled back via a SAVEPOINT and the run
continues (Servicio 1 del spec).
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.enums import ResultadoVerificacion
from app.models.movimiento_bancario import MovimientoBancario
from app.models.verificacion_extracto import VerificacionExtracto
from app.schemas.movimiento_bancario import MovimientoBancarioParsed
from app.services.llm_reviewer import (
    StatementReviewer,
    StatementReviewRequest,
    get_statement_reviewer,
)
from app.services.statement_verifier import Hallazgo, StatementVerifier, VerificacionResult
from app.workers.base import BankParserStrategy

logger = logging.getLogger(__name__)

_WHITESPACE = re.compile(r"\s+")


def _normalize_descripcion(descripcion: str) -> str:
    """UPPERCASE + collapse whitespace so the hash is layout-stable."""
    return _WHITESPACE.sub(" ", descripcion.strip()).upper()


def compute_hash(
    *,
    fecha_movimiento: object,
    monto_real: Decimal,
    saldo_posterior: Decimal,
    descripcion_limpia: str,
) -> str:
    """SHA256(fecha + monto + saldo_posterior + descripcion_limpia)."""
    payload = f"{fecha_movimiento}{monto_real}{saldo_posterior}{descripcion_limpia}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hallazgo_to_dict(hallazgo: Hallazgo) -> dict:
    """JSONB-safe serialization (``Severidad`` is a ``str`` Enum but we store
    its plain value, not the Enum wrapper)."""
    return {
        "codigo": hallazgo.codigo,
        "severidad": hallazgo.severidad.value,
        "detalle": hallazgo.detalle,
        "indice_fila": hallazgo.indice_fila,
        "pagina": hallazgo.pagina,
    }


@dataclass(frozen=True)
class IngestSummary:
    insertados: int
    omitidos: int
    verificacion: VerificacionResult | None = None

    @property
    def total(self) -> int:
        return self.insertados + self.omitidos


class PDFIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        parser: BankParserStrategy,
        *,
        verifier: StatementVerifier | None = None,
        reviewer: StatementReviewer | None = None,
    ) -> None:
        self.session = session
        self.parser = parser
        self.verifier = verifier or StatementVerifier()
        # Resolves to NullStatementReviewer unless LLM_REVIEW_ENABLED — tests
        # override with StubReviewer to assert the escalation call happens.
        self.reviewer = reviewer or get_statement_reviewer()

    def _to_model(self, row: MovimientoBancarioParsed) -> MovimientoBancario:
        descripcion_limpia = _normalize_descripcion(row.descripcion_concepto)
        return MovimientoBancario(
            banco_origen=row.banco_origen,
            fecha_movimiento=row.fecha_movimiento,
            monto_real=row.monto_real,
            saldo_posterior=row.saldo_posterior,
            numero_referencia=row.numero_referencia,
            descripcion_concepto=row.descripcion_concepto,
            hash_idempotencia=compute_hash(
                fecha_movimiento=row.fecha_movimiento,
                monto_real=row.monto_real,
                saldo_posterior=row.saldo_posterior,
                descripcion_limpia=descripcion_limpia,
            ),
        )

    async def ingest(self, source: bytes | str) -> IngestSummary:
        """Parse ``source``, verify completeness, and persist new movements
        idempotently. The verification verdict is persisted alongside the
        movements in the SAME commit, so there can never be movements
        without their verdict — but a DISCREPANCIA verdict never blocks
        persistence (see statement_verifier.py module docstring)."""
        doc = await self.parser.parse_document(source)
        verificacion = self.verifier.verify(doc)
        insertados = 0
        omitidos = 0

        for row in doc.filas:
            movimiento = self._to_model(row)
            try:
                # SAVEPOINT per row: a duplicate rolls back only this row,
                # never the whole batch, so processing always continues.
                async with self.session.begin_nested():
                    self.session.add(movimiento)
                insertados += 1
            except IntegrityError:
                omitidos += 1
                logger.info(
                    "Movimiento duplicado omitido (hash=%s, banco=%s)",
                    movimiento.hash_idempotencia,
                    movimiento.banco_origen,
                )

        hash_extracto = (
            hashlib.sha256(source).hexdigest() if isinstance(source, bytes) else None
        )

        # Escalate to tier 2 ONLY on a DISCREPANCIA — with NullStatementReviewer
        # (the default) this is one `await` returning None, zero cost. A
        # reviewer failure (timeout, model down) must never fail the ingest;
        # its verdict is advisory and never touches persisted movements.
        revisado_por_llm = False
        modelo_llm: str | None = None
        revision_llm: dict | None = None
        if verificacion.resultado is ResultadoVerificacion.DISCREPANCIA:
            try:
                request = StatementReviewRequest(
                    banco=doc.banco,
                    hallazgos=[_hallazgo_to_dict(h) for h in verificacion.hallazgos],
                    resumen=doc.resumen,
                    filas_emitidas=verificacion.filas_emitidas,
                    # Best-effort context: the row-like raw lines, capped —
                    # NOT the full statement (context length + PII).
                    lineas_contexto=doc.lineas_candidatas[
                        : settings.LLM_MAX_LINEAS_CONTEXTO
                    ],
                )
                verdict = await self.reviewer.review(request)
                if verdict is not None:
                    revisado_por_llm = True
                    modelo_llm = settings.LLM_MODEL
                    revision_llm = verdict.model_dump(mode="json")
            except Exception:
                logger.exception(
                    "StatementReviewer falló para banco=%s; se continúa sin "
                    "su veredicto (el resultado del verificador determinístico "
                    "no se ve afectado).",
                    doc.banco,
                )
                revision_llm = {"error": "LLM no disponible"}

        self.session.add(
            VerificacionExtracto(
                banco=doc.banco,
                resultado=verificacion.resultado,
                filas_emitidas=verificacion.filas_emitidas,
                filas_candidatas=verificacion.filas_candidatas,
                insertados=insertados,
                omitidos=omitidos,
                hallazgos=[_hallazgo_to_dict(h) for h in verificacion.hallazgos],
                hash_extracto=hash_extracto,
                revisado_por_llm=revisado_por_llm,
                modelo_llm=modelo_llm,
                revision_llm=revision_llm,
            )
        )

        await self.session.commit()
        return IngestSummary(
            insertados=insertados, omitidos=omitidos, verificacion=verificacion
        )
