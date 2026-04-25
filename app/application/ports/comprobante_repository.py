"""Puerto de repositorio: Comprobante."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.domain.entities.entities import Comprobante
from app.domain.value_objects.enums import TipoComprobante, EstadoSincronizacion


class ComprobanteRepository(ABC):
    """Interfaz del repositorio de comprobantes."""

    @abstractmethod
    def get_by_id(self, comprobante_id: int) -> Optional[Comprobante]:
        """Busca un comprobante por ID, incluyendo detalles y formas de pago."""
        ...

    @abstractmethod
    def save(self, comprobante: Comprobante) -> Comprobante:
        """Persiste un comprobante completo (encabezado + detalles + formas de pago)."""
        ...

    @abstractmethod
    def get_next_numero(self, punto_venta: int, tipo: TipoComprobante) -> int:
        """Retorna el próximo número de comprobante para el tipo y punto de venta."""
        ...

    @abstractmethod
    def list_by_tipo(self, tipo: TipoComprobante) -> Sequence[Comprobante]:
        """Lista comprobantes de un tipo determinado."""
        ...

    @abstractmethod
    def list_cotizaciones_pendientes(self) -> Sequence[Comprobante]:
        """Lista cotizaciones que aún no fueron convertidas a factura."""
        ...

    @abstractmethod
    def list_by_caja(self, caja_id: int) -> Sequence[Comprobante]:
        """Lista comprobantes de una caja determinada."""
        ...