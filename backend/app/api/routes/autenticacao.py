from fastapi import APIRouter, BackgroundTasks, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.repositories.administrador import AdministradorRepository
from app.schemas.autenticacao import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UsuarioAtualResponse,
)
from app.api.dependencies import CurrentUser, DatabaseSession, EmailSender
from app.models.usuario import Usuario
from app.schemas.autenticacao import (
    EsqueciSenhaRequest,
    EsqueciSenhaResponse,
    LoginRequest,
    RedefinirSenhaRequest,
    RefreshTokenRequest,
    TokenResponse,
    ValidarTokenRecuperacaoRequest,
)
from app.schemas.usuario import UsuarioRead
from app.services.autenticacao import AutenticacaoService
from app.services.email import enviar_registrando_falhas
from app.services.recuperacao_senha import RecuperacaoSenhaService

router = APIRouter(prefix="/auth", tags=["autenticação"])


@router.post("/login", response_model=TokenResponse)
async def login(dados: LoginRequest, session: DatabaseSession) -> TokenResponse:
    tokens = await AutenticacaoService(session).autenticar(dados.email, dados.senha)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(dados: RefreshTokenRequest, session: DatabaseSession) -> TokenResponse:
    tokens = await AutenticacaoService(session).renovar(dados.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.get("/me", response_model=UsuarioAtualResponse)
async def obter_usuario_atual(
    usuario_atual: CurrentUser,
    session: DatabaseSession,
) -> UsuarioAtualResponse:
    administrador = await AdministradorRepository(session).eh_administrador(usuario_atual.id)
    return UsuarioAtualResponse.model_validate(usuario_atual).model_copy(
        update={"administrador": administrador}
    )
@router.get("/me", response_model=UsuarioRead)
async def obter_usuario_atual(usuario_atual: CurrentUser) -> Usuario:
    return usuario_atual


@router.post(
    "/forgot-password",
    response_model=EsqueciSenhaResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def solicitar_recuperacao_senha(
    dados: EsqueciSenhaRequest,
    session: DatabaseSession,
    enviador: EmailSender,
    tarefas: BackgroundTasks,
) -> EsqueciSenhaResponse:
    mensagem = await RecuperacaoSenhaService(session).solicitar(dados.email)
    if mensagem is not None:
        # O envio acontece depois da resposta: o tempo de resposta não depende do SMTP
        # e não revela se o e-mail está cadastrado.
        tarefas.add_task(enviar_registrando_falhas, enviador, mensagem)
    return EsqueciSenhaResponse(
        detail=(
            "Se o e-mail estiver cadastrado, você receberá um link para redefinir sua senha."
        )
    )


@router.post("/reset-password/validate", status_code=status.HTTP_204_NO_CONTENT)
async def validar_token_recuperacao(
    dados: ValidarTokenRecuperacaoRequest,
    session: DatabaseSession,
) -> None:
    await RecuperacaoSenhaService(session).validar(dados.token)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def redefinir_senha(dados: RedefinirSenhaRequest, session: DatabaseSession) -> None:
    await RecuperacaoSenhaService(session).redefinir(dados.token, dados.nova_senha)
