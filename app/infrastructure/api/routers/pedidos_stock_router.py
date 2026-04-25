"""Router: Pedidos de Stock."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.schemas import PedidoStockRequest, PedidoStockResponse, DetallePedidoStockResponse
from app.application.use_cases.pedido_stock_use_case import PedidoStockUseCase
from app.domain.value_objects.enums import EstadoPedido
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.articulo_repo import SqlAlchemyArticuloRepository
from app.infrastructure.database.repositories.pedido_stock_repo import SqlAlchemyPedidoStockRepository


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
    return PedidoStockResponse(
        id=pedido.id,
        vendedor_id=pedido.vendedor_id,
        fecha=pedido.fecha,
        estado=pedido.estado,
        estado_sincronizacion=pedido.estado_sincronizacion,
        detalles=[
            DetallePedidoStockResponse(
                id=d.id,
                articulo_codigo=d.articulo_codigo,
                rubro_id=d.rubro_id,
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


@router.get("/{pedido_id}", response_model=PedidoStockResponse)
def get_pedido(pedido_id: int, db: Session = Depends(get_db)):
    use_case = PedidoStockUseCase(
        repo=SqlAlchemyPedidoStockRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
    )
    pedido = use_case.get_by_id(pedido_id)
    return PedidoStockResponse(
        id=pedido.id,
        vendedor_id=pedido.vendedor_id,
        fecha=pedido.fecha,
        estado=pedido.estado,
        estado_sincronizacion=pedido.estado_sincronizacion,
        detalles=[
            DetallePedidoStockResponse(
                id=d.id,
                articulo_codigo=d.articulo_codigo,
                rubro_id=d.rubro_id,
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


@router.get("/", response_model=list[PedidoStockResponse])
def listar_pedidos(estado: EstadoPedido = None, db: Session = Depends(get_db)):
    use_case = PedidoStockUseCase(
        repo=SqlAlchemyPedidoStockRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
    )
    if estado:
        pedidos = use_case.listar_por_estado(estado)
    else:
        pedidos = use_case.listar_pendientes()
    return [
        PedidoStockResponse(
            id=p.id,
            vendedor_id=p.vendedor_id,
            fecha=p.fecha,
            estado=p.estado,
            estado_sincronizacion=p.estado_sincronizacion,
            detalles=[
                DetallePedidoStockResponse(
                    id=d.id,
                    articulo_codigo=d.articulo_codigo,
                    rubro_id=d.rubro_id,
                    cantidad=d.cantidad,
                    precio_unitario=d.precio_unitario,
                    total=d.total,
                    stock_actual_al_pedido=d.stock_actual_al_pedido,
                    stock_minimo=d.stock_minimo,
                    stock_pedido=d.stock_pedido,
                    multiplo=d.multiplo,
                    inventario_estado=d.inventario_estado,
                )
                for d in p.detalles
            ],
        )
        for p in pedidos
    ]