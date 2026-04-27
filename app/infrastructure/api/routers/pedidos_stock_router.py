"""Router: Pedidos de Stock."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.application.schemas import PedidoStockRequest, PedidoStockResponse, DetallePedidoStockResponse
from app.application.use_cases.pedido_stock_use_case import PedidoStockUseCase
from app.domain.value_objects.enums import EstadoPedido
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.articulo_repo import SqlAlchemyArticuloRepository
from app.infrastructure.database.repositories.pedido_stock_repo import SqlAlchemyPedidoStockRepository
from app.infrastructure.database.repositories.rubro_repo import SqlAlchemyRubroRepository
from app.infrastructure.database.repositories.vendedor_repo import SqlAlchemyVendedorRepository


def _resolve_nombres(pedido, db: Session) -> dict:
    """Resuelve nombres relacionados de un pedido de stock (evita N+1)."""
    vendedor_repo = SqlAlchemyVendedorRepository(db)
    articulo_repo = SqlAlchemyArticuloRepository(db)
    rubro_repo = SqlAlchemyRubroRepository(db)

    vendedor = vendedor_repo.get_by_id(pedido.vendedor_id)

    # Batch: articulo_codigo → descripcion
    codigos = {d.articulo_codigo for d in pedido.detalles}
    articulos_map = {}
    for codigo in codigos:
        art = articulo_repo.get_by_codigo(codigo)
        if art:
            articulos_map[codigo] = art.descripcion

    # Batch: rubro_id → nombre
    rubro_ids = {d.rubro_id for d in pedido.detalles}
    rubros_map = {}
    for rid in rubro_ids:
        rubro = rubro_repo.get_by_id(rid)
        if rubro:
            rubros_map[rid] = rubro.nombre

    return {
        "vendedor_nombre": vendedor.nombre if vendedor else None,
        "articulos_map": articulos_map,
        "rubros_map": rubros_map,
    }


def _pedido_to_response(pedido, nombres: dict | None = None) -> PedidoStockResponse:
    nombres = nombres or {}
    return PedidoStockResponse(
        id=pedido.id,
        vendedor_id=pedido.vendedor_id,
        vendedor_nombre=nombres.get("vendedor_nombre"),
        fecha=pedido.fecha,
        estado=pedido.estado,
        estado_sincronizacion=pedido.estado_sincronizacion,
        detalles=[
            DetallePedidoStockResponse(
                id=d.id,
                articulo_codigo=d.articulo_codigo,
                articulo_descripcion=nombres.get("articulos_map", {}).get(d.articulo_codigo),
                rubro_id=d.rubro_id,
                rubro_nombre=nombres.get("rubros_map", {}).get(d.rubro_id),
                cantidad=d.cantidad,
                precio_unitario=d.precio_unitario,
                total=d.total,
                stock_actual_al_pedido=d.stock_actual_al_pedido,
                stock_minimo=d.stock_minimo,
                stock_pedido=d.stock_pedido,
                multiplo=d.multiplo,
                inventario_estado=d.inventario_estado,
            )
            for d in pedido.detalles
        ],
    )


router = APIRouter(prefix="/pedidos-stock", tags=["Pedidos de Stock"])


@router.post("/", response_model=PedidoStockResponse)
def crear_pedido(request: PedidoStockRequest, db: Session = Depends(get_db)):
    use_case = PedidoStockUseCase(
        repo=SqlAlchemyPedidoStockRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
    )
    pedido = use_case.crear_pedido(
        vendedor_id=request.vendedor_id,
        articulo_codigos=[d.articulo_codigo for d in request.detalles],
    )
    db.commit()
    nombres = _resolve_nombres(pedido, db)
    return _pedido_to_response(pedido, nombres)


@router.get("/{pedido_id}", response_model=PedidoStockResponse)
def get_pedido(pedido_id: int, db: Session = Depends(get_db)):
    use_case = PedidoStockUseCase(
        repo=SqlAlchemyPedidoStockRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
    )
    pedido = use_case.get_by_id(pedido_id)
    nombres = _resolve_nombres(pedido, db)
    return _pedido_to_response(pedido, nombres)


@router.get("/", response_model=list[PedidoStockResponse])
def listar_pedidos(estado: Optional[EstadoPedido] = Query(default=None), db: Session = Depends(get_db)):
    use_case = PedidoStockUseCase(
        repo=SqlAlchemyPedidoStockRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
    )
    if estado:
        pedidos = use_case.listar_por_estado(estado)
    else:
        pedidos = use_case.listar_pendientes()
    return [_pedido_to_response(p, _resolve_nombres(p, db)) for p in pedidos]