from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.categoria import Categoria
from app.models.enums import CategoriaStatus
from app.repositories.categoria import CategoriaRepository
from app.schemas.categoria import (
    CategoriaCreate,
    CategoriaFilters,
    CategoriaListResponse,
    CategoriaUpdate,
)


class CategoriaService:
    """Regras de negócio de categorias.

    Conforme `docs/domain/categoria.md`: o nome é único, apenas categorias
    `ATIVA` podem ser usadas em novos anúncios (validado em
    `AnuncioService`), inativar não afeta anúncios existentes e a
    reativação volta a permitir novos anúncios. Por isso a exclusão aqui é
    sempre lógica (`status = INATIVA`), nunca uma remoção de linha.
    """

    def __init__(
        self,
        session: AsyncSession,
        repository: CategoriaRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or CategoriaRepository(session)

    async def criar(self, dados: CategoriaCreate) -> Categoria:
        async with self.session.begin():
            await self._validar_nome_disponivel(dados.nome)

            categoria = Categoria(nome=dados.nome, descricao=dados.descricao)
            return await self.repository.criar(categoria)

    async def listar(self, filtros: CategoriaFilters) -> CategoriaListResponse:
        categorias, total = await self.repository.listar(filtros)
        return CategoriaListResponse(
            items=categorias,
            total=total,
            offset=filtros.offset,
            limit=filtros.limit,
        )

    async def buscar(self, categoria_id: UUID) -> Categoria:
        categoria = await self.repository.buscar_por_id(categoria_id)
        if categoria is None:
            raise self._nao_encontrada()
        return categoria

    async def atualizar(self, categoria_id: UUID, dados: CategoriaUpdate) -> Categoria:
        async with self.session.begin():
            categoria = await self.repository.buscar_por_id(categoria_id, bloquear=True)
            if categoria is None:
                raise self._nao_encontrada()

            if dados.nome is not None and dados.nome != categoria.nome:
                await self._validar_nome_disponivel(dados.nome, excluir_id=categoria.id)

            for campo, valor in dados.model_dump(exclude_unset=True).items():
                setattr(categoria, campo, valor)

            await self.session.flush()
            await self.session.refresh(categoria)
            return categoria

    async def excluir(self, categoria_id: UUID) -> None:
        """Exclusão lógica: a categoria passa para `INATIVA`.

        Não remove a linha nem toca em anúncios já vinculados a ela, para
        não excluir/modificar anúncios existentes (regra de domínio).
        """
        async with self.session.begin():
            categoria = await self.repository.buscar_por_id(categoria_id, bloquear=True)
            if categoria is None:
                raise self._nao_encontrada()

            categoria.status = CategoriaStatus.INATIVA
            await self.session.flush()

    async def _validar_nome_disponivel(
        self,
        nome: str,
        *,
        excluir_id: UUID | None = None,
    ) -> None:
        existente = await self.repository.buscar_por_nome(nome, excluir_id=excluir_id)
        if existente is not None:
            raise AppError(
                status_code=409,
                detail="Já existe uma categoria cadastrada com este nome.",
                code="CATEGORY_NAME_TAKEN",
            )

    @staticmethod
    def _nao_encontrada() -> AppError:
        return AppError(
            status_code=404,
            detail="Categoria não encontrada.",
            code="CATEGORY_NOT_FOUND",
        )
