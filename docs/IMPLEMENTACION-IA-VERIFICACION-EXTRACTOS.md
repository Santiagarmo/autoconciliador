# Implementación del auditor IA (Granite 4.1 3B) — guía de continuación

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
| `granite4.1:8b` (si vuelve la GPU) | 5.3 GB | ~6 GB | ~1.5-2 | ~3 min ❌ |

GPU en el VPS: 0. En una PC con 8 GB VRAM, cualquiera de los cuatro entra sin problema.

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

## Qué falta — pasos concretos

### 1. Levantar el servidor del modelo (en el VPS, o en la PC con GPU si aplica)

Cualquier servidor OpenAI-compatible sirve; no hay atadura a uno en particular. Ejemplo con
Ollama (el más simple de operar):

```bash
# En el VPS (o la máquina donde corra el modelo)
ollama pull granite4.1:3b
ollama serve   # expone /v1/chat/completions en :11434 por defecto
```

Confirmar que responde antes de tocar código:

```bash
curl http://<host-o-ip>:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"granite4.1:3b","messages":[{"role":"user","content":"di OK"}]}'
```

### 2. Configurar las 6 variables (único punto de contacto con el deploy)

En `.env` (backend, o el `.env` que corresponda si el proyecto se despliega en otra
máquina):

```
LLM_REVIEW_ENABLED=True
LLM_BASE_URL=http://<host-o-localhost>:11434/v1
LLM_MODEL=granite4.1:3b
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

**Nota para mejorar el contrato original:** ExtractBench (2026) midió ~51% de tasa de
JSON válido entre seis modelos evaluados — pedir `response_format={"type":"json_object"}`
no es garantía suficiente. Ollama soporta el parámetro `format` con un **JSON Schema**
completo (decodificación restringida por gramática), que sí fuerza la forma de la
respuesta a nivel de generación, no solo de post-validación. Vale la pena usarlo al
implementar `review()`, generando el schema desde `StatementReviewVerdict.model_json_schema()`.

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

### 5. Ajustar prompts y timeout con casos reales

El contrato de prompt es un punto de partida, no algo probado contra el modelo real todavía.
Al conectar Granite por primera vez, esperar iterar:

- Confirmar que el modelo respeta "NUNCA inventes montos" — pedirle explícitamente que
  devuelva `INDETERMINADO` si no hay evidencia clara en `lineas_contexto`, y verificar que no
  alucina un monto cuando la línea es ambigua.
- Ajustar `LLM_MAX_LINEAS_CONTEXTO` según qué tan seguido el contexto se queda corto o de
  más (empieza en 40; el módulo lo expone como config sin tocar código).
- **Medir tok/s reales en el VPS.** La tabla de la sección anterior está extrapolada de
  benchmarks públicos, no medida en el hardware destino. Si el veredicto tarda más de lo
  estimado, subir `LLM_TIMEOUT_SECONDS` antes de asumir que el modelo elegido no sirve.

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
