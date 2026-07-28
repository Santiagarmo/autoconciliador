# Auditor IA en la PC local con GPU (RTX 2060, 6 GB VRAM) — resultado

**Estado: implementado y probado.** `OpenAICompatStatementReviewer.review()` está conectado
a `granite4.1:8b` corriendo en esta PC vía Ollama, y `.env` ya apunta ahí
(`LLM_REVIEW_ENABLED=True`). Este documento queda como referencia de esa variante de deploy
— la guía completa (contrato de prompt, request/response, qué NO hacer) sigue viviendo en
`docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md`, que también tiene el detalle de lo que
se implementó.

## Diferencia clave con el VPS

El VPS de Hostinger es CPU-only, por eso ahí el modelo elegido es `granite4.1:3b` (ver
§ "Consumo y dimensionamiento" del doc principal). En esta PC, **el modelo es
`granite4.1:8b`**: en Q4_K_M pesa 5.3 GB.

**Corrección de hardware (medido, 2026-07-28):** la GPU real es una **RTX 2060 de 6 GB**,
no 8 GB como asumía la primera versión de este doc. `granite4.1:8b` entra **al límite**, no
"cómodo": con contexto en el default de Ollama, `ollama ps` mostró un split
**31%/69% CPU/GPU** (6.2 GB de footprint total, 4096 de contexto efectivo) — no es 100% GPU,
pero como el modelo es chico igual respondió rápido: ~1.8 s de wall-clock para un prompt de
~965 tokens + veredicto corto. No hace falta bajar `OLLAMA_CONTEXT_LENGTH` en la práctica;
mencionado acá como mitigación disponible si algún caso real con contexto más largo empuja el
split más hacia CPU. VRAM libre en reposo (modelo descargado): ~5 GB de 6 GB — sobra para el
resto del sistema.

## Qué se leyó antes de tocar código

En este orden (queda como referencia de cómo se abordó, útil para el próximo cambio en el
seam):

1. `docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md` completo — contrato de prompt,
   contrato de `StatementReviewRequest`/`StatementReviewVerdict`, y la sección "Qué NO
   hacer".
2. `backend/app/services/llm_reviewer.py` — el seam. Ahora ~250 líneas con `review()`
   implementado, los helpers puros (`build_messages`, `build_payload`, `build_headers`,
   `parse_verdict`) y `_clamp_confianzas`.
3. `backend/app/core/config.py` — las 6 variables de settings (`LLM_REVIEW_ENABLED`,
   `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS`,
   `LLM_MAX_LINEAS_CONTEXTO`).
4. `backend/app/services/pdf_ingestion_service.py` (líneas ~142-174) — dónde se llama al
   reviewer. El `try/except Exception` → `{"error": "LLM no disponible"}` quedó como red
   de seguridad para bugs imprevistos; el camino normal de "endpoint caído" ahora es
   `review()` devolviendo `None` (ver `IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md`).
5. `backend/tests/conftest.py` (`StubReviewer`) y `backend/tests/test_pdf_ingestion_service.py`
   — cómo está testeado el escalamiento.
6. `backend/tests/test_verificacion_e2e.py` — el caso con fila saboteada, reusado en
   `backend/tests/test_llm_reviewer_integration.py` para probar contra el modelo real.
7. `backend/requirements.txt` — `httpx` ya tiene su propio bloque de producción.

## Resultado

- `OpenAICompatStatementReviewer.review()` implementado en
  `backend/app/services/llm_reviewer.py`, usando `response_format:
  {"type":"json_schema", ...}` (estándar OpenAI) en vez del parámetro `format` nativo de
  Ollama — verificado que Ollama 0.32.5 lo acepta en `/v1/chat/completions` con el schema
  crudo de pydantic, sin atar el backend a un servidor en particular. Detalle completo en
  `docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md`.
- Tests unitarios (`backend/tests/test_llm_reviewer.py`, 17 tests, sin red) verdes.
- Test de integración (`backend/tests/test_llm_reviewer_integration.py`, gateado por
  `LLM_INTEGRATION_TESTS=1`) corrido contra `granite4.1:8b` real en esta PC: el caso
  saboteado de `test_verificacion_e2e.py` (fila 3 con montos pegados) produjo un veredicto
  válido en ~12-14 s (377 tokens de prompt, 139 de respuesta), citando correctamente la
  línea saboteada en `filas_sugeridas` sin inventar ninguna — la regla "NUNCA inventes
  montos" se sostuvo en la corrida real.
- Suite completa (`docker compose exec backend pytest -q`): 115 passed, 1 skipped (el test
  de integración, sin `LLM_INTEGRATION_TESTS=1`).
- Camino de falla verificado manualmente: apuntando `LLM_BASE_URL` a un puerto sin nada
  escuchando, `review()` devuelve `None` sin excepción tras los 2 reintentos; el ingest se
  completa igual.

## Paso a paso

1. **Instalar y levantar Ollama (Windows).** Los comandos `ollama serve` de la guía
   original son para Linux/VPS — en Windows, Ollama se instala como app + servicio de
   sistema:

   ```powershell
   winget install --id Ollama.Ollama --exact --source winget
   # Reiniciar la shell para que el PATH tome ollama.exe.
   ```

   El instalador ya deja un proceso corriendo, pero por defecto escucha solo en
   `127.0.0.1:11434` — inalcanzable desde un contenedor Docker. Exponerlo con dos
   variables de entorno de **usuario** (persisten entre reinicios) y luego reiniciar el
   proceso de Ollama para que las tome:

   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
   [Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "0", "User")
   ```

   `OLLAMA_KEEP_ALIVE=0` es el mismo ajuste que recomienda el doc principal para el VPS
   (§ "Consumo y dimensionamiento") — el LLM se invoca casi nunca, no vale la pena tener el
   modelo residente en VRAM 24/7. `OLLAMA_NUM_THREAD=1` en cambio **no** aplica acá: es una
   mitigación para el VPS de 2 vCPU compartidos con Postgres; en esta PC (GPU + 32 GB RAM)
   se omite.

   El `winget install` también abre una regla de firewall entrante para `ollama.exe` en el
   perfil "Public" — confirmar que es aceptable en la red donde está la PC (típicamente sí,
   en una red doméstica detrás de router).

   Descargar el modelo y confirmar que el endpoint responde:

   ```powershell
   ollama pull granite4.1:8b
   curl.exe http://localhost:11434/v1/chat/completions -H "Content-Type: application/json" -d '{\"model\":\"granite4.1:8b\",\"messages\":[{\"role\":\"user\",\"content\":\"di OK\"}]}'
   ```

   (`curl.exe` explícito en PowerShell — el alias `curl` apunta a `Invoke-WebRequest` y no
   acepta estos flags igual.)

2. **Configurar `.env`** — con `host.docker.internal`, no `localhost` (el backend corre en
   Docker; `localhost` desde el contenedor apunta al propio contenedor, nunca al host):

   ```
   LLM_REVIEW_ENABLED=True
   LLM_BASE_URL=http://host.docker.internal:11434/v1
   LLM_MODEL=granite4.1:8b
   LLM_TIMEOUT_SECONDS=90.0
   LLM_MAX_LINEAS_CONTEXTO=40
   ```

   Verificar la conexión desde dentro del contenedor antes de seguir:

   ```bash
   docker compose exec backend python -c "import httpx; print(httpx.get('http://host.docker.internal:11434/api/version', timeout=10).json())"
   ```

3. **`review()` implementado** — ver § Resultado arriba y el detalle completo en
   `docs/IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md`. ✅

4. **Probado contra el modelo real** el caso saboteado de `test_verificacion_e2e.py` —
   veredicto coherente, sin montos inventados (verificado con una aserción explícita en
   `test_llm_reviewer_integration.py`, no solo a mano). ✅

5. **Camino de falla confirmado** — endpoint caído/timeout deja `revision_llm=NULL` con
   `revisado_por_llm=False` (NO `{"error": "LLM no disponible"}`, que quedó reservado para
   bugs imprevistos — ver la corrección de contrato en el doc principal). El ingest se
   completa igual. ✅

6. **Suite completa verde**:

   ```bash
   docker compose exec backend pytest -q
   # 115 passed, 1 skipped
   ```

   ✅

No hace falta repetir la comparación de modelos ni las cuentas de VPS de
`IMPLEMENTACION-IA-VERIFICACION-EXTRACTOS.md` — con `granite4.1:8b` en esta PC el veredicto
vuelve en segundos, no minutos, incluso con el split parcial CPU/GPU medido arriba (a
diferencia del VPS, acá no hay riesgo real de pegarle al timeout de 90 s con este modelo).
