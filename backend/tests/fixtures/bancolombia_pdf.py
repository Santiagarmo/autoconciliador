"""Synthetic Bancolombia statement PDF generator, for tests only.

Real Bancolombia statements contain PII and are deliberately never committed
to this repo (see ``tests/test_bancolombia_parser.py``). To exercise the real
``BancolombiaParser.parse``/``parse_document`` I/O path (pdfplumber read ->
regex -> rows) without a real file, this builds a minimal PDF at test time
with PyMuPDF (``fitz`` — already a project dependency, no new package
needed) whose extracted text matches the parser's expected layout exactly.

Monospace font is mandatory: ``bancolombia_parser._ROW`` splits columns on
whitespace runs, and a proportional font can collapse the run of spaces
between the description and the amounts when pdfplumber re-extracts the text.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import fitz  # PyMuPDF

_COLUMN_HEADER = (
    "FECHA        DESCRIPCION                              VALOR         SALDO\n"
)


@dataclass(frozen=True)
class StatementRow:
    dia: int
    mes: int
    descripcion: str
    valor: Decimal
    saldo: Decimal

    def as_line(self, *, mangled: bool = False) -> str:
        signo_valor = "-" if self.valor < 0 else ""
        signo_saldo = "-" if self.saldo < 0 else ""
        valor_fmt = f"{signo_valor}{abs(self.valor):,.2f}"
        saldo_fmt = f"{signo_saldo}{abs(self.saldo):,.2f}"
        if mangled:
            # No whitespace between descripcion and valor: `_ROW` requires
            # `\s+` before EACH amount group, so gluing them together leaves
            # only one whitespace run in the tail (before saldo) instead of
            # the two the regex needs — the row silently fails to match,
            # exactly like a real glued-column PDF extraction artifact.
            # `_LOOSE_ROW` (date-only) still matches, so it still counts as
            # a "candidate" line for CONTEO_FILAS to catch.
            return f"{self.dia}/{self.mes:02d} {self.descripcion}{valor_fmt} {saldo_fmt}"
        return f"{self.dia}/{self.mes:02d} {self.descripcion} {valor_fmt} {saldo_fmt}"


def _fmt_resumen_amount(v: Decimal) -> str:
    signo = "-" if v < 0 else ""
    return f"{signo}{abs(v):,.2f}"


def _resumen_block(resumen: dict[str, Decimal]) -> str:
    """Render the RESUMEN block in its real two-column shape (see the
    right-column labels — SALDO PROMEDIO/CUENTAS X COBRAR/etc — which the
    parser's label-anchored extraction must skip past to find the correct
    left-column amount)."""
    saldo_anterior = resumen.get("saldo_anterior", Decimal("0.00"))
    total_abonos = resumen.get("total_abonos", Decimal("0.00"))
    total_cargos = resumen.get("total_cargos", Decimal("0.00"))
    saldo_actual = resumen.get("saldo_actual", Decimal("0.00"))
    return (
        f"SALDO ANTERIOR $ {_fmt_resumen_amount(saldo_anterior)} SALDO PROMEDIO $ .00\n"
        f"TOTAL ABONOS $ {_fmt_resumen_amount(total_abonos)} CUENTAS X COBRAR $ .00\n"
        f"TOTAL CARGOS $ {_fmt_resumen_amount(total_cargos)} VALOR INTERESES PAGADOS $ .00\n"
        f"SALDO ACTUAL $ {_fmt_resumen_amount(saldo_actual)} RETEFUENTE $ .00\n"
    )


def build_bancolombia_pdf(
    rows: list[StatementRow],
    desde: date,
    hasta: date,
    *,
    resumen: dict[str, Decimal] | None = None,
    mangle_row_index: int | None = None,
    filas_por_pagina: int | None = None,
) -> bytes:
    """Render ``rows`` as a Bancolombia-layout PDF the real parser can read.

    ``desde``/``hasta`` populate the header range the parser requires to
    resolve each row's year (``_extract_desde_hasta``).

    ``resumen`` — optional dict with any of saldo_anterior/total_abonos/
    total_cargos/saldo_actual — renders the RESUMEN block (real two-column
    shape) once, on the first page.

    ``mangle_row_index`` — renders that one row with its amount columns
    glued together so ``_ROW`` fails to match it (simulating a dropped row)
    while ``_LOOSE_ROW`` still counts it as a candidate.

    ``filas_por_pagina`` — splits ``rows`` across multiple pages (real
    statements repeat the header/column-header boilerplate on every page,
    per the spike against a real 5-page statement). ``None`` = single page.
    """
    doc = fitz.open()

    header_base = (
        f"EXTRACTO DE CUENTA DE AHORROS\n"
        f"DESDE: {desde.isoformat().replace('-', '/')}   "
        f"HASTA: {hasta.isoformat().replace('-', '/')}\n"
    )
    resumen_block = _resumen_block(resumen) if resumen else ""

    lines = [
        row.as_line(mangled=(i == mangle_row_index)) for i, row in enumerate(rows)
    ]
    chunk_size = filas_por_pagina or max(len(lines), 1)

    for start in range(0, max(len(lines), 1), chunk_size):
        chunk = lines[start : start + chunk_size]
        text = header_base
        if start == 0 and resumen_block:
            text += resumen_block
        text += _COLUMN_HEADER
        text += "\n".join(chunk)

        page = doc.new_page()
        page.insert_text(
            (36, 50), text, fontname="cour", fontsize=9, lineheight=1.4
        )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
