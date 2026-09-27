from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_senha
from app.models.enums import UsuarioStatus
from app.models.usuario import Usuario
from app.repositories.usuario import UsuarioRepository
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate


class UsuarioService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repositorio = UsuarioRepository(session)

    async def criar(self, dados: UsuarioCreate) -> Usuario:
        if await self._repositorio.obter_por_email(dados.email) is not None:
            raise ConflictError("Já existe um usuário cadastrado com este e-mail.")

        usuario = Usuario(
            nome=dados.nome,
            email=dados.email,
            senha_hash=hash_senha(dados.senha),
            telefone=dados.telefone,
            status=UsuarioStatus.ATIVO,
        )
        self._repositorio.adicionar(usuario)
        await self._salvar(usuario)
        return usuario

    async def listar(
        self, *, status_filtro: UsuarioStatus | None, limit: int, offset: int
    ) -> tuple[list[Usuario], int]:
        return await self._repositorio.listar(
            status_filtro=status_filtro, limit=limit, offset=offset
        )

    async def obter(self, usuario_id: UUID) -> Usuario:
        usuario = await self._repositorio.obter_por_id(usuario_id)
        if usuario is None:
            raise NotFoundError("Usuário não encontrado.")
        return usuario

    async def atualizar(self, usuario_id: UUID, dados: UsuarioUpdate) -> Usuario:
        usuario = await self.obter(usuario_id)
        alteracoes = dados.model_dump(exclude_unset=True)

        if "email" in alteracoes:
            novo_email = alteracoes.pop("email")
            conflito = await self._repositorio.obter_por_email(novo_email, excluir_id=usuario.id)
            if conflito is not None:
                raise ConflictError("Já existe um usuário cadastrado com este e-mail.")
            usuario.email = novo_email

        if "senha" in alteracoes:
            usuario.senha_hash = hash_senha(alteracoes.pop("senha"))

        for campo, valor in alteracoes.items():
            setattr(usuario, campo, valor)

        await self._salvar(usuario)
        return usuario

    async def excluir(self, usuario_id: UUID) -> None:
        usuario = await self.obter(usuario_id)
        usuario.deletado_em = datetime.now(UTC)
        await self._session.commit()

    async def _salvar(self, usuario: Usuario) -> None:
        try:
            await self._session.commit()
        except IntegrityError as erro:
            await self._session.rollback()
            # O índice também protege contra dois pedidos simultâneos com o mesmo e-mail.
            causa = erro.orig.__cause__ if erro.orig is not None else None
            if getattr(causa, "constraint_name", None) == "uq_usuarios_email_normalizado":
                raise ConflictError("Já existe um usuário cadastrado com este e-mail.") from erro
            raise
        await self._session.refresh(usuario)
