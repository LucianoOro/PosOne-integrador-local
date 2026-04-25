"""Puerto de repositorio: Vendedor."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.domain.entities.entities import Vendedor


class VendedorRepository(ABC):
    """Interfaz del repositorio de vendedores."""

    @abstractmethod
    def get_by_id(self, vendedor_id: int) -> Optional[Vendedor]:
        ...

    @abstractmethod
    def list_all(self, solo_activos: bool = True) -> Sequence[Vendedor]:
        ...