# Implementación del auditor IA (Granite 4.1) — guía de continuación

**Estado:** tier 1 (determinístico) completo y en producción. Tier 2 (LLM) implementado y
probado contra un modelo real (`granite4.1:8b` en la PC local con GPU — ver
`docs/IMPLEMENTACION-IA-LOCAL-GPU.md`). El destino de producción sigue siendo el VPS
Hostinger CPU-only con `granite4.1:3b`; ese despliegue queda pendiente, pero el código de
`OpenAICompatStatementReviewer.review()` es el mismo en ambos casos — solo cambian las 6
variables de `.env`. Este documento describe el diseño ya construido y qué falta para el
despliegue en VPS.

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
que le pasa el hallazgo + contexto crudo a un LLM para una segunda opinión. Con
`LLM_REVIEW_ENABLED=False` (default) ese escalamiento llama a `NullStatementReviewer`, que
devuelve `None` sin hacer nada: costo cero, sin dependencias. Con `LLM_REVIEW_ENABLED=True`
llama a `OpenAICompatStatementReviewer.review()` (implementado, ver §3), que le habla por
HTTP al endpoint de `LLM_BASE_URL`. Sobre el extracto real de referencia, los tres checks de
tier 1 pasaron limpios — el LLM se habría invocado **cero veces**. Por diseño, es la
excepción, no la regla.

## Dónde corre el modelo

Este host (donde corre el backend hoy) no tiene GPU utilizable (Vega integrada, sin
CUDA/ROCm). El destino de despliegue del proyecto es un **VPS de Hostinger sin GPU** —
Ollama corre ahí mismo, en CPU, junto al backend. Por eso el modelo elegido es
**Granite 4.1 3B**, no un 7-8B: en 2 vCPU un 7-8B genera a ~1.5-2 tok/s
(~2.5-3 min por veredicto), muy por encima de cualquier `LLM_TIMEOUT_SECONDS` razonable.
Ver § "Consumo y dimensionamiento" para las cuentas completas.

Si en algún momento aparece una máquina con GPU dedicada (el escenario original
contemplaba una PC con 64 GB RAM + 8 GB VRAM), sigue siendo un destino válido — ahí
entra cómodo `granite4.1:8b` (5.3 GB en Q4_K_M, IFEval más alto) sin tocar código, solo
las 6 variables de configuración. Lo que importa en cualquier caso: el modelo se sirve
por un endpoint HTTP compatible con OpenAI (Ollama / llama.cpp server / vLLM), y este
backend le habla por `LLM_BASE_URL` sin cargarlo nunca en el propio proceso.

## Consumo y dimensionamiento

Decisión: `granite4.1:3b` (IBM Granite 4.1 3B, Apache 2.0), quantización Q4_K_M.

Por qué este y no un 7-8B:

- **Cabe y responde a tiempo.** ~4-5 tok/s estimados en 2 vCPU → veredicto en ~60-90 s,
  dentro de un timeout de 90 s. Un 7-8B no llega (ver tabla).
- **La tarea premia obediencia, no potencia.** El reviewer debe devolver
  `INDETERMINADO` cuando no hay evidencia clara y nunca inventar montos — eso es
  seguimiento de instrucciones (IFEval), no razonamiento profundo. Granite 4.1 3B mide
  82.3 en IFEval, por encima de Qwen 2.5 7B Instruct (~75).
- **Salida JSON estructurada nativa** y **español como idioma soportado oficialmente**
  en el model card de IBM (no "y otros N idiomas más").
- Apache 2.0, sin fricción de licencia.

Nota de arquitectura: Granite 4.1 es un **transformer denso**, no un híbrido Mamba-2 —
los variantes `h` con KV cache reducido son de **Granite 4.0**. No hay ventaja de
memoria sobre Qwen acá; se elige por IFEval y por orientación a extracción documental.

Tabla de referencia (Ollama, Q4_K_M). Los tok/s están **extrapolados de benchmarks
públicos en 4 vCPU** (modelos de 1.5B-3.8B midieron 6-17 tok/s), **no medidos en el
hardware destino** — confirmar en el VPS real antes de fijar `LLM_TIMEOUT_SECONDS`:

| Modelo | Pesos | RSS aprox. | tok/s @2 vCPU (est.) | Veredicto |
|---|---|---|---|---|
| `granite4.1:3b` (elegido) | 2.1 GB | ~2.5 GB | ~4-5 | ~60-90 s |
| `qwen3:4b-instruct-2507` (alternativa) | 2.5 GB | ~3 GB | ~3-4 | ~70-100 s |
| `qwen2.5:7b-instruct` (plan original, descartado) | 4.7 GB | ~5.3 GB | ~1.5-2 | ~2.5-3 min ❌ |
| `granite4.1:8b` (VPS, hipotético) | 5.3 GB | ~6 GB | ~1.5-2 | ~3 min ❌ |

GPU en el VPS: 0 — la fila `granite4.1:8b` de la tabla sigue siendo la proyección para *ese*
caso (CPU pura), no medida.

**Medición real (2026-07-28, no en el VPS):** `granite4.1:8b` corriendo en la PC local con
GPU (RTX 2060 6 GB, split 31%/69% CPU/GPU) respondió en **~12 s** de wall-clock para el caso
saboteado de `test_verificacion_e2e.py` (377 tokens de prompt, 139 de respuesta) — ver
`docs/IMPLEMENTACION-IA-LOCAL-GPU.md` para el detalle de esa máquina. Las estimaciones de
CPU-only de la tabla de arriba siguen sin confirmar contra el VPS real.

Plan de VPS de referencia: Hostinger KVM 2 (2 vCPU, 8 GB RAM, ~$8.99/mes) alcanza para
backend + Postgres + frontend + `granite4.1:3b` bajo demanda. No hace falta subir a un
plan más grande solo por el LLM.

Dos ajustes operativos a nivel de servidor Ollama (no leídos por este backend):

1. **`OLLAMA_KEEP_ALIVE=0`** — el modelo se carga bajo demanda y libera la RAM al
   terminar. Como el LLM se invoca casi nunca (ver arriba: cero veces sobre el extracto
   de referencia), tener ~2.5 GB residentes 24/7 para una llamada esporádica es
   desperdicio. Costo: ~3-8 s de carga desde NVMe por invocación, irrelevante contra un
   timeout de 90 s.
2. **`OLLAMA_NUM_THREAD=1`** — durante la generación, llama.cpp satura los vCPU
   disponibles y compite con Postgres/FastAPI. Limitarlo a un hilo deja el otro núcleo
   libre. Aceptable porque la llamada vive en un background task que ya devolvió 202.

## Diseño implementado

`OpenAICompatStatementReviewer.review()` (`backend/app/services/llm_reviewer.py`) está
implementado y probado contra un modelo real. `httpx==0.28.1` pasó a un bloque de producción
propio en `requirements.txt` (ya no vive bajo `# --- Testing (dev) ---`) — sigue siendo la
única dependencia HTTP, sin SDK de LLM.

Contrato tal como quedó construido:

- **Request** (`StatementReviewRequest`): `banco`, `hallazgos` (los `Hallazgo` serializados
  que dispararon la `DISCREPANCIA`), `resumen` (bloque RESUMEN del extracto),
  `filas_emitidas`, `lineas_contexto` (SOLO las líneas candidatas, capadas a
  `LLM_MAX_LINEAS_CONTEXTO` — nunca el extracto completo: ni por longitud de contexto ni
  por PII, ya que `ParsedStatement.texto_paginas` trae nombre/dirección/número de cuenta del
  titular y no debe salir de este proceso en ese formato). Serializado con
  `model_dump_json()` — `resumen` trae `Decimal`, y `json.dumps(model_dump())` revienta con
  `TypeError` sobre esos campos.
- **System prompt** (español, verbatim, constante `SYSTEM_PROMPT` en el módulo): *"Eres un
  verificador de extractos bancarios. [...] Responde SOLO con JSON válido conforme al
  esquema. Si no estás seguro, responde INDETERMINADO. NUNCA inventes montos."*
- **Response**: `response_format: {"type": "json_schema", "json_schema": {...}}` con el
  schema completo de `StatementReviewVerdict.model_json_schema()` — ver nota más abajo sobre
  por qué no es el parámetro `format` nativo de Ollama. Parseo con
  `StatementReviewVerdict.model_validate_json(...)` dentro de `try/except ValidationError` →
  degrada a `INDETERMINADO`, nunca revienta el ingest (`parse_verdict()`).
- `confianza` se clampea a `[0, 1]` tras el parseo (`_clamp_confianzas()`) — el schema solo
  fuerza `"type": "number"`, nada impide que el modelo devuelva `95` pensando en porcentaje;
  ese valor lo lee un humano en `revision_llm`.
- Reintento simple: `_MAX_INTENTOS = 2`, sin `tenacity`.
- **Semántica de fallo, más estricta que el contrato original:** `review()` devuelve `None`
  ante cualquier fallo de transporte (timeout, conexión rechazada, HTTP no-2xx, forma de
  respuesta inesperada) — nunca un veredicto `INDETERMINADO` ni una excepción. Solo cuando el
  modelo **sí respondió** pero el contenido no valida como `StatementReviewVerdict` se
  devuelve `INDETERMINADO`. Ver la corrección en la sección "Testear contra el modelo real"
  más abajo — esto reemplaza lo que decía antes esta sección.

**Nota sobre el mecanismo de JSON forzado (cambio respecto al contrato original):**
ExtractBench (2026) midió ~51% de tasa de JSON válido entre seis modelos evaluados — pedir
`response_format={"type":"json_object"}` no es garantía suficiente, eso seguía siendo
correcto. Pero el contrato original recomendaba el parámetro `format` nativo de Ollama para
resolverlo — **eso hay que evitarlo**: `format` vive en el endpoint nativo `/api/chat`, no en
`/v1/chat/completions`, así que usarlo habría roto `LLM_BASE_URL` (apunta a `/v1`) y atado el
backend a un servidor en particular, justo lo que este documento pide no hacer. Verificado
contra Ollama 0.32.5: `/v1/chat/completions` acepta directamente el
`response_format.json_schema` estándar de OpenAI, con la misma decodificación restringida
por gramática, y el schema crudo de pydantic (`$defs`/`$ref` incluidos) funciona sin
aplanarlo. vLLM y llama.cpp server también lo soportan — `LLM_BASE_URL` sigue intercambiable.

Regla de seguridad respetada: el veredicto es **asesor y nada más**. Nunca inserta un
movimiento, nunca muta `estado_*`, nunca dispara conciliación — solo se guarda en
`VerificacionExtracto.revision_llm` para que un humano lo lea.

## Testear contra el modelo real

- `backend/tests/test_llm_reviewer.py` — unit tests contra un `httpx.MockTransport`, sin red
  ni Postgres: happy path, JSON malformado → `INDETERMINADO`, HTTP 500/timeout → `None`,
  reintento que se recupera, clamp de `confianza`, y el test de PII que confirma que
  `texto_paginas` nunca llega al payload.
- `backend/tests/test_llm_reviewer_integration.py` — gateado por `pytest.mark.skipif` sobre
  `LLM_INTEGRATION_TESTS=1` (no corre en `pytest -q` por defecto). Repite el caso saboteado de
  `test_verificacion_e2e.py` contra el endpoint real y asserta forma + la regla de seguridad
  ("NUNCA inventes montos": toda `linea_cruda` sugerida debe existir en las líneas de
  contexto enviadas), no una etiqueta exacta — corrida real contra `granite4.1:8b` devolvió
  tanto `FALSO_POSITIVO` como `INDETERMINADO` en distintas corridas, ambos con la línea
  saboteada correctamente citada cuando aplica; exigir `FILAS_FALTANTES` sería un test frágil.
- **Corrección respecto al contrato original:** un timeout/endpoint caído deja
  `revisado_por_llm=False` y **`revision_llm=NULL`**, no `{"error": "LLM no disponible"}`.
  Ese mensaje de error queda como red de seguridad de `pdf_ingestion_service.py` solo para
  una excepción imprevista (un bug), no como el camino normal de "endpoint caído" — tener
  contenido en `revision_llm` junto con `revisado_por_llm=False` es un estado incoherente. El
  ingest se completa igual en cualquier caso.

## Ajustar prompts y timeout con casos reales

El contrato de prompt sigue siendo un punto de partida — probado una vez contra
`granite4.1:8b`, no afinado. Antes de confiar en el veredicto para más que "avisale a un
humano":

- Seguir confirmando que el modelo respeta "NUNCA inventes montos" con más casos reales.
- Ajustar `LLM_MAX_LINEAS_CONTEXTO` según qué tan seguido el contexto se queda corto o de
  más (empieza en 40; el módulo lo expone como config sin tocar código).
- **Medir tok/s reales en el VPS**, cuando se despliegue ahí. La tabla de la sección anterior
  sigue extrapolada de benchmarks públicos para el caso CPU-only — solo la fila de GPU local
  tiene medición real. Si el veredicto tarda más de lo estimado, subir
  `LLM_TIMEOUT_SECONDS` antes de asumir que el modelo elegido no sirve.

## Qué falta para el despliegue en VPS

El código no cambia — solo las 6 variables de `.env` (`LLM_MODEL=granite4.1:3b`,
`LLM_BASE_URL` apuntando al Ollama del VPS, ver `.env.example`):

1. Levantar Ollama en el VPS y `ollama pull granite4.1:3b` (mismo comando que en la PC local,
   ver `docs/IMPLEMENTACION-IA-LOCAL-GPU.md` para el equivalente ya ejecutado ahí).
2. Confirmar que `/v1/chat/completions` responde antes de tocar `.env`.
3. Correr `test_llm_reviewer_integration.py` con `LLM_INTEGRATION_TESTS=1` contra el VPS para
   confirmar que `granite4.1:3b` también da veredictos coherentes (no solo `granite4.1:8b`).
4. Medir tok/s reales — ver sección anterior.

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
- **No meter un modelo de 7B o más en el VPS.** No es un problema de RAM — es que no
  entra en el timeout: en 2 vCPU un 7-8B corre a ~1.5-2 tok/s, ~2.5-3 min por veredicto.
