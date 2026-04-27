"""Router: Comprobantes (facturación y cotización)."""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
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
from app.infrastructure.pdf.comprobante_pdf import ComprobantePDFService


def _resolve_nombres(comprobante: Comprobante, db: Session) -> dict:
    """Resuelve todos los nombres relacionados de un comprobante (evita N+1)."""
    cliente_repo = SqlAlchemyClienteRepository(db)
    vendedor_repo = SqlAlchemyVendedorRepository(db)
    articulo_repo = SqlAlchemyArticuloRepository(db)
    forma_pago_repo = SqlAlchemyFormaPagoRepository(db)

    cliente = cliente_repo.get_by_id(comprobante.cliente_id)
    vendedor = vendedor_repo.get_by_id(comprobante.vendedor_id)

    # Batch: un dict de articulo_codigo → descripcion
    codigos = {d.articulo_codigo for d in comprobante.detalles}
    articulos_map = {}
    for codigo in codigos:
        art = articulo_repo.get_by_codigo(codigo)
        if art:
            articulos_map[codigo] = art.descripcion

    # Batch: un dict de forma_pago_id → nombre
    fp_ids = {fp.forma_pago_id for fp in comprobante.formas_pago}
    formas_pago_map = {}
    for fp_id in fp_ids:
        fp = forma_pago_repo.get_by_id(fp_id)
        if fp:
            formas_pago_map[fp_id] = fp.nombre

    return {
        "cliente_razon_social": cliente.razon_social if cliente else None,
        "cliente_cuit": cliente.cuit if cliente else None,
        "cliente_condicion_iva": cliente.condicion_iva.value if cliente else None,
        "vendedor_nombre": vendedor.nombre if vendedor else None,
        "articulos_map": articulos_map,
        "formas_pago_map": formas_pago_map,
    }


def _entity_to_response(c: Comprobante, nombres: dict | None = None) -> ComprobanteResponse:
    nombres = nombres or {}
    return ComprobanteResponse(
        id=c.id,
        tipo=c.tipo,
        punto_venta=c.punto_venta,
        numero=c.numero,
        cliente_id=c.cliente_id,
        cliente_razon_social=nombres.get("cliente_razon_social"),
        vendedor_id=c.vendedor_id,
        vendedor_nombre=nombres.get("vendedor_nombre"),
        caja_id=c.caja_id,
        consumidor_final=c.consumidor_final,
        lista_mayorista=c.lista_mayorista,
        fecha=c.fecha,
        subtotal=c.subtotal,
        descuento_pie=c.descuento_pie,
        total=c.total,
        estado_sincronizacion=c.estado_sincronizacion,
        cotizacion_origen_id=c.cotizacion_origen_id,
        canal=c.canal,
        detalles=[
            DetalleComprobanteResponse(
                id=d.id,
                articulo_codigo=d.articulo_codigo,
                articulo_descripcion=nombres.get("articulos_map", {}).get(d.articulo_codigo),
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
                forma_pago_nombre=nombres.get("formas_pago_map", {}).get(fp.forma_pago_id),
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
        canal=request.canal,
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
    nombres = _resolve_nombres(result, db)
    return _entity_to_response(result, nombres)


@router.get("/{comprobante_id}/pdf")
def get_comprobante_pdf(comprobante_id: int, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    comp = use_case.get_by_id(comprobante_id)
    nombres = _resolve_nombres(comp, db)

    pdf_service = ComprobantePDFService()
    pdf_bytes = pdf_service.generar_pdf(comp, nombres)

    tipo_label = comp.tipo.value
    filename = f"{tipo_label}_{comp.punto_venta:04d}-{comp.numero:08d}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{comprobante_id}", response_model=ComprobanteResponse)
def get_comprobante(comprobante_id: int, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    comp = use_case.get_by_id(comprobante_id)
    nombres = _resolve_nombres(comp, db)
    return _entity_to_response(comp, nombres)


@router.get("/cotizaciones/pendientes", response_model=list[ComprobanteResponse])
def cotizaciones_pendientes(db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    cotizaciones = use_case.listar_cotizaciones_pendientes()
    return [_entity_to_response(c, _resolve_nombres(c, db)) for c in cotizaciones]


@router.get("/tipo/{tipo}", response_model=list[ComprobanteResponse])
def comprobantes_por_tipo(tipo: TipoComprobante, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    comprobantes = use_case.listar_por_tipo(tipo)
    return [_entity_to_response(c, _resolve_nombres(c, db)) for c in comprobantes]


@router.get("/caja/{caja_id}", response_model=list[ComprobanteResponse])
def comprobantes_por_caja(caja_id: int, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    comprobantes = use_case.listar_por_caja(caja_id)
    return [_entity_to_response(c, _resolve_nombres(c, db)) for c in comprobantes]


@router.post("/cotizacion/{cotizacion_id}/convertir", response_model=ComprobanteResponse)
def convertir_cotizacion(cotizacion_id: int, request: CotizacionConvertRequest, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    factura = use_case.convertir_cotizacion_a_factura(cotizacion_id, tipo_factura=request.tipo)
    db.commit()
    nombres = _resolve_nombres(factura, db)
    return _entity_to_response(factura, nombres)