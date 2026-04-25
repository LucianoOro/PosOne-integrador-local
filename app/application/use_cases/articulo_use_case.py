"""Caso de uso: Artículos.

Orquesta la búsqueda y gestión del catálogo de artículos.
"""

from typing import Sequence

from app.application.ports.articulo_repository import ArticuloRepository
from app.application.ports.rubro_repository import RubroRepository
from app.domain.entities.entities import Articulo
from app.domain.exceptions import ArticuloBloqueadoError, ArticuloNoEncontradoError
from app.domain.value_objects.enums import InventarioEstado


class ArticuloUseCase:
    """Caso de uso para operaciones con artículos."""

    def __init__(self, repo: ArticuloRepository, rubro_repo: RubroRepository):
        self.repo = repo
        self.rubro_repo = rubro_repo

    def get_by_codigo(self, codigo: str) -> Articulo:
        articulo = self.repo.get_by_codigo(codigo)
        if not articulo:
            raise ArticuloNoEncontradoError(codigo)
        return articulo

    def search(self, query: str) -> Sequence[Articulo]:
        """Búsqueda flexible: código, nombre, barra, rápido."""
        return self.repo.search(query)

    def list_all(self, solo_activos: bool = True) -> Sequence[Articulo]:
        return self.repo.list_all(solo_activos=solo_activos)

    def list_by_rubro(self, rubro_id: int) -> Sequence[Articulo]:
        return self.repo.list_by_rubro(rubro_id)

    def list_bajo_stock(self) -> Sequence[Articulo]:
        """Artículos con stock bajo o bloqueado."""
        bajos = self.repo.list_by_inventario_estado(InventarioEstado.BAJO)
        bloqueados = self.repo.list_by_inventario_estado(InventarioEstado.BLOQUEADO)
        return list(bajos) + list(bloqueados)

    def bloquear(self, codigo: str) -> Articulo:
        """Bloquea un artículo para impedir su venta."""
        articulo = self.get_by_codigo(codigo)
        articulo.bloquear()
        return self.repo.save(articulo)

    def desbloquear(self, codigo: str) -> Articulo:
        """Desbloquea un artículo previamente bloqueado."""
        articulo = self.get_by_codigo(codigo)
        articulo.desbloquear(articulo.stock_minimo)
        return self.repo.save(articulo)