"""Esquemas Pydantic para la API REST.

Estos son los DTOs de entrada/salida. La capa de dominio NUNCA los ve.
Los routers los usan para validar request/response y los casos de uso
reciben/devuelven entidades de dominio puras.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.value_objects.enums import (
    TipoComprobante,
    InventarioEstado,
    CondicionIVA,
    EstadoCaja,
    EstadoSincronizacion,
    EstadoPedido,
)


# ─── Rubro ──────────────────────────────────────────────────

class RubroResponse(BaseModel):
    id: int
    nombre: str
    activo: bool

    model_config = {"from_attributes": True}


# ─── Artículo ────────────────────────────────────────────────

class ArticuloResponse(BaseModel):
    codigo: str
    descripcion: str
    rubro_id: int
    rubro_nombre: Optional[str] = None
    precio_publico: float
    precio_mayorista: float
    stock_actual: int
    stock_minimo: int
    inventario_estado: InventarioEstado
    codigo_barra: str
    codigo_rapido: str
    activo: bool

    model_config = {"from_attributes": True}


class ArticuloSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Texto a buscar (código, nombre, barra, rápido)")


class ArticuloUpdateRequest(BaseModel):
    descripcion: Optional[str] = None
    rubro_id: Optional[int] = None
    precio_publico: Optional[float] = None
    precio_mayorista: Optional[float] = None
    stock_actual: Optional[int] = None
    stock_minimo: Optional[int] = None
    codigo_barra: Optional[str] = None
    codigo_rapido: Optional[str] = None


# ─── Cliente ─────────────────────────────────────────────────

class ClienteResponse(BaseModel):
    id: int
    razon_social: str
    cuit: str
    condicion_iva: CondicionIVA
    direccion: str
    telefono: str
    email: str
    activo: bool

    model_config = {"from_attributes": True}


class ClienteSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Texto a buscar en razón social o CUIT")


# ─── Vendedor ────────────────────────────────────────────────

class VendedorResponse(BaseModel):
    id: int
    nombre: str
    activo: bool

    model_config = {"from_attributes": True}


# ─── Caja ────────────────────────────────────────────────────

class CajaResponse(BaseModel):
    id: int
    vendedor_id: int
    vendedor_nombre: Optional[str] = None
    fecha_apertura: Optional[datetime] = None
    fecha_cierre: Optional[datetime] = None
    saldo_inicial: float
    diferencia: float
    estado: EstadoCaja

    model_config = {"from_attributes": True}


class CajaOpenRequest(BaseModel):
    vendedor_id: int = 1
    saldo_inicial: float = 0.0


class CajaCloseRequest(BaseModel):
    diferencia: float = 0.0


# ─── Formas de Pago ─────────────────────────────────────────

class FormaPagoResponse(BaseModel):
    id: int
    nombre: str
    tiene_recargo: bool
    recargo_financiero: float

    model_config = {"from_attributes": True}


# ─── Detalle Comprobante ────────────────────────────────────

class DetalleComprobanteRequest(BaseModel):
    articulo_codigo: str
    cantidad: int = Field(..., gt=0)
    porc_dto: float = 0.0
    imp_int: float = 0.0


class DetalleComprobanteResponse(BaseModel):
    id: Optional[int] = None
    articulo_codigo: str
    articulo_descripcion: Optional[str] = None
    cantidad: int
    precio_unitario: float
    imp_int: float
    porc_dto: float
    descuento: float
    porc_alicuota: float
    subtotal: float

    model_config = {"from_attributes": True}


# ─── Comprobante Forma de Pago ──────────────────────────────

class ComprobanteFormaPagoRequest(BaseModel):
    forma_pago_id: int
    monto: float = Field(..., gt=0)
    cuotas: int = 1
    lote: str = ""
    nro_cupon: str = ""


class ComprobanteFormaPagoResponse(BaseModel):
    id: Optional[int] = None
    forma_pago_id: int
    forma_pago_nombre: Optional[str] = None
    monto: float
    cuotas: int
    lote: str
    nro_cupon: str
    recargo_financiero: float

    model_config = {"from_attributes": True}


# ─── Comprobante ─────────────────────────────────────────────

class ComprobanteRequest(BaseModel):
    tipo: TipoComprobante = TipoComprobante.FACTURA_B
    cliente_id: int = 1
    vendedor_id: int = 1
    lista_mayorista: bool = False
    descuento_pie: float = 0.0
    detalles: list[DetalleComprobanteRequest]
    formas_pago: list[ComprobanteFormaPagoRequest]


class CotizacionConvertRequest(BaseModel):
    """Request para convertir cotización a factura."""
    tipo: TipoComprobante = TipoComprobante.FACTURA_B


class ComprobanteResponse(BaseModel):
    id: int
    tipo: TipoComprobante
    punto_venta: int
    numero: int
    cliente_id: int
    cliente_razon_social: Optional[str] = None
    vendedor_id: int
    vendedor_nombre: Optional[str] = None
    caja_id: int
    consumidor_final: bool
    lista_mayorista: bool
    fecha: Optional[datetime] = None
    subtotal: float
    descuento_pie: float
    total: float
    estado_sincronizacion: EstadoSincronizacion
    cotizacion_origen_id: Optional[int] = None
    detalles: list[DetalleComprobanteResponse] = []
    formas_pago: list[ComprobanteFormaPagoResponse] = []

    model_config = {"from_attributes": True}


# ─── Pedido Stock ────────────────────────────────────────────

class DetallePedidoStockRequest(BaseModel):
    articulo_codigo: str
    cantidad: int = Field(..., gt=0)


class PedidoStockRequest(BaseModel):
    vendedor_id: int = 1
    detalles: list[DetallePedidoStockRequest]


class DetallePedidoStockResponse(BaseModel):
    id: Optional[int] = None
    articulo_codigo: str
    articulo_descripcion: Optional[str] = None
    rubro_id: int
    rubro_nombre: Optional[str] = None
    cantidad: int
    precio_unitario: float
    total: float
    stock_actual_al_pedido: int
    stock_minimo: int
    stock_pedido: int
    multiplo: int
    inventario_estado: InventarioEstado

    model_config = {"from_attributes": True}


class PedidoStockResponse(BaseModel):
    id: int
    vendedor_id: int
    vendedor_nombre: Optional[str] = None
    fecha: Optional[datetime] = None
    estado: EstadoPedido
    estado_sincronizacion: EstadoSincronizacion
    detalles: list[DetallePedidoStockResponse] = []

    model_config = {"from_attributes": True}


# ─── Error ──────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error_code: str
    message: str