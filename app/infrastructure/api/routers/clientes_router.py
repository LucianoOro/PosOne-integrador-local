"""Router: Clientes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.schemas import ClienteResponse
from app.application.use_cases.cliente_use_case import ClienteUseCase
from app.domain.entities.entities import Cliente
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.repositories.cliente_repo import SqlAlchemyClienteRepository


def _entity_to_response(c: Cliente) -> ClienteResponse:
    return ClienteResponse(
        id=c.id,
        razon_social=c.razon_social,
        cuit=c.cuit,
        condicion_iva=c.condicion_iva,
        direccion=c.direccion,
        telefono=c.telefono,
        email=c.email,
        activo=c.activo,
    )


router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("/", response_model=list[ClienteResponse])
def listar_clientes(solo_activos: bool = Query(default=True), db: Session = Depends(get_db)):
    use_case = ClienteUseCase(SqlAlchemyClienteRepository(db))
    clientes = use_case.list_all(solo_activos=solo_activos)
    return [_entity_to_response(c) for c in clientes]


@router.get("/buscar", response_model=list[ClienteResponse])
def buscar_clientes(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    use_case = ClienteUseCase(SqlAlchemyClienteRepository(db))
    clientes = use_case.search(q)
    return [_entity_to_response(c) for c in clientes]


@router.get("/{cliente_id}", response_model=ClienteResponse)
def get_cliente(cliente_id: int, db: Session = Depends(get_db)):
    use_case = ClienteUseCase(SqlAlchemyClienteRepository(db))
    cliente = use_case.get_by_id(cliente_id)
    return _entity_to_response(cliente)