import asyncio

from app.core.database import SessionLocal, engine
from app.services.reserva_estoque import ReservaEstoqueService


async def main() -> None:
    async with SessionLocal() as session:
        quantidade = await ReservaEstoqueService(session).liberar_expiradas()
        print(f"Reservas expiradas liberadas: {quantidade}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
