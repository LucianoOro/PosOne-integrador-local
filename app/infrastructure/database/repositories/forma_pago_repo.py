"""Implementación SQLAlchemy del repositorio de Formas de Pago."""

from sqlalchemy.orm import Session

from app.application.ports.forma_pago_repository import FormaPagoRepository
from app.domain.entities.entities import FormaPago
from app.infrastructure.database.models import FormaPagoModel


def _model_to_entity(m: FormaPagoModel) -> FormaPago:
    return FormaPago(
        id=m.id,
        nombre=m.nombre,
        tiene_recargo=m.tiene_recargo,
        recargo_financiero=m.recargo_financiero,
    )


class SqlAlchemyFormaPagoRepository(FormaPagoRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, forma_pago_id: int) -> FormaPago | None:
        m = self.db.query(FormaPagoModel).filter(FormaPagoModel.id == forma_pago_id).first()
        return _model_to_entity(m) if m else None

    def list_all(self) -> list[FormaPago]:
        models = self.db.query(FormaPagoModel).all()
        return [_model_to_entity(m) for m in models]