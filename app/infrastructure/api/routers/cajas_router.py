"""Router: Cajas."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.schemas import CajaResponse, CajaOpenRequest, CajaCloseRequest
from app.application.use_cases.caja_use_case import CajaUseCase
from app.domain.entities.entities import Caja
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.caja_repo import SqlAlchemyCajaRepository
from app.infrastructure.database.repositories.vendedor_repo import SqlAlchemyVendedorRepository


def _entity_to_response(c: Caja) -> CajaResponse:
    return CajaResponse(
        id=c.id,
        vendedor_id=c.vendedor_id,
        fecha_apertura=c.fecha_apertura,
        fecha_cierre=c.fecha_cierre,
        saldo_inicial=c.saldo_inicial,
        diferencia=c.diferencia,
        estado=c.estado,
    )


router = APIRouter(prefix="/cajas", tags=["Cajas"])


@router.get("/abierta", response_model=CajaResponse)
def get_caja_abierta(db: Session = Depends(get_db)):
    use_case = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
    caja = use_case.get_abierta()
    return _entity_to_response(caja)


@router.post("/abrir", response_model=CajaResponse)
def abrir_caja(request: CajaOpenRequest, db: Session = Depends(get_db)):
    use_case = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
    caja = use_case.abrir(vendedor_id=request.vendedor_id, saldo_inicial=request.saldo_inicial)
    db.commit()
    return _entity_to_response(caja)


@router.post("/{caja_id}/cerrar", response_model=CajaResponse)
def cerrar_caja(caja_id: int, request: CajaCloseRequest, db: Session = Depends(get_db)):
    use_case = CajaUseCase(SqlAlchemyCajaRepository(db), SqlAlchemyVendedorRepository(db))
    caja = use_case.cerrar(caja_id=caja_id, diferencia=request.diferencia)
    db.commit()
    return _entity_to_response(caja)