import pytest
from pydantic import ValidationError

from app.schemas.endereco import EnderecoCreate, EnderecoUpdate

DADOS_VALIDOS = {
    "cep": "01001-000",
    "logradouro": "Praça da Sé",
    "numero": "100",
    "bairro": "Sé",
    "cidade": "São Paulo",
    "estado": "sp",
}


def test_cep_e_normalizado_para_oito_digitos() -> None:
    endereco = EnderecoCreate(**DADOS_VALIDOS)

    assert endereco.cep == "01001000"


def test_estado_e_convertido_para_maiusculas() -> None:
    endereco = EnderecoCreate(**DADOS_VALIDOS)

    assert endereco.estado == "SP"


@pytest.mark.parametrize("cep", ["1234567", "123456789", "abcdefgh", ""])
def test_cep_invalido_e_rejeitado(cep: str) -> None:
    with pytest.raises(ValidationError, match="CEP inválido"):
        EnderecoCreate(**{**DADOS_VALIDOS, "cep": cep})


@pytest.mark.parametrize("estado", ["XX", "S", "SPP"])
def test_estado_invalido_e_rejeitado(estado: str) -> None:
    with pytest.raises(ValidationError, match="Estado inválido"):
        EnderecoCreate(**{**DADOS_VALIDOS, "estado": estado})


def test_espacos_em_branco_sao_removidos() -> None:
    endereco = EnderecoCreate(**{**DADOS_VALIDOS, "logradouro": "  Praça da Sé  "})

    assert endereco.logradouro == "Praça da Sé"


def test_campos_obrigatorios_nao_aceitam_texto_vazio() -> None:
    with pytest.raises(ValidationError):
        EnderecoCreate(**{**DADOS_VALIDOS, "logradouro": "   "})


def test_complemento_e_opcional() -> None:
    endereco = EnderecoCreate(**DADOS_VALIDOS)

    assert endereco.complemento is None


def test_atualizacao_exige_ao_menos_um_campo() -> None:
    with pytest.raises(ValidationError, match="ao menos um campo"):
        EnderecoUpdate()


def test_atualizacao_nao_aceita_null_em_campo_obrigatorio() -> None:
    with pytest.raises(ValidationError, match="não podem receber null"):
        EnderecoUpdate(cidade=None)


def test_atualizacao_aceita_limpar_complemento() -> None:
    dados = EnderecoUpdate(complemento=None)

    assert dados.model_dump(exclude_unset=True) == {"complemento": None}


def test_atualizacao_normaliza_cep_e_estado() -> None:
    dados = EnderecoUpdate(cep="20.040-020", estado="rj")

    assert dados.cep == "20040020"
    assert dados.estado == "RJ"
