from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentAdmin, DatabaseSession
from app.models.enums import RepasseStatus
from app.models.operacao_repasse import EventoRepasse
from app.schemas.repasse import (
    DestinoRepasseCreate,
    DestinoRepasseResponse,
    EventoRepasseResponse,
    RepasseListResponse,
    RepasseResponse,
)
from app.services.repasse import RepasseService

router = APIRouter(prefix="/admin", tags=["repasses"])


@router.get("/payouts", response_model=RepasseListResponse)
async def listar_repasses(
    session: DatabaseSession,
    _admin: CurrentAdmin,
    status: RepasseStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RepasseListResponse:
    return await RepasseService(session).listar(status=status, offset=offset, limit=limit)


@router.put("/users/{vendedor_id}/payout-destination", response_model=DestinoRepasseResponse)
async def cadastrar_destino(
    vendedor_id: UUID,
    dados: DestinoRepasseCreate,
    session: DatabaseSession,
    admin: CurrentAdmin,
) -> DestinoRepasseResponse:
    return await RepasseService(session).cadastrar_destino(vendedor_id, dados, admin.id)


@router.post("/payouts/{repasse_id}/release", response_model=RepasseResponse)
async def liberar_repasse(
    repasse_id: UUID,
    session: DatabaseSession,
    admin: CurrentAdmin,
) -> RepasseResponse:
    return await RepasseService(session).liberar(repasse_id, admin.id)


@router.post("/payouts/{repasse_id}/reconcile", response_model=RepasseResponse)
async def conciliar_repasse(
    repasse_id: UUID,
    session: DatabaseSession,
    admin: CurrentAdmin,
) -> RepasseResponse:
    return await RepasseService(session).conciliar(repasse_id, admin.id)


@router.get("/payouts/{repasse_id}/events", response_model=list[EventoRepasseResponse])
async def listar_eventos(
    repasse_id: UUID,
    session: DatabaseSession,
    _admin: CurrentAdmin,
) -> list[EventoRepasseResponse]:
    eventos = await session.scalars(
        select(EventoRepasse)
        .where(EventoRepasse.repasse_id == repasse_id)
        .order_by(EventoRepasse.criado_em, EventoRepasse.id)
    )
    return [EventoRepasseResponse.model_validate(evento) for evento in eventos]
