from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.anuncio import Anuncio
from app.models.enums import AnuncioStatus, CategoriaStatus, UsuarioStatus
from app.repositories.anuncio import AnuncioRepository
from app.schemas.anuncio import AnuncioCreate, AnuncioFilters, AnuncioListResponse, AnuncioUpdate


class AnuncioService:
    def __init__(
        self,
        session: AsyncSession,
        repository: AnuncioRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or AnuncioRepository(session)

    async def criar(self, dados: AnuncioCreate, vendedor_id: UUID) -> Anuncio:
        async with self.session.begin():
            await self._validar_vendedor(vendedor_id)
            await self._validar_categoria(dados.categoria_id)
            await self._validar_endereco(dados.endereco_id, vendedor_id)

            anuncio = Anuncio(
                titulo=dados.titulo,
                descricao=dados.descricao,
                categoria_id=dados.categoria_id,
                vendedor_id=vendedor_id,
                endereco_id=dados.endereco_id,
                preco=dados.preco,
                imagem_url=str(dados.imagem_url) if dados.imagem_url is not None else None,
                quantidade=dados.quantidade,
                status=(AnuncioStatus.ESGOTADO if dados.quantidade == 0 else AnuncioStatus.ATIVO),
            )
            return await self.repository.criar(anuncio)

    async def buscar(self, anuncio_id: UUID) -> Anuncio:
        anuncio = await self.repository.buscar_por_id(anuncio_id)
        if anuncio is None:
            raise AppError(
                status_code=404,
                detail="Anúncio não encontrado.",
                code="AD_NOT_FOUND",
            )
        return anuncio

    async def listar(
        self,
        filtros: AnuncioFilters,
        *,
        vendedor_id: UUID | None = None,
    ) -> AnuncioListResponse:
        anuncios, total = await self.repository.listar(filtros, vendedor_id=vendedor_id)
        return AnuncioListResponse(
            items=anuncios,
            total=total,
            offset=filtros.offset,
            limit=filtros.limit,
        )

    async def atualizar(
        self,
        anuncio_id: UUID,
        dados: AnuncioUpdate,
        vendedor_id: UUID,
    ) -> Anuncio:
        async with self.session.begin():
            anuncio = await self._buscar_para_alteracao(anuncio_id, vendedor_id)

            if anuncio.status == AnuncioStatus.ENCERRADO:
                raise AppError(
                    status_code=400,
                    detail="Anúncios encerrados não podem ser alterados.",
                    code="AD_CLOSED",
                )

            if dados.categoria_id is not None:
                await self._validar_categoria(dados.categoria_id)
            if dados.endereco_id is not None:
                await self._validar_endereco(dados.endereco_id, vendedor_id)

            alteracoes = dados.model_dump(exclude_unset=True, exclude={"status", "imagem_url"})
            for campo, valor in alteracoes.items():
                setattr(anuncio, campo, valor)

            if "imagem_url" in dados.model_fields_set:
                anuncio.imagem_url = str(dados.imagem_url) if dados.imagem_url is not None else None

            quantidade_final = (
                dados.quantidade if dados.quantidade is not None else anuncio.quantidade
            )
            anuncio.status = self._definir_status(
                status_atual=anuncio.status,
                status_solicitado=dados.status,
                quantidade=quantidade_final,
            )

            if anuncio.status == AnuncioStatus.ENCERRADO:
                anuncio.encerrado_em = datetime.now(UTC)

            await self.session.flush()
            await self.session.refresh(anuncio)
            return anuncio

    async def excluir(self, anuncio_id: UUID, vendedor_id: UUID) -> None:
        async with self.session.begin():
            anuncio = await self._buscar_para_alteracao(anuncio_id, vendedor_id)
            agora = datetime.now(UTC)
            anuncio.deletado_em = agora
            anuncio.status = AnuncioStatus.ENCERRADO
            anuncio.encerrado_em = anuncio.encerrado_em or agora
            await self.session.flush()

    async def _buscar_para_alteracao(self, anuncio_id: UUID, vendedor_id: UUID) -> Anuncio:
        anuncio = await self.repository.buscar_por_id(anuncio_id, bloquear=True)
        if anuncio is None:
            raise AppError(
                status_code=404,
                detail="Anúncio não encontrado.",
                code="AD_NOT_FOUND",
            )
        if anuncio.vendedor_id != vendedor_id:
            raise AppError(
                status_code=403,
                detail="Somente o vendedor pode alterar este anúncio.",
                code="AD_FORBIDDEN",
            )
        await self._validar_vendedor(vendedor_id)
        return anuncio

    async def _validar_vendedor(self, vendedor_id: UUID) -> None:
        vendedor = await self.repository.buscar_usuario(vendedor_id)
        if vendedor is None:
            raise AppError(
                status_code=404,
                detail="Vendedor não encontrado.",
                code="SELLER_NOT_FOUND",
            )
        if vendedor.status != UsuarioStatus.ATIVO:
            raise AppError(
                status_code=400,
                detail="O vendedor precisa estar ativo.",
                code="SELLER_NOT_ACTIVE",
            )

    async def _validar_categoria(self, categoria_id: UUID) -> None:
        categoria = await self.repository.buscar_categoria(categoria_id)
        if categoria is None:
            raise AppError(
                status_code=404,
                detail="Categoria não encontrada.",
                code="CATEGORY_NOT_FOUND",
            )
        if categoria.status != CategoriaStatus.ATIVA:
            raise AppError(
                status_code=400,
                detail="A categoria precisa estar ativa.",
                code="CATEGORY_NOT_ACTIVE",
            )

    async def _validar_endereco(self, endereco_id: UUID, vendedor_id: UUID) -> None:
        endereco = await self.repository.buscar_endereco(endereco_id)
        if endereco is None:
            raise AppError(
                status_code=404,
                detail="Endereço não encontrado.",
                code="ADDRESS_NOT_FOUND",
            )
        if endereco.usuario_id != vendedor_id:
            raise AppError(
                status_code=403,
                detail="O endereço precisa pertencer ao vendedor.",
                code="ADDRESS_NOT_OWNED",
            )

    @staticmethod
    def _definir_status(
        *,
        status_atual: AnuncioStatus,
        status_solicitado: AnuncioStatus | None,
        quantidade: int,
    ) -> AnuncioStatus:
        status_estoque = AnuncioStatus.ESGOTADO if quantidade == 0 else AnuncioStatus.ATIVO

        if status_solicitado is None:
            return status_estoque
        if status_solicitado == AnuncioStatus.ENCERRADO:
            return AnuncioStatus.ENCERRADO
        if status_solicitado != status_estoque:
            raise AppError(
                status_code=400,
                detail="O status informado não corresponde à quantidade do anúncio.",
                code="AD_STATUS_INVALID",
            )
        if status_atual == AnuncioStatus.ENCERRADO:
            raise AppError(
                status_code=400,
                detail="Anúncios encerrados não podem ser reativados.",
                code="AD_CLOSED",
            )
        return status_solicitado
