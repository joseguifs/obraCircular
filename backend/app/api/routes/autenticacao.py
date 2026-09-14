from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.usuario import Usuario
from app.schemas.autenticacao import LoginRequest, RefreshTokenRequest, TokenResponse
from app.schemas.usuario import UsuarioRead
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


@router.get("/me", response_model=UsuarioRead)
async def obter_usuario_atual(usuario_atual: CurrentUser) -> Usuario:
    return usuario_atual
