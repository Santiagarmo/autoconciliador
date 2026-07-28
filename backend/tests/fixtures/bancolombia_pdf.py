"""Synthetic Bancolombia statement PDF generator, for tests only.

Real Bancolombia statements contain PII and are deliberately never committed
to this repo (see ``tests/test_bancolombia_parser.py``). To exercise the real
``BancolombiaParser.parse`` I/O path (pdfplumber read -> regex -> rows) without
a real file, this builds a minimal PDF at test time with PyMuPDF (``fitz`` —
already a project dependency, no new package needed) whose extracted text
matches the parser's expected layout exactly.

Monospace font is mandatory: ``bancolombia_parser._ROW`` splits columns on
whitespace runs, and a proportional font can collapse the run of spaces
between the description and the amounts when pdfplumber re-extracts the text.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import fitz  # PyMuPDF


@dataclass(frozen=True)
class StatementRow:
    dia: int
    mes: int
    descripcion: str
    valor: Decimal
    saldo: Decimal

    def as_line(self) -> str:
        signo_valor = "-" if self.valor < 0 else ""
        signo_saldo = "-" if self.saldo < 0 else ""
        valor_fmt = f"{signo_valor}{abs(self.valor):,.2f}"
        saldo_fmt = f"{signo_saldo}{abs(self.saldo):,.2f}"
        return f"{self.dia}/{self.mes:02d} {self.descripcion} {valor_fmt} {saldo_fmt}"


def build_bancolombia_pdf(
    rows: list[StatementRow], desde: date, hasta: date
) -> bytes:
    """Render ``rows`` as a one-page PDF whose extracted text the real
    ``BancolombiaParser`` can parse end to end.

    ``desde``/``hasta`` populate the header range the parser requires to
    resolve each row's year (``_extract_desde_hasta``).
    """
    doc = fitz.open()
    page = doc.new_page()

    header = (
        f"EXTRACTO DE CUENTA DE AHORROS\n"
        f"DESDE: {desde.isoformat().replace('-', '/')}   "
        f"HASTA: {hasta.isoformat().replace('-', '/')}\n"
        f"FECHA        DESCRIPCION                              VALOR         SALDO\n"
    )
    body = "\n".join(row.as_line() for row in rows)
    full_text = header + body

    page.insert_text(
        (36, 50),
        full_text,
        fontname="cour",
        fontsize=9,
        lineheight=1.4,
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
