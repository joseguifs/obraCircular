"""Exceções de domínio, independentes do transporte HTTP.

As camadas de serviço devem levantar estas exceções em vez de `HTTPException`;
a tradução para respostas HTTP acontece nos handlers registrados em `app.main`.
"""


class DomainError(Exception):
    """Erro de negócio base."""


class NotFoundError(DomainError):
    """O recurso solicitado não existe ou não está mais visível."""


class ConflictError(DomainError):
    """A operação conflita com o estado atual dos dados (ex.: e-mail em uso)."""
