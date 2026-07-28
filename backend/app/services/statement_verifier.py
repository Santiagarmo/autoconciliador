"""StatementVerifier — deterministic, tier-1 completeness check.

Runs on every ingestion, before persistence, at ~zero cost. Cross-checks a
``ParsedStatement`` three independent ways so that a layout change or a
silently-dropped row (e.g. ``bancolombia_parser.py``'s ``if match is None:
continue``) surfaces as a verdict instead of vanishing into logs:

1. ``CONTEO_FILAS`` — candidate row-looking lines vs rows actually emitted.
2. ``CADENA_SALDOS`` — ``saldo_posterior[n-1] + monto_real[n] == saldo_posterior[n]``,
   the mathematical proof that no row is missing, anchored at both ends
   against the statement's own RESUMEN block so a row dropped at the very
   first or last position (invisible to the pairwise walk) is still caught.
3. ``RESUMEN_*`` — the statement's own totals (TOTAL ABONOS/CARGOS, SALDO
   ANTERIOR/ACTUAL), which assume nothing about row order.

Any one check can be defeated by an unexpected layout; all three failing at
once while hiding a missing row is not credible. Each check is skipped
(not failed) when its inputs are absent, so a parser strategy with no
provenance/resumen support (the ``BankParserStrategy.parse_document``
default, e.g. ``StubParser``/``NequiParser``) correctly rolls up to
``NO_VERIFICABLE`` rather than a false ``DISCREPANCIA``.

IMPORTANT — a ``DISCREPANCIA`` verdict must NEVER block persistence. The
rows parsed are real money movements regardless of the verdict; refusing to
insert them because one row *might* be missing turns a partial-data problem
into a no-data problem, and a false positive would halt the business. This
verifier only flags, loudly, for a human (and, on escalation, a
``StatementReviewer``) to look at.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.enums import ResultadoVerificacion
from app.schemas.extracto import ParsedStatement

# A statement laid out with rows NOT in saldo-chain order degrades this
# check to "not applicable" rather than emitting one false CRITICO per pair.
# The ratio fallback only kicks in once there are enough pairs to tell "this
# layout isn't chain-ordered" apart from "one row is genuinely missing" —
# below that floor, any break is reported as CRITICO regardless of ratio
# (e.g. a 2-row statement with its one pair broken is not "20% ambiguous",
# it's a single missing row).
_CADENA_NO_APLICABLE_RATIO = 0.2
_CADENA_NO_APLICABLE_MIN_PARES = 5


class Severidad(str, enum.Enum):
    INFO = "INFO"
    ADVERTENCIA = "ADVERTENCIA"
    CRITICO = "CRITICO"


@dataclass(frozen=True)
class Hallazgo:
    codigo: str
    severidad: Severidad
    detalle: str
    indice_fila: int | None = None
    pagina: int | None = None


@dataclass(frozen=True)
class VerificacionResult:
    resultado: ResultadoVerificacion
    filas_emitidas: int
    filas_candidatas: int
    checks_ejecutados: tuple[str, ...] = field(default_factory=tuple)
    hallazgos: tuple[Hallazgo, ...] = field(default_factory=tuple)


def _cap(texto: str, n: int = 200) -> str:
    return texto if len(texto) <= n else texto[: n - 1] + "…"


class StatementVerifier:
    """Pure: no session, no I/O, no repository. Mirrors the frozen-dataclass
    summary convention of ``IngestSummary``/``ReconSummary``."""

    def verify(self, doc: ParsedStatement) -> VerificacionResult:
        checks: list[str] = []
        hallazgos: list[Hallazgo] = []

        self._check_conteo_filas(doc, checks, hallazgos)
        self._check_cadena_saldos(doc, checks, hallazgos)
        self._check_resumen(doc, checks, hallazgos)

        if not checks:
            resultado = ResultadoVerificacion.NO_VERIFICABLE
        elif any(h.severidad is Severidad.CRITICO for h in hallazgos):
            resultado = ResultadoVerificacion.DISCREPANCIA
        else:
            resultado = ResultadoVerificacion.OK

        return VerificacionResult(
            resultado=resultado,
            filas_emitidas=len(doc.filas),
            filas_candidatas=len(doc.lineas_candidatas),
            checks_ejecutados=tuple(checks),
            hallazgos=tuple(hallazgos),
        )

    # --- checks --------------------------------------------------------

    def _check_conteo_filas(
        self, doc: ParsedStatement, checks: list[str], hallazgos: list[Hallazgo]
    ) -> None:
        if not doc.lineas_candidatas:
            return
        checks.append("CONTEO_FILAS")
        n_candidatas, n_filas = len(doc.lineas_candidatas), len(doc.filas)
        if n_candidatas == n_filas:
            return
        ejemplos = ", ".join(
            _cap(l.texto.strip(), 60) for l in doc.lineas_candidatas[:5]
        )
        hallazgos.append(
            Hallazgo(
                codigo="CONTEO_FILAS",
                severidad=Severidad.CRITICO,
                detalle=_cap(
                    f"{n_candidatas} líneas parecen movimientos (arrancan con "
                    f"fecha) pero se emitieron {n_filas} filas. Posible fila "
                    f"perdida/mal parseada. Ejemplos: {ejemplos}"
                ),
            )
        )

    def _check_cadena_saldos(
        self, doc: ParsedStatement, checks: list[str], hallazgos: list[Hallazgo]
    ) -> None:
        filas = doc.filas
        if len(filas) < 2:
            return
        checks.append("CADENA_SALDOS")

        roturas: list[tuple[int, Decimal, Decimal]] = []
        for i in range(1, len(filas)):
            esperado = filas[i - 1].saldo_posterior + filas[i].monto_real
            real = filas[i].saldo_posterior
            if esperado != real:
                roturas.append((i, esperado, real))

        total_pares = len(filas) - 1
        ratio = len(roturas) / total_pares if total_pares else 0.0
        no_aplicable = (
            total_pares >= _CADENA_NO_APLICABLE_MIN_PARES
            and ratio > _CADENA_NO_APLICABLE_RATIO
        )
        if roturas and no_aplicable:
            hallazgos.append(
                Hallazgo(
                    codigo="CADENA_NO_APLICABLE",
                    severidad=Severidad.ADVERTENCIA,
                    detalle=(
                        f"{len(roturas)}/{total_pares} pares consecutivos no "
                        "encadenan por saldo; el extracto no viene ordenado "
                        "por saldo y la verificación de cadena no aplica a "
                        "este layout."
                    ),
                )
            )
        else:
            for i, esperado, real in roturas:
                hallazgos.append(
                    Hallazgo(
                        codigo="CADENA_SALDOS",
                        severidad=Severidad.CRITICO,
                        detalle=_cap(
                            f"Posible fila faltante o mal parseada entre la "
                            f"fila {i - 1} y {i}: saldo esperado {esperado}, "
                            f"saldo real {real} (hueco {real - esperado})."
                        ),
                        indice_fila=i,
                    )
                )

        # Anchor the ends against the statement's own RESUMEN — the pairwise
        # walk above structurally cannot see a row dropped at position 0 or
        # -1, since there's no prior/next row to compare against.
        resumen = doc.resumen
        if resumen is not None:
            if resumen.saldo_anterior is not None:
                esperado_inicio = resumen.saldo_anterior + filas[0].monto_real
                if esperado_inicio != filas[0].saldo_posterior:
                    hallazgos.append(
                        Hallazgo(
                            codigo="CADENA_SALDOS",
                            severidad=Severidad.CRITICO,
                            detalle=_cap(
                                "Posible fila faltante antes de la primera "
                                f"fila: SALDO ANTERIOR + monto[0] = "
                                f"{esperado_inicio}, saldo real "
                                f"{filas[0].saldo_posterior}."
                            ),
                            indice_fila=0,
                        )
                    )
            if resumen.saldo_actual is not None:
                if filas[-1].saldo_posterior != resumen.saldo_actual:
                    hallazgos.append(
                        Hallazgo(
                            codigo="CADENA_SALDOS",
                            severidad=Severidad.CRITICO,
                            detalle=_cap(
                                "Posible fila faltante después de la última "
                                f"fila: saldo final de filas "
                                f"{filas[-1].saldo_posterior}, SALDO ACTUAL "
                                f"del extracto {resumen.saldo_actual}."
                            ),
                            indice_fila=len(filas) - 1,
                        )
                    )

    def _check_resumen(
        self, doc: ParsedStatement, checks: list[str], hallazgos: list[Hallazgo]
    ) -> None:
        resumen = doc.resumen
        if resumen is None:
            return

        abonos = sum((f.monto_real for f in doc.filas if f.monto_real > 0), Decimal("0"))
        cargos = sum((-f.monto_real for f in doc.filas if f.monto_real < 0), Decimal("0"))

        if resumen.total_abonos is not None:
            checks.append("RESUMEN_ABONOS")
            if abonos != resumen.total_abonos:
                hallazgos.append(
                    Hallazgo(
                        codigo="RESUMEN_ABONOS",
                        severidad=Severidad.CRITICO,
                        detalle=_cap(
                            f"Suma de abonos parseados ({abonos}) no coincide "
                            f"con TOTAL ABONOS del extracto "
                            f"({resumen.total_abonos}); delta "
                            f"{abonos - resumen.total_abonos}."
                        ),
                    )
                )

        if resumen.total_cargos is not None:
            checks.append("RESUMEN_CARGOS")
            if cargos != resumen.total_cargos:
                hallazgos.append(
                    Hallazgo(
                        codigo="RESUMEN_CARGOS",
                        severidad=Severidad.CRITICO,
                        detalle=_cap(
                            f"Suma de cargos parseados ({cargos}) no coincide "
                            f"con TOTAL CARGOS del extracto "
                            f"({resumen.total_cargos}); delta "
                            f"{cargos - resumen.total_cargos}."
                        ),
                    )
                )

        campos_identidad = (
            resumen.saldo_anterior,
            resumen.total_abonos,
            resumen.total_cargos,
            resumen.saldo_actual,
        )
        if all(c is not None for c in campos_identidad):
            checks.append("RESUMEN_IDENTIDAD")
            esperado = resumen.saldo_anterior + resumen.total_abonos - resumen.total_cargos
            if esperado != resumen.saldo_actual:
                # The rows themselves may be perfectly fine — this fires when
                # the RESUMEN block's own numbers are internally inconsistent,
                # most likely because the two-column layout was misread (e.g.
                # SALDO PROMEDIO grabbed instead of SALDO ANTERIOR). Downgraded
                # to ADVERTENCIA rather than CRITICO for exactly that reason.
                hallazgos.append(
                    Hallazgo(
                        codigo="RESUMEN_IDENTIDAD",
                        severidad=Severidad.ADVERTENCIA,
                        detalle=_cap(
                            "El bloque RESUMEN es internamente inconsistente "
                            f"(posible lectura incorrecta de columna): SALDO "
                            f"ANTERIOR + ABONOS - CARGOS = {esperado}, SALDO "
                            f"ACTUAL declarado {resumen.saldo_actual}."
                        ),
                    )
                )
