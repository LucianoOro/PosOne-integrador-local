"""Main entry point de la API PosONE.

Configura FastAPI con CORS, lifespan (seed data), routers
y manejador de excepciones de dominio.
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.domain.exceptions import PosOneError
from app.infrastructure.database.connection import SessionLocal, create_tables
from app.infrastructure.database.seed import seed_database
from app.infrastructure.api.routers.health_router import router as health_router
from app.infrastructure.api.routers.articulos_router import router as articulos_router
from app.infrastructure.api.routers.clientes_router import router as clientes_router
from app.infrastructure.api.routers.cajas_router import router as cajas_router
from app.infrastructure.api.routers.comprobantes_router import router as comprobantes_router
from app.infrastructure.api.routers.catalogo_router import router as catalogo_router
from app.infrastructure.api.routers.pedidos_stock_router import router as pedidos_router
from app.infrastructure.api.routers.whatsapp_router import router as whatsapp_router
from app.infrastructure.api.routers.whatsapp_api_router import router as whatsapp_api_router

logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env
# Buscar explícitamente en el directorio del proyecto para mayor robustez
from pathlib import Path
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path, override=True)


def _validate_env_vars() -> None:
    """Valida que las variables de entorno críticas estén configuradas.
    Warn si faltan, pero no crashea (para permitir desarrollo sin credenciales).
    """
    warnings = []

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("AI_API_KEY"):
        warnings.append("OPENAI_API_KEY / AI_API_KEY no configurado — el asistente de IA no funcionará")

    if not os.environ.get("TWILIO_ACCOUNT_SID"):
        warnings.append("TWILIO_ACCOUNT_SID no configurado — los mensajes WhatsApp no se enviarán")

    if not os.environ.get("TWILIO_AUTH_TOKEN"):
        warnings.append("TWILIO_AUTH_TOKEN no configurado — los mensajes WhatsApp no se enviarán")

    if not os.environ.get("TWILIO_PHONE_NUMBER"):
        warnings.append("TWILIO_PHONE_NUMBER no configurado — los mensajes WhatsApp no se enviarán")

    for warning in warnings:
        logger.warning("⚠️  %s", warning)

    if not warnings:
        logger.info("✅ Todas las variables de entorno están configuradas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: crea tablas, pobla datos iniciales y valida env vars."""
    create_tables()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    _validate_env_vars()
    yield


app = FastAPI(
    title="PosONE Integrador",
    description="API REST para sistema POS con facturación, cotización y pedidos de stock",
    version="0.1.0",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Manejador de excepciones de dominio ─────────────────────
@app.exception_handler(PosOneError)
async def posone_error_handler(request: Request, exc: PosOneError):
    """Convierte las excepciones de dominio en respuestas HTTP semánticas."""
    status_map = {
        "CAJA_NO_ABIERTA": 409,
        "CAJA_YA_ABIERTA": 409,
        "ARTICULO_BLOQUEADO": 403,
        "ARTICULO_NO_ENCONTRADO": 404,
        "STOCK_INSUFICIENTE": 409,
        "COTIZACION_YA_CONVERTIDA": 409,
        "COTIZACION_NO_ENCONTRADA": 404,
        "COMPROBANTE_NO_ENCONTRADO": 404,
        "TIPO_COMPROBANTE_INVALIDO": 400,
        "CLIENTE_NO_ENCONTRADO": 404,
        "PEDIDO_NO_ENCONTRADO": 404,
    }
    # Mapear clases por nombre de clase como fallback
    class_name = exc.__class__.__name__
    if exc.error_code in status_map:
        status = status_map[exc.error_code]
    else:
        # Default por tipo de excepción
        status = 400
    return JSONResponse(
        status_code=status,
        content={"error_code": exc.error_code, "message": exc.message},
    )


# ─── Routers ─────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(articulos_router)
app.include_router(clientes_router)
app.include_router(cajas_router)
app.include_router(comprobantes_router)
app.include_router(catalogo_router)
app.include_router(pedidos_router)
app.include_router(whatsapp_router)
app.include_router(whatsapp_api_router)