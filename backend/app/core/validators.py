"""Validadores e normalizadores de campos usados por múltiplos schemas."""

import re

_APENAS_DIGITOS = re.compile(r"\D")
_DDD_VALIDO = re.compile(r"^[1-9][1-9]$")


def normalizar_telefone(valor: str) -> str:
    """Valida um telefone brasileiro e o normaliza para `+55DDNUMERO`.

    Aceita o número com ou sem código do país e com qualquer pontuação
    (parênteses, espaços, hífen). Levanta `ValueError` quando o telefone é
    inválido, para ser usado diretamente em um `field_validator` do Pydantic.
    """
    digitos = _APENAS_DIGITOS.sub("", valor)

    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]

    if len(digitos) not in (10, 11):
        raise ValueError("Telefone inválido: informe DDD + número (10 ou 11 dígitos).")

    ddd, numero = digitos[:2], digitos[2:]
    if not _DDD_VALIDO.match(ddd):
        raise ValueError("Telefone inválido: DDD inexistente.")
    if len(numero) == 9 and numero[0] != "9":
        raise ValueError("Telefone inválido: celular com 9 dígitos deve começar com 9.")
    if len(numero) == 8 and numero[0] in "01":
        raise ValueError("Telefone inválido: número fixo não pode começar com 0 ou 1.")

    return f"+55{ddd}{numero}"
