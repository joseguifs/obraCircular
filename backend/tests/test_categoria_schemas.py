import pytest
from pydantic import ValidationError

from app.models.enums import CategoriaStatus
from app.schemas.categoria import CategoriaCreate, CategoriaUpdate

DADOS_VALIDOS = {"nome": "Ferramentas", "descricao": "Ferramentas manuais e elétricas"}


def test_nome_com_espacos_no_inicio_e_fim_e_removido() -> None:
    categoria = CategoriaCreate(**{**DADOS_VALIDOS, "nome": "  Ferramentas  "})

    assert categoria.nome == "Ferramentas"


def test_espacos_internos_duplicados_sao_colapsados() -> None:
    categoria = CategoriaCreate(**{**DADOS_VALIDOS, "nome": "Material   de   Obra"})

    assert categoria.nome == "Material de Obra"


def test_nome_obrigatorio_nao_aceita_apenas_espacos() -> None:
    with pytest.raises(ValidationError, match="Nome é obrigatório"):
        CategoriaCreate(**{**DADOS_VALIDOS, "nome": "   "})


def test_nome_vazio_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        CategoriaCreate(**{**DADOS_VALIDOS, "nome": ""})


def test_descricao_e_opcional() -> None:
    categoria = CategoriaCreate(nome="Ferramentas")

    assert categoria.descricao is None


def test_descricao_em_branco_vira_none() -> None:
    categoria = CategoriaCreate(nome="Ferramentas", descricao="   ")

    assert categoria.descricao is None


def test_atualizacao_exige_ao_menos_um_campo() -> None:
    with pytest.raises(ValidationError, match="ao menos um campo"):
        CategoriaUpdate()


def test_atualizacao_nao_aceita_null_em_nome() -> None:
    with pytest.raises(ValidationError, match="não podem receber null"):
        CategoriaUpdate(nome=None)


def test_atualizacao_aceita_limpar_descricao() -> None:
    dados = CategoriaUpdate(descricao=None)

    assert dados.model_dump(exclude_unset=True) == {"descricao": None}


def test_atualizacao_aceita_alterar_status() -> None:
    dados = CategoriaUpdate(status=CategoriaStatus.INATIVA)

    assert dados.status == CategoriaStatus.INATIVA


def test_atualizacao_normaliza_nome() -> None:
    dados = CategoriaUpdate(nome="  Material   Elétrico  ")

    assert dados.nome == "Material Elétrico"
