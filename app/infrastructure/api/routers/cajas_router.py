"""Router: Cajas."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.application.schemas import CajaResponse, CajaOpenRequest, CajaCloseRequest
from app.application.use_cases.caja_use_case import CajaUseCase
from app.domain.entities.entities import Caja
from app.domain.exceptions import CajaNoAbiertaError
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.caja_repo import SqlAlchemyCajaRepository
from app.infrastructure.database.repositories.vendedor_repo import SqlAlchemyVendedorRepository


def _resolve_nombres(caja: Caja, db: Session) -> dict:
    """Resuelve nombres relacionados de una caja (evita N+1)."""
    vendedor_repo = SqlAlchemyVendedorRepository(db)
    vendedor = vendedor_repo.get_by_id(caja.vendedor_id)
    return {
        "vendedor_nombre": vendedor.nombre if vendedor else None,
    }


def _entity_to_response(c: Caja, nombres: dict | None = None) -> CajaResponse:
    nombres = nombres or {}
    return CajaResponse(
        id=c.id,
        vendedor_id=c.vendedor_id,
        vendedor_nombre=nombres.get("vendedor_nombre"),
        fecha_apertura=c.fecha_apertura,
        fecha_cierre=c.fecha_cierre,
        saldo_inicial=c.saldo_inicial,
        diferencia=c.diferencia,
        estado=c.estado,
    )


router = APIRouter(prefix="/cajas", tags=["Cajas"])


@router.get("/abierta", response_model=Optional[CajaResponse])
def get_caja_abierta(db: Session = Depends(get_db)):
    """Retorna la caja abierta o null si no hay ninguna."""
    use_case = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
    try:
        caja = use_case.get_abierta()
    except CajaNoAbiertaError:
        return None
    nombres = _resolve_nombres(caja, db)
    return _entity_to_response(caja, nombres)


@router.post("/abrir", response_model=CajaResponse)
def abrir_caja(request: CajaOpenRequest, db: Session = Depends(get_db)):
    use_case = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
    caja = use_case.abrir(vendedor_id=request.vendedor_id, saldo_inicial=request.saldo_inicial)
    db.commit()
    nombres = _resolve_nombres(caja, db)
    return _entity_to_response(caja, nombres)


@router.post("/{caja_id}/cerrar", response_model=CajaResponse)
def cerrar_caja(caja_id: int, request: CajaCloseRequest, db: Session = Depends(get_db)):
    use_case = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
    caja = use_case.cerrar(caja_id=caja_id, diferencia=request.diferencia)
    db.commit()
    nombres = _resolve_nombres(caja, db)
    return _entity_to_response(caja, nombres)