"""Caso de uso: Comprobantes.

Orquesta facturación, cotización y conversión de cotización → factura.
Reglas de negocio clave:
- No se puede facturar sin caja abierta (CajaNoAbiertaError)
- No se puede facturar artículos bloqueados (ArticuloBloqueadoError)
- Las facturas descuentan stock, las cotizaciones NO
- Cada comprobante obtiene número correlativo automático
- La conversión cotización → factura crea un NUEVO comprobante (no modifica el original)
"""

from app.application.ports.articulo_repository import ArticuloRepository
from app.application.ports.caja_repository import CajaRepository
from app.application.ports.cliente_repository import ClienteRepository
from app.application.ports.comprobante_repository import ComprobanteRepository
from app.application.ports.forma_pago_repository import FormaPagoRepository
from app.application.ports.vendedor_repository import VendedorRepository
from app.domain.entities.entities import Comprobante, DetalleComprobante, ComprobanteFormaPago
from app.domain.exceptions import (
    ArticuloBloqueadoError,
    ComprobanteNoEncontradoError,
    CotizacionYaConvertidaError,
    TipoComprobanteInvalidoError,
)
from app.domain.value_objects.enums import TipoComprobante, EstadoSincronizacion


class ComprobanteUseCase:
    def __init__(
        self,
        repo: ComprobanteRepository,
        caja_repo: CajaRepository,
        articulo_repo: ArticuloRepository,
        cliente_repo: ClienteRepository,
        vendedor_repo: VendedorRepository,
        forma_pago_repo: FormaPagoRepository,
    ):
        self.repo = repo
        self.caja_repo = caja_repo
        self.articulo_repo = articulo_repo
        self.cliente_repo = cliente_repo
        self.vendedor_repo = vendedor_repo
        self.forma_pago_repo = forma_pago_repo

    def crear_comprobante(self, comprobante: Comprobante) -> Comprobante:
        """Crea un comprobante (factura o cotización).

        Si es factura: valida caja abierta, valida artículos no bloqueados, descuenta stock.
        Si es cotización: soloersistence, sin afectar stock ni requerir caja.
        """
        es_factura = comprobante.es_factura

        # 1. Si es factura, requiere caja abierta
        if es_factura:
            caja = self.caja_repo.find_abierta()
            if not caja:
                from app.domain.exceptions import CajaNoAbiertaError
                raise CajaNoAbiertaError()
            comprobante.caja_id = caja.id

        # 2. Validar y procesar artículos
        for detalle in comprobante.detalles:
            articulo = self.articulo_repo.get_by_codigo(detalle.articulo_codigo)
            if not articulo:
                from app.domain.exceptions import ArticuloNoEncontradoError
                raise ArticuloNoEncontradoError(detalle.articulo_codigo)
            if es_factura and articulo.inventario_estado.value == "BLOQUEADO":
                raise ArticuloBloqueadoError(detalle.articulo_codigo)
            # Calcular precio según lista
            detalle.precio_unitario = articulo.calcular_precio(comprobante.lista_mayorista)
            # Calcular subtotal de la línea
            detalle.calcular_subtotal()
            # Descontar stock SOLO en facturas
            if es_factura and comprobante.descuenta_stock:
                articulo.descontar_stock(detalle.cantidad)
                self.articulo_repo.save(articulo)

        # 3. Calcular totales
        comprobante.subtotal = sum(d.subtotal for d in comprobante.detalles)
        comprobante.calcular_total()

        # 4. Validar formas de pago y calcular recargos
        for fp in comprobante.formas_pago:
            forma_pago = self.forma_pago_repo.get_by_id(fp.forma_pago_id)
            if forma_pago and forma_pago.tiene_recargo:
                fp.recargo_financiero = forma_pago.recargo_financiero

        # 5. Asignar número correlativo
        comprobante.numero = self.repo.get_next_numero(
            comprobante.punto_venta, comprobante.tipo
        )

        # 6. Persistir
        comprobante.estado_sincronizacion = EstadoSincronizacion.PENDIENTE
        return self.repo.save(comprobante)

    def get_by_id(self, comprobante_id: int) -> Comprobante:
        comp = self.repo.get_by_id(comprobante_id)
        if not comp:
            raise ComprobanteNoEncontradoError(comprobante_id)
        return comp

    def listar_cotizaciones_pendientes(self):
        return self.repo.list_cotizaciones_pendientes()

    def listar_por_tipo(self, tipo: TipoComprobante):
        return self.repo.list_by_tipo(tipo)

    def listar_por_caja(self, caja_id: int):
        return self.repo.list_by_caja(caja_id)

    def convertir_cotizacion_a_factura(
        self, cotizacion_id: int, tipo_factura: TipoComprobante = TipoComprobante.FACTURA_B
    ) -> Comprobante:
        """Convierte una cotización en factura.

        Crea un NUEVO comprobante (la cotización original NO se modifica).
        La cotización queda vinculada via cotizacion_origen_id en la nueva factura.
        """
        cotizacion = self.repo.get_by_id(cotizacion_id)
        if not cotizacion:
            from app.domain.exceptions import CotizacionNoEncontradaError
            raise CotizacionNoEncontradaError(cotizacion_id)

        # Verificar que sea cotización
        if cotizacion.tipo != TipoComprobante.COTIZACION:
            raise TipoComprobanteInvalidoError(cotizacion.tipo.value, "convertir a factura")

        # Verificar que no fue ya convertida
        # (Si existe una factura con cotizacion_origen_id == cotizacion_id, ya fue convertida)
        facturas = self.repo.list_by_tipo(tipo_factura)
        for f in facturas:
            if f.cotizacion_origen_id == cotizacion_id:
                raise CotizacionYaConvertidaError(cotizacion_id, f.id)

        # Crear NUEVO comprobante (factura) copiando datos de la cotización
        factura = Comprobante(
            tipo=tipo_factura,
            punto_venta=cotizacion.punto_venta,
            cliente_id=cotizacion.cliente_id,
            vendedor_id=cotizacion.vendedor_id,
            caja_id=0,  # Se asigna en crear_comprobante
            consumidor_final=cotizacion.consumidor_final,
            lista_mayorista=cotizacion.lista_mayorista,
            descuento_pie=cotizacion.descuento_pie,
            cotizacion_origen_id=cotizacion.id,
            detalles=[],
            formas_pago=[],
        )

        # Copiar detalles
        for det in cotizacion.detalles:
            factura.detalles.append(DetalleComprobante(
                articulo_codigo=det.articulo_codigo,
                cantidad=det.cantidad,
                porc_dto=det.porc_dto,
                imp_int=det.imp_int,
                porc_alicuota=det.porc_alicota,
            ))

        # Copiar formas de pago
        for fp in cotizacion.formas_pago:
            factura.formas_pago.append(ComprobanteFormaPago(
                forma_pago_id=fp.forma_pago_id,
                monto=fp.monto,
                cuotas=fp.cuotas,
                lote=fp.lote,
                nro_cupon=fp.nro_cupon,
            ))

        # Esto valida caja, artículos, stock y asigna número
        return self.crear_comprobante(factura)