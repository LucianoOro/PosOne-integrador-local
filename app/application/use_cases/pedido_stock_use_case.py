"""Caso de uso: Pedidos de Stock."""

from app.application.ports.articulo_repository import ArticuloRepository
from app.application.ports.pedido_stock_repository import PedidoStockRepository
from app.domain.entities.entities import PedidoStock, DetallePedidoStock
from app.domain.exceptions import PedidoNoEncontradoError
from app.domain.value_objects.enums import EstadoPedido, EstadoSincronizacion


class PedidoStockUseCase:
    def __init__(self, repo: PedidoStockRepository, articulo_repo: ArticuloRepository):
        self.repo = repo
        self.articulo_repo = articulo_repo

    def crear_pedido(self, vendedor_id: int, articulo_codigos: list[str]) -> PedidoStock:
        """Crea un pedido de stock con los artículos indicados.

        Snapshot del estado de inventario al momento del pedido.
        """
        pedido = PedidoStock(
            vendedor_id=vendedor_id,
            estado=EstadoPedido.PENDIENTE,
            estado_sincronizacion=EstadoSincronizacion.PENDIENTE,
            detalles=[],
        )

        for codigo in articulo_codigos:
            articulo = self.articulo_repo.get_by_codigo(codigo)
            if not articulo:
                continue  # Artículos no encontrados se ignoran en el pedido

            # Calcular cantidad sugerida según múltiplo
            cantidad_sugerida = max(articulo.stock_minimo - articulo.stock_actual, 0)
            # Redondear al múltiplo superior (por ahora múltiplo = 1)
            stock_pedido = cantidad_sugerida

            detalle = DetallePedidoStock(
                articulo_codigo=articulo.codigo,
                rubro_id=articulo.rubro_id,
                cantidad=stock_pedido if stock_pedido > 0 else articulo.stock_minimo,
                precio_unitario=articulo.precio_publico,
                total=stock_pedido * articulo.precio_publico if stock_pedido > 0 else articulo.stock_minimo * articulo.precio_publico,
                stock_actual_al_pedido=articulo.stock_actual,
                stock_minimo=articulo.stock_minimo,
                stock_pedido=stock_pedido,
                inventario_estado=articulo.inventario_estado,
            )
            pedido.detalles.append(detalle)

        return self.repo.save(pedido)

    def get_by_id(self, pedido_id: int) -> PedidoStock:
        pedido = self.repo.get_by_id(pedido_id)
        if not pedido:
            raise PedidoNoEncontradoError(pedido_id)
        return pedido

    def listar_pendientes(self):
        return self.repo.list_by_estado(EstadoPedido.PENDIENTE)

    def listar_por_estado(self, estado: EstadoPedido):
        return self.repo.list_by_estado(estado)