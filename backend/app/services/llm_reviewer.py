"""StatementReviewer — tier 2, LLM-assisted second opinion.

``PDFIngestionService`` escalates a ``DISCREPANCIA`` verdict from
``StatementVerifier`` to an LLM for a second opinion. The escalation path is
exercised by tests via ``NullStatementReviewer`` (the default, off) and
``StubReviewer`` (test-only, ``tests/conftest.py``); ``OpenAICompatStatementReviewer``
below is the real implementation, talking HTTP to whatever OpenAI-compatible
endpoint ``LLM_BASE_URL`` points at.

Deploy targets today: a local Windows box with a GPU (Ollama, ``granite4.1:8b``,
see docs/IMPLEMENTACION-IA-LOCAL-GPU.md) and, longer-term, a CPU-only Hostinger
VPS (``granite4.1:3b`` — see docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md §
Consumo y dimensionamiento for why a 7-8B model doesn't fit a CPU timeout
budget). Either way this backend never loads a model in-process — it only ever
speaks HTTP, and the six settings in ``app.core.config`` are the only thing a
deploy decision touches.

SAFETY RULE — the reviewer's verdict is advisory ONLY. It is persisted to
``VerificacionExtracto.revision_llm`` and shown to a human. It must never:
insert a movement, mutate any ``estado_*``, or trigger reconciliation. A model
hallucinating a COP 3,000,000 movement into a reconciliation ledger is a far
worse outcome than the missing row it was asked to hunt for.

PROMPT CONTRACT:

System (Spanish, see ``SYSTEM_PROMPT`` below): verifies bank statements,
decides whether a raw line contains a movement that wasn't extracted, answers
ONLY with JSON per the schema, says INDETERMINADO when unsure, NEVER invents
amounts.

User: JSON matching ``StatementReviewRequest`` — the ``hallazgos`` that
triggered escalation, the RESUMEN block, and ONLY the ``lineas_contexto``
window (capped by ``LLM_MAX_LINEAS_CONTEXTO`` at the call site), never the
full statement — both a context-length and a PII-minimization concern:
``ParsedStatement.texto_paginas`` carries the account holder's name/address/
account number and must never be sent in full, or logged.

Response: ``response_format: {"type": "json_schema", "json_schema": {...}}``
built from ``StatementReviewVerdict.model_json_schema()`` — grammar-constrained
decoding, not just a JSON-mode hint. Verified against Ollama 0.32.5 on
``/v1/chat/completions``: it accepts the OpenAI-standard ``json_schema`` form
directly (no need for Ollama's proprietary ``format`` parameter, which would
require the native ``/api/chat`` endpoint and tie this module to one server —
``json_schema`` is also what vLLM and llama.cpp server accept, so
``LLM_BASE_URL`` stays swappable). The raw pydantic schema works as-is, with
``$defs``/``$ref`` intact — no flattening needed. Still, ``parse_verdict``
below validates defensively: assume the model WILL sometimes return prose
instead of JSON, and treat a validation failure as ``INDETERMINADO``, never a
crash.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.schemas.extracto import LineaCruda, ResumenExtracto

logger = logging.getLogger(__name__)


class StatementReviewRequest(BaseModel):
    banco: str
    hallazgos: list[dict]
    resumen: ResumenExtracto | None
    filas_emitidas: int
    lineas_contexto: list[LineaCruda]


class FilaSugerida(BaseModel):
    linea_cruda: str
    fecha: str | None = None
    monto: Decimal | None = None
    saldo_posterior: Decimal | None = None
    confianza: float


class StatementReviewVerdict(BaseModel):
    veredicto: Literal["FILAS_FALTANTES", "FALSO_POSITIVO", "INDETERMINADO"]
    confianza: float
    filas_sugeridas: list[FilaSugerida] = []
    explicacion: str


class StatementReviewer(ABC):
    """Second-opinion reviewer for a StatementVerifier DISCREPANCIA verdict.

    Returning ``None`` means "no review performed" (disabled, or the review
    itself failed — transport error, timeout, unreachable endpoint) — NOT
    "reviewed and found nothing wrong". Callers must not conflate the two.
    A verdict of ``INDETERMINADO`` is different: the model DID respond, its
    answer just didn't validate or wasn't conclusive.
    """

    @abstractmethod
    async def review(
        self, request: StatementReviewRequest
    ) -> StatementReviewVerdict | None: ...


class NullStatementReviewer(StatementReviewer):
    """The default when ``LLM_REVIEW_ENABLED`` is off. Zero cost, zero deps."""

    async def review(
        self, request: StatementReviewRequest
    ) -> StatementReviewVerdict | None:
        return None


# System prompt — verbatim per the contract above. Change here only, and
# expect to iterate against real cases per docs/IMPLEMENTACION-IA-VERIFICACION-
# EXTRACTOS.md § "Ajustar prompts y timeout con casos reales" — this is a
# starting point, not something tuned against the real model yet.
SYSTEM_PROMPT = (
    "Eres un verificador de extractos bancarios. Recibes líneas de texto "
    "crudo de un extracto y una discrepancia aritmética detectada. Tu única "
    "tarea es decidir si alguna línea contiene un movimiento que no fue "
    "extraído. Responde SOLO con JSON válido conforme al esquema. Si no "
    "estás seguro, responde INDETERMINADO. NUNCA inventes montos."
)

# One retry is enough for a transient timeout/5xx; no backoff library per
# docs' "Qué NO hacer" (no tenacity for an occasional await in a background
# task that already returned 202).
_MAX_INTENTOS = 2


def build_messages(request: StatementReviewRequest) -> list[dict]:
    """System prompt + the request serialized as the user message.

    Uses ``model_dump_json()``, NOT ``json.dumps(request.model_dump())`` —
    ``resumen`` carries ``Decimal`` fields and ``json.dumps`` raises
    ``TypeError: Object of type Decimal is not JSON serializable`` on those.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request.model_dump_json()},
    ]


def build_payload(request: StatementReviewRequest) -> dict:
    return {
        "model": settings.LLM_MODEL,
        "messages": build_messages(request),
        "temperature": 0,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "StatementReviewVerdict",
                "strict": True,
                "schema": StatementReviewVerdict.model_json_schema(),
            },
        },
    }


def build_headers() -> dict[str, str]:
    """Authorization header only when the endpoint requires one."""
    headers = {"Content-Type": "application/json"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
    return headers


def _clamp_confianzas(verdict: StatementReviewVerdict) -> StatementReviewVerdict:
    """Clamp confidence values into [0, 1].

    ``confianza: float`` has no ``ge``/``le`` and the JSON Schema the model
    sees only says ``"type": "number"`` — nothing stops it returning e.g.
    ``95`` (percentage-thinking) or ``1.5``. This value is persisted to
    ``revision_llm`` and read by a human, so an out-of-range number needs
    normalizing, not silent trust. Clamp rather than reject: ``veredicto``
    itself is already constrained by the schema's enum, so an odd confidence
    doesn't invalidate the rest of the verdict. No divide-by-100 guess at
    scale — capping is safer than assuming what the model meant.
    """
    verdict.confianza = min(1.0, max(0.0, verdict.confianza))
    for fila in verdict.filas_sugeridas:
        fila.confianza = min(1.0, max(0.0, fila.confianza))
    return verdict


def parse_verdict(content: str) -> StatementReviewVerdict:
    """Defensive parse: the model WILL sometimes return prose instead of JSON."""
    try:
        verdict = StatementReviewVerdict.model_validate_json(content)
    except ValidationError:
        # Deliberately not logging `content`: it's derived from
        # lineas_contexto, which carries raw movement descriptions — same
        # PII-minimization rule as texto_paginas never leaving this process.
        logger.warning(
            "Respuesta del LLM no conforma StatementReviewVerdict; "
            "se degrada a INDETERMINADO."
        )
        return StatementReviewVerdict(
            veredicto="INDETERMINADO",
            confianza=0.0,
            explicacion="El modelo devolvió una respuesta no interpretable.",
        )
    return _clamp_confianzas(verdict)


class OpenAICompatStatementReviewer(StatementReviewer):
    """Talks to any OpenAI-compatible ``/v1/chat/completions`` endpoint
    (Ollama, llama.cpp server, vLLM) named by ``LLM_BASE_URL``.

    Failure handling, by design (see ``StatementReviewer`` docstring):

    - Transport failure (timeout, connection refused, non-2xx, malformed
      response shape) after retries -> returns ``None``. The model never
      opined; persisting an ``INDETERMINADO`` verdict here would claim
      otherwise. ``pdf_ingestion_service`` leaves
      ``revisado_por_llm=False, revision_llm=NULL`` in this case — a clean
      state, same as ``NullStatementReviewer``.
    - Model responded but the content doesn't validate as
      ``StatementReviewVerdict`` -> returns an ``INDETERMINADO`` verdict
      (``parse_verdict``). The model DID opine; the output just wasn't usable.
    - Anything else unexpected propagates as an exception — caught by
      ``pdf_ingestion_service``'s existing safety net
      (``revision_llm = {"error": "LLM no disponible"}``), which stays a
      backstop for genuine bugs, not the normal "endpoint down" path.
    """

    async def review(
        self, request: StatementReviewRequest
    ) -> StatementReviewVerdict | None:
        url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
        payload = build_payload(request)
        headers = build_headers()

        # A client per call, not a module-level shared one: this escalation
        # is exceptional (only on DISCREPANCIA) and already runs inside a
        # background task that returned 202 — a shared client would need its
        # lifecycle tied to FastAPI's lifespan and a specific event loop, to
        # save a TCP handshake that happens rarely.
        #
        # `timeout=` as a bare float applies to connect/read/write/pool alike
        # and is a PER-ATTEMPT budget, so worst case across _MAX_INTENTOS is
        # ~2x LLM_TIMEOUT_SECONDS. Acceptable for a post-202 background task
        # (observed latency in practice: ~12s against granite4.1:8b).
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            for intento in range(1, _MAX_INTENTOS + 1):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                    # httpx.HTTPError covers TimeoutException, ConnectError,
                    # HTTPStatusError (raise_for_status), ReadError. ValueError
                    # covers a non-JSON body (JSONDecodeError). KeyError/
                    # IndexError cover a 200 with an unexpected shape.
                    logger.warning(
                        "Intento %d/%d contra el endpoint LLM falló: %s",
                        intento,
                        _MAX_INTENTOS,
                        exc,
                    )
                    continue
                return parse_verdict(content)

        logger.warning(
            "StatementReviewer: %d intentos agotados contra %s; sin veredicto.",
            _MAX_INTENTOS,
            url,
        )
        return None


def get_statement_reviewer() -> StatementReviewer:
    if not settings.LLM_REVIEW_ENABLED:
        return NullStatementReviewer()
    return OpenAICompatStatementReviewer()
