"""Bank statement parsing — Strategy pattern interface.

Each bank exposes its statement in a different PDF layout, so parsing is
delegated to a concrete ``BankParserStrategy`` chosen at runtime. Strategies
return the internal ``MovimientoBancarioParsed`` DTO (no hash yet); the
ingestion service computes ``hash_idempotencia`` before persisting.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.extracto import ParsedStatement
from app.schemas.movimiento_bancario import MovimientoBancarioParsed


class BankParserStrategy(ABC):
    """Parse a single bank's statement into normalized movement rows."""

    #: Bank identifier this strategy handles, e.g. "BANCOLOMBIA", "NEQUI".
    banco: str

    @abstractmethod
    async def parse(self, source: bytes | str) -> list[MovimientoBancarioParsed]:
        """Parse a PDF (bytes or path) into a list of parsed movements."""
        ...

    async def parse_document(self, source: bytes | str) -> ParsedStatement:
        """Rich parse for ``StatementVerifier``: rows plus provenance.

        Default implementation (used by strategies with no verifier support
        yet, e.g. ``StubParser``/``NequiParser``): rows only, no provenance.
        A ``StatementVerifier`` sees empty candidates/resumen and correctly
        reports ``NO_VERIFICABLE`` rather than a false ``DISCREPANCIA``.

        NOTE for implementors: never stash parse state on ``self`` — parser
        instances are module-level singletons in ``workers.factory._REGISTRY``
        shared across concurrent requests. Return everything, keep nothing.
        """
        return ParsedStatement(banco=self.banco, filas=await self.parse(source))
