import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import RepasseStatus


class DestinoRepasseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tipo_chave: Literal["CPF", "CNPJ", "EMAIL", "PHONE", "PIX_CODE", "CONTA_MP_TESTE"]
    chave: str = Field(min_length=3, max_length=255)
    titularidade_conferida: Literal[True]

    @field_validator("chave")
    @classmethod
    def validar_chave(cls, valor: str) -> str:
        if any(c.isspace() for c in valor):
            raise ValueError("O destino não deve conter espaços.")
        return valor

    @model_validator(mode="after")
    def validar_formato_por_tipo(self) -> "DestinoRepasseCreate":
        if self.tipo_chave in {"CPF", "CNPJ"}:
            normalizada = re.sub(r"[.\-/]", "", self.chave)
            tamanho = 11 if self.tipo_chave == "CPF" else 14
            if not normalizada.isdigit() or len(normalizada) != tamanho:
                raise ValueError("Documento da chave Pix inválido.")
            self.chave = normalizada
        elif self.tipo_chave in {"EMAIL", "CONTA_MP_TESTE"}:
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.chave):
                raise ValueError("E-mail do destino inválido.")
            if self.tipo_chave == "CONTA_MP_TESTE":
                self.chave = self.chave.lower()
                if not self.chave.endswith("@testuser.com"):
                    raise ValueError("Use o e-mail de uma conta de teste @testuser.com.")
        elif self.tipo_chave == "PHONE":
            if not re.fullmatch(r"\+[1-9][0-9]{9,14}", self.chave):
                raise ValueError("Use telefone Pix com + e código do país.")
        else:
            self.chave = str(UUID(self.chave))
        return self


class DestinoRepasseResponse(BaseModel):
    vendedor_id: UUID
    tipo_chave: str
    validado_em: datetime
    ativo: bool


class RepasseResponse(BaseModel):
    id: UUID
    pedido_id: UUID
    vendedor_id: UUID
    vendedor_nome: str
    modelo_financeiro: str
    valor_bruto: Decimal
    percentual_marketplace: Decimal
    taxa_marketplace: Decimal
    taxa_provedor: Decimal
    valor_liquido: Decimal
    taxas_por_conta_marketplace: bool
    status: RepasseStatus
    liberacao_prevista_em: datetime | None
    pago_em: datetime | None
    destino_cadastrado: bool
    pode_liberar: bool
    pode_consultar: bool = False
    destino_tipo: str | None = None
    motivo_bloqueio: str | None


class RepasseListResponse(BaseModel):
    items: list[RepasseResponse]
    total: int
    offset: int
    limit: int


class EventoRepasseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operador_id: UUID | None
    acao: str
    status: str
    criado_em: datetime
