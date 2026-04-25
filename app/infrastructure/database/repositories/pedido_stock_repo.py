"""Implementación SQLAlchemy del repositorio de Pedidos de Stock."""

from sqlalchemy.orm import Session

from app.application.ports.pedido_stock_repository import PedidoStockRepository
from app.domain.entities.entities import PedidoStock, DetallePedidoStock
from app.domain.value_objects.enums import EstadoPedido, InventarioEstado
from app.infrastructure.database.models import (
    PedidoStockModel,
    DetallePedidoStockModel,
)


def _detalle_model_to_entity(m: DetallePedidoStockModel) -> DetallePedidoStock:
    return DetallePedidoStock(
        id=m.id,
        pedido_id=m.pedido_id,
        articulo_codigo=m.articulo_codigo,
        rubro_id=m.rubro_id,
        cantidad=m.cantidad,
        precio_unitario=m.precio_unitario,
        total=m.total,
        stock_actual_al_pedido=m.stock_actual_al_pedido,
        stock_minimo=m.stock_minimo,
        stock_pedido=m.stock_pedido,
        multiplo=m.multiplo,
        inventario_estado=InventarioEstado(m.inventario_estado),
    )


def _model_to_entity(m: PedidoStockModel) -> PedidoStock:
    return PedidoStock(
        id=m.id,
        vendedor_id=m.vendedor_id,
        fecha=m.fecha,
        estado=EstadoPedido(m.estado),
        estado_sincronizacion=EstadoPedido(m.estado),  # Will be fixed below
        detalles=[_detalle_model_to_entity(d) for d in m.detalles],
    )


def _model_to_entity_full(m: PedidoStockModel) -> PedidoStock:
    """Full mapping including estado_sincronizacion."""
    from app.domain.value_objects.enums import EstadoSincronizacion
    return PedidoStock(
        id=m.id,
        vendedor_id=m.vendedor_id,
        fecha=m.fecha,
        estado=EstadoPedido(m.estado),
        estado_sincronizacion=EstadoSincronizacion(m.estado_sincronizacion),
        detalles=[_detalle_model_to_entity(d) for d in m.detalles],
    )


class SqlAlchemyPedidoStockRepository(PedidoStockRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, pedido_id: int) -> PedidoStock | None:
        m = self.db.query(PedidoStockModel).filter(
            PedidoStockModel.id == pedido_id
        ).first()
        return _model_to_entity_full(m) if m else None

    def save(self, pedido: PedidoStock) -> PedidoStock:
        from app.domain.value_objects.enums import EstadoSincronizacion

        # Encabezado
        if pedido.id:
            model = self.db.query(PedidoStockModel).filter(
                PedidoStockModel.id == pedido.id
            ).first()
            if model:
                model.estado = pedido.estado.value
                model.estado_sincronizacion = pedido.estado_sincronizacion.value
                for d in model.detalles:
                    self.db.delete(d)
                self.db.flush()
        else:
            model = PedidoStockModel(
                vendedor_id=pedido.vendedor_id,
                estado=pedido.estado.value,
                estado_sincronizacion=pedido.estado_sincronizacion.value,
            )
            self.db.add(model)
            self.db.flush()

        # Insertar detalles
        for det in pedido.detalles:
            det_model = DetallePedidoStockModel(
                pedido_id=model.id,
                articulo_codigo=det.articulo_codigo,
                rubro_id=det.rubro_id,
                cantidad=det.cantidad,
                precio_unitario=det.precio_unitario,
                total=det.total,
                stock_actual_al_pedido=det.stock_actual_al_pedido,
                stock_minimo=det.stock_minimo,
                stock_pedido=det.stock_pedido,
                multiplo=det.multiplo,
                inventario_estado=det.inventario_estado.value,
            )
            self.db.add(det_model)

        self.db.flush()
        return _model_to_entity_full(model)

    def list_by_estado(self, estado: EstadoPedido) -> list[PedidoStock]:
        models = self.db.query(PedidoStockModel).filter(
            PedidoStockModel.estado == estado.value
        ).order_by(PedidoStockModel.fecha.desc()).all()
        return [_model_to_entity_full(m) for m in models]