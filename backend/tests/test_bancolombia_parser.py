"""BancolombiaParser — parse_statement_lines with synthetic lines (no real PDF).

Lines below mimic the real statement's text-extraction format but use
invented names/amounts; the actual PDF the layout was tuned against has
personal data and is never committed to the repo.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.workers.bancolombia_parser import BancolombiaParser, parse_statement_lines
from tests.fixtures.bancolombia_pdf import StatementRow, build_bancolombia_pdf

SAME_YEAR = date(2026, 3, 31)
SAME_YEAR_HASTA = date(2026, 6, 30)


def test_credit_and_debit_signs_preserved():
    lines = [
        "4/04 TRANSFERENCIA DESDE NEQUI 58,900.00 962,633.11",
        "4/04 COMPRA EN TIENDA D1 -29,230.00 1,267,931.66",
    ]
    rows = parse_statement_lines(lines, SAME_YEAR, SAME_YEAR_HASTA)

    assert rows[0].monto_real == Decimal("58900.00")
    assert rows[1].monto_real == Decimal("-29230.00")


def test_amounts_without_integer_part():
    lines = [
        "14/05 AJUSTE INTERES AHORROS DB -.02 716,375.31",
        "8/04 ABONO INTERESES AHORROS .62 1,134,924.52",
    ]
    rows = parse_statement_lines(lines, SAME_YEAR, SAME_YEAR_HASTA)

    assert rows[0].monto_real == Decimal("-0.02")
    assert rows[1].monto_real == Decimal("0.62")


def test_thousands_separator_parsed():
    lines = ["27/04 PAGO INTERBANC DIR TESORO NACI 3,092,197.00 3,444,038.96"]
    rows = parse_statement_lines(lines, SAME_YEAR, SAME_YEAR_HASTA)

    assert rows[0].monto_real == Decimal("3092197.00")
    assert rows[0].saldo_posterior == Decimal("3444038.96")


def test_year_inferred_within_same_year_statement():
    lines = ["30/06 PAGO QR URBAN COFFEE -5,000.00 404,098.70"]
    rows = parse_statement_lines(lines, SAME_YEAR, SAME_YEAR_HASTA)

    assert rows[0].fecha_movimiento == datetime(2026, 6, 30, tzinfo=timezone.utc)


def test_year_inferred_across_year_boundary():
    desde = date(2025, 12, 1)
    hasta = date(2026, 1, 31)
    lines = [
        "15/12 COMPRA EN TIENDA D1 -20,000.00 500,000.00",
        "5/01 ABONO INTERESES AHORROS 1.10 500,001.10",
    ]
    rows = parse_statement_lines(lines, desde, hasta)

    assert rows[0].fecha_movimiento == datetime(2025, 12, 15, tzinfo=timezone.utc)
    assert rows[1].fecha_movimiento == datetime(2026, 1, 5, tzinfo=timezone.utc)


def test_numero_referencia_is_none_and_banco_is_bancolombia():
    lines = ["1/04 TRANSFERENCIAS A NEQUI -16,000.00 1,337,554.53"]
    rows = parse_statement_lines(lines, SAME_YEAR, SAME_YEAR_HASTA)

    assert rows[0].numero_referencia is None
    assert rows[0].banco_origen == "BANCOLOMBIA"


def test_non_row_lines_are_ignored():
    lines = [
        "FECHA DESCRIPCIÓN SUCURSAL DCTO. VALOR SALDO",
        "SALDO ANTERIOR $ 1,353,554.53",
        "PÁGINA: 1",
        "FIN ESTADO DE CUENTA",
    ]
    rows = parse_statement_lines(lines, SAME_YEAR, SAME_YEAR_HASTA)

    assert rows == []


def test_row_with_populated_sucursal_column_still_parses():
    # Retiros/consignaciones por corresponsal traen la SUCURSAL poblada
    # ("CANAL CORRESPONSA", "DIR GENERAL"); al no tener columnas separadas
    # en la capa de texto, ese valor queda pegado a la descripción — se
    # acepta como parte de descripcion_concepto en vez de perder la fila.
    lines = ["18/10 RETIRO CORRESPONSAL CB CANAL CORRESPONSA -500,000.00 1,056,595.68"]
    rows = parse_statement_lines(lines, SAME_YEAR, SAME_YEAR_HASTA)

    assert len(rows) == 1
    assert rows[0].monto_real == Decimal("-500000.00")
    assert rows[0].saldo_posterior == Decimal("1056595.68")
    assert rows[0].numero_referencia is None


# --- Real I/O half: BancolombiaParser.parse (pdfplumber read + header regex) -
# Everything above exercises only the pure parse_statement_lines function.
# These close that gap using a synthetic (PyMuPDF-generated) PDF instead of
# a real, PII-bearing statement — see tests/fixtures/bancolombia_pdf.py.

async def test_parser_lee_pdf_real_end_to_end():
    pdf_bytes = build_bancolombia_pdf(
        rows=[
            StatementRow(4, 7, "TRANSFERENCIA DESDE NEQUI", Decimal("58900.00"), Decimal("962633.11")),
            StatementRow(4, 7, "COMPRA EN TIENDA D1", Decimal("-29230.00"), Decimal("1267931.66")),
        ],
        desde=date(2026, 7, 1),
        hasta=date(2026, 7, 31),
    )
    parser = BancolombiaParser()
    rows = await parser.parse(pdf_bytes)

    assert len(rows) == 2
    assert rows[0].monto_real == Decimal("58900.00")
    assert rows[0].fecha_movimiento == datetime(2026, 7, 4, tzinfo=timezone.utc)
    assert rows[1].monto_real == Decimal("-29230.00")
    assert all(r.banco_origen == "BANCOLOMBIA" for r in rows)


async def test_parser_pdf_sin_encabezado_desde_hasta_lanza():
    """A statement missing the DESDE/HASTA header can't resolve any row's
    year — the parser must raise rather than silently guessing."""
    import fitz
    import pytest

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((36, 50), "4/07 ALGO 1,000.00 2,000.00", fontname="cour", fontsize=9)
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = BancolombiaParser()
    with pytest.raises(ValueError, match="DESDE/HASTA"):
        await parser.parse(pdf_bytes)
