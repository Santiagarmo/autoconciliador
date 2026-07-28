# AutoConciliador

Sistema B2B de conciliación bancaria automática para empresas de e-commerce que venden por WhatsApp. Cruza los pagos declarados por asesores comerciales contra el extracto bancario oficial (Nequi, Davivienda, Bancolombia) para liberar pedidos sin depender de APIs de Open Banking.

**Stack:** FastAPI (async) + PostgreSQL 15 + SQLAlchemy 2.0/Alembic + Vue 3/Vite/Tailwind/Pinia, todo orquestado con Docker Compose.

## Requisitos

- Docker + Docker Compose (Docker Desktop en Windows/Mac, o Docker Engine en Linux).
- Nada más — Python/Node corren dentro de los contenedores.

## Levantar el proyecto

1. **Clonar el repo y ubicarse en la raíz** (donde está `docker-compose.yml`).

2. **Crear el archivo de entorno:**

   ```bash
   cp .env.example .env
   ```

   Los valores por defecto sirven para desarrollo local. Revisa especialmente `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` y `SECRET_KEY` si vas a exponer el entorno más allá de tu máquina.

3. **Construir y levantar los contenedores:**

   ```bash
   docker compose up -d --build
   ```

   Esto levanta 3 servicios:
   - `db` — PostgreSQL 15 (puerto host `5433` → `5432` en el contenedor).
   - `backend` — FastAPI con reload automático (puerto `8000`).
   - `frontend` — Vite dev server (puerto `5173`).

4. **Aplicar las migraciones de base de datos** (no se ejecutan automáticamente):

   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. **Crear el usuario administrador inicial** (idempotente, usa `SEED_ADMIN_EMAIL`/`SEED_ADMIN_PASSWORD` del `.env`):

   ```bash
   docker compose exec backend python -m scripts.seed_admin
   ```

## URLs

| Servicio  | URL                                  |
|-----------|---------------------------------------|
| Frontend  | http://localhost:5173                 |
| Backend   | http://localhost:8000/api              |
| Docs API (Swagger) | http://localhost:8000/docs   |
| PostgreSQL | localhost:5433 (usuario/clave/db en `.env`) |

Inicia sesión en el frontend (o vía `/api/auth`) con el email/clave definidos en `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`.

## Comandos útiles

```bash
# Ver logs de un servicio
docker compose logs -f backend
docker compose logs -f frontend

# Estado de los contenedores
docker compose ps

# Ejecutar tests del backend
docker compose exec backend pytest

# Revisar versión de migración aplicada
docker compose exec backend alembic current

# Bajar los contenedores (conserva datos en el volumen pgdata)
docker compose down

# Bajar contenedores y borrar datos de Postgres
docker compose down -v
```

## Estructura del backend

Clean Architecture por capas dentro de `backend/app`:

```
app/
├── api/            # Routers FastAPI (HTTP únicamente)
├── core/           # Config, JWT, middlewares
├── db/             # Sesión async y migraciones Alembic
├── domain/         # Entidades y enums puros
├── models/         # Modelos SQLAlchemy (ORM)
├── schemas/        # DTOs Pydantic
├── repositories/    # Única capa que ejecuta SQL
├── services/       # Lógica de negocio
└── workers/        # Estrategias de parseo de extractos (BancolombiaParser, etc.)
```

Más contexto de negocio y arquitectura en `docs/prompt.md`.
