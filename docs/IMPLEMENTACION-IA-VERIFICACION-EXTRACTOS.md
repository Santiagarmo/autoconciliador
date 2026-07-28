# Implementación del auditor IA (Qwen 2.5 7B Instruct) — guía de continuación

**Estado:** tier 1 (determinístico) completo y en producción. Tier 2 (LLM) tiene el seam
construido, sin modelo instalado. Este documento es la guía para conectar el modelo cuando
esté disponible.

## Contexto — qué se construyó y por qué

`app/workers/bancolombia_parser.py` puede descartar en silencio una línea del PDF que no
matchee su regex (`if match is None: continue`). Se validó contra un extracto real
(Bancolombia, junio 2026, 5 páginas, 216 movimientos) que el parser funciona al 100% —
pero esa garantía dependía de una auditoría manual línea por línea. No escala.

Se construyó `StatementVerifier` (tier 1): tres chequeos matemáticos independientes que
corren en **cada ingesta**, gratis, sin red ni modelo:

1. **Conteo de filas** — líneas candidatas (arrancan con fecha `D/MM`) vs filas emitidas.
2. **Cadena de saldos** — `saldo[n-1] + monto[n] == saldo[n]`, ancladas en los extremos
   contra el bloque RESUMEN del extracto (atrapa filas perdidas al principio o al final,
   que el recorrido de pares no puede ver).
3. **Bloque RESUMEN** — TOTAL ABONOS/CARGOS y SALDO ANTERIOR/ACTUAL, testigo independiente
   que no asume nada sobre el orden de las filas.

El veredicto (`OK` / `DISCREPANCIA` / `NO_VERIFICABLE` / `ERROR`) se persiste en
`verificaciones_extracto` (migración `0003_verificaciones_extracto`) y se ve en
`GET /api/movimientos/verificaciones` y en la tabla "Últimas ingestas" del frontend.

**Solo cuando tier 1 devuelve `DISCREPANCIA`** se escala a tier 2 — un `StatementReviewer`
que le pasa el hallazgo + contexto crudo a un LLM para una segunda opinión. Hoy ese
escalamiento llama a `NullStatementReviewer`, que devuelve `None` sin hacer nada: costo
cero, sin dependencias. Sobre el extracto real de referencia, los tres checks de tier 1
pasaron limpios — el LLM se habría invocado **cero veces**. Por diseño, es la excepción,
no la regla.

## Por qué el LLM vive en otra máquina

Este host (donde corre el backend hoy) no tiene GPU utilizable (Vega integrada, sin
CUDA/ROCm) y tiene poco margen de disco. El modelo (**Qwen 2.5 7B Instruct**) se despliega
en una PC distinta con **64 GB RAM + GPU dedicada de 8 GB** — ahí entra cómodo en Q4_K_M
(~4.7 GB en VRAM, deja margen para contexto). El proyecto completo (backend incluido)
puede desplegarse en esa misma máquina; lo que importa es que el modelo se sirve por un
endpoint HTTP compatible con OpenAI (Ollama / llama.cpp server / vLLM), y este backend le
habla por `LLM_BASE_URL` sin cargarlo nunca en el propio proceso. Si backend y modelo
terminan en la misma máquina, `LLM_BASE_URL` simplemente apunta a `localhost` o al nombre
del servicio en la red de docker — el código es idéntico en cualquier caso.

## Qué falta — pasos concretos

### 1. Levantar el servidor del modelo (en la PC con GPU)

Cualquier servidor OpenAI-compatible sirve; no hay atadura a uno en particular. Ejemplo con
Ollama (el más simple de operar):

```bash
# En la PC con GPU
ollama pull qwen2.5:7b-instruct
ollama serve   # expone /v1/chat/completions en :11434 por defecto
```

Confirmar que responde antes de tocar código:

```bash
curl http://<host-o-ip>:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5:7b-instruct","messages":[{"role":"user","content":"di OK"}]}'
```

### 2. Configurar las 6 variables (único punto de contacto con el deploy)

En `.env` (backend, o el `.env` que corresponda si el proyecto se despliega en la GPU PC):

```
LLM_REVIEW_ENABLED=True
LLM_BASE_URL=http://<host-o-localhost>:11434/v1
LLM_MODEL=qwen2.5:7b-instruct
LLM_API_KEY=                      # vacío si el servidor no pide auth
LLM_TIMEOUT_SECONDS=90.0
LLM_MAX_LINEAS_CONTEXTO=40
```

Definidas en `backend/app/core/config.py` y espejadas en `.env.example`. `LLM_REVIEW_ENABLED`
en `False` (default actual) mantiene `NullStatementReviewer` — nada se rompe si el endpoint
no está disponible todavía.

### 3. Implementar `OpenAICompatStatementReviewer.review()`

Archivo: `backend/app/services/llm_reviewer.py`. La clase ya existe, con
`raise NotImplementedError` — reemplazar el cuerpo. `httpx==0.28.1` ya es dependencia del
proyecto (mover su línea en `requirements.txt` fuera del bloque `# --- Testing (dev) ---`);
no hace falta un SDK de LLM.

Contrato ya definido en el docstring del módulo — resumen:

- **Request** (`StatementReviewRequest`): `banco`, `hallazgos` (los `Hallazgo` serializados
  que dispararon la `DISCREPANCIA`), `resumen` (bloque RESUMEN del extracto),
  `filas_emitidas`, `lineas_contexto` (SOLO las líneas candidatas, capadas a
  `LLM_MAX_LINEAS_CONTEXTO` — nunca el extracto completo: ni por longitud de contexto ni
  por PII, ya que `ParsedStatement.texto_paginas` trae nombre/dirección/número de cuenta del
  titular y no debe salir de este proceso en ese formato).
- **System prompt** (español): *"Eres un verificador de extractos bancarios. [...] Responde
  SOLO con JSON válido conforme al esquema. Si no estás seguro, responde INDETERMINADO.
  NUNCA inventes montos."*
- **Response**: pedir `response_format={"type": "json_object"}` si el servidor lo soporta;
  parsear con `StatementReviewVerdict.model_validate_json(...)` dentro de un
  `try/except ValidationError` — el modelo **va a** devolver prosa alguna vez; tratarlo como
  `INDETERMINADO`, nunca dejar que reviente el ingest.
- Reintento simple (un `for` de 1-2 intentos alcanza; no hace falta `tenacity`).

Regla de seguridad que ya está en el docstring y hay que respetar al implementar: el
veredicto es **asesor y nada más**. Nunca inserta un movimiento, nunca muta `estado_*`,
nunca dispara conciliación — solo se guarda en `VerificacionExtracto.revision_llm` para que
un humano lo lea.

### 4. Testear contra el modelo real

- Repetir manualmente el caso de `tests/test_verificacion_e2e.py`
  (`test_fila_saboteada_en_extracto_multipagina_produce_discrepancia`) pero con
  `LLM_REVIEW_ENABLED=True` apuntando al servidor real, y confirmar que
  `OpenAICompatStatementReviewer.review()` devuelve un `StatementReviewVerdict` coherente
  (idealmente `FILAS_FALTANTES` señalando la fila saboteada).
- Agregar un test de integración marcado explícitamente como "requiere LLM real" (se puede
  saltar en CI/entornos sin el endpoint arriba — usar `pytest.mark.skipif` sobre una env var
  tipo `LLM_INTEGRATION_TESTS=1`).
- Confirmar el caso de timeout/endpoint caído: `revision_llm` debe quedar con
  `{"error": "LLM no disponible"}` y el ingest debe completarse igual (ver
  `pdf_ingestion_service.py`, bloque `try/except Exception` alrededor de `reviewer.review(...)`).

### 5. Ajustar prompts con casos reales

El contrato de prompt es un punto de partida, no algo probado contra el modelo real todavía.
Al conectar Qwen por primera vez, esperar iterar:

- Confirmar que el modelo respeta "NUNCA inventes montos" — pedirle explícitamente que
  devuelva `INDETERMINADO` si no hay evidencia clara en `lineas_contexto`, y verificar que no
  alucina un monto cuando la línea es ambigua.
- Ajustar `LLM_MAX_LINEAS_CONTEXTO` según qué tan seguido el contexto se queda corto o de
  más (empieza en 40; el módulo lo expone como config sin tocar código).
- Medir latencia real (7B en GPU de 8GB debería responder en segundos, no minutos) y ajustar
  `LLM_TIMEOUT_SECONDS` si hace falta.

## Verificación rápida de que el seam sigue intacto

```bash
docker compose exec backend pytest -q tests/test_pdf_ingestion_service.py -k reviewer
# 2 tests: escalamiento SOLO en DISCREPANCIA, cero llamadas en OK
```

## Qué NO hacer al conectar el modelo (sobreingeniería / riesgo)

- No dejar que el veredicto del LLM inserte, edite o borre un `MovimientoBancario` — es
  asesor, punto.
- No mandar `texto_paginas` completo al modelo — ni por PII ni por costo de contexto.
- No agregar un SDK de LLM, `tenacity`, ni una cola/broker para esta llamada — es un `await`
  ocasional dentro de un background task que ya devolvió 202.
- No quitarle a `StatementVerifier` (tier 1) su poder de veto informativo — la discrepancia
  determinística sigue siendo la señal primaria; el LLM es una segunda opinión, no un
  reemplazo.
