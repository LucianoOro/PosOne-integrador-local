"""Caso de uso: Cajas.

Orquesta apertura y cierre de cajas. Regla clave:
SOLO puede haber UNA caja abierta a la vez.
"""

from app.application.ports.caja_repository import CajaRepository
from app.application.ports.vendedor_repository import VendedorRepository
from app.domain.entities.entities import Caja
from app.domain.exceptions import CajaNoAbiertaError, CajaYaAbiertaError
from app.domain.value_objects.enums import EstadoCaja


class CajaUseCase:
    def __init__(self, repo: CajaRepository, vendedor_repo: VendedorRepository):
        self.repo = repo
        self.vendedor_repo = vendedor_repo

    def get_abierta(self) -> Caja:
        """Retorna la caja abierta o lanza error si no hay."""
        caja = self.repo.find_abierta()
        if not caja:
            raise CajaNoAbiertaError()
        return caja

    def abrir(self, vendedor_id: int, saldo_inicial: float = 0.0) -> Caja:
        """Abre una nueva caja. Falla si ya hay una abierta."""
        existente = self.repo.find_abierta()
        if existente:
            raise CajaYaAbiertaError(existente.id)
        caja = Caja(
            vendedor_id=vendedor_id,
            saldo_inicial=saldo_inicial,
            estado=EstadoCaja.ABIERTA,
        )
        return self.repo.save(caja)

    def cerrar(self, caja_id: int, diferencia: float = 0.0) -> Caja:
        """Cierra una caja existente."""
        caja = self.repo.get_by_id(caja_id)
        if not caja:
            raise CajaNoAbiertaError()
        caja.cerrar(diferencia=diferencia)
        return self.repo.save(caja)

    def require_caja_abierta(self) -> Caja:
        """Retorna la caja abierta o lanza error. Útil como prerrequisito para facturar."""
        return self.get_abierta()