"""Puerto de repositorio: Forma de Pago."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.domain.entities.entities import FormaPago


class FormaPagoRepository(ABC):
    """Interfaz del repositorio de formas de pago."""

    @abstractmethod
    def get_by_id(self, forma_pago_id: int) -> Optional[FormaPago]:
        ...

    @abstractmethod
    def list_all(self) -> Sequence[FormaPago]:
        ...