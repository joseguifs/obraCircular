from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.endereco import Endereco
from app.models.enums import UsuarioStatus
from app.repositories.endereco import EnderecoRepository
from app.schemas.endereco import (
    EnderecoCreate,
    EnderecoFilters,
    EnderecoListResponse,
    EnderecoUpdate,
)


class EnderecoService:
    """Regras de negócio dos endereços do usuário autenticado.

    Conforme `docs/domain/endereco.md`, alterar ou excluir um endereço não pode
    afetar o `endereco_entrega_snapshot` já gravado em pedidos. Por isso a
    exclusão é lógica (`deletado_em`): a linha permanece no banco, preservando
    as chaves estrangeiras de `anuncios` e `pedidos`, e nenhuma operação deste
    serviço escreve na tabela `pedidos`.
    """

    def __init__(
        self,
        session: AsyncSession,
        repository: EnderecoRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or EnderecoRepository(session)

    async def criar(self, dados: EnderecoCreate, usuario_id: UUID) -> Endereco:
        async with self.session.begin():
            await self._validar_usuario_ativo(usuario_id)

            endereco = Endereco(usuario_id=usuario_id, **dados.model_dump())
            return await self.repository.criar(endereco)

    async def listar(self, filtros: EnderecoFilters, usuario_id: UUID) -> EnderecoListResponse:
        enderecos, total = await self.repository.listar(usuario_id, filtros)
        return EnderecoListResponse(
            items=enderecos,
            total=total,
            offset=filtros.offset,
            limit=filtros.limit,
        )

    async def buscar(self, endereco_id: UUID, usuario_id: UUID) -> Endereco:
        endereco = await self.repository.buscar_por_id(endereco_id, usuario_id)
        if endereco is None:
            raise self._nao_encontrado()
        return endereco

    async def atualizar(
        self,
        endereco_id: UUID,
        dados: EnderecoUpdate,
        usuario_id: UUID,
    ) -> Endereco:
        async with self.session.begin():
            await self._validar_usuario_ativo(usuario_id)
            endereco = await self.repository.buscar_por_id(endereco_id, usuario_id, bloquear=True)
            if endereco is None:
                raise self._nao_encontrado()

            for campo, valor in dados.model_dump(exclude_unset=True).items():
                setattr(endereco, campo, valor)

            await self.session.flush()
            await self.session.refresh(endereco)
            return endereco

    async def excluir(self, endereco_id: UUID, usuario_id: UUID) -> None:
        async with self.session.begin():
            await self._validar_usuario_ativo(usuario_id)
            endereco = await self.repository.buscar_por_id(endereco_id, usuario_id, bloquear=True)
            if endereco is None:
                raise self._nao_encontrado()

            endereco.deletado_em = datetime.now(UTC)
            await self.session.flush()

    async def _validar_usuario_ativo(self, usuario_id: UUID) -> None:
        usuario = await self.repository.buscar_usuario(usuario_id)
        if usuario is None:
            raise AppError(
                status_code=404,
                detail="Usuário não encontrado.",
                code="USER_NOT_FOUND",
            )
        if usuario.status != UsuarioStatus.ATIVO:
            raise AppError(
                status_code=400,
                detail="O usuário precisa estar ativo.",
                code="USER_NOT_ACTIVE",
            )

    @staticmethod
    def _nao_encontrado() -> AppError:
        """404 também quando o endereço existe mas é de outro usuário."""
        return AppError(
            status_code=404,
            detail="Endereço não encontrado.",
            code="ADDRESS_NOT_FOUND",
        )
