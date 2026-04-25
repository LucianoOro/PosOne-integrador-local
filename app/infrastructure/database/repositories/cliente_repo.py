"""Implementación SQLAlchemy del repositorio de Clientes."""

from sqlalchemy.orm import Session

from app.application.ports.cliente_repository import ClienteRepository
from app.domain.entities.entities import Cliente
from app.domain.value_objects.enums import CondicionIVA
from app.infrastructure.database.models import ClienteModel


def _model_to_entity(m: ClienteModel) -> Cliente:
    return Cliente(
        id=m.id,
        razon_social=m.razon_social,
        cuit=m.cuit,
        condicion_iva=CondicionIVA(m.condicion_iva),
        direccion=m.direccion or "",
        telefono=m.telefono or "",
        email=m.email or "",
        activo=m.activo,
    )


class SqlAlchemyClienteRepository(ClienteRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, cliente_id: int) -> Cliente | None:
        m = self.db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
        return _model_to_entity(m) if m else None

    def get_by_cuit(self, cuit: str) -> Cliente | None:
        m = self.db.query(ClienteModel).filter(ClienteModel.cuit == cuit).first()
        return _model_to_entity(m) if m else None

    def search_by_razon_social(self, query: str) -> list[Cliente]:
        models = self.db.query(ClienteModel).filter(
            ClienteModel.razon_social.ilike(f"%{query}%"),
            ClienteModel.activo == True,  # noqa: E712
        ).all()
        return [_model_to_entity(m) for m in models]

    def list_all(self, solo_activos: bool = True) -> list[Cliente]:
        q = self.db.query(ClienteModel)
        if solo_activos:
            q = q.filter(ClienteModel.activo == True)  # noqa: E712
        return [_model_to_entity(m) for m in q.all()]

    def save(self, cliente: Cliente) -> Cliente:
        if cliente.id:
            existing = self.db.query(ClienteModel).filter(ClienteModel.id == cliente.id).first()
            if existing:
                existing.razon_social = cliente.razon_social
                existing.cuit = cliente.cuit
                existing.condicion_iva = cliente.condicion_iva.value
                existing.direccion = cliente.direccion
                existing.telefono = cliente.telefono
                existing.email = cliente.email
                existing.activo = cliente.activo
                self.db.flush()
                return _model_to_entity(existing)
        model = ClienteModel(
            razon_social=cliente.razon_social,
            cuit=cliente.cuit,
            condicion_iva=cliente.condicion_iva.value,
            direccion=cliente.direccion,
            telefono=cliente.telefono,
            email=cliente.email,
            activo=cliente.activo,
        )
        self.db.add(model)
        self.db.flush()
        return _model_to_entity(model)