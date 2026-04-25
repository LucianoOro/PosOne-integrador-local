"""Excepciones de dominio del sistema PosONE.

Estas excepciones representan violaciones de reglas de negocio,
NO errores de infraestructura. Son lanzadas por los casos de uso
y capturadas por los routers de la API para devolver respuestas HTTP apropiadas.
"""


class PosOneError(Exception):
    """Excepción base del dominio PosONE."""
    def __init__(self, message: str, error_code: str = "POS_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


# ─── Errores de Caja ────────────────────────────────────────

class CajaNoAbiertaError(PosOneError):
    """No se puede facturar sin una caja abierta."""
    def __init__(self):
        super().__init__(
            message="No se puede facturar: no hay una caja abierta. Abra caja primero.",
            error_code="CAJA_NO_ABIERTA",
        )


class CajaYaAbiertaError(PosOneError):
    """Ya existe una caja abierta, no se puede abrir otra."""
    def __init__(self, caja_id: int):
        super().__init__(
            message=f"Ya existe una caja abierta (ID: {caja_id}). Cierre la caja actual antes de abrir una nueva.",
            error_code="CAJA_YA_ABIERTA",
        )


# ─── Errores de Artículo ────────────────────────────────────

class ArticuloBloqueadoError(PosOneError):
    """No se puede facturar un artículo bloqueado."""
    def __init__(self, codigo: str):
        super().__init__(
            message=f"El artículo '{codigo}' está bloqueado y no se puede incluir en un comprobante.",
            error_code="ARTICULO_BLOQUEADO",
        )


class ArticuloNoEncontradoError(PosOneError):
    """Artículo no encontrado en la base de datos."""
    def __init__(self, codigo: str):
        super().__init__(
            message=f"Artículo con código '{codigo}' no encontrado.",
            error_code="ARTICULO_NO_ENCONTRADO",
        )


class StockInsuficienteError(PosOneError):
    """Stock insuficiente para la cantidad solicitada."""
    def __init__(self, codigo: str, solicitado: int, disponible: int):
        super().__init__(
            message=f"Stock insuficiente para '{codigo}': solicitado {solicitado}, disponible {disponible}.",
            error_code="STOCK_INSUFICIENTE",
        )


# ─── Errores de Comprobante ──────────────────────────────────

class CotizacionYaConvertidaError(PosOneError):
    """La cotización ya fue convertida a factura."""
    def __init__(self, cotizacion_id: int, factura_id: int):
        super().__init__(
            message=f"La cotización {cotizacion_id} ya fue convertida a factura {factura_id}.",
            error_code="COTIZACION_YA_CONVERTIDA",
        )


class CotizacionNoEncontradaError(PosOneError):
    """Cotización no encontrada."""
    def __init__(self, cotizacion_id: int):
        super().__init__(
            message=f"Cotización con ID {cotizacion_id} no encontrada.",
            error_code="COTIZACION_NO_ENCONTRADA",
        )


class ComprobanteNoEncontradoError(PosOneError):
    """Comprobante no encontrado."""
    def __init__(self, comprobante_id: int):
        super().__init__(
            message=f"Comprobante con ID {comprobante_id} no encontrado.",
            error_code="COMPROBANTE_NO_ENCONTRADO",
        )


class TipoComprobanteInvalidoError(PosOneError):
    """Tipo de comprobante inválido para la operación solicitada."""
    def __init__(self, tipo: str, operacion: str):
        super().__init__(
            message=f"Tipo de comprobante '{tipo}' inválido para la operación '{operacion}'.",
            error_code="TIPO_COMPROBANTE_INVALIDO",
        )


# ─── Errores de Cliente ──────────────────────────────────────

class ClienteNoEncontradoError(PosOneError):
    """Cliente no encontrado."""
    def __init__(self, cliente_id: int):
        super().__init__(
            message=f"Cliente con ID {cliente_id} no encontrado.",
            error_code="CLIENTE_NO_ENCONTRADO",
        )


# ─── Errores de Pedido ───────────────────────────────────────

class PedidoNoEncontradoError(PosOneError):
    """Pedido de stock no encontrado."""
    def __init__(self, pedido_id: int):
        super().__init__(
            message=f"Pedido de stock con ID {pedido_id} no encontrado.",
            error_code="PEDIDO_NO_ENCONTRADO",
        )