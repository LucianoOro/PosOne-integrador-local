"""Router: Artículos.

Endpoints para búsqueda y gestión del catálogo de artículos.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.schemas import ArticuloResponse, ArticuloSearchRequest, ErrorResponse
from app.application.use_cases.articulo_use_case import ArticuloUseCase
from app.domain.entities.entities import Articulo
from app.domain.value_objects.enums import InventarioEstado
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.articulo_repo import SqlAlchemyArticuloRepository
from app.infrastructure.database.repositories.rubro_repo import SqlAlchemyRubroRepository


def _resolve_nombres(articulo: Articulo, db: Session) -> dict:
    """Resuelve nombres relacionados de un artículo (evita N+1)."""
    rubro_repo = SqlAlchemyRubroRepository(db)
    rubro = rubro_repo.get_by_id(articulo.rubro_id)
    return {
        "rubro_nombre": rubro.nombre if rubro else None,
    }


def _resolve_nombres_batch(articulos: list[Articulo], db: Session) -> dict[int, dict]:
    """Resuelve nombres en batch para una lista de artículos (evita N+1)."""
    rubro_ids = {a.rubro_id for a in articulos}
    rubro_repo = SqlAlchemyRubroRepository(db)
    rubros_map = {}
    for rid in rubro_ids:
        rubro = rubro_repo.get_by_id(rid)
        if rubro:
            rubros_map[rid] = rubro.nombre
    # Retorna dict: rubro_id → {"rubro_nombre": nombre}
    return {rid: {"rubro_nombre": nombre} for rid, nombre in rubros_map.items()}


def _entity_to_response(a: Articulo, nombres: dict | None = None) -> ArticuloResponse:
    nombres = nombres or {}
    return ArticuloResponse(
        codigo=a.codigo,
        descripcion=a.descripcion,
        rubro_id=a.rubro_id,
        rubro_nombre=nombres.get("rubro_nombre"),
        precio_publico=a.precio_publico,
        precio_mayorista=a.precio_mayorista,
        stock_actual=a.stock_actual,
        stock_minimo=a.stock_minimo,
        inventario_estado=a.inventario_estado,
        codigo_barra=a.codigo_barra,
        codigo_rapido=a.codigo_rapido,
        activo=a.activo,
    )


router = APIRouter(prefix="/articulos", tags=["Artículos"])


@router.get("/", response_model=list[ArticuloResponse])
def listar_articulos(solo_activos: bool = Query(default=True), db: Session = Depends(get_db)):
    use_case = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
    articulos = use_case.list_all(solo_activos=solo_activos)
    nombres_batch = _resolve_nombres_batch(articulos, db)
    return [_entity_to_response(a, nombres_batch.get(a.rubro_id)) for a in articulos]


@router.get("/buscar", response_model=list[ArticuloResponse])
def buscar_articulos(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    use_case = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
    articulos = use_case.search(q)
    nombres_batch = _resolve_nombres_batch(articulos, db)
    return [_entity_to_response(a, nombres_batch.get(a.rubro_id)) for a in articulos]


@router.get("/bajo-stock", response_model=list[ArticuloResponse])
def articulos_bajo_stock(db: Session = Depends(get_db)):
    use_case = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
    articulos = use_case.list_bajo_stock()
    nombres_batch = _resolve_nombres_batch(articulos, db)
    return [_entity_to_response(a, nombres_batch.get(a.rubro_id)) for a in articulos]


@router.get("/rubro/{rubro_id}", response_model=list[ArticuloResponse])
def articulos_por_rubro(rubro_id: int, db: Session = Depends(get_db)):
    use_case = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
    articulos = use_case.list_by_rubro(rubro_id)
    nombres_batch = _resolve_nombres_batch(articulos, db)
    return [_entity_to_response(a, nombres_batch.get(a.rubro_id)) for a in articulos]


@router.get("/{codigo}", response_model=ArticuloResponse)
def get_articulo(codigo: str, db: Session = Depends(get_db)):
    use_case = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
    articulo = use_case.get_by_codigo(codigo)
    nombres = _resolve_nombres(articulo, db)
    return _entity_to_response(articulo, nombres)


@router.post("/{codigo}/bloquear", response_model=ArticuloResponse)
def bloquear_articulo(codigo: str, db: Session = Depends(get_db)):
    use_case = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
    articulo = use_case.bloquear(codigo)
    db.commit()
    nombres = _resolve_nombres(articulo, db)
    return _entity_to_response(articulo, nombres)


@router.post("/{codigo}/desbloquear", response_model=ArticuloResponse)
def desbloquear_articulo(codigo: str, db: Session = Depends(get_db)):
    use_case = ArticuloUseCase(SqlAlchemyArticuloRepository(db), SqlAlchemyRubroRepository(db))
    articulo = use_case.desbloquear(codigo)
    db.commit()
    nombres = _resolve_nombres(articulo, db)
    return _entity_to_response(articulo, nombres)