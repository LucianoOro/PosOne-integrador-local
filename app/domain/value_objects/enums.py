from enum import Enum


class TipoComprobante(str, Enum):
    """Tipos de comprobante fiscales argentinos y comerciales."""
    FACTURA_A = "FACTURA_A"
    FACTURA_B = "FACTURA_B"
    FACTURA_C = "FACTURA_C"
    COTIZACION = "COTIZACION"
    PRESUPUESTO = "PRESUPUESTO"
    NOTA_CREDITO = "NOTA_CREDITO"

    @classmethod
    def es_factura(cls, tipo: "TipoComprobante") -> bool:
        return tipo in (cls.FACTURA_A, cls.FACTURA_B, cls.FACTURA_C)

    @classmethod
    def desconta_stock(cls, tipo: "TipoComprobante") -> bool:
        """Solo las facturas y notas de crédito afectan stock."""
        return tipo in (cls.FACTURA_A, cls.FACTURA_B, cls.FACTURA_C, cls.NOTA_CREDITO)


class InventarioEstado(str, Enum):
    """Estado del inventario de un artículo."""
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    BLOQUEADO = "BLOQUEADO"

    @classmethod
    def calcular(cls, stock_actual: int, stock_minimo: int) -> "InventarioEstado":
        """Calcula el estado de inventario según los umbrales definidos."""
        if stock_actual == 0:
            return cls.BLOQUEADO
        if stock_actual <= stock_minimo:
            return cls.BAJO
        if stock_actual <= stock_minimo * 2:
            return cls.MEDIO
        return cls.ALTO


class CondicionIVA(str, Enum):
    """Condición fiscal de IVA del cliente (Argentina)."""
    RESPONSABLE_INSCRIPTO = "RESPONSABLE_INSCRIPTO"
    CONSUMIDOR_FINAL = "CONSUMIDOR_FINAL"
    MONOTRIBUTO = "MONOTRIBUTO"
    EXENTO = "EXENTO"

    @classmethod
    def tipo_factura_default(cls, condicion: "CondicionIVA") -> TipoComprobante:
        """Determina el tipo de factura según la condición de IVA."""
        mapping = {
            cls.RESPONSABLE_INSCRIPTO: TipoComprobante.FACTURA_A,
            cls.CONSUMIDOR_FINAL: TipoComprobante.FACTURA_B,
            cls.MONOTRIBUTO: TipoComprobante.FACTURA_C,
            cls.EXENTO: TipoComprobante.FACTURA_C,
        }
        return mapping[condicion]


class EstadoCaja(str, Enum):
    """Estado de una caja (turno de ventas)."""
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"


class EstadoSincronizacion(str, Enum):
    """Estado de sincronización con el servidor central."""
    PENDIENTE = "PENDIENTE"
    SINCRONIZADO = "SINCRONIZADO"


class EstadoPedido(str, Enum):
    """Estado de un pedido de stock."""
    PENDIENTE = "PENDIENTE"
    ENVIADO = "ENVIADO"
    RECIBIDO = "RECIBIDO"