"""Envio de e-mails transacionais.

`SmtpEnviadorEmail` envia de fato pelo servidor configurado (ex.: Gmail). Quando o
SMTP não está configurado, `LogEnviadorEmail` apenas escreve o e-mail no log do
backend, o que permite testar os fluxos localmente sem credenciais.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EnviadorEmail(Protocol):
    def enviar(self, mensagem: EmailMessage) -> None: ...


class SmtpEnviadorEmail:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enviar(self, mensagem: EmailMessage) -> None:
        settings = self._settings
        host = settings.smtp_host or ""
        contexto = ssl.create_default_context()
        smtp: smtplib.SMTP
        if settings.smtp_security == "ssl":
            smtp = smtplib.SMTP_SSL(
                host, settings.smtp_port, timeout=settings.smtp_timeout_seconds, context=contexto
            )
        else:
            smtp = smtplib.SMTP(host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)

        with smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=contexto)
            if settings.smtp_username and settings.smtp_password is not None:
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            smtp.send_message(mensagem)


class LogEnviadorEmail:
    def enviar(self, mensagem: EmailMessage) -> None:
        corpo = mensagem.get_body(preferencelist=("plain",))
        texto = corpo.get_content() if corpo is not None else ""
        logger.warning(
            "SMTP não configurado; e-mail não enviado.\nPara: %s\nAssunto: %s\n\n%s",
            mensagem["To"],
            mensagem["Subject"],
            texto,
        )


def criar_enviador_email(settings: Settings) -> EnviadorEmail:
    if settings.smtp_host:
        return SmtpEnviadorEmail(settings)
    return LogEnviadorEmail()


def montar_mensagem(
    settings: Settings,
    *,
    destinatario: str,
    assunto: str,
    texto: str,
    html: str,
) -> EmailMessage:
    remetente = settings.smtp_from_email or settings.smtp_username or "nao-responda@localhost"
    mensagem = EmailMessage()
    mensagem["From"] = formataddr((settings.smtp_from_name, remetente))
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(texto)
    mensagem.add_alternative(html, subtype="html")
    return mensagem


def enviar_registrando_falhas(enviador: EnviadorEmail, mensagem: EmailMessage) -> None:
    """Usado em tarefas de segundo plano, onde uma exceção não chega ao cliente."""
    try:
        enviador.enviar(mensagem)
    except Exception:
        logger.exception("Falha ao enviar e-mail para %s.", mensagem["To"])
