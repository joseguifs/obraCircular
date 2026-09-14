from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.anuncio import AnuncioCreate, AnuncioFilters, AnuncioUpdate


def test_criacao_normaliza_texto_e_aceita_valores_validos() -> None:
    dados = AnuncioCreate(
        titulo="  Saco de cimento  ",
        descricao="  Material fechado e pronto para retirada.  ",
        categoria_id=uuid4(),
        endereco_id=uuid4(),
        preco=Decimal("35.90"),
        quantidade=10,
    )

    assert dados.titulo == "Saco de cimento"
    assert dados.descricao == "Material fechado e pronto para retirada."


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("preco", Decimal("-0.01")), ("quantidade", -1)],
)
def test_criacao_rejeita_preco_ou_quantidade_negativos(campo: str, valor: object) -> None:
    payload: dict[str, object] = {
        "titulo": "Saco de cimento",
        "descricao": "Material fechado e pronto para retirada.",
        "categoria_id": uuid4(),
        "endereco_id": uuid4(),
        "preco": Decimal("35.90"),
        "quantidade": 10,
    }
    payload[campo] = valor

    with pytest.raises(ValidationError):
        AnuncioCreate.model_validate(payload)


def test_atualizacao_exige_ao_menos_um_campo() -> None:
    with pytest.raises(ValidationError, match="ao menos um campo"):
        AnuncioUpdate()


def test_atualizacao_permite_remover_imagem() -> None:
    dados = AnuncioUpdate(imagem_url=None)

    assert dados.model_fields_set == {"imagem_url"}


def test_filtros_rejeitam_faixa_de_preco_invertida() -> None:
    with pytest.raises(ValidationError, match="min_price"):
        AnuncioFilters(min_price=Decimal("100.00"), max_price=Decimal("50.00"))
