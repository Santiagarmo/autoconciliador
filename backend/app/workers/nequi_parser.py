"""Nequi statement parser (Strategy).

DEFERRED: pending a real anonymized Nequi PDF statement to tune the layout.
Once a sample is available, implement ``parse`` with pdfplumber and register
the strategy in ``app.workers.factory``.
"""
from __future__ import annotations

from app.schemas.movimiento_bancario import MovimientoBancarioParsed
from app.workers.base import BankParserStrategy


class NequiParser(BankParserStrategy):
    banco = "NEQUI"

    async def parse(self, source: bytes | str) -> list[MovimientoBancarioParsed]:
        raise NotImplementedError(
            "NequiParser pendiente de PDF de muestra real para afinar layout."
        )
