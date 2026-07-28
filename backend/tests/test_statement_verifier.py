"""StatementVerifier — pure unit tests, no DB, no PDF.

Each test hand-builds a ``ParsedStatement`` to isolate exactly one check.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.domain.enums import ResultadoVerificacion
from app.schemas.extracto import LineaCruda, ParsedStatement, ResumenExtracto
from app.schemas.movimiento_bancario import MovimientoBancarioParsed
from app.services.statement_verifier import Severidad, StatementVerifier

_FECHA = datetime(2026, 7, 4, tzinfo=timezone.utc)


def _fila(monto: str, saldo: str) -> MovimientoBancarioParsed:
    return MovimientoBancarioParsed(
        banco_origen="BANCOLOMBIA",
        fecha_movimiento=_FECHA,
        monto_real=Decimal(monto),
        saldo_posterior=Decimal(saldo),
        numero_referencia=None,
        descripcion_concepto="MOV",
    )


def _candidatas(n: int) -> list[LineaCruda]:
    return [LineaCruda(pagina=1, indice=i, texto=f"{i}/07 MOV 1.00 1.00") for i in range(n)]


def test_extracto_limpio_es_ok():
    filas = [_fila("100.00", "1100.00"), _fila("-50.00", "1050.00"), _fila("20.00", "1070.00")]
    doc = ParsedStatement(
        banco="BANCOLOMBIA",
        filas=filas,
        resumen=ResumenExtracto(
            saldo_anterior=Decimal("1000.00"),
            total_abonos=Decimal("120.00"),
            total_cargos=Decimal("50.00"),
            saldo_actual=Decimal("1070.00"),
        ),
        lineas_candidatas=_candidatas(3),
        lineas_totales=3,
    )
    result = StatementVerifier().verify(doc)
    assert result.resultado is ResultadoVerificacion.OK
    assert result.filas_emitidas == 3
    assert not any(h.severidad is Severidad.CRITICO for h in result.hallazgos)


def test_fila_faltante_en_medio_rompe_cadena():
    # Original chain: 1000 -[100]-> 1100 -[-50]-> 1050 -[20]-> 1070.
    # Middle row (-50 -> 1050) dropped: filas jumps straight to the 3rd row.
    filas = [_fila("100.00", "1100.00"), _fila("20.00", "1070.00")]
    doc = ParsedStatement(banco="BANCOLOMBIA", filas=filas, lineas_totales=2)
    result = StatementVerifier().verify(doc)

    assert result.resultado is ResultadoVerificacion.DISCREPANCIA
    criticos = [h for h in result.hallazgos if h.severidad is Severidad.CRITICO]
    assert len(criticos) == 1
    assert criticos[0].codigo == "CADENA_SALDOS"
    assert criticos[0].indice_fila == 1


def test_primera_fila_faltante_la_atrapa_ancla_saldo_anterior():
    # True chain: anterior=1000 -[100]-> 1100 -[-50]-> 1050. First row dropped:
    # filas=[row2] only. Pairwise check can't run (needs >=2 rows), but the
    # saldo_anterior anchor must still catch it.
    filas = [_fila("-50.00", "1050.00"), _fila("20.00", "1070.00")]
    doc = ParsedStatement(
        banco="BANCOLOMBIA",
        filas=filas,
        resumen=ResumenExtracto(saldo_anterior=Decimal("1000.00")),
        lineas_totales=2,
    )
    result = StatementVerifier().verify(doc)

    assert result.resultado is ResultadoVerificacion.DISCREPANCIA
    criticos = [h for h in result.hallazgos if h.severidad is Severidad.CRITICO]
    assert len(criticos) == 1
    assert criticos[0].codigo == "CADENA_SALDOS"
    assert criticos[0].indice_fila == 0


def test_ultima_fila_faltante_la_atrapa_ancla_saldo_actual():
    filas = [_fila("100.00", "1100.00"), _fila("-50.00", "1050.00")]
    doc = ParsedStatement(
        banco="BANCOLOMBIA",
        filas=filas,
        resumen=ResumenExtracto(saldo_actual=Decimal("1070.00")),
        lineas_totales=2,
    )
    result = StatementVerifier().verify(doc)

    assert result.resultado is ResultadoVerificacion.DISCREPANCIA
    criticos = [h for h in result.hallazgos if h.severidad is Severidad.CRITICO]
    assert len(criticos) == 1
    assert criticos[0].codigo == "CADENA_SALDOS"
    assert criticos[0].indice_fila == len(filas) - 1


def test_total_abonos_desviado_dispara_hallazgo_resumen():
    filas = [_fila("100.00", "1100.00"), _fila("20.00", "1120.00")]
    doc = ParsedStatement(
        banco="BANCOLOMBIA",
        filas=filas,
        resumen=ResumenExtracto(total_abonos=Decimal("120.01")),  # off by 0.01
        lineas_totales=2,
    )
    result = StatementVerifier().verify(doc)

    assert result.resultado is ResultadoVerificacion.DISCREPANCIA
    codigos = [h.codigo for h in result.hallazgos]
    assert codigos == ["RESUMEN_ABONOS"]


def test_extracto_no_ordenado_por_saldo_degrada_a_advertencia_unica():
    # 5 pairs, 4 broken (ratio 0.8 > 0.2 threshold, and total_pares is above
    # the small-sample floor) — must NOT explode into one CRITICO per broken
    # pair; must degrade to a single ADVERTENCIA.
    filas = [
        _fila("100.00", "1100.00"),
        _fila("50.00", "999.00"),    # breaks pair 0->1
        _fila("10.00", "500.00"),    # breaks pair 1->2
        _fila("5.00", "700.00"),     # breaks pair 2->3
        _fila("1.00", "1234.00"),    # breaks pair 3->4
        _fila("2.00", "1236.00"),    # this pair (4->5) actually holds
    ]
    doc = ParsedStatement(banco="BANCOLOMBIA", filas=filas, lineas_totales=6)
    result = StatementVerifier().verify(doc)

    assert len(result.hallazgos) == 1
    assert result.hallazgos[0].codigo == "CADENA_NO_APLICABLE"
    assert result.hallazgos[0].severidad is Severidad.ADVERTENCIA
    # ADVERTENCIA-only findings ride along on an OK verdict.
    assert result.resultado is ResultadoVerificacion.OK


def test_extracto_vacio_shape_stub_parser_es_no_verificable():
    doc = ParsedStatement(banco="STUB", filas=[])
    result = StatementVerifier().verify(doc)

    assert result.resultado is ResultadoVerificacion.NO_VERIFICABLE
    assert result.checks_ejecutados == ()
    assert result.hallazgos == ()


def test_conteo_filas_detecta_linea_perdida():
    filas = [_fila("100.00", "1100.00")]
    doc = ParsedStatement(
        banco="BANCOLOMBIA",
        filas=filas,
        lineas_candidatas=_candidatas(2),  # 2 candidate lines, only 1 row emitted
        lineas_totales=2,
    )
    result = StatementVerifier().verify(doc)

    assert result.resultado is ResultadoVerificacion.DISCREPANCIA
    assert any(h.codigo == "CONTEO_FILAS" for h in result.hallazgos)


def test_identidad_resumen_inconsistente_es_advertencia_no_critico():
    # Rows and cadena are perfectly fine; only the RESUMEN block's own
    # numbers don't add up (simulating a misread two-column value).
    filas = [_fila("100.00", "1100.00")]
    doc = ParsedStatement(
        banco="BANCOLOMBIA",
        filas=filas,
        resumen=ResumenExtracto(
            saldo_anterior=Decimal("1000.00"),
            total_abonos=Decimal("100.00"),
            total_cargos=Decimal("0.00"),
            saldo_actual=Decimal("9999.00"),  # inconsistent with the other 3
        ),
        lineas_totales=1,
    )
    result = StatementVerifier().verify(doc)

    identidad = [h for h in result.hallazgos if h.codigo == "RESUMEN_IDENTIDAD"]
    assert len(identidad) == 1
    assert identidad[0].severidad is Severidad.ADVERTENCIA
