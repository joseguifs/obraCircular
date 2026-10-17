from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession
from app.repositories.administrador import AdministradorRepository
from app.schemas.autenticacao import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UsuarioAtualResponse,
)
from app.services.autenticacao import AutenticacaoService

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
