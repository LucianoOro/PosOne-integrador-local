"""Puerto de repositorio: Cliente."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.domain.entities.entities import Cliente


class ClienteRepository(ABC):
    """Interfaz del repositorio de clientes."""

    @abstractmethod
    def get_by_id(self, cliente_id: int) -> Optional[Cliente]:
        ...

    @abstractmethod
    def get_by_cuit(self, cuit: str) -> Optional[Cliente]:
        ...

    @abstractmethod
    def search_by_razon_social(self, query: str) -> Sequence[Cliente]:
        """Búsqueda fuzzy por razón social (case-insensitive, contiene)."""
        ...

    @abstractmethod
    def list_all(self, solo_activos: bool = True) -> Sequence[Cliente]:
        ...

    @abstractmethod
    def save(self, cliente: Cliente) -> Cliente:
        ...