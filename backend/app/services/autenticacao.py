from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError
from app.core.security import (
    ParTokens,
    TipoToken,
    criar_par_tokens,
    hash_senha,
    obter_usuario_id_do_token,
    senha_precisa_atualizacao,
    verificar_senha_sem_revelar_usuario,
)
from app.models.enums import UsuarioStatus
from app.models.usuario import Usuario
from app.repositories.usuario import UsuarioRepository

_CREDENCIAIS_INVALIDAS = "E-mail ou senha inválidos."
_TOKEN_INVALIDO = "Token inválido ou expirado."


class AutenticacaoService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._repositorio = UsuarioRepository(session)
        self._settings = settings or get_settings()

    async def autenticar(self, email: str, senha: str) -> ParTokens:
        usuario = await self._repositorio.obter_por_email(email)
        senha_valida = verificar_senha_sem_revelar_usuario(
            senha,
            usuario.senha_hash if usuario is not None else None,
        )
        if (
            usuario is None
            or usuario.deletado_em is not None
            or usuario.status != UsuarioStatus.ATIVO
            or not senha_valida
        ):
            raise AuthenticationError(_CREDENCIAIS_INVALIDAS)

        usuario_id = usuario.id
        if senha_precisa_atualizacao(usuario.senha_hash):
            usuario.senha_hash = hash_senha(senha)
            await self._session.commit()

        return criar_par_tokens(usuario_id, self._settings)

    async def renovar(self, refresh_token: str) -> ParTokens:
        usuario = await self.obter_usuario_por_token(refresh_token, tipo="refresh")
        return criar_par_tokens(usuario.id, self._settings)

    async def obter_usuario_por_token(self, token: str, *, tipo: TipoToken) -> Usuario:
        usuario_id = obter_usuario_id_do_token(
            token,
            tipo_esperado=tipo,
            settings=self._settings,
        )
        if usuario_id is None:
            raise AuthenticationError(_TOKEN_INVALIDO)

        usuario = await self._repositorio.obter_por_id(usuario_id)
        if usuario is None or usuario.status != UsuarioStatus.ATIVO:
            raise AuthenticationError(_TOKEN_INVALIDO)
        return usuario
