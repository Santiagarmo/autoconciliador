"""End-to-end proof: a real PDF with one dropped row surfaces as
DISCREPANCIA through the actual parser -> verifier path (no synthetic
ParsedStatement shortcuts, unlike test_statement_verifier.py)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.enums import ResultadoVerificacion
from app.services.statement_verifier import Severidad, StatementVerifier
from app.workers.bancolombia_parser import BancolombiaParser
from tests.fixtures.bancolombia_pdf import StatementRow, build_bancolombia_pdf


async def test_fila_saboteada_en_extracto_multipagina_produce_discrepancia():
    # True chain: anterior=1000 -[100]-> 1100 -[50]-> 1150 -[-30]-> 1120 -[20]-> 1140.
    # Row 3 (-30.00 -> 1120.00) gets its amount columns glued together, so
    # `_ROW` fails to match it — exactly the real-world "line silently
    # dropped" failure mode. Split across 2 pages (2 rows each) to also
    # exercise the multi-page provenance path.
    rows = [
        StatementRow(1, 7, "TRANSFERENCIA DESDE NEQUI", Decimal("100.00"), Decimal("1100.00")),
        StatementRow(2, 7, "ABONO INTERESES", Decimal("50.00"), Decimal("1150.00")),
        StatementRow(3, 7, "COMPRA EN TIENDA D1", Decimal("-30.00"), Decimal("1120.00")),
        StatementRow(4, 7, "PAGO QR CAFE", Decimal("20.00"), Decimal("1140.00")),
    ]
    pdf_bytes = build_bancolombia_pdf(
        rows,
        desde=date(2026, 7, 1),
        hasta=date(2026, 7, 31),
        resumen={
            "saldo_anterior": Decimal("1000.00"),
            "total_abonos": Decimal("170.00"),
            "total_cargos": Decimal("30.00"),
            "saldo_actual": Decimal("1140.00"),
        },
        mangle_row_index=2,
        filas_por_pagina=2,
    )

    doc = await BancolombiaParser().parse_document(pdf_bytes)

    # The dropped row is invisible to the parser's own row count...
    assert len(doc.filas) == 3
    # ...but the LOOSE candidate regex still sees all 4 date-prefixed lines.
    assert len(doc.lineas_candidatas) == 4

    result = StatementVerifier().verify(doc)

    assert result.resultado is ResultadoVerificacion.DISCREPANCIA
    codigos_criticos = {
        h.codigo for h in result.hallazgos if h.severidad is Severidad.CRITICO
    }
    assert "CONTEO_FILAS" in codigos_criticos
    assert "CADENA_SALDOS" in codigos_criticos
