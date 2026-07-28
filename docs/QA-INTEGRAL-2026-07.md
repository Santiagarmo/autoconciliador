# Reporte de QA integral — AutoConciliador (2026-07-27)

## Resumen ejecutivo

Se hizo testing integral del proyecto: tests de flujo backend end-to-end, un seeder de datos demo, y un recorrido manual del frontend contra `localhost:5173`.

- **Tests backend:** 57 → **87** (30 nuevos), todos verdes, corriendo contra una DB de test separada (`autoconciliador_test`).
- **DB de dev sembrada** con 12 pedidos, 10 pagos, 12 movimientos, 2 usuarios demo (`asesor@demo.local` / `auditor@demo.local`, password `Demo-1234`). Reconciliación ejecutada: exactamente 3 matches nuevos, como diseñado.
- **Bugs confirmados:** 8 (0 críticos que bloqueen uso, 1 de severidad alta en UX de sesión, resto medios/bajos).
- **Descartado:** 1 hallazgo inicial que se investigó y resultó ser correcto (badges de estado sí traducen bien el enum).
- **Decisión de diseño confirmada por el usuario:** `POST /movimientos/ingesta` sin gate de AUDITOR es intencional — los asesores sí suben extractos. No es bug.

## Cómo reproducir

```bash
# Tests (DB de test separada, no toca datos de dev)
docker compose exec db createdb -U conciliador autoconciliador_test   # una sola vez
docker compose exec -e DATABASE_URL=postgresql+asyncpg://conciliador:conciliador@db:5432/autoconciliador_test backend alembic upgrade head  # una sola vez
docker compose exec backend pytest -q

# Sembrar datos demo en la DB de dev
docker compose exec backend python -m scripts.seed_demo --reset --users

# Frontend
# http://localhost:5173 — login asesor@demo.local / Demo-1234 o auditor@demo.local / Demo-1234
```

## Bugs confirmados (ordenados por severidad)

| # | Severidad | Bug | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 1 | **Alta** | El interceptor de 401 desloguea al usuario pero **nunca redirige a `/login`**. El usuario se queda mirando la página con datos obsoletos, sin ningún indicio de que su sesión murió. Solo se ve un toast rojo "Credenciales inválidas o expiradas." que desaparece a los 4s. | `frontend/src/api/http.ts:58-60` (interceptor), `frontend/src/stores/auth.store.ts:48` (`logout()` no navega) | D12: token corrompido manualmente en `localStorage`, click en "Refrescar" en `/movimientos` → toast de error, tabla intacta, sin redirect. Captura tomada. |
| 2 | **Alta** | Fallas de parseo en la ingesta en background son invisibles para el usuario. El endpoint responde 202 antes de que el parseo ocurra; si el PDF es inválido, la excepción muere silenciosamente en el log del servidor. Confirmado con test unitario directo a `_ingest_and_reconcile` con bytes corruptos. | `backend/app/api/movimientos.py:44-68` | `backend/tests/test_ingesta_background_e2e.py::test_ingesta_pdf_corrupto_no_explota_en_silencio` |
| 3 | **Media** | Sin refresh de token — la sesión JWT muere en silencio a los 60 min (`ACCESS_TOKEN_EXPIRE_MINUTES`), y el usuario recién se entera en la siguiente acción, cayendo en el mismo bug #1. | `backend/.env` (`ACCESS_TOKEN_EXPIRE_MINUTES=60`), `frontend/src/api/http.ts` (sin lógica de refresh) | Inspección de código; no hay endpoint de refresh ni retry post-refresh en el interceptor. |
| 4 | **Media** | La tabla de "Movimientos bancarios" no se refresca automáticamente tras subir un extracto. El usuario debe adivinar cuándo (y cuántas veces) clickear "Refrescar" — en la prueba hicieron falta **dos clicks** antes de que apareciera el nuevo movimiento. | `frontend/src/views/MovimientosView.vue` (`handleIngesta` no llama `load()`) | D7/D8: subida de extracto sintético como asesor, primer refresh sin cambios, segundo refresh mostró la fila nueva. Dos capturas. |
| 5 | **Baja** | La vista "Conciliaciones" muestra los UUIDs crudos de `pago_declarado_id` y `movimiento_bancario_id` en vez de una referencia legible (código de pedido, referencia bancaria). | `frontend/src/views/ConciliacionesView.vue:21-22` | D9: captura de la tabla con columnas de UUID. |
| 6 | **Baja** | El `<select>` de filtro por estado en el Dashboard (y el de cambio de estado en el detalle de pedido) muestra el valor crudo del enum (`PENDIENTE_PAGO`, `LISTO_PARA_DESPACHO`) como texto de las opciones, en vez de la etiqueta traducida que sí usan los badges (`ESTADO_PEDIDO_META`). | `frontend/src/views/DashboardView.vue` (opciones del `<select>`), `frontend/src/views/PedidoDetailView.vue` (mismo patrón) | D4/D11: `read_page` mostró las opciones del combobox como texto crudo del enum. |
| 7 | **Baja** | `GET /api/pedidos?estado=` filtra en Python después de traer toda la tabla (`repo.list()`), no en SQL. Funciona bien a esta escala, pero no escala. | `backend/app/api/pedidos.py:47-49` | `backend/tests/test_pedidos_api.py::test_filtro_estado_devuelve_solo_ese_estado` (fija el contrato de comportamiento actual) |
| 8 | **Baja** | `ReconciliationService._matches` hace `await pedido_repo.get()` dentro del loop O(pagos × movimientos), en vez de resolver el pedido una sola vez por pago. Impacto real bajo (identity map de SQLAlchemy cachea), pero es una ineficiencia evitable. | `backend/app/services/reconciliation_service.py:76` | Inspección de código. |

## Descartado (investigado, no es bug)

- **"Las vistas muestran los enums crudos en los badges de estado"** — se verificó que `DashboardView.vue` y `PedidoDetailView.vue` sí usan el componente `<EstadoBadge>` con `ESTADO_PEDIDO_META`, mostrando etiquetas correctas en español ("Listo para despacho", "Pendiente de pago", etc.). Confirmado visualmente en D3 y D11. El bug real y más acotado es el #6 (los `<select>`, no los badges).

## Decisión de diseño confirmada

- **`POST /movimientos/ingesta` sin restricción de rol AUDITOR** (`backend/app/api/movimientos.py:74`): el usuario confirmó que es intencional — los asesores sí suben extractos bancarios como parte del flujo operativo. Se documenta como decisión, no como bug. El test `test_ingesta_permitida_a_asesor_decision_de_diseno` en `backend/tests/test_authz_matrix.py` fija ese comportamiento como esperado (202, no 403) para que quede pinneado y no se reporte como regresión a futuro.

## Riesgo residual

- El parser de Bancolombia (`backend/app/workers/bancolombia_parser.py`) fue validado end-to-end contra un PDF **sintético** generado con PyMuPDF (fuente: `backend/tests/fixtures/bancolombia_pdf.py`), reproduciendo el layout exacto (columnas monoespaciadas, formato `FECHA DESCRIPCION VALOR SALDO`, encabezado `DESDE/HASTA`). Esto valida el pipeline pdfplumber → regex, pero **no** las particularidades de un extracto real (multipágina, descripciones cortadas, pies de página variables). No hay un extracto real committeado al repo (correcto — tiene PII), así que este riesgo queda abierto hasta que se pruebe contra un PDF real anonimizado.
- No hay tests de frontend (ni unitarios ni e2e automatizados) — todo el recorrido D1-D13 fue manual vía navegador.
- No hay CI configurado — los tests se corren a mano.

## Backlog (no bugs, mejoras a futuro)

- 6 valores de enum nunca alcanzados por ningún camino de código bajo uso normal, pero ahora sí visibles en la UI gracias al seeder (`ALERTA_PAGO`, `ALERTA_NO_ENCONTRADO`, `RECHAZADO`, `EN_VERIFICACION`, `NO_OPERATIVO`, `MANUAL_AUDITOR`) — están declarados en `backend/app/domain/enums.py` pero ningún flujo de negocio actual los asigna automáticamente; solo aparecen si se insertan manualmente (como hace el seeder).
- Ninguna vista pagina — todas traen la colección completa. Bien para el volumen actual, revisar si crece.
- `BANCOS_DECLARABLES` en el frontend (`frontend/src/types/enums.ts`) incluye NEQUI/DAVIVIENDA como bancos declarables aunque solo BANCOLOMBIA tiene parser registrado — es intencional según el propio código (comentado), pero vale la pena revisar si sigue siendo así conforme se agreguen parsers.

## Qué se agregó al repo

- `backend/app/core/config.py`: nueva setting `TEST_DATABASE_URL`.
- `backend/tests/conftest.py`: fixture `engine` apunta a `TEST_DATABASE_URL`; nuevos fixtures `committing_session`, `real_async_session_local`, `client_real_db` para tests que necesitan commits reales (background tasks, seeder).
- `backend/tests/fixtures/bancolombia_pdf.py`: generador de PDF sintético con PyMuPDF.
- `backend/scripts/seed_demo.py`: seeder idempotente de datos demo (`--reset`, `--users`).
- Nuevos archivos de test: `test_flujo_e2e.py`, `test_ingesta_background_e2e.py`, `test_authz_matrix.py`, `test_concurrencia_conciliacion.py`, `test_seed_demo.py`.
- Ampliaciones: `test_pedidos_api.py` (filtro de estado), `test_bancolombia_parser.py` (parser real con PDF sintético).
- `.env` / `.env.example`: documentado `TEST_DATABASE_URL`.
