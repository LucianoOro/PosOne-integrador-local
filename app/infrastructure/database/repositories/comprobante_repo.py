"""Implementación SQLAlchemy del repositorio de Comprobantes."""

from sqlalchemy.orm import Session

from app.application.ports.comprobante_repository import ComprobanteRepository
from app.domain.entities.entities import Comprobante, DetalleComprobante, ComprobanteFormaPago
from app.domain.value_objects.enums import TipoComprobante, EstadoSincronizacion, CanalOrigen
from app.infrastructure.database.models import (
    ComprobanteModel,
    DetalleComprobanteModel,
    ComprobanteFormaPagoModel,
)


def _detalle_model_to_entity(m: DetalleComprobanteModel) -> DetalleComprobante:
    return DetalleComprobante(
        id=m.id,
        comprobante_id=m.comprobante_id,
        articulo_codigo=m.articulo_codigo,
        cantidad=m.cantidad,
        precio_unitario=m.precio_unitario,
        imp_int=m.imp_int,
        porc_dto=m.porc_dto,
        descuento=m.descuento,
        porc_alicuota=m.porc_alicuota,
        subtotal=m.subtotal,
    )


def _forma_pago_model_to_entity(m: ComprobanteFormaPagoModel) -> ComprobanteFormaPago:
    return ComprobanteFormaPago(
        id=m.id,
        comprobante_id=m.comprobante_id,
        forma_pago_id=m.forma_pago_id,
        monto=m.monto,
        cuotas=m.cuotas,
        lote=m.lote or "",
        nro_cupon=m.nro_cupon or "",
        recargo_financiero=m.recargo_financiero,
    )


def _model_to_entity(m: ComprobanteModel) -> Comprobante:
    comp = Comprobante(
        id=m.id,
        tipo=TipoComprobante(m.tipo),
        punto_venta=m.punto_venta,
        numero=m.numero,
        cliente_id=m.cliente_id,
        vendedor_id=m.vendedor_id,
        caja_id=m.caja_id,
        consumidor_final=m.consumidor_final,
        lista_mayorista=m.lista_mayorista,
        fecha=m.fecha,
        subtotal=m.subtotal,
        descuento_pie=m.descuento_pie,
        total=m.total,
        estado_sincronizacion=EstadoSincronizacion(m.estado_sincronizacion),
        cotizacion_origen_id=m.cotizacion_origen_id,
        canal=m.canal or CanalOrigen.WEB.value,
        detalles=[_detalle_model_to_entity(d) for d in m.detalles],
        formas_pago=[_forma_pago_model_to_entity(fp) for fp in m.formas_pago],
    )
    return comp


class SqlAlchemyComprobanteRepository(ComprobanteRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, comprobante_id: int) -> Comprobante | None:
        m = self.db.query(ComprobanteModel).filter(
            ComprobanteModel.id == comprobante_id
        ).first()
        return _model_to_entity(m) if m else None

    def save(self, comprobante: Comprobante) -> Comprobante:
        # Encabezado
        if comprobante.id:
            model = self.db.query(ComprobanteModel).filter(
                ComprobanteModel.id == comprobante.id
            ).first()
            if model:
                model.tipo = comprobante.tipo.value
                model.punto_venta = comprobante.punto_venta
                model.numero = comprobante.numero
                model.cliente_id = comprobante.cliente_id
                model.vendedor_id = comprobante.vendedor_id
                model.caja_id = comprobante.caja_id
                model.consumidor_final = comprobante.consumidor_final
                model.lista_mayorista = comprobante.lista_mayorista
                model.subtotal = comprobante.subtotal
                model.descuento_pie = comprobante.descuento_pie
                model.total = comprobante.total
                model.estado_sincronizacion = comprobante.estado_sincronizacion.value
                model.cotizacion_origen_id = comprobante.cotizacion_origen_id
                model.canal = comprobante.canal
                # Borrar detalles y formas de pago viejas
                for d in model.detalles:
                    self.db.delete(d)
                for fp in model.formas_pago:
                    self.db.delete(fp)
                self.db.flush()
        else:
            model = ComprobanteModel(
                tipo=comprobante.tipo.value,
                punto_venta=comprobante.punto_venta,
                numero=comprobante.numero,
                cliente_id=comprobante.cliente_id,
                vendedor_id=comprobante.vendedor_id,
                caja_id=comprobante.caja_id,
                consumidor_final=comprobante.consumidor_final,
                lista_mayorista=comprobante.lista_mayorista,
                subtotal=comprobante.subtotal,
                descuento_pie=comprobante.descuento_pie,
                total=comprobante.total,
                estado_sincronizacion=comprobante.estado_sincronizacion.value,
                cotizacion_origen_id=comprobante.cotizacion_origen_id,
                canal=comprobante.canal,
            )
            self.db.add(model)
            self.db.flush()

        # Insertar detalles
        for det in comprobante.detalles:
            det_model = DetalleComprobanteModel(
                comprobante_id=model.id,
                articulo_codigo=det.articulo_codigo,
                cantidad=det.cantidad,
                precio_unitario=det.precio_unitario,
                imp_int=det.imp_int,
                porc_dto=det.porc_dto,
                descuento=det.descuento,
                porc_alicuota=det.porc_alicuota,
                subtotal=det.subtotal,
            )
            self.db.add(det_model)

        # Insertar formas de pago
        for fp in comprobante.formas_pago:
            fp_model = ComprobanteFormaPagoModel(
                comprobante_id=model.id,
                forma_pago_id=fp.forma_pago_id,
                monto=fp.monto,
                cuotas=fp.cuotas,
                lote=fp.lote,
                nro_cupon=fp.nro_cupon,
                recargo_financiero=fp.recargo_financiero,
            )
            self.db.add(fp_model)

        self.db.flush()
        return _model_to_entity(model)

    def get_next_numero(self, punto_venta: int, tipo: TipoComprobante) -> int:
        """Obtiene el próximo número para un tipo y punto de venta."""
        from sqlalchemy import func
        max_num = self.db.query(func.max(ComprobanteModel.numero)).filter(
            ComprobanteModel.punto_venta == punto_venta,
            ComprobanteModel.tipo == tipo.value,
        ).scalar()
        return (max_num or 0) + 1

    def list_by_tipo(self, tipo: TipoComprobante) -> list[Comprobante]:
        models = self.db.query(ComprobanteModel).filter(
            ComprobanteModel.tipo == tipo.value
        ).order_by(ComprobanteModel.fecha.desc()).all()
        return [_model_to_entity(m) for m in models]

    def list_cotizaciones_pendientes(self) -> list[Comprobante]:
        """Cotizaciones que NO fueron convertidas a factura (cotizacion_origen_id IS NULL para ese tipo)."""
        # Buscamos cotizaciones cuyo ID NO aparece como cotizacion_origen_id en otra factura
        from sqlalchemy import select
        subq = select(ComprobanteModel.cotizacion_origen_id).where(
            ComprobanteModel.cotizacion_origen_id.isnot(None)
        )
        models = self.db.query(ComprobanteModel).filter(
            ComprobanteModel.tipo == TipoComprobante.COTIZACION.value,
            ~ComprobanteModel.id.in_(subq),
        ).order_by(ComprobanteModel.fecha.desc()).all()
        return [_model_to_entity(m) for m in models]

    def list_by_caja(self, caja_id: int) -> list[Comprobante]:
        models = self.db.query(ComprobanteModel).filter(
            ComprobanteModel.caja_id == caja_id
        ).order_by(ComprobanteModel.fecha.desc()).all()
        return [_model_to_entity(m) for m in models]