"""Database access abstractions."""

from app.repositories.anuncio import AnuncioRepository
from app.repositories.categoria import CategoriaRepository

__all__ = ["AnuncioRepository", "CategoriaRepository"]
