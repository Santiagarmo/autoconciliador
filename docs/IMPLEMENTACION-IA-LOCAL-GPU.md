# Implementar el auditor IA en la PC local con GPU (8 GB VRAM) — guía rápida

Este documento es la variante del deploy en la PC con GPU dedicada de 8 GB, para cuando
se implemente `OpenAICompatStatementReviewer.review()` ahí en vez de en el VPS. La guía
completa (contrato de prompt, request/response, qué NO hacer) sigue viviendo en
`docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md` — este doc solo ajusta el modelo y los
pasos al hardware local.

## Diferencia clave con el VPS

El VPS de Hostinger es CPU-only, por eso ahí el modelo elegido es `granite4.1:3b` (ver
§ "Consumo y dimensionamiento" del doc principal). En esta PC con 8 GB VRAM, **el modelo
es `granite4.1:8b`**: en Q4_K_M pesa 5.3 GB, entra cómodo en la GPU y deja margen para el
contexto. No hace falta el análisis de latencia CPU — con GPU el veredicto vuelve en
segundos, no minutos.

## Qué leer antes de tocar código

En este orden:

1. `docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md` completo — contrato de prompt,
   contrato de `StatementReviewRequest`/`StatementReviewVerdict`, y la sección "Qué NO
   hacer".
2. `backend/app/services/llm_reviewer.py` — el seam completo (125 líneas). Acá vive la
   clase a implementar.
3. `backend/app/core/config.py` — las 6 variables de settings (`LLM_REVIEW_ENABLED`,
   `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS`,
   `LLM_MAX_LINEAS_CONTEXTO`).
4. `backend/app/services/pdf_ingestion_service.py` (líneas ~142-174) — dónde se llama al
   reviewer y cómo se maneja el error (`try/except Exception` → `revision_llm =
   {"error": "LLM no disponible"}`).
5. `backend/tests/conftest.py` (línea ~245, `StubReviewer`) y
   `backend/tests/test_pdf_ingestion_service.py` — cómo está testeado el escalamiento hoy.
6. `backend/tests/test_verificacion_e2e.py` — el caso con fila saboteada, sirve para
   probar contra el modelo real.
7. `backend/requirements.txt`, bloque `# --- Testing (dev) ---` — ahí vive `httpx`, hay
   que mover su línea fuera de ese bloque.

## El prompt para darle a la IA

Copiar tal cual, en el repo, con Ollama ya levantado:

> Quiero implementar `OpenAICompatStatementReviewer.review()` en
> `backend/app/services/llm_reviewer.py`. Ya tengo Ollama corriendo en esta misma PC
> (8GB VRAM) con `granite4.1:8b` levantado en `http://localhost:11434/v1`. Leé primero
> `docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md` completo — ahí está el contrato de
> prompt, el contrato de request/response, y qué NO hacer. Implementá `review()` con
> `httpx` (moveé su línea en `requirements.txt` fuera del bloque
> `# --- Testing (dev) ---`), usando el parámetro `format` de Ollama con el JSON Schema
> de `StatementReviewVerdict.model_json_schema()` en vez de solo
> `response_format={"type":"json_object"}` — el doc explica por qué. Parseo defensivo
> con `try/except ValidationError` → `INDETERMINADO`, reintento simple de 1-2 intentos,
> sin `tenacity`. Después agregá un test de integración gateado por
> `LLM_INTEGRATION_TESTS=1` con `pytest.mark.skipif`, y corré manualmente el caso
> saboteado de `test_verificacion_e2e.py` contra el endpoint real para confirmar que
> devuelve `FILAS_FALTANTES` coherente. Al final corré la suite completa y confirmá que
> sigue en verde.

## Paso a paso

1. **Levantar el modelo:**

   ```bash
   ollama pull granite4.1:8b
   ollama serve
   curl http://localhost:11434/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"granite4.1:8b","messages":[{"role":"user","content":"di OK"}]}'
   ```

2. **Configurar `.env`:**

   ```
   LLM_REVIEW_ENABLED=True
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_MODEL=granite4.1:8b
   LLM_TIMEOUT_SECONDS=90.0
   LLM_MAX_LINEAS_CONTEXTO=40
   ```

3. **Dejar que la IA implemente `review()`** con el prompt de arriba.

4. **Probar contra el modelo real** el caso saboteado de `test_verificacion_e2e.py` —
   confirmar veredicto y que nunca inventa montos.

5. **Confirmar el camino de falla** (endpoint caído/timeout) sigue devolviendo
   `{"error": "LLM no disponible"}` sin romper el ingest.

6. **Suite completa verde** antes de mergear:

   ```bash
   docker compose exec backend pytest -q
   ```

No hace falta repetir la comparación de modelos ni las cuentas de VPS de
`IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md` — ese análisis de latencia CPU no aplica
acá, porque hay GPU.
