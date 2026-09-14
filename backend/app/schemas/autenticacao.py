from pydantic import BaseModel, EmailStr, Field, field_validator


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
