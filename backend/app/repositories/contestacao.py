from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.anuncio import Anuncio
from app.models.contestacao import Contestacao
from app.models.pedido import Pedido
from app.models.reembolso import Reembolso
from app.models.usuario import Usuario
from app.schemas.admin import AdminContestacaoFilters, AdminContestacaoResponse


class ContestacaoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def consulta_admin(self) -> Select[Any]:
        comprador = aliased(Usuario)
        vendedor = aliased(Usuario)
        return (
            select(
                Contestacao.id,
                Contestacao.pedido_id,
                Contestacao.motivo,
                Contestacao.descricao,
                Contestacao.status,
                Contestacao.criado_em,
                Contestacao.resolucao,
                Contestacao.resolvida_por,
                Contestacao.resolvida_em,
                Anuncio.titulo.label("anuncio_titulo"),
                comprador.nome.label("comprador_nome"),
                vendedor.nome.label("vendedor_nome"),
                Reembolso.status.label("reembolso_status"),
                Reembolso.reembolso_externo_id,
            )
            .join(Pedido, Pedido.id == Contestacao.pedido_id)
            .join(Anuncio, Anuncio.id == Pedido.anuncio_id)
            .join(comprador, comprador.id == Contestacao.comprador_id)
            .join(vendedor, vendedor.id == Anuncio.vendedor_id)
            .outerjoin(Reembolso, Reembolso.contestacao_id == Contestacao.id)
        )

    async def listar(
        self, filtros: AdminContestacaoFilters
    ) -> tuple[list[AdminContestacaoResponse], int]:
        condicoes = []
        if filtros.status is not None:
            condicoes.append(Contestacao.status == filtros.status)
        total = await self.session.scalar(
            select(func.count()).select_from(Contestacao).where(*condicoes)
        )
        resultado = await self.session.execute(
            self.consulta_admin()
            .where(*condicoes)
            .order_by(Contestacao.criado_em.desc(), Contestacao.id.desc())
            .offset(filtros.offset)
            .limit(filtros.limit)
        )
        return [
            AdminContestacaoResponse.model_validate(linha) for linha in resultado.mappings()
        ], int(total or 0)

    async def buscar_resposta(self, contestacao_id: UUID) -> AdminContestacaoResponse:
        resultado = await self.session.execute(
            self.consulta_admin().where(Contestacao.id == contestacao_id)
        )
        return AdminContestacaoResponse.model_validate(resultado.mappings().one())
