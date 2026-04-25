"""Implementación SQLAlchemy del repositorio de Artículos."""

from sqlalchemy.orm import Session

from app.application.ports.articulo_repository import ArticuloRepository
from app.domain.entities.entities import Articulo
from app.domain.value_objects.enums import InventarioEstado
from app.infrastructure.database.models import ArticuloModel


def _model_to_entity(m: ArticuloModel) -> Articulo:
    """Mapea un modelo SQLAlchemy a una entidad de dominio."""
    return Articulo(
        codigo=m.codigo,
        descripcion=m.descripcion,
        rubro_id=m.rubro_id,
        precio_publico=m.precio_publico,
        precio_mayorista=m.precio_mayorista,
        stock_actual=m.stock_actual,
        stock_minimo=m.stock_minimo,
        inventario_estado=InventarioEstado(m.inventario_estado),
        codigo_barra=m.codigo_barra or "",
        codigo_rapido=m.codigo_rapido or "",
        activo=m.activo,
    )


def _entity_to_model(a: Articulo) -> dict:
    """Convierte una entidad a dict para update/insert."""
    return {
        "codigo": a.codigo,
        "descripcion": a.descripcion,
        "rubro_id": a.rubro_id,
        "precio_publico": a.precio_publico,
        "precio_mayorista": a.precio_mayorista,
        "stock_actual": a.stock_actual,
        "stock_minimo": a.stock_minimo,
        "inventario_estado": a.inventario_estado.value,
        "codigo_barra": a.codigo_barra,
        "codigo_rapido": a.codigo_rapido,
        "activo": a.activo,
    }


class SqlAlchemyArticuloRepository(ArticuloRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_codigo(self, codigo: str) -> Articulo | None:
        m = self.db.query(ArticuloModel).filter(ArticuloModel.codigo == codigo).first()
        return _model_to_entity(m) if m else None

    def get_by_codigo_barra(self, codigo_barra: str) -> Articulo | None:
        m = self.db.query(ArticuloModel).filter(
            ArticuloModel.codigo_barra == codigo_barra
        ).first()
        return _model_to_entity(m) if m else None

    def get_by_codigo_rapido(self, codigo_rapido: str) -> Articulo | None:
        m = self.db.query(ArticuloModel).filter(
            ArticuloModel.codigo_rapido == codigo_rapido
        ).first()
        return _model_to_entity(m) if m else None

    def search_by_descripcion(self, query: str) -> list[Articulo]:
        models = self.db.query(ArticuloModel).filter(
            ArticuloModel.descripcion.ilike(f"%{query}%"),
            ArticuloModel.activo == True,  # noqa: E712
        ).all()
        return [_model_to_entity(m) for m in models]

    def list_all(self, solo_activos: bool = True) -> list[Articulo]:
        q = self.db.query(ArticuloModel)
        if solo_activos:
            q = q.filter(ArticuloModel.activo == True)  # noqa: E712
        return [_model_to_entity(m) for m in q.all()]

    def list_by_rubro(self, rubro_id: int) -> list[Articulo]:
        models = self.db.query(ArticuloModel).filter(
            ArticuloModel.rubro_id == rubro_id,
            ArticuloModel.activo == True,  # noqa: E712
        ).all()
        return [_model_to_entity(m) for m in models]

    def list_by_inventario_estado(self, estado: InventarioEstado) -> list[Articulo]:
        models = self.db.query(ArticuloModel).filter(
            ArticuloModel.inventario_estado == estado.value,
            ArticuloModel.activo == True,  # noqa: E712
        ).all()
        return [_model_to_entity(m) for m in models]

    def save(self, articulo: Articulo) -> Articulo:
        existing = self.db.query(ArticuloModel).filter(
            ArticuloModel.codigo == articulo.codigo
        ).first()
        if existing:
            for key, value in _entity_to_model(articulo).items():
                setattr(existing, key, value)
            self.db.flush()
            return _model_to_entity(existing)
        else:
            model = ArticuloModel(**_entity_to_model(articulo))
            self.db.add(model)
            self.db.flush()
            return _model_to_entity(model)

    def search(self, query: str) -> list[Articulo]:
        """Búsqueda flexible: código, código barra, código rápido o descripción."""
        like = f"%{query}%"
        models = self.db.query(ArticuloModel).filter(
            ArticuloModel.activo == True,  # noqa: E712
        ).filter(
            (ArticuloModel.codigo.ilike(like))
            | (ArticuloModel.descripcion.ilike(like))
            | (ArticuloModel.codigo_barra.ilike(like))
            | (ArticuloModel.codigo_rapido.ilike(like))
        ).all()
        return [_model_to_entity(m) for m in models]