from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import ModalidadeEntrega
from app.schemas.pedido import CheckoutCreate
from app.services.pedido import PedidoService


def test_comissao_marketplace_e_25_por_cento_com_arredondamento() -> None:
    assert PedidoService.calcular_taxa_marketplace(Decimal("99.99"), Decimal("25.00")) == Decimal(
        "25.00"
    )


def test_auto_return_exige_url_https_publica() -> None:
    assert PedidoService._url_publica_https("https://obra-circular.example")
    assert not PedidoService._url_publica_https("http://localhost:8000")
    assert not PedidoService._url_publica_https("https://127.0.0.1:8000")


def test_entrega_exige_endereco() -> None:
    with pytest.raises(ValidationError):
        CheckoutCreate(
            anuncio_id=uuid4(),
            quantidade=1,
            modalidade_entrega=ModalidadeEntrega.ENTREGA,
            endereco_entrega_id=None,
        )


def test_retirada_recusa_endereco() -> None:
    with pytest.raises(ValidationError):
        CheckoutCreate(
            anuncio_id=uuid4(),
            quantidade=1,
            modalidade_entrega=ModalidadeEntrega.RETIRADA,
            endereco_entrega_id=uuid4(),
        )
