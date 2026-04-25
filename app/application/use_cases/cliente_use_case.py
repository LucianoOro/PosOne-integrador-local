"""Caso de uso: Clientes."""

from typing import Sequence

from app.application.ports.cliente_repository import ClienteRepository
from app.domain.entities.entities import Cliente
from app.domain.exceptions import ClienteNoEncontradoError


class ClienteUseCase:
    def __init__(self, repo: ClienteRepository):
        self.repo = repo

    def get_by_id(self, cliente_id: int) -> Cliente:
        cliente = self.repo.get_by_id(cliente_id)
        if not cliente:
            raise ClienteNoEncontradoError(cliente_id)
        return cliente

    def search(self, query: str) -> Sequence[Cliente]:
        return self.repo.search_by_razon_social(query)

    def list_all(self, solo_activos: bool = True) -> Sequence[Cliente]:
        return self.repo.list_all(solo_activos=solo_activos)