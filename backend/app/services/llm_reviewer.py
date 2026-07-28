"""StatementReviewer — tier 2, LLM-assisted second opinion (SEAM ONLY).

No model is installed or called by this module. It exists so
``PDFIngestionService`` can escalate a ``DISCREPANCIA`` verdict from
``StatementVerifier`` to an LLM for a second opinion, with the escalation
path itself fully exercised by tests today via ``NullStatementReviewer``
(the default) and ``StubReviewer`` (test-only, ``tests/conftest.py``).

Deploy target: Granite 4.1 3B, running on the same Hostinger VPS as this
backend, CPU-only (no GPU there — see docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md
§ Consumo y dimensionamiento before assuming otherwise), served through any
OpenAI-compatible HTTP endpoint (Ollama, llama.cpp server, vLLM). A GPU box
remains a valid alternative deploy (e.g. granite4.1:8b once GPU is available);
either way, this backend talks to the model over HTTP via ``LLM_BASE_URL`` —
it never loads the model in-process. The six settings in ``app.core.config``
are the ONLY thing a deploy decision touches; this module's code is identical
regardless of what sits behind that URL. Model choice is sized for CPU
latency, not just RAM: a 7-8B model on 2 vCPU runs ~2.5-3 min per verdict,
past any sane timeout — see the doc for the numbers behind this pick.

SAFETY RULE — the reviewer's verdict is advisory ONLY. It is persisted to
``VerificacionExtracto.revision_llm`` and shown to a human. It must never:
insert a movement, mutate any ``estado_*``, or trigger reconciliation. A 7B
model hallucinating a COP 3,000,000 movement into a reconciliation ledger is
a far worse outcome than the missing row it was asked to hunt for.

PROMPT CONTRACT (design artifact — not yet exercised against a real model):

System (Spanish): "Eres un verificador de extractos bancarios. Recibes
líneas de texto crudo de un extracto y una discrepancia aritmética
detectada. Tu única tarea es decidir si alguna línea contiene un movimiento
que no fue extraído. Responde SOLO con JSON válido conforme al esquema. Si
no estás seguro, responde INDETERMINADO. NUNCA inventes montos."

User: JSON matching ``StatementReviewRequest`` — the ``hallazgos`` that
triggered escalation, the RESUMEN block, and ONLY the ``lineas_contexto``
window (±``LLM_MAX_LINEAS_CONTEXTO/2`` lines around each break, never the
full statement — both a context-length and a PII-minimization concern:
``ParsedStatement.texto_paginas`` carries the account holder's name/address/
account number and must never be sent in full).

Response: request ``response_format={"type": "json_object"}`` where the
server supports it, then ``StatementReviewVerdict.model_validate_json``
defensively — assume the model WILL sometimes return prose instead of JSON,
and treat a validation failure as ``INDETERMINADO``, never as a crash.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.core.config import settings
from app.schemas.extracto import LineaCruda, ResumenExtracto


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
    itself failed) — NOT "reviewed and found nothing wrong". Callers must
    not conflate the two.
    """

    @abstractmethod
    async def review(
        self, request: StatementReviewRequest
    ) -> StatementReviewVerdict | None: ...


class NullStatementReviewer(StatementReviewer):
    """The default, always, until a real endpoint is configured and reachable."""

    async def review(
        self, request: StatementReviewRequest
    ) -> StatementReviewVerdict | None:
        return None


class OpenAICompatStatementReviewer(StatementReviewer):
    """DEFERRED: pendiente de que el endpoint Granite esté arriba en el VPS
    (ver ``LLM_BASE_URL``). Sigue el idiom de ``NequiParser``: clase
    nombrada, sin cablear, ``NotImplementedError`` explícito — nadie la
    instancia hasta que ``get_statement_reviewer()`` decida hacerlo.

    Implementation note for later: ``httpx`` is already a project dependency
    (currently listed under "Testing (dev)" in requirements.txt — move that
    line when this lands) and is the client to use; no new package needed.
    """

    async def review(
        self, request: StatementReviewRequest
    ) -> StatementReviewVerdict | None:
        raise NotImplementedError(
            "OpenAICompatStatementReviewer pendiente del endpoint LLM "
            "(LLM_BASE_URL) en la máquina donde corra Granite 4.1 3B."
        )


def get_statement_reviewer() -> StatementReviewer:
    if not settings.LLM_REVIEW_ENABLED:
        return NullStatementReviewer()
    return OpenAICompatStatementReviewer()
