"""FastAPI application entrypoint (Phase 4).

Wires the routers under ``/api`` and enables CORS for the Vue frontend
(Phase 5). Business logic lives in services; routers only handle HTTP.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, conciliaciones, movimientos, pagos, pedidos
from app.core.config import settings

app = FastAPI(
    title="AutoConciliador API",
    version="0.4.0",
    description="Conciliación bancaria B2B: cruce de pagos declarados vs. extractos.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(pedidos.router, prefix=api_prefix)
app.include_router(pagos.router, prefix=api_prefix)
app.include_router(movimientos.router, prefix=api_prefix)
app.include_router(conciliaciones.router, prefix=api_prefix)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
