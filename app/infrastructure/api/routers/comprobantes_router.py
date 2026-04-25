"""Router: Comprobantes (facturación y cotización)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.schemas import (
    ComprobanteRequest,
    ComprobanteResponse,
    CotizacionConvertRequest,
    DetalleComprobanteResponse,
    ComprobanteFormaPagoResponse,
)
from app.application.use_cases.comprobante_use_case import ComprobanteUseCase
from app.domain.entities.entities import Comprobante, DetalleComprobante, ComprobanteFormaPago
from app.domain.value_objects.enums import TipoComprobante
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.articulo_repo import SqlAlchemyArticuloRepository
from app.infrastructure.database.repositories.caja_repo import SqlAlchemyCajaRepository
from app.infrastructure.database.repositories.cliente_repo import SqlAlchemyClienteRepository
from app.infrastructure.database.repositories.comprobante_repo import SqlAlchemyComprobanteRepository
from app.infrastructure.database.repositories.forma_pago_repo import SqlAlchemyFormaPagoRepository
from app.infrastructure.database.repositories.vendedor_repo import SqlAlchemyVendedorRepository


def _entity_to_response(c: Comprobante) -> ComprobanteResponse:
    return ComprobanteResponse(
        id=c.id,
        tipo=c.tipo,
        punto_venta=c.punto_venta,
        numero=c.numero,
        cliente_id=c.cliente_id,
        vendedor_id=c.vendedor_id,
        caja_id=c.caja_id,
        consumidor_final=c.consumidor_final,
        lista_mayorista=c.lista_mayorista,
        fecha=c.fecha,
        subtotal=c.subtotal,
        descuento_pie=c.descuento_pie,
        total=c.total,
        estado_sincronizacion=c.estado_sincronizacion,
        cotizacion_origen_id=c.cotizacion_origen_id,
        detalles=[
            DetalleComprobanteResponse(
                id=d.id,
                articulo_codigo=d.articulo_codigo,
                cantidad=d.cantidad,
                precio_unitario=d.precio_unitario,
                imp_int=d.imp_int,
                porc_dto=d.porc_dto,
                descuento=d.descuento,
                porc_alicuota=d.porc_alicuota,
                subtotal=d.subtotal,
            )
            for d in c.detalles
        ],
        formas_pago=[
            ComprobanteFormaPagoResponse(
                id=fp.id,
                forma_pago_id=fp.forma_pago_id,
                monto=fp.monto,
                cuotas=fp.cuotas,
                lote=fp.lote,
                nro_cupon=fp.nro_cupon,
                recargo_financiero=fp.recargo_financiero,
            )
            for fp in c.formas_pago
        ],
    )


def _get_use_case(db: Session) -> ComprobanteUseCase:
    return ComprobanteUseCase(
        repo=SqlAlchemyComprobanteRepository(db),
        caja_repo=SqlAlchemyCajaRepository(db),
        articulo_repo=SqlAlchemyArticuloRepository(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        vendedor_repo=SqlAlchemyVendedorRepository(db),
        forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
    )


router = APIRouter(prefix="/comprobantes", tags=["Comprobantes"])


@router.post("/", response_model=ComprobanteResponse)
def crear_comprobante(request: ComprobanteRequest, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)

    comprobante = Comprobante(
        tipo=request.tipo,
        cliente_id=request.cliente_id,
        vendedor_id=request.vendedor_id,
        lista_mayorista=request.lista_mayorista,
        descuento_pie=request.descuento_pie,
        consumidor_final=(request.cliente_id == 1),
        detalles=[
            DetalleComprobante(
                articulo_codigo=d.articulo_codigo,
                cantidad=d.cantidad,
                porc_dto=d.porc_dto,
                imp_int=d.imp_int,
            )
            for d in request.detalles
        ],
        formas_pago=[
            ComprobanteFormaPago(
                forma_pago_id=fp.forma_pago_id,
                monto=fp.monto,
                cuotas=fp.cuotas,
                lote=fp.lote,
                nro_cupon=fp.nro_cupon,
            )
            for fp in request.formas_pago
        ],
    )

    result = use_case.crear_comprobante(comprobante)
    db.commit()
    return _entity_to_response(result)


@router.get("/{comprobante_id}", response_model=ComprobanteResponse)
def get_comprobante(comprobante_id: int, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    comp = use_case.get_by_id(comprobante_id)
    return _entity_to_response(comp)


@router.get("/cotizaciones/pendientes", response_model=list[ComprobanteResponse])
def cotizaciones_pendientes(db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    cotizaciones = use_case.listar_cotizaciones_pendientes()
    return [_entity_to_response(c) for c in cotizaciones]


@router.get("/tipo/{tipo}", response_model=list[ComprobanteResponse])
def comprobantes_por_tipo(tipo: TipoComprobante, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    comprobantes = use_case.listar_por_tipo(tipo)
    return [_entity_to_response(c) for c in comprobantes]


@router.get("/caja/{caja_id}", response_model=list[ComprobanteResponse])
def comprobantes_por_caja(caja_id: int, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    comprobantes = use_case.listar_por_caja(caja_id)
    return [_entity_to_response(c) for c in comprobantes]


@router.post("/cotizacion/{cotizacion_id}/convertir", response_model=ComprobanteResponse)
def convertir_cotizacion(cotizacion_id: int, request: CotizacionConvertRequest, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    factura = use_case.convertir_cotizacion_a_factura(cotizacion_id, tipo_factura=request.tipo)
    db.commit()
    return _entity_to_response(factura)