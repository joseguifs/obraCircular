from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.usuario import UsuarioRead


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: EmailStr) -> str:
        return str(valor).lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UsuarioAtualResponse(UsuarioRead):
    administrador: bool = False
class EsqueciSenhaRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: EmailStr) -> str:
        return str(valor).lower()


class EsqueciSenhaResponse(BaseModel):
    detail: str


class ValidarTokenRecuperacaoRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)


class RedefinirSenhaRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    nova_senha: str = Field(min_length=8, max_length=72)
