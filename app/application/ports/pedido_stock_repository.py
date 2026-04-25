"""Puerto de repositorio: Pedido de Stock."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.domain.entities.entities import PedidoStock
from app.domain.value_objects.enums import EstadoPedido


class PedidoStockRepository(ABC):
    """Interfaz del repositorio de pedidos de stock."""

    @abstractmethod
    def get_by_id(self, pedido_id: int) -> Optional[PedidoStock]:
        """Busca un pedido por ID, incluyendo sus detalles."""
        ...

    @abstractmethod
    def save(self, pedido: PedidoStock) -> PedidoStock:
        """Persiste un pedido completo (encabezado + detalles)."""
        ...

    @abstractmethod
    def list_by_estado(self, estado: EstadoPedido) -> Sequence[PedidoStock]:
        """Lista pedidos por estado."""
        ...