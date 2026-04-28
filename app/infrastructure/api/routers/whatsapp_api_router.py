"""Router: API directa de WhatsApp (para testing sin Twilio).

Endpoints REST que exponen las mismas funciones que el agente de IA,
pero con llamadas directas. Útil para desarrollo y testing.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.use_cases.articulo_use_case import ArticuloUseCase
from app.application.use_cases.caja_use_case import CajaUseCase
from app.application.use_cases.cliente_use_case import ClienteUseCase
from app.application.use_cases.comprobante_use_case import ComprobanteUseCase
from app.domain.entities.entities import Comprobante, DetalleComprobante
from app.domain.value_objects.enums import TipoComprobante
from app.infrastructure.ai.ai_service import AIService, AIServiceEmptyResponseError
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.articulo_repo import (
    SqlAlchemyArticuloRepository,
)
from app.infrastructure.database.repositories.caja_repo import SqlAlchemyCajaRepository
from app.infrastructure.database.repositories.cliente_repo import (
    SqlAlchemyClienteRepository,
)
from app.infrastructure.database.repositories.comprobante_repo import (
    SqlAlchemyComprobanteRepository,
)
from app.infrastructure.database.repositories.forma_pago_repo import (
    SqlAlchemyFormaPagoRepository,
)
from app.infrastructure.database.repositories.rubro_repo import SqlAlchemyRubroRepository
from app.infrastructure.database.repositories.vendedor_repo import (
    SqlAlchemyVendedorRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp API"])


# ─── Schemas de request ──────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request para el endpoint de chat con IA."""
    message: str = Field(..., min_length=1, description="Mensaje para el asistente IA")
    phone_number: str = Field(default="+5491112345678", description="Número de teléfono del usuario")


class ConsultarStockRequest(BaseModel):
    """Request para consultar stock de un artículo."""
    query: str = Field(..., min_length=1, description="Código del artículo")


class ConsultarPrecioRequest(BaseModel):
    """Request para consultar precio de un artículo."""
    codigo: str = Field(..., min_length=1, description="Código del artículo")
    lista: str = Field(default="publico", description="Lista de precios: 'publico' o 'mayorista'")


class BuscarClientesRequest(BaseModel):
    """Request para buscar clientes."""
    query: str = Field(..., min_length=1, description="Texto a buscar en razón social o CUIT")


class CotizacionItem(BaseModel):
    """Item dentro de una cotización."""
    codigo: str = Field(..., description="Código del artículo")
    cantidad: int = Field(..., gt=0, description="Cantidad solicitada")


class GenerarCotizacionRequest(BaseModel):
    """Request para generar una cotización."""
    cliente_id: int = Field(..., description="ID del cliente")
    items: list[CotizacionItem] = Field(..., min_length=1, description="Lista de items")


class ConvertirCotizacionRequest(BaseModel):
    """Request para convertir cotización a factura."""
    cotizacion_id: int = Field(..., description="ID de la cotización")
    tipo_factura: str = Field(default="FACTURA_B", description="Tipo de factura: FACTURA_A, FACTURA_B, FACTURA_C")


class BloquearArticuloRequest(BaseModel):
    """Request para bloquear/desbloquear un artículo."""
    codigo: str = Field(..., min_length=1, description="Código del artículo")


class CotizacionesPendientesRequest(BaseModel):
    """Request para listar cotizaciones pendientes."""
    cliente_id: Optional[int] = Field(default=None, description="ID del cliente para filtrar (opcional)")


# ─── Endpoint de chat con IA ─────────────────────────────────────


@router.post("/chat")
def chat_with_ai(request: ChatRequest):
    """Envía un mensaje al asistente de IA y retorna la respuesta.

    Este endpoint procesa el mensaje a través de IA con function calling,
    igual que lo haría el webhook de WhatsApp, pero vía API directa.
    Si la IA no está configurada o falla, usa fallback rule-based.
    
    Mantiene historial de conversación por número de teléfono para contexto.
    """
    from app.infrastructure.whatsapp.message_processor import _add_to_history, _get_history
    
    ai = AIService()

    # Intentar con IA primero
    if ai.is_configured:
        try:
            # Pasar historial de conversación como contexto
            context = {"history": _get_history(request.phone_number)} if _get_history(request.phone_number) else None
            result = ai.process_message(request.phone_number, request.message, context=context)
            # Guardar en historial
            _add_to_history(request.phone_number, "user", request.message)
            _add_to_history(request.phone_number, "assistant", result.text)
            return {
                "response": result.text,
                "cotizacion_id": result.cotizacion_id,
                "comprobante_id": result.comprobante_id,
                "source": "ai",
            }
        except Exception as e:
            error_msg = str(e)
            logger.warning("Error en IA, usando fallback: %s", error_msg[:100])
            # Cualquier error de IA (quota, respuesta vacía, etc.) → fallback
            from app.infrastructure.whatsapp.fallback_processor import FallbackProcessor
            fallback = FallbackProcessor()
            response_text = fallback.process(request.message)
            _add_to_history(request.phone_number, "user", request.message)
            _add_to_history(request.phone_number, "assistant", response_text)
            return {
                "response": response_text,
                "cotizacion_id": None,
                "comprobante_id": None,
                "source": "fallback",
                "note": f"AI error: {error_msg[:80]}",
            }

    # IA no configurada → fallback
    from app.infrastructure.whatsapp.fallback_processor import FallbackProcessor
    fallback = FallbackProcessor()
    response_text = fallback.process(request.message)
    _add_to_history(request.phone_number, "user", request.message)
    _add_to_history(request.phone_number, "assistant", response_text)
    return {
        "response": response_text,
        "cotizacion_id": None,
        "comprobante_id": None,
        "source": "fallback",
        "note": "AI not configured — using rule-based fallback",
    }


# ─── Endpoints directos de funciones ────────────────────────────


@router.post("/consultar-stock")
def consultar_stock(request: ConsultarStockRequest, db: Session = Depends(get_db)):
    """Consulta el stock de un artículo por su código."""
    uc = ArticuloUseCase(
        SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
    )
    try:
        articulo = uc.get_by_codigo(request.query)
        return {
            "codigo": articulo.codigo,
            "descripcion": articulo.descripcion,
            "stock_actual": articulo.stock_actual,
            "stock_minimo": articulo.stock_minimo,
            "inventario_estado": articulo.inventario_estado.value,
            "precio_publico": articulo.precio_publico,
            "precio_mayorista": articulo.precio_mayorista,
        }
    except Exception as e:
        return {"error": True, "message": str(e)}


@router.post("/buscar-articulos")
def buscar_articulos(request: ConsultarStockRequest, db: Session = Depends(get_db)):
    """Busca artículos por nombre, código, barra o rápido."""
    uc = ArticuloUseCase(
        SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
    )
    articulos = uc.search(request.query)
    return [
        {
            "codigo": a.codigo,
            "descripcion": a.descripcion,
            "precio_publico": a.precio_publico,
            "precio_mayorista": a.precio_mayorista,
            "stock_actual": a.stock_actual,
            "inventario_estado": a.inventario_estado.value,
        }
        for a in articulos
    ]


@router.post("/consultar-precio")
def consultar_precio(request: ConsultarPrecioRequest, db: Session = Depends(get_db)):
    """Consulta el precio de un artículo en una lista específica."""
    uc = ArticuloUseCase(
        SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
    )
    try:
        articulo = uc.get_by_codigo(request.codigo)
        es_mayorista = request.lista.lower() == "mayorista"
        precio = articulo.calcular_precio(es_mayorista)
        return {
            "codigo": articulo.codigo,
            "descripcion": articulo.descripcion,
            "lista": request.lista,
            "precio": precio,
            "precio_publico": articulo.precio_publico,
            "precio_mayorista": articulo.precio_mayorista,
        }
    except Exception as e:
        return {"error": True, "message": str(e)}


@router.post("/buscar-clientes")
def buscar_clientes(request: BuscarClientesRequest, db: Session = Depends(get_db)):
    """Busca clientes por razón social o CUIT."""
    uc = ClienteUseCase(SqlAlchemyClienteRepository(db))
    clientes = uc.search(request.query)
    return [
        {
            "id": c.id,
            "razon_social": c.razon_social,
            "cuit": c.cuit,
            "condicion_iva": c.condicion_iva.value,
            "telefono": c.telefono,
            "email": c.email,
        }
        for c in clientes
    ]


@router.post("/cotizaciones-pendientes")
def cotizaciones_pendientes(request: CotizacionesPendientesRequest, db: Session = Depends(get_db)):
    """Lista cotizaciones pendientes, opcionalmente filtradas por cliente."""
    uc = ComprobanteUseCase(
        repo=SqlAlchemyComprobanteRepository(db),
        caja_repo=SqlAlchemyCajaRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        vendedor_repo=SqlAlchemyVendedorRepository(db),
        forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
    )
    cotizaciones = uc.listar_cotizaciones_pendientes()

    if request.cliente_id:
        cotizaciones = [c for c in cotizaciones if c.cliente_id == request.cliente_id]

    resultados = []
    for c in cotizaciones:
        cliente_repo = SqlAlchemyClienteRepository(db)
        cliente = cliente_repo.get_by_id(c.cliente_id)
        resultados.append({
            "id": c.id,
            "numero": c.numero,
            "fecha": c.fecha.isoformat() if c.fecha else None,
            "cliente_id": c.cliente_id,
            "cliente_nombre": cliente.razon_social if cliente else "Desconocido",
            "total": c.total,
        })

    return resultados


@router.post("/generar-cotizacion")
def generar_cotizacion(request: GenerarCotizacionRequest, db: Session = Depends(get_db)):
    """Genera una cotización para un cliente con los items indicados."""
    uc = ComprobanteUseCase(
        repo=SqlAlchemyComprobanteRepository(db),
        caja_repo=SqlAlchemyCajaRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        vendedor_repo=SqlAlchemyVendedorRepository(db),
        forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
    )

    detalles = [
        DetalleComprobante(
            articulo_codigo=item.codigo,
            cantidad=item.cantidad,
        )
        for item in request.items
    ]

    cotizacion = Comprobante(
        tipo=TipoComprobante.COTIZACION,
        cliente_id=request.cliente_id,
        vendedor_id=1,  # Vendedor default
        lista_mayorista=False,
        consumidor_final=(request.cliente_id == 1),
        canal="WHATSAPP",
        detalles=detalles,
        formas_pago=[],
    )

    try:
        result = uc.crear_comprobante(cotizacion)
        db.commit()
        cliente = SqlAlchemyClienteRepository(db).get_by_id(result.cliente_id)
        return {
            "id": result.id,
            "numero": f"{result.punto_venta:04d}-{result.numero:08d}",
            "tipo": result.tipo.value,
            "cliente_nombre": cliente.razon_social if cliente else "Desconocido",
            "total": result.total,
            "subtotal": result.subtotal,
            "items_count": len(result.detalles),
        }
    except Exception as e:
        db.rollback()
        return {"error": True, "message": str(e)}


@router.post("/convertir-cotizacion")
def convertir_cotizacion(request: ConvertirCotizacionRequest, db: Session = Depends(get_db)):
    """Convierte una cotización en factura."""
    uc = ComprobanteUseCase(
        repo=SqlAlchemyComprobanteRepository(db),
        caja_repo=SqlAlchemyCajaRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        vendedor_repo=SqlAlchemyVendedorRepository(db),
        forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
    )

    try:
        tipo = TipoComprobante(request.tipo_factura)
    except ValueError:
        tipo = TipoComprobante.FACTURA_B

    try:
        factura = uc.convertir_cotizacion_a_factura(request.cotizacion_id, tipo)
        db.commit()
        cliente = SqlAlchemyClienteRepository(db).get_by_id(factura.cliente_id)
        return {
            "id": factura.id,
            "numero": f"{factura.punto_venta:04d}-{factura.numero:08d}",
            "tipo": factura.tipo.value,
            "cotizacion_origen_id": factura.cotizacion_origen_id,
            "cliente_nombre": cliente.razon_social if cliente else "Desconocido",
            "total": factura.total,
        }
    except Exception as e:
        db.rollback()
        return {"error": True, "message": str(e)}


@router.post("/bloquear-articulo")
def bloquear_articulo(request: BloquearArticuloRequest, db: Session = Depends(get_db)):
    """Bloquea un artículo de emergencia."""
    uc = ArticuloUseCase(
        SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
    )
    try:
        articulo = uc.bloquear(request.codigo)
        db.commit()
        return {
            "codigo": articulo.codigo,
            "descripcion": articulo.descripcion,
            "inventario_estado": articulo.inventario_estado.value,
            "mensaje": f"Artículo '{articulo.descripcion}' bloqueado.",
        }
    except Exception as e:
        db.rollback()
        return {"error": True, "message": str(e)}


@router.post("/desbloquear-articulo")
def desbloquear_articulo(request: BloquearArticuloRequest, db: Session = Depends(get_db)):
    """Desbloquea un artículo previamente bloqueado."""
    uc = ArticuloUseCase(
        SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db)
    )
    try:
        articulo = uc.desbloquear(request.codigo)
        db.commit()
        return {
            "codigo": articulo.codigo,
            "descripcion": articulo.descripcion,
            "stock_actual": articulo.stock_actual,
            "inventario_estado": articulo.inventario_estado.value,
            "mensaje": f"Artículo '{articulo.descripcion}' desbloqueado.",
        }
    except Exception as e:
        db.rollback()
        return {"error": True, "message": str(e)}


@router.get("/consultar-caja")
def consultar_caja(db: Session = Depends(get_db)):
    """Consulta el estado de la caja actual."""
    uc = CajaUseCase(
        SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db)
    )
    try:
        caja = uc.get_abierta()
        vendedor = SqlAlchemyVendedorRepository(db).get_by_id(caja.vendedor_id)
        return {
            "abierta": True,
            "caja_id": caja.id,
            "vendedor": vendedor.nombre if vendedor else "Desconocido",
            "fecha_apertura": caja.fecha_apertura.isoformat() if caja.fecha_apertura else None,
            "saldo_inicial": caja.saldo_inicial,
            "estado": caja.estado.value,
        }
    except Exception:
        return {"abierta": False, "mensaje": "No hay ninguna caja abierta."}


def _resolve_nombres_whatsapp(comprobante, db: Session) -> dict:
    """Resolve names for comprobante fields (reused by whatsapp API)."""
    from app.infrastructure.database.repositories.articulo_repo import SqlAlchemyArticuloRepository

    cliente_repo = SqlAlchemyClienteRepository(db)
    vendedor_repo = SqlAlchemyVendedorRepository(db)
    articulo_repo = SqlAlchemyArticuloRepository(db)
    forma_pago_repo = SqlAlchemyFormaPagoRepository(db)

    cliente = cliente_repo.get_by_id(comprobante.cliente_id)
    vendedor = vendedor_repo.get_by_id(comprobante.vendedor_id)

    codigos = {d.articulo_codigo for d in comprobante.detalles}
    articulos_map = {}
    for codigo in codigos:
        art = articulo_repo.get_by_codigo(codigo)
        if art:
            articulos_map[codigo] = art.descripcion

    fp_ids = {fp.forma_pago_id for fp in comprobante.formas_pago}
    formas_pago_map = {}
    for fp_id in fp_ids:
        fp = forma_pago_repo.get_by_id(fp_id)
        if fp:
            formas_pago_map[fp_id] = fp.nombre

    return {
        "cliente_razon_social": cliente.razon_social if cliente else None,
        "vendedor_nombre": vendedor.nombre if vendedor else None,
        "articulos_map": articulos_map,
        "formas_pago_map": formas_pago_map,
    }


@router.post("/listar-comprobantes")
def listar_comprobantes(request: ConsultarStockRequest, db: Session = Depends(get_db)):
    """Lista comprobantes por tipo (default: FACTURA_B)."""
    tipo_str = request.query.upper()
    tipo_map = {
        "FACTURA_A": TipoComprobante.FACTURA_A,
        "FACTURA_B": TipoComprobante.FACTURA_B,
        "FACTURA_C": TipoComprobante.FACTURA_C,
        "COTIZACION": TipoComprobante.COTIZACION,
    }
    tipo = tipo_map.get(tipo_str, TipoComprobante.FACTURA_B)

    uc = ComprobanteUseCase(
        repo=SqlAlchemyComprobanteRepository(db),
        caja_repo=SqlAlchemyCajaRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        vendedor_repo=SqlAlchemyVendedorRepository(db),
        forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
    )
    comprobantes = uc.listar_por_tipo(tipo)

    return [
        {
            "id": c.id,
            "tipo": c.tipo.value,
            "numero": f"{c.punto_venta:04d}-{c.numero:08d}",
            "fecha": c.fecha.isoformat() if c.fecha else None,
            "cliente_nombre": SqlAlchemyClienteRepository(db).get_by_id(c.cliente_id).razon_social if SqlAlchemyClienteRepository(db).get_by_id(c.cliente_id) else "Desconocido",
            "total": c.total,
            "estado_sincronizacion": c.estado_sincronizacion.value,
        }
        for c in comprobantes
    ]


@router.post("/ver-comprobante")
def ver_comprobante(request: ConsultarStockRequest, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de un comprobante por ID."""
    try:
        comprobante_id = int(request.query)
    except ValueError:
        return {"error": True, "message": "El ID debe ser un número"}

    uc = ComprobanteUseCase(
        repo=SqlAlchemyComprobanteRepository(db),
        caja_repo=SqlAlchemyCajaRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        vendedor_repo=SqlAlchemyVendedorRepository(db),
        forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
    )
    comp = uc.get_by_id(comprobante_id)
    nombres = _resolve_nombres_whatsapp(comp, db)

    # Return basic info + details + formas_pago
    return {
        "id": comp.id,
        "tipo": comp.tipo.value,
        "numero": f"{comp.punto_venta:04d}-{comp.numero:08d}",
        "fecha": comp.fecha.isoformat() if comp.fecha else None,
        "cliente_nombre": nombres.get("cliente_razon_social"),
        "consumidor_final": comp.consumidor_final,
        "total": comp.total,
        "subtotal": comp.subtotal,
        "descuento_pie": comp.descuento_pie,
        "detalles": [
            {
                "articulo_codigo": d.articulo_codigo,
                "articulo_descripcion": nombres.get("articulos_map", {}).get(d.articulo_codigo),
                "cantidad": d.cantidad,
                "precio_unitario": d.precio_unitario,
                "subtotal": d.subtotal,
            }
            for d in comp.detalles
        ],
        "formas_pago": [
            {
                "forma_pago_nombre": nombres.get("formas_pago_map", {}).get(fp.forma_pago_id),
                "monto": fp.monto,
                "cuotas": fp.cuotas,
            }
            for fp in comp.formas_pago
        ],
    }


@router.post("/facturas-caja")
def facturas_caja(db: Session = Depends(get_db)):
    """Lista facturas de la caja abierta actual."""
    caja_uc = CajaUseCase(
        SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db)
    )
    try:
        caja = caja_uc.get_abierta()
    except Exception:
        return {"abierta": False, "facturas": [], "total_facturado": 0}

    comp_uc = ComprobanteUseCase(
        repo=SqlAlchemyComprobanteRepository(db),
        caja_repo=SqlAlchemyCajaRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        vendedor_repo=SqlAlchemyVendedorRepository(db),
        forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
    )
    comprobantes = comp_uc.listar_por_caja(caja.id)
    facturas = [c for c in comprobantes if c.es_factura]
    total = sum(f.total for f in facturas)

    return {
        "abierta": True,
        "caja_id": caja.id,
        "total_facturas": len(facturas),
        "total_facturado": total,
        "facturas": [
            {
                "id": f.id,
                "tipo": f.tipo.value,
                "numero": f"{f.punto_venta:04d}-{f.numero:08d}",
                "cliente_nombre": SqlAlchemyClienteRepository(db).get_by_id(f.cliente_id).razon_social if SqlAlchemyClienteRepository(db).get_by_id(f.cliente_id) else "Desconocido",
                "total": f.total,
            }
            for f in facturas
        ],
    }