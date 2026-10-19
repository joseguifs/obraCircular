from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from html import escape
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.security import (
    gerar_token_recuperacao_senha,
    hash_senha,
    hash_token_recuperacao_senha,
)
from app.models.enums import UsuarioStatus
from app.models.token_recuperacao_senha import TokenRecuperacaoSenha
from app.models.usuario import Usuario
from app.repositories.token_recuperacao_senha import TokenRecuperacaoSenhaRepository
from app.repositories.usuario import UsuarioRepository
from app.services.email import montar_mensagem

_CAMINHO_REDEFINICAO = "/redefinir-senha"


class RecuperacaoSenhaService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._usuarios = UsuarioRepository(session)
        self._tokens = TokenRecuperacaoSenhaRepository(session)
        self._settings = settings or get_settings()

    async def solicitar(self, email: str) -> EmailMessage | None:
        """Gera um link de redefinição e devolve o e-mail a ser enviado.

        Retorna `None` quando não há usuário ativo com o e-mail. A rota responde da
        mesma forma nos dois casos para não revelar quais e-mails estão cadastrados.
        """
        usuario = await self._usuarios.obter_por_email(email)
        if (
            usuario is None
            or usuario.deletado_em is not None
            or usuario.status != UsuarioStatus.ATIVO
        ):
            return None

        agora = datetime.now(UTC)
        # Só o link mais recente vale: pedidos anteriores deixam de funcionar.
        await self._tokens.invalidar_pendentes(usuario.id, agora)
        token, token_hash = gerar_token_recuperacao_senha()
        self._tokens.adicionar(
            TokenRecuperacaoSenha(
                usuario_id=usuario.id,
                token_hash=token_hash,
                expira_em=agora
                + timedelta(minutes=self._settings.password_reset_token_expire_minutes),
            )
        )
        await self._session.commit()
        return self._montar_email(usuario, token)

    async def validar(self, token: str) -> None:
        await self._obter_usuario_do_token(token)

    async def redefinir(self, token: str, nova_senha: str) -> None:
        usuario = await self._obter_usuario_do_token(token, bloquear=True)
        usuario.senha_hash = hash_senha(nova_senha)
        # Consome o token usado e qualquer outro link pendente do mesmo usuário.
        await self._tokens.invalidar_pendentes(usuario.id, datetime.now(UTC))
        await self._session.commit()

    async def _obter_usuario_do_token(self, token: str, *, bloquear: bool = False) -> Usuario:
        registro = await self._tokens.obter_por_hash(
            hash_token_recuperacao_senha(token), bloquear=bloquear
        )
        if (
            registro is None
            or registro.usado_em is not None
            or registro.expira_em <= datetime.now(UTC)
        ):
            raise _token_invalido()

        usuario = await self._usuarios.obter_por_id(registro.usuario_id)
        if usuario is None or usuario.status != UsuarioStatus.ATIVO:
            raise _token_invalido()
        return usuario

    def _montar_email(self, usuario: Usuario, token: str) -> EmailMessage:
        link = (
            f"{self._settings.frontend_url.rstrip('/')}{_CAMINHO_REDEFINICAO}"
            f"?{urlencode({'token': token})}"
        )
        minutos = self._settings.password_reset_token_expire_minutes
        primeiro_nome = usuario.nome.split()[0] if usuario.nome.strip() else usuario.nome

        texto = (
            f"Olá, {primeiro_nome}!\n\n"
            "Recebemos um pedido para redefinir a senha da sua conta na Obra Circular.\n"
            "Para criar uma nova senha, acesse o link abaixo:\n\n"
            f"{link}\n\n"
            f"O link é válido por {minutos} minutos e só pode ser usado uma vez.\n"
            "Se você não fez este pedido, ignore este e-mail: sua senha continua a mesma.\n\n"
            "Equipe Obra Circular"
        )
        html = _HTML_RECUPERACAO.format(
            nome=escape(primeiro_nome),
            link=escape(link, quote=True),
            minutos=minutos,
        )
        return montar_mensagem(
            self._settings,
            destinatario=usuario.email,
            assunto="Redefinição de senha | Obra Circular",
            texto=texto,
            html=html,
        )


def _token_invalido() -> AppError:
    return AppError(
        status_code=400,
        detail="Este link de redefinição é inválido ou expirou. Solicite um novo link.",
        code="PASSWORD_RESET_TOKEN_INVALID",
    )


# Estilos inline: a maioria dos clientes de e-mail ignora <style> e CSS externo.
_HTML_RECUPERACAO = """\
<!doctype html>
<html lang="pt-BR">
  <body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#f5f7fb;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="max-width:520px;background:#ffffff;border:1px solid #e3e8f0;
                        border-radius:16px;padding:36px 32px;color:#0c1e36;">
            <tr>
              <td style="font-size:20px;font-weight:bold;padding-bottom:24px;">
                Obra <span style="color:#2f7fd4;">Circular</span>
              </td>
            </tr>
            <tr>
              <td style="font-size:22px;font-weight:bold;padding-bottom:12px;">
                Redefina sua senha
              </td>
            </tr>
            <tr>
              <td style="font-size:15px;line-height:1.6;color:#4a5b72;padding-bottom:28px;">
                Olá, {nome}! Recebemos um pedido para redefinir a senha da sua conta.
                Clique no botão abaixo para criar uma nova senha.
              </td>
            </tr>
            <tr>
              <td align="center" style="padding-bottom:28px;">
                <a href="{link}"
                   style="display:inline-block;background:#0c1e36;color:#ffffff;
                          text-decoration:none;font-weight:bold;font-size:15px;
                          padding:15px 28px;border-radius:12px;">
                  Redefinir minha senha
                </a>
              </td>
            </tr>
            <tr>
              <td style="font-size:13px;line-height:1.6;color:#6b7a90;padding-bottom:16px;">
                O link é válido por {minutos} minutos e só pode ser usado uma vez. Se o botão
                não funcionar, copie e cole este endereço no navegador:<br>
                <a href="{link}" style="color:#1b5fa8;word-break:break-all;">{link}</a>
              </td>
            </tr>
            <tr>
              <td style="font-size:13px;line-height:1.6;color:#6b7a90;
                         border-top:1px solid #edf1f6;padding-top:16px;">
                Se você não pediu a redefinição, ignore este e-mail: sua senha continua a mesma.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
