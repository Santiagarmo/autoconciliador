"""Bank statement parsing — Strategy pattern interface.

Each bank exposes its statement in a different PDF layout, so parsing is
delegated to a concrete ``BankParserStrategy`` chosen at runtime. Strategies
return the internal ``MovimientoBancarioParsed`` DTO (no hash yet); the
ingestion service computes ``hash_idempotencia`` before persisting.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.movimiento_bancario import MovimientoBancarioParsed


class BankParserStrategy(ABC):
    """Parse a single bank's statement into normalized movement rows."""

    #: Bank identifier this strategy handles, e.g. "BANCOLOMBIA", "NEQUI".
    banco: str

    @abstractmethod
    async def parse(self, source: bytes | str) -> list[MovimientoBancarioParsed]:
        """Parse a PDF (bytes or path) into a list of parsed movements."""
        ...
