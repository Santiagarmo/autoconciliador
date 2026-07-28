"""Bancolombia statement parser (Strategy).

Tuned against a real anonymized "cuenta de ahorros" statement, plan
estándar/personal (no empresarial). Layout: one text line per movement
(``FECHA DESCRIPCIÓN VALOR SALDO``); the ``SUCURSAL``/``DCTO.`` columns are
always blank in this plan, so no ``numero_referencia`` is available. The
statement year isn't in the ``FECHA`` column (``D/MM``) — it's inferred from
the ``DESDE``/``HASTA`` header range, which also lets a statement that
crosses a year boundary (Dec -> Jan) resolve the right year per row.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

import pdfplumber

from app.schemas.extracto import LineaCruda, ParsedStatement, ResumenExtracto
from app.schemas.movimiento_bancario import MovimientoBancarioParsed
from app.workers.base import BankParserStrategy

_WHITESPACE = re.compile(r"\s+")

_HEADER_RANGE = re.compile(
    r"DESDE:\s*(\d{4})/(\d{2})/(\d{2}).*?HASTA:\s*(\d{4})/(\d{2})/(\d{2})",
    re.DOTALL,
)

_AMOUNT = r"-?(?:\d{1,3}(?:,\d{3})*)?\.\d{2}"
_ROW = re.compile(
    rf"^(\d{{1,2}})/(\d{{2}})\s+(.+?)\s+({_AMOUNT})\s+({_AMOUNT})$"
)

# Deliberately looser AND independently written from ``_ROW`` — no amount
# requirement, just "starts with a D/MM date". Its independence is what
# makes the CONTEO_FILAS verification check a real signal instead of a
# tautology: it must be able to disagree with ``_ROW`` when a row's amount
# columns are malformed/glued. Do NOT refactor these two into one regex —
# that would silently neuter the check (it'd always read candidatas==filas
# by construction).
_LOOSE_ROW = re.compile(r"^\d{1,2}/\d{2}\s")

_AMOUNT_RE = re.compile(_AMOUNT)

# RESUMEN block labels -> ResumenExtracto field. The block is two-column
# (e.g. "TOTAL ABONOS $ 10,858,989.64   CUENTAS X COBRAR $ .00"); taking the
# first amount after the label works because the label always anchors the
# left column. See StatementVerifier.RESUMEN_IDENTIDAD for the self-check
# that catches a misread (e.g. grabbing SALDO PROMEDIO instead).
_RESUMEN_LABELS = {
    "SALDO ANTERIOR": "saldo_anterior",
    "TOTAL ABONOS": "total_abonos",
    "TOTAL CARGOS": "total_cargos",
    "SALDO ACTUAL": "saldo_actual",
}


def _extract_desde_hasta(text: str) -> tuple[date, date]:
    match = _HEADER_RANGE.search(text)
    if match is None:
        raise ValueError("No se encontró el rango DESDE/HASTA en el encabezado del extracto.")
    desde = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    hasta = date(int(match.group(4)), int(match.group(5)), int(match.group(6)))
    return desde, hasta


def _resolve_year(mes: int, desde: date, hasta: date) -> int:
    if desde.year == hasta.year:
        return desde.year
    return desde.year if mes >= desde.month else hasta.year


def _parse_amount(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ""))


def _extract_resumen(lines: Iterable[str]) -> ResumenExtracto | None:
    """Best-effort extraction of the RESUMEN block. All 4 fields optional —
    an absent field simply skips its corresponding verifier check rather
    than failing. Returns ``None`` when nothing was found at all."""
    values: dict[str, Decimal] = {}
    for line in lines:
        stripped = line.strip()
        for label, field in _RESUMEN_LABELS.items():
            if field in values or not stripped.startswith(label):
                continue
            match = _AMOUNT_RE.search(stripped[len(label):])
            if match is not None:
                values[field] = _parse_amount(match.group())
    return ResumenExtracto(**values) if values else None


def parse_statement_lines(
    lines: Iterable[str], desde: date, hasta: date
) -> list[MovimientoBancarioParsed]:
    """Parse extracted text lines of a Bancolombia statement (pure, no I/O)."""
    rows: list[MovimientoBancarioParsed] = []
    for line in lines:
        match = _ROW.match(line.strip())
        if match is None:
            continue
        dia_s, mes_s, descripcion, valor_s, saldo_s = match.groups()
        dia, mes = int(dia_s), int(mes_s)
        year = _resolve_year(mes, desde, hasta)
        rows.append(
            MovimientoBancarioParsed(
                banco_origen="BANCOLOMBIA",
                fecha_movimiento=datetime(year, mes, dia, tzinfo=timezone.utc),
                monto_real=_parse_amount(valor_s),
                saldo_posterior=_parse_amount(saldo_s),
                numero_referencia=None,
                descripcion_concepto=_WHITESPACE.sub(" ", descripcion.strip()),
            )
        )
    return rows


class BancolombiaParser(BankParserStrategy):
    banco = "BANCOLOMBIA"

    async def parse(self, source: bytes | str) -> list[MovimientoBancarioParsed]:
        return (await self.parse_document(source)).filas

    async def parse_document(self, source: bytes | str) -> ParsedStatement:
        pdf_source = io.BytesIO(source) if isinstance(source, bytes) else source
        with pdfplumber.open(pdf_source) as pdf:
            texts = [page.extract_text() or "" for page in pdf.pages]

        desde, hasta = _extract_desde_hasta(texts[0] if texts else "")

        # (pagina, indice_global, texto) — provenance for candidatas/verifier.
        all_lines: list[tuple[int, int, str]] = []
        indice = 0
        for pagina, text in enumerate(texts, start=1):
            for texto in text.splitlines():
                all_lines.append((pagina, indice, texto))
                indice += 1

        filas = parse_statement_lines((t for _, _, t in all_lines), desde, hasta)
        candidatas = [
            LineaCruda(pagina=pagina, indice=indice, texto=texto)
            for pagina, indice, texto in all_lines
            if _LOOSE_ROW.match(texto.strip())
        ]
        resumen = _extract_resumen(t for _, _, t in all_lines)

        return ParsedStatement(
            banco=self.banco,
            filas=filas,
            resumen=resumen,
            lineas_candidatas=candidatas,
            lineas_totales=len(all_lines),
            texto_paginas=texts,
        )
