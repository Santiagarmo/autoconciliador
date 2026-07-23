"""Bancolombia statement parser (Strategy).

DEFERRED: pending a real anonymized Bancolombia PDF statement to tune the
table layout (columns, date format, sign of amounts). Once a sample is
available, implement ``parse`` with pdfplumber and register the strategy in
``app.workers.factory``.
"""
from __future__ import annotations

from app.schemas.movimiento_bancario import MovimientoBancarioParsed
from app.workers.base import BankParserStrategy


class BancolombiaParser(BankParserStrategy):
    banco = "BANCOLOMBIA"

    async def parse(self, source: bytes | str) -> list[MovimientoBancarioParsed]:
        raise NotImplementedError(
            "BancolombiaParser pendiente de PDF de muestra real para afinar layout."
        )
