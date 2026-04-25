"""Implementación SQLAlchemy del repositorio de Rubros."""

from sqlalchemy.orm import Session

from app.application.ports.rubro_repository import RubroRepository
from app.domain.entities.entities import Rubro
from app.infrastructure.database.models import RubroModel


def _model_to_entity(m: RubroModel) -> Rubro:
    return Rubro(
        id=m.id,
        nombre=m.nombre,
        activo=m.activo,
    )


class SqlAlchemyRubroRepository(RubroRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, rubro_id: int) -> Rubro | None:
        m = self.db.query(RubroModel).filter(RubroModel.id == rubro_id).first()
        return _model_to_entity(m) if m else None

    def list_all(self, solo_activos: bool = True) -> list[Rubro]:
        q = self.db.query(RubroModel)
        if solo_activos:
            q = q.filter(RubroModel.activo == True)  # noqa: E712
        return [_model_to_entity(m) for m in q.all()]