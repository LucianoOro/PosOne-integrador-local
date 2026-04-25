"""Puerto de repositorio: Caja."""

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.entities.entities import Caja


class CajaRepository(ABC):
    """Interfaz del repositorio de cajas."""

    @abstractmethod
    def get_by_id(self, caja_id: int) -> Optional[Caja]:
        ...

    @abstractmethod
    def find_abierta(self) -> Optional[Caja]:
        """Retorna la caja abierta actual, o None si no hay ninguna."""
        ...

    @abstractmethod
    def save(self, caja: Caja) -> Caja:
        ...