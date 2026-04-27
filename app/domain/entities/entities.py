from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.value_objects.enums import (
    TipoComprobante,
    InventarioEstado,
    CondicionIVA,
    EstadoCaja,
    EstadoSincronizacion,
    EstadoPedido,
    CanalOrigen,
)


@dataclass
class Rubro:
    """Categoría de artículos (ej: Bicicletas, Repuestos, Indumentaria)."""
    id: Optional[int] = None
    nombre: str = ""
    activo: bool = True


@dataclass
class Articulo:
    """Producto del catálogo. PK = codigo (string)."""
    codigo: str = ""
    descripcion: str = ""
    rubro_id: int = 0
    precio_publico: float = 0.0
    precio_mayorista: float = 0.0
    stock_actual: int = 0
    stock_minimo: int = 0
    inventario_estado: InventarioEstado = InventarioEstado.ALTO
    codigo_barra: str = ""
    codigo_rapido: str = ""
    activo: bool = True

    def calcular_precio(self, lista_mayorista: bool = False) -> float:
        """Retorna el precio según la lista seleccionada."""
        if lista_mayorista and self.precio_mayorista > 0:
            return self.precio_mayorista
        return self.precio_publico

    def actualizar_inventario_estado(self) -> None:
        """Recalcula el estado de inventario según stock actual y mínimo."""
        self.inventario_estado = InventarioEstado.calcular(
            self.stock_actual, self.stock_minimo
        )

    def descontar_stock(self, cantidad: int) -> None:
        """Descuenta stock y recalcula estado de inventario."""
        self.stock_actual -= cantidad
        self.actualizar_inventario_estado()

    def bloquear(self) -> None:
        """Bloquea el artículo: stock a 0 y estado BLOQUEADO."""
        self.stock_actual = 0
        self.inventario_estado = InventarioEstado.BLOQUEADO

    def desbloquear(self, stock_minimo: int) -> None:
        """Desbloquea el artículo y recalcula estado. No restauramos stock."""
        self.inventario_estado = InventarioEstado.calcular(
            self.stock_actual, stock_minimo
        )


@dataclass
class Cliente:
    """Cliente del POS. El CF (Consumidor Final) es un cliente especial."""
    id: Optional[int] = None
    razon_social: str = ""
    cuit: str = ""
    condicion_iva: CondicionIVA = CondicionIVA.CONSUMIDOR_FINAL
    direccion: str = ""
    telefono: str = ""
    email: str = ""
    activo: bool = True


@dataclass
class Vendedor:
    """Vendedor del POS. En MVP se hardcodea uno default."""
    id: Optional[int] = None
    nombre: str = ""
    activo: bool = True


@dataclass
class Caja:
    """Turno de caja. Prerrequisito para facturar."""
    id: Optional[int] = None
    vendedor_id: int = 0
    fecha_apertura: Optional[datetime] = None
    fecha_cierre: Optional[datetime] = None
    saldo_inicial: float = 0.0
    diferencia: float = 0.0
    estado: EstadoCaja = EstadoCaja.ABIERTA

    def cerrar(self, diferencia: float = 0.0) -> None:
        """Cierra la caja con la diferencia indicada."""
        self.estado = EstadoCaja.CERRADA
        self.fecha_cierre = datetime.now()
        self.diferencia = diferencia


@dataclass
class Comprobante:
    """Comprobante unificado: Factura A/B/C, Cotización, Presupuesto, NC."""
    id: Optional[int] = None
    tipo: TipoComprobante = TipoComprobante.FACTURA_B
    punto_venta: int = 1
    numero: int = 0
    cliente_id: int = 0
    vendedor_id: int = 0
    caja_id: int = 0
    consumidor_final: bool = True
    lista_mayorista: bool = False
    fecha: Optional[datetime] = None
    subtotal: float = 0.0
    descuento_pie: float = 0.0
    total: float = 0.0
    estado_sincronizacion: EstadoSincronizacion = EstadoSincronizacion.PENDIENTE
    cotizacion_origen_id: Optional[int] = None
    canal: str = CanalOrigen.WEB.value  # "WEB" or "WHATSAPP" — tracks origin of the comprobante
    detalles: list = field(default_factory=list)
    formas_pago: list = field(default_factory=list)

    def calcular_total(self) -> float:
        """Calcula el total: subtotal - descuento_pie."""
        self.total = self.subtotal - self.descuento_pie
        return self.total

    @property
    def es_factura(self) -> bool:
        return TipoComprobante.es_factura(self.tipo)

    @property
    def descuenta_stock(self) -> bool:
        return TipoComprobante.desconta_stock(self.tipo)


@dataclass
class DetalleComprobante:
    """Línea de item dentro de un comprobante."""
    id: Optional[int] = None
    comprobante_id: int = 0
    articulo_codigo: str = ""
    cantidad: int = 0
    precio_unitario: float = 0.0
    imp_int: float = 0.0
    porc_dto: float = 0.0
    descuento: float = 0.0
    porc_alicuota: float = 21.0
    subtotal: float = 0.0

    def calcular_subtotal(self) -> float:
        """Calcula el subtotal de la línea: (precio * cantidad) - descuento."""
        base = self.precio_unitario * self.cantidad
        self.descuento = base * (self.porc_dto / 100)
        self.subtotal = base - self.descuento + self.imp_int
        return self.subtotal


@dataclass
class FormaPago:
    """Forma de pago disponible (Efectivo, TC, TD, etc.)."""
    id: Optional[int] = None
    nombre: str = ""
    tiene_recargo: bool = False
    recargo_financiero: float = 0.0


@dataclass
class ComprobanteFormaPago:
    """Relación entre comprobante y forma de pago (N:M con datos adicionales)."""
    id: Optional[int] = None
    comprobante_id: int = 0
    forma_pago_id: int = 0
    monto: float = 0.0
    cuotas: int = 1
    lote: str = ""
    nro_cupon: str = ""
    recargo_financiero: float = 0.0


@dataclass
class PedidoStock:
    """Pedido de reposición de stock al proveedor/sucursal central."""
    id: Optional[int] = None
    vendedor_id: int = 0
    fecha: Optional[datetime] = None
    estado: EstadoPedido = EstadoPedido.PENDIENTE
    estado_sincronizacion: EstadoSincronizacion = EstadoSincronizacion.PENDIENTE
    detalles: list = field(default_factory=list)


@dataclass
class DetallePedidoStock:
    """Línea de item dentro de un pedido de stock. Snapshot del estado al momento del pedido."""
    id: Optional[int] = None
    pedido_id: int = 0
    articulo_codigo: str = ""
    rubro_id: int = 0
    cantidad: int = 0
    precio_unitario: float = 0.0
    total: float = 0.0
    stock_actual_al_pedido: int = 0
    stock_minimo: int = 0
    stock_pedido: int = 0
    multiplo: int = 1
    inventario_estado: InventarioEstado = InventarioEstado.ALTO