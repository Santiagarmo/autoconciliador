"""Tier 2 against a REAL LLM endpoint. Skipped unless LLM_INTEGRATION_TESTS=1
is set and LLM_BASE_URL points at a reachable server — this is not part of
the default `pytest -q` run.

Run explicitly:
    docker compose exec -e LLM_INTEGRATION_TESTS=1 backend \
        pytest -q tests/test_llm_reviewer_integration.py -s
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest

from app.domain.enums import ResultadoVerificacion
from app.services.llm_reviewer import (
    OpenAICompatStatementReviewer,
    StatementReviewRequest,
    StatementReviewVerdict,
)
from app.services.statement_verifier import StatementVerifier
from app.workers.bancolombia_parser import BancolombiaParser
from tests.fixtures.bancolombia_pdf import StatementRow, build_bancolombia_pdf

pytestmark = pytest.mark.skipif(
    os.getenv("LLM_INTEGRATION_TESTS") != "1",
    reason="Requiere un endpoint LLM real; setear LLM_INTEGRATION_TESTS=1.",
)


async def test_caso_saboteado_real_produce_veredicto_coherente():
    # Same sabotaged case as test_verificacion_e2e.py's
    # test_fila_saboteada_en_extracto_multipagina_produce_discrepancia: row 3
    # gets its amount columns glued together so the parser silently drops it.
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
    verificacion = StatementVerifier().verify(doc)
    assert verificacion.resultado is ResultadoVerificacion.DISCREPANCIA

    # Same request shape pdf_ingestion_service.py builds on escalation.
    from app.core.config import settings

    request = StatementReviewRequest(
        banco=doc.banco,
        hallazgos=[
            {
                "codigo": h.codigo,
                "severidad": h.severidad.value,
                "detalle": h.detalle,
                "indice_fila": h.indice_fila,
                "pagina": h.pagina,
            }
            for h in verificacion.hallazgos
        ],
        resumen=doc.resumen,
        filas_emitidas=verificacion.filas_emitidas,
        lineas_contexto=doc.lineas_candidatas[: settings.LLM_MAX_LINEAS_CONTEXTO],
    )

    verdict = await OpenAICompatStatementReviewer().review(request)

    assert verdict is not None, "el endpoint LLM no respondió"
    assert isinstance(verdict, StatementReviewVerdict)
    assert verdict.veredicto in {"FILAS_FALTANTES", "FALSO_POSITIVO", "INDETERMINADO"}
    assert 0.0 <= verdict.confianza <= 1.0
    assert verdict.explicacion.strip()

    # The central safety rule: NUNCA inventes montos. Every suggested row
    # must cite a line that actually exists in the context it was given —
    # this is the one assertion that would catch a hallucinated movement.
    textos_enviados = {l.texto for l in request.lineas_contexto}
    for fila in verdict.filas_sugeridas:
        assert fila.linea_cruda in textos_enviados, (
            f"el modelo inventó una línea inexistente: {fila.linea_cruda!r}"
        )

    print(f"\nVeredicto real: {verdict.veredicto} (confianza={verdict.confianza})")
    print(f"Explicación: {verdict.explicacion}")
