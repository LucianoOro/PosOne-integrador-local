"""Implementación SQLAlchemy del repositorio de Cajas."""

from sqlalchemy.orm import Session

from app.application.ports.caja_repository import CajaRepository
from app.domain.entities.entities import Caja
from app.domain.value_objects.enums import EstadoCaja
from app.infrastructure.database.models import CajaModel


def _model_to_entity(m: CajaModel) -> Caja:
    return Caja(
        id=m.id,
        vendedor_id=m.vendedor_id,
        fecha_apertura=m.fecha_apertura,
        fecha_cierre=m.fecha_cierre,
        saldo_inicial=m.saldo_inicial,
        diferencia=m.diferencia,
        estado=EstadoCaja(m.estado),
    )


class SqlAlchemyCajaRepository(CajaRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, caja_id: int) -> Caja | None:
        m = self.db.query(CajaModel).filter(CajaModel.id == caja_id).first()
        return _model_to_entity(m) if m else None

    def find_abierta(self) -> Caja | None:
        m = self.db.query(CajaModel).filter(
            CajaModel.estado == EstadoCaja.ABIERTA.value
        ).first()
        return _model_to_entity(m) if m else None

    def save(self, caja: Caja) -> Caja:
        if caja.id:
            existing = self.db.query(CajaModel).filter(CajaModel.id == caja.id).first()
            if existing:
                existing.vendedor_id = caja.vendedor_id
                existing.fecha_cierre = caja.fecha_cierre
                existing.saldo_inicial = caja.saldo_inicial
                existing.diferencia = caja.diferencia
                existing.estado = caja.estado.value
                self.db.flush()
                return _model_to_entity(existing)
        model = CajaModel(
            vendedor_id=caja.vendedor_id,
            saldo_inicial=caja.saldo_inicial,
            diferencia=caja.diferencia,
            estado=caja.estado.value,
        )
        self.db.add(model)
        self.db.flush()
        return _model_to_entity(model)