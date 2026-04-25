"""Puerto de repositorio: Rubro."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.domain.entities.entities import Rubro


class RubroRepository(ABC):
    """Interfaz del repositorio de rubros."""

    @abstractmethod
    def get_by_id(self, rubro_id: int) -> Optional[Rubro]:
        ...

    @abstractmethod
    def list_all(self, solo_activos: bool = True) -> Sequence[Rubro]:
        ...