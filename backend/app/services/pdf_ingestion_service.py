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

from app.models.movimiento_bancario import MovimientoBancario
from app.schemas.movimiento_bancario import MovimientoBancarioParsed
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


@dataclass(frozen=True)
class IngestSummary:
    insertados: int
    omitidos: int

    @property
    def total(self) -> int:
        return self.insertados + self.omitidos


class PDFIngestionService:
    def __init__(self, session: AsyncSession, parser: BankParserStrategy) -> None:
        self.session = session
        self.parser = parser

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
        """Parse ``source`` and persist new movements idempotently."""
        rows = await self.parser.parse(source)
        insertados = 0
        omitidos = 0

        for row in rows:
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

        await self.session.commit()
        return IngestSummary(insertados=insertados, omitidos=omitidos)
