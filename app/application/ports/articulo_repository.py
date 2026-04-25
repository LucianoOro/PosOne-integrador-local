"""Puerto de repositorio: Artículo.

Define QUÉ operaciones se pueden hacer con artículos,
sin importar CÓMO se almacenan.
"""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from app.domain.entities.entities import Articulo
from app.domain.value_objects.enums import InventarioEstado


class ArticuloRepository(ABC):
    """Interfaz del repositorio de artículos."""

    @abstractmethod
    def get_by_codigo(self, codigo: str) -> Optional[Articulo]:
        """Busca un artículo por su código primario."""
        ...

    @abstractmethod
    def get_by_codigo_barra(self, codigo_barra: str) -> Optional[Articulo]:
        """Busca un artículo por código de barras."""
        ...

    @abstractmethod
    def get_by_codigo_rapido(self, codigo_rapido: str) -> Optional[Articulo]:
        """Busca un artículo por código rápido."""
        ...

    @abstractmethod
    def search_by_descripcion(self, query: str) -> Sequence[Articulo]:
        """Busca artículos cuya descripción contenga el texto dado (case-insensitive)."""
        ...

    @abstractmethod
    def list_all(self, solo_activos: bool = True) -> Sequence[Articulo]:
        """Lista todos los artículos. Filtra inactivos por defecto."""
        ...

    @abstractmethod
    def list_by_rubro(self, rubro_id: int) -> Sequence[Articulo]:
        """Lista artículos de un rubro determinado."""
        ...

    @abstractmethod
    def list_by_inventario_estado(self, estado: InventarioEstado) -> Sequence[Articulo]:
        """Lista artículos por estado de inventario (BAJO, BLOQUEADO, etc.)."""
        ...

    @abstractmethod
    def save(self, articulo: Articulo) -> Articulo:
        """Crea o actualiza un artículo."""
        ...

    @abstractmethod
    def search(self, query: str) -> Sequence[Articulo]:
        """Búsqueda flexible: busca por código, código barra, código rápido o descripción."""
        ...