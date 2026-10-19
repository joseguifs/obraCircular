from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.enums import AnuncioStatus, UsuarioStatus
from app.models.usuario import Usuario
from app.repositories.administrador import AdministradorRepository
from app.repositories.anuncio_imagem import AnuncioImagemRepository
from app.schemas.admin import (
    AdminAnuncioFilters,
    AdminAnuncioListResponse,
    AdminAnuncioResponse,
    AdminResumoResponse,
    AdminUsuarioFilters,
    AdminUsuarioListResponse,
    AdminUsuarioResponse,
    ContagemPorStatus,
)
from app.services.armazenamento import ArmazenamentoLocal


class AdminService:
    """Operações do painel administrativo, conforme `docs/domain/administrador.md`.

    O administrador nunca altera o próprio status nem remove o próprio perfil, e a
    moderação de anúncios segue as mesmas regras de encerramento e exclusão lógica
    do vendedor (`docs/domain/anuncio.md`).
    """

    def __init__(
        self,
        session: AsyncSession,
        repository: AdministradorRepository | None = None,
        imagem_repository: AnuncioImagemRepository | None = None,
        armazenamento: ArmazenamentoLocal | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or AdministradorRepository(session)
        self.imagem_repository = imagem_repository or AnuncioImagemRepository(session)
        self.armazenamento = armazenamento or ArmazenamentoLocal(get_settings().storage_path)

    async def resumo(self) -> AdminResumoResponse:
        usuarios = await self.repository.contar_por_status(
            Usuario.status, Usuario.deletado_em.is_(None)
        )
        anuncios = await self.repository.contar_por_status(
            Anuncio.status, Anuncio.deletado_em.is_(None)
        )
        categorias = await self.repository.contar_por_status(Categoria.status)
        return AdminResumoResponse(
            usuarios=_contagem(usuarios),
            anuncios=_contagem(anuncios),
            categorias=_contagem(categorias),
            administradores=await self.repository.contar_administradores(),
        )

    async def listar_usuarios(self, filtros: AdminUsuarioFilters) -> AdminUsuarioListResponse:
        usuarios, total = await self.repository.listar_usuarios(filtros)
        administradores = await self.repository.filtrar_administradores(
            [usuario.id for usuario in usuarios]
        )
        return AdminUsuarioListResponse(
            items=[
                AdminUsuarioResponse.model_validate(usuario).model_copy(
                    update={"administrador": usuario.id in administradores}
                )
                for usuario in usuarios
            ],
            total=total,
            offset=filtros.offset,
            limit=filtros.limit,
        )

    async def alterar_status_usuario(
        self,
        usuario_id: UUID,
        status: UsuarioStatus,
        administrador_id: UUID,
    ) -> AdminUsuarioResponse:
        if usuario_id == administrador_id:
            raise AppError(
                status_code=400,
                detail="Você não pode alterar o próprio status.",
                code="ADMIN_SELF_STATUS",
            )
        async with self.session.begin():
            usuario = await self._buscar_usuario(usuario_id)
            usuario.status = status
            await self.session.flush()
            await self.session.refresh(usuario)
            return await self._usuario_response(usuario)

    async def conceder_administrador(
        self,
        usuario_id: UUID,
        administrador_id: UUID,
    ) -> AdminUsuarioResponse:
        async with self.session.begin():
            usuario = await self._buscar_usuario(usuario_id)
            if usuario.status != UsuarioStatus.ATIVO:
                raise AppError(
                    status_code=400,
                    detail="Apenas usuários ativos podem ser administradores.",
                    code="USER_NOT_ACTIVE",
                )
            # Idempotente: conceder novamente a quem já é administrador não falha.
            if not await self.repository.eh_administrador(usuario.id):
                await self.repository.adicionar(usuario.id, administrador_id)
            return await self._usuario_response(usuario)

    async def revogar_administrador(
        self,
        usuario_id: UUID,
        administrador_id: UUID,
    ) -> AdminUsuarioResponse:
        if usuario_id == administrador_id:
            raise AppError(
                status_code=400,
                detail="Você não pode remover o próprio perfil de administrador.",
                code="ADMIN_SELF_REVOKE",
            )
        async with self.session.begin():
            usuario = await self._buscar_usuario(usuario_id)
            await self.repository.remover(usuario.id)
            return await self._usuario_response(usuario)

    async def listar_anuncios(self, filtros: AdminAnuncioFilters) -> AdminAnuncioListResponse:
        linhas, total = await self.repository.listar_anuncios(filtros)
        capas = await self.imagem_repository.listar_capas([anuncio.id for anuncio, _, _ in linhas])
        return AdminAnuncioListResponse(
            items=[
                self._anuncio_response(anuncio, vendedor, categoria, capas.get(anuncio.id))
                for anuncio, vendedor, categoria in linhas
            ],
            total=total,
            offset=filtros.offset,
            limit=filtros.limit,
        )

    async def encerrar_anuncio(self, anuncio_id: UUID) -> None:
        async with self.session.begin():
            anuncio = await self._buscar_anuncio(anuncio_id)
            if anuncio.status != AnuncioStatus.ENCERRADO:
                anuncio.status = AnuncioStatus.ENCERRADO
                anuncio.encerrado_em = datetime.now(UTC)
                await self.session.flush()

    async def excluir_anuncio(self, anuncio_id: UUID) -> None:
        async with self.session.begin():
            anuncio = await self._buscar_anuncio(anuncio_id)
            agora = datetime.now(UTC)
            anuncio.deletado_em = agora
            anuncio.status = AnuncioStatus.ENCERRADO
            anuncio.encerrado_em = anuncio.encerrado_em or agora
            await self.session.flush()

    async def _buscar_usuario(self, usuario_id: UUID) -> Usuario:
        usuario = await self.repository.buscar_usuario(usuario_id, bloquear=True)
        if usuario is None:
            raise AppError(
                status_code=404,
                detail="Usuário não encontrado.",
                code="USER_NOT_FOUND",
            )
        return usuario

    async def _buscar_anuncio(self, anuncio_id: UUID) -> Anuncio:
        anuncio = await self.repository.buscar_anuncio(anuncio_id, bloquear=True)
        if anuncio is None:
            raise AppError(
                status_code=404,
                detail="Anúncio não encontrado.",
                code="AD_NOT_FOUND",
            )
        return anuncio

    async def _usuario_response(self, usuario: Usuario) -> AdminUsuarioResponse:
        return AdminUsuarioResponse.model_validate(usuario).model_copy(
            update={"administrador": await self.repository.eh_administrador(usuario.id)}
        )

    def _anuncio_response(
        self,
        anuncio: Anuncio,
        vendedor: Usuario,
        categoria: Categoria,
        chave_capa: str | None,
    ) -> AdminAnuncioResponse:
        return AdminAnuncioResponse(
            id=anuncio.id,
            titulo=anuncio.titulo,
            preco=anuncio.preco,
            quantidade=anuncio.quantidade,
            status=anuncio.status,
            categoria_id=categoria.id,
            categoria_nome=categoria.nome,
            vendedor_id=vendedor.id,
            vendedor_nome=vendedor.nome,
            vendedor_email=vendedor.email,
            imagem_capa_url=(
                self.armazenamento.url_publica(chave_capa)
                if chave_capa is not None
                else anuncio.imagem_url
            ),
            postado_em=anuncio.postado_em,
            atualizado_em=anuncio.atualizado_em,
            encerrado_em=anuncio.encerrado_em,
            deletado_em=anuncio.deletado_em,
        )


def _contagem(por_status: dict[str, int]) -> ContagemPorStatus:
    return ContagemPorStatus(total=sum(por_status.values()), por_status=por_status)
