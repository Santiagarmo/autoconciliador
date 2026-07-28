"""Pure domain enumerations for entity states.

Values are the strings persisted in PostgreSQL native ENUM types.
"""
from __future__ import annotations

import enum


class EstadoPedido(str, enum.Enum):
    PENDIENTE_PAGO = "PENDIENTE_PAGO"
    EN_VERIFICACION = "EN_VERIFICACION"
    LISTO_PARA_DESPACHO = "LISTO_PARA_DESPACHO"
    ALERTA_PAGO = "ALERTA_PAGO"
    DESPACHADO = "DESPACHADO"
    CANCELADO = "CANCELADO"


class EstadoPago(str, enum.Enum):
    REGISTRADO = "REGISTRADO"
    CONCILIADO = "CONCILIADO"
    RECHAZADO = "RECHAZADO"
    ALERTA_NO_ENCONTRADO = "ALERTA_NO_ENCONTRADO"


class EstadoMovimiento(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"
    CONCILIADO = "CONCILIADO"
    NO_OPERATIVO = "NO_OPERATIVO"


class TipoConciliacion(str, enum.Enum):
    AUTOMATICA = "AUTOMATICA"
    MANUAL_AUDITOR = "MANUAL_AUDITOR"


class RolUsuario(str, enum.Enum):
    """System roles. The advisor registers payments but never dispatches;
    the auditor reconciles manually and releases orders for dispatch."""

    ASESOR = "ASESOR"
    AUDITOR = "AUDITOR"


class ResultadoVerificacion(str, enum.Enum):
    """Verdict of ``StatementVerifier`` (and, later, ``StatementReviewer``)
    for one statement ingestion. Deliberately not named after "auditor" —
    that word already means the human ``RolUsuario.AUDITOR`` in this domain.
    """

    OK = "OK"
    DISCREPANCIA = "DISCREPANCIA"
    NO_VERIFICABLE = "NO_VERIFICABLE"
    ERROR = "ERROR"
