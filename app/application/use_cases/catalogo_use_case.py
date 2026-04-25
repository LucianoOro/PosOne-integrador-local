"""Caso de uso: Catálogo (Rubros, Formas de Pago, Vendedores).

Casos de uso simples de solo-lectura para datos de referencia.
"""

from typing import Sequence

from app.application.ports.rubro_repository import RubroRepository
from app.application.ports.forma_pago_repository import FormaPagoRepository
from app.application.ports.vendedor_repository import VendedorRepository
from app.domain.entities.entities import Rubro, FormaPago, Vendedor


class CatalogoUseCase:
    """Caso de uso para datos de referencia (catálogos)."""

    def __init__(
        self,
        rubro_repo: RubroRepository,
        forma_pago_repo: FormaPagoRepository,
        vendedor_repo: VendedorRepository,
    ):
        self.rubro_repo = rubro_repo
        self.forma_pago_repo = forma_pago_repo
        self.vendedor_repo = vendedor_repo

    # ─── Rubros ──────────────────────────────────────────────

    def listar_rubros(self, solo_activos: bool = True) -> Sequence[Rubro]:
        return self.rubro_repo.list_all(solo_activos=solo_activos)

    def get_rubro(self, rubro_id: int) -> Rubro | None:
        return self.rubro_repo.get_by_id(rubro_id)

    # ─── Formas de Pago ──────────────────────────────────────

    def listar_formas_pago(self) -> Sequence[FormaPago]:
        return self.forma_pago_repo.list_all()

    def get_forma_pago(self, forma_pago_id: int) -> FormaPago | None:
        return self.forma_pago_repo.get_by_id(forma_pago_id)

    # ─── Vendedores ──────────────────────────────────────────

    def listar_vendedores(self, solo_activos: bool = True) -> Sequence[Vendedor]:
        return self.vendedor_repo.list_all(solo_activos=solo_activos)

    def get_vendedor(self, vendedor_id: int) -> Vendedor | None:
        return self.vendedor_repo.get_by_id(vendedor_id)