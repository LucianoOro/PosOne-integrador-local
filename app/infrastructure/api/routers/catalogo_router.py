"""Router: Catálogo (Rubros, Formas de Pago, Vendedores)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.application.schemas import RubroResponse, FormaPagoResponse, VendedorResponse
from app.application.use_cases.catalogo_use_case import CatalogoUseCase
from app.domain.entities.entities import Rubro, FormaPago, Vendedor
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.rubro_repo import SqlAlchemyRubroRepository
from app.infrastructure.database.repositories.forma_pago_repo import SqlAlchemyFormaPagoRepository
from app.infrastructure.database.repositories.vendedor_repo import SqlAlchemyVendedorRepository


def _rubro_to_response(r: Rubro) -> RubroResponse:
    return RubroResponse(id=r.id, nombre=r.nombre, activo=r.activo)


def _forma_pago_to_response(fp: FormaPago) -> FormaPagoResponse:
    return FormaPagoResponse(
        id=fp.id, nombre=fp.nombre,
        tiene_recargo=fp.tiene_recargo, recargo_financiero=fp.recargo_financiero,
    )


def _vendedor_to_response(v: Vendedor) -> VendedorResponse:
    return VendedorResponse(id=v.id, nombre=v.nombre, activo=v.activo)


router = APIRouter(prefix="/catalogo", tags=["Catálogo"])


def _get_use_case(db: Session) -> CatalogoUseCase:
    return CatalogoUseCase(
        rubro_repo=SqlAlchemyRubroRepository(db),
        forma_pago_repo=SqlAlchemyFormaPagoRepository(db),
        vendedor_repo=SqlAlchemyVendedorRepository(db),
    )


# ─── Rubros ──────────────────────────────────────────────────

@router.get("/rubros", response_model=list[RubroResponse])
def listar_rubros(solo_activos: bool = Query(default=True), db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    rubros = use_case.listar_rubros(solo_activos=solo_activos)
    return [_rubro_to_response(r) for r in rubros]


@router.get("/rubros/{rubro_id}", response_model=RubroResponse)
def get_rubro(rubro_id: int, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    rubro = use_case.get_rubro(rubro_id)
    if rubro is None:
        raise HTTPException(status_code=404, detail="Rubro no encontrado")
    return _rubro_to_response(rubro)


# ─── Formas de Pago ──────────────────────────────────────────

@router.get("/formas-pago", response_model=list[FormaPagoResponse])
def listar_formas_pago(db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    formas = use_case.listar_formas_pago()
    return [_forma_pago_to_response(fp) for fp in formas]


@router.get("/formas-pago/{forma_pago_id}", response_model=FormaPagoResponse)
def get_forma_pago(forma_pago_id: int, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    fp = use_case.get_forma_pago(forma_pago_id)
    if fp is None:
        raise HTTPException(status_code=404, detail="Forma de pago no encontrada")
    return _forma_pago_to_response(fp)


# ─── Vendedores ───────────────────────────────────────────────

@router.get("/vendedores", response_model=list[VendedorResponse])
def listar_vendedores(solo_activos: bool = Query(default=True), db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    vendedores = use_case.listar_vendedores(solo_activos=solo_activos)
    return [_vendedor_to_response(v) for v in vendedores]


@router.get("/vendedores/{vendedor_id}", response_model=VendedorResponse)
def get_vendedor(vendedor_id: int, db: Session = Depends(get_db)):
    use_case = _get_use_case(db)
    vendedor = use_case.get_vendedor(vendedor_id)
    if vendedor is None:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")
    return _vendedor_to_response(vendedor)