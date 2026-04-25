"""Implementación SQLAlchemy del repositorio de Vendedores."""

from sqlalchemy.orm import Session

from app.application.ports.vendedor_repository import VendedorRepository
from app.domain.entities.entities import Vendedor
from app.infrastructure.database.models import VendedorModel


def _model_to_entity(m: VendedorModel) -> Vendedor:
    return Vendedor(
        id=m.id,
        nombre=m.nombre,
        activo=m.activo,
    )


class SqlAlchemyVendedorRepository(VendedorRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, vendedor_id: int) -> Vendedor | None:
        m = self.db.query(VendedorModel).filter(VendedorModel.id == vendedor_id).first()
        return _model_to_entity(m) if m else None

    def list_all(self, solo_activos: bool = True) -> list[Vendedor]:
        q = self.db.query(VendedorModel)
        if solo_activos:
            q = q.filter(VendedorModel.activo == True)  # noqa: E712
        return [_model_to_entity(m) for m in q.all()]