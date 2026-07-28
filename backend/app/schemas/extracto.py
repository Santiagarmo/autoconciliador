"""Pydantic DTOs for the enriched statement parse (verification support).

``BankParserStrategy.parse_document`` returns a ``ParsedStatement`` carrying
the same rows as ``parse`` plus provenance and a summary block, so a
``StatementVerifier`` (Fase 2) can cross-check completeness without
re-reading the PDF. Kept separate from ``MovimientoBancarioParsed`` on
purpose: that DTO feeds ``PDFIngestionService._to_model`` and the hash
computation, and page/line provenance has no business in that path.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.schemas.movimiento_bancario import MovimientoBancarioParsed


class LineaCruda(BaseModel):
    """One raw text line as extracted from the PDF, with its position."""

    pagina: int
    indice: int
    texto: str


class ResumenExtracto(BaseModel):
    """The statement's own RESUMEN block — an independent witness to
    completeness that makes no assumption about row order."""

    saldo_anterior: Decimal | None = None
    total_abonos: Decimal | None = None
    total_cargos: Decimal | None = None
    saldo_actual: Decimal | None = None


class ParsedStatement(BaseModel):
    """Rich parse result: rows plus everything a verifier needs.

    ``texto_paginas`` exists ONLY to give the (future) LLM reviewer context
    around a detected discrepancy. It must never be persisted or logged —
    it is full raw statement text and may carry PII (holder name, address,
    account number). Keep it out of anything that reaches the DB or logs.
    """

    banco: str
    filas: list[MovimientoBancarioParsed] = []
    resumen: ResumenExtracto | None = None
    lineas_candidatas: list[LineaCruda] = []
    lineas_totales: int = 0
    texto_paginas: list[str] = []
