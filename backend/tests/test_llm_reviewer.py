"""Tier 2 — OpenAICompatStatementReviewer.review() against a mocked HTTP
transport. No network, no Postgres (no `session` fixture) — these run even
without the DB up."""
from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import settings
from app.schemas.extracto import LineaCruda, ResumenExtracto
from app.services import llm_reviewer
from app.services.llm_reviewer import (
    SYSTEM_PROMPT,
    OpenAICompatStatementReviewer,
    StatementReviewRequest,
    build_messages,
    parse_verdict,
)


def _patch_transport(monkeypatch, handler) -> None:
    """Make every httpx.AsyncClient() created inside llm_reviewer use a
    MockTransport driven by `handler`, instead of touching the network."""
    real_async_client = httpx.AsyncClient

    def _factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(llm_reviewer.httpx, "AsyncClient", _factory)


def _request() -> StatementReviewRequest:
    return StatementReviewRequest(
        banco="BANCOLOMBIA",
        hallazgos=[{"codigo": "CADENA_SALDOS", "severidad": "CRITICO"}],
        resumen=ResumenExtracto(
            saldo_anterior="1000.00",
            total_abonos="170.00",
            total_cargos="30.00",
            saldo_actual="1140.00",
        ),
        filas_emitidas=3,
        lineas_contexto=[
            LineaCruda(pagina=1, indice=0, texto="01/07 TRANSFERENCIA DESDE NEQUI 100.00 1100.00"),
            LineaCruda(pagina=1, indice=1, texto="02/07 ABONO INTERESES 50.00 1150.00"),
            LineaCruda(pagina=2, indice=0, texto="03/07 COMPRA EN TIENDA D1 -30.001120.00"),
            LineaCruda(pagina=2, indice=1, texto="04/07 PAGO QR CAFE 20.00 1140.00"),
        ],
    )


def _chat_response(content: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={"choices": [{"message": {"content": content}}]},
    )


_VEREDICTO_JSON = json.dumps(
    {
        "veredicto": "FILAS_FALTANTES",
        "confianza": 0.8,
        "filas_sugeridas": [
            {
                "linea_cruda": "03/07 COMPRA EN TIENDA D1 -30.001120.00",
                "fecha": "03/07",
                "monto": "-30.00",
                "saldo_posterior": "1120.00",
                "confianza": 0.8,
            }
        ],
        "explicacion": "La línea 3 no fue extraída como fila.",
    }
)


# --- async: review() end to end against a mocked transport -----------------

async def test_happy_path_devuelve_veredicto(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(_VEREDICTO_JSON)

    _patch_transport(monkeypatch, handler)
    verdict = await OpenAICompatStatementReviewer().review(_request())

    assert verdict is not None
    assert verdict.veredicto == "FILAS_FALTANTES"
    assert verdict.filas_sugeridas[0].linea_cruda == (
        "03/07 COMPRA EN TIENDA D1 -30.001120.00"
    )


async def test_json_malformado_degrada_a_indeterminado(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response("no puedo ayudarte con eso")

    _patch_transport(monkeypatch, handler)
    verdict = await OpenAICompatStatementReviewer().review(_request())

    assert verdict is not None
    assert verdict.veredicto == "INDETERMINADO"
    assert verdict.confianza == 0.0


async def test_http_500_devuelve_none(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_transport(monkeypatch, handler)
    verdict = await OpenAICompatStatementReviewer().review(_request())

    assert verdict is None


async def test_timeout_devuelve_none(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    _patch_transport(monkeypatch, handler)
    verdict = await OpenAICompatStatementReviewer().review(_request())

    assert verdict is None


async def test_reintenta_una_vez_y_recupera(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="unavailable")
        return _chat_response(_VEREDICTO_JSON)

    _patch_transport(monkeypatch, handler)
    verdict = await OpenAICompatStatementReviewer().review(_request())

    assert verdict is not None
    assert verdict.veredicto == "FILAS_FALTANTES"
    assert calls["n"] == 2


async def test_respuesta_sin_choices_devuelve_none(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    _patch_transport(monkeypatch, handler)
    verdict = await OpenAICompatStatementReviewer().review(_request())

    assert verdict is None


async def test_authorization_ausente_sin_api_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        return _chat_response(_VEREDICTO_JSON)

    _patch_transport(monkeypatch, handler)
    await OpenAICompatStatementReviewer().review(_request())

    assert "authorization" not in seen["headers"]


async def test_authorization_presente_con_api_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "secreto")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        return _chat_response(_VEREDICTO_JSON)

    _patch_transport(monkeypatch, handler)
    await OpenAICompatStatementReviewer().review(_request())

    assert seen["headers"]["authorization"] == "Bearer secreto"


async def test_confianza_fuera_de_rango_se_clampea(monkeypatch):
    contenido = json.dumps(
        {
            "veredicto": "FILAS_FALTANTES",
            "confianza": 95,
            "filas_sugeridas": [
                {
                    "linea_cruda": "03/07 COMPRA EN TIENDA D1 -30.001120.00",
                    "confianza": -3,
                }
            ],
            "explicacion": "confianza fuera de rango",
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(contenido)

    _patch_transport(monkeypatch, handler)
    verdict = await OpenAICompatStatementReviewer().review(_request())

    assert verdict is not None
    assert verdict.confianza == 1.0
    assert verdict.filas_sugeridas[0].confianza == 0.0


async def test_payload_no_incluye_texto_paginas(monkeypatch):
    # The PII test. lineas_contexto is the only statement text allowed to
    # reach the model; StatementReviewRequest has no texto_paginas field at
    # all, so this also guards against ever adding one without noticing here.
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _chat_response(_VEREDICTO_JSON)

    _patch_transport(monkeypatch, handler)
    await OpenAICompatStatementReviewer().review(_request())

    user_content = seen["body"]["messages"][1]["content"]
    assert "texto_paginas" not in user_content
    assert "texto_paginas" not in json.dumps(seen["body"])


async def test_payload_pide_json_schema_no_json_object(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _chat_response(_VEREDICTO_JSON)

    _patch_transport(monkeypatch, handler)
    await OpenAICompatStatementReviewer().review(_request())

    response_format = seen["body"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "StatementReviewVerdict"
    assert "properties" in response_format["json_schema"]["schema"]


# --- sync: pure helpers ------------------------------------------------------

def test_build_messages_serializa_decimales():
    messages = build_messages(_request())
    user_content = messages[1]["content"]

    parsed = json.loads(user_content)  # must not raise
    assert parsed["resumen"]["saldo_anterior"] == "1000.00"


def test_system_prompt_es_el_del_contrato():
    assert "NUNCA inventes montos" in SYSTEM_PROMPT
    assert "INDETERMINADO" in SYSTEM_PROMPT


def test_parse_verdict_prosa_es_indeterminado():
    verdict = parse_verdict("no sé qué responder")

    assert verdict.veredicto == "INDETERMINADO"
    assert verdict.confianza == 0.0
