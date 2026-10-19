"""Concede o perfil de administrador a um usuário existente.

Uso: `python -m app.cli.promover_administrador usuario@example.com`
"""

import asyncio
import sys

from app.core.database import SessionLocal, engine
from app.models.enums import UsuarioStatus
from app.repositories.administrador import AdministradorRepository
from app.repositories.usuario import UsuarioRepository


async def promover(email: str) -> str:
    async with SessionLocal() as session, session.begin():
        usuario = await UsuarioRepository(session).obter_por_email(email)
        if usuario is None or usuario.deletado_em is not None:
            return f"Usuário com e-mail {email} não encontrado."
        if usuario.status != UsuarioStatus.ATIVO:
            return "Apenas usuários ativos podem ser administradores."

        repositorio = AdministradorRepository(session)
        if await repositorio.eh_administrador(usuario.id):
            return f"{usuario.nome} já é administrador."
        # Sem administrador logado: o próprio usuário fica registrado como concedente.
        await repositorio.adicionar(usuario.id, usuario.id)
        return f"{usuario.nome} agora é administrador."


async def _main(email: str) -> None:
    try:
        print(await promover(email))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python -m app.cli.promover_administrador <email>")
        sys.exit(1)
    asyncio.run(_main(sys.argv[1]))
