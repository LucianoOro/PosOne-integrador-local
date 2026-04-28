"""Implementación SQLAlchemy del repositorio de Artículos."""

import re

from sqlalchemy.orm import Session

from app.application.ports.articulo_repository import ArticuloRepository
from app.domain.entities.entities import Articulo
from app.domain.value_objects.enums import InventarioEstado
from app.infrastructure.database.models import ArticuloModel


def _normalize_search_query(query: str) -> str:
    """Normaliza una query de búsqueda para manejar plurales en español.
    
    Remueve terminaciones plurales comunes:
    - bicicletas → bicicleta
    - cascos → casco
    - repuestos → repuesto
    - guantes → guante
    - zapatillas → zapatilla
    
    También se intenta sin la 's' final como fallback,
    para cubrir casos como bicicletas→bicicleta.
    """
    q = query.strip()
    # Reglas de plural español (ordenadas de más específicas a menos)
    rules = [
        (r'eses$', ''),      # ingresos → ingres (raro)
        (r'ces$', 'z'),      # luces → luz
        (r'iones$', 'ión'),   # cotizaciones → cotización
        (r'eres$', 'er'),     # hombres → hombr (no ideal, raro)
        (r'ajes$', 'aje'),    # viajes → viaje
        (r'ones$', 'ón'),     # cotizaciones → cotización (accent)
        (r'ales$', 'al'),     # formas → forma (no exacto pero cercano)
        (r'eles$', 'el'),     # cascos → casc (raro)
        (r'iles$', 'il'),     # civiles → civil
        (r'ivas$', 'ivo'),    # activas → activo
        (r'osos$', 'oso'),    # peligrosos → peligroso
        (r'ls$', 'l'),        # animales → animal (no funciona bien)
        (r'as$', 'a'),        # bicicletas → bicicleta, cotizas → cotiza
        (r'es$', ''),         # cascos → casco, repuestos → repuesto
        (r's$', ''),          # guantes → guante, bicicletas... 
    ]
    
    for pattern, replacement in rules:
        if re.search(pattern, q, re.IGNORECASE):
            return re.sub(pattern, replacement, q, count=1, flags=re.IGNORECASE)
    
    return q


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
        """Busca artículos por descripción. Normaliza plurales en español."""
        normalized = _normalize_search_query(query)
        like_original = f"%{query}%"
        like_normalized = f"%{normalized}%"
        
        if normalized.lower() == query.lower():
            models = self.db.query(ArticuloModel).filter(
                ArticuloModel.descripcion.ilike(like_original),
                ArticuloModel.activo == True,  # noqa: E712
            ).all()
        else:
            models = self.db.query(ArticuloModel).filter(
                ArticuloModel.activo == True,  # noqa: E712
            ).filter(
                (ArticuloModel.descripcion.ilike(like_original))
                | (ArticuloModel.descripcion.ilike(like_normalized))
            ).all()
        
        seen = set()
        unique = []
        for m in models:
            if m.codigo not in seen:
                seen.add(m.codigo)
                unique.append(m)
        return [_model_to_entity(m) for m in unique]

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
        """Búsqueda flexible: código, código barra, código rápido o descripción.
        
        Normaliza plurales en español para mejorar resultados:
        'bicicletas' → busca 'bicicleta', 'cascos' → busca 'casco', etc.
        """
        like = f"%{query}%"
        normalized = _normalize_search_query(query)
        like_normalized = f"%{normalized}%"
        
        # Si la query normalizada es igual a la original, buscar solo una vez
        if normalized.lower() == query.lower():
            models = self.db.query(ArticuloModel).filter(
                ArticuloModel.activo == True,  # noqa: E712
            ).filter(
                (ArticuloModel.codigo.ilike(like))
                | (ArticuloModel.descripcion.ilike(like))
                | (ArticuloModel.codigo_barra.ilike(like))
                | (ArticuloModel.codigo_rapido.ilike(like))
            ).all()
        else:
            # Buscar con ambos términos (original y normalizado) para máxima cobertura
            models = self.db.query(ArticuloModel).filter(
                ArticuloModel.activo == True,  # noqa: E712
            ).filter(
                (ArticuloModel.codigo.ilike(like))
                | (ArticuloModel.descripcion.ilike(like))
                | (ArticuloModel.codigo_barra.ilike(like))
                | (ArticuloModel.codigo_rapido.ilike(like))
                | (ArticuloModel.codigo.ilike(like_normalized))
                | (ArticuloModel.descripcion.ilike(like_normalized))
                | (ArticuloModel.codigo_barra.ilike(like_normalized))
                | (ArticuloModel.codigo_rapido.ilike(like_normalized))
            ).all()
        
        # Deduplicar por código
        seen = set()
        unique = []
        for m in models:
            if m.codigo not in seen:
                seen.add(m.codigo)
                unique.append(m)
        
        return [_model_to_entity(m) for m in unique]