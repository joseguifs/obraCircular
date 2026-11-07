"""Concilia repasses pendentes; novas liberacoes exigem --liberar e um administrador."""

import argparse
import asyncio
import json

from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.core.exceptions import AppError
from app.models.enums import RepasseStatus
from app.models.pedido import Pedido
from app.models.repasse import Repasse
from app.models.usuario import Usuario
from app.services.repasse import RepasseService


async def executar(*, liberar: bool, admin_email: str | None) -> int:
    async with SessionLocal() as session:
        atualizados = await RepasseService(session).atualizar_estados()
        operador_id = await session.scalar(select(Usuario.id).where(Usuario.email == admin_email))
        if liberar:
            if operador_id is None:
                raise AppError(
                    status_code=403, detail="Administrador não encontrado.", code="PAYOUT_FORBIDDEN"
                )
            await RepasseService(session)._validar_admin(operador_id)
        ids = list(
            await session.scalars(
                select(Repasse.id)
                .join(Pedido)
                .where(
                    Pedido.modelo_financeiro == "REPASSE_POSTERIOR",
                    Repasse.status.in_(
                        {
                            RepasseStatus.AGUARDANDO_ENTREGA,
                            RepasseStatus.EM_PERIODO_CONTESTACAO,
                            RepasseStatus.PRONTO_PARA_LIBERACAO,
                            RepasseStatus.PROCESSANDO,
                        }
                    ),
                )
            )
        )
        await session.rollback()
        resultados = []
        for repasse_id in ids:
            repasse = await session.get(Repasse, repasse_id)
            assert repasse is not None
            processando = repasse.status == RepasseStatus.PROCESSANDO
            await session.rollback()
            try:
                servico = RepasseService(session)
                if processando:
                    await servico.conciliar(repasse_id)
                elif liberar and operador_id:
                    await servico.liberar(repasse_id, operador_id)
                else:
                    continue
                resultados.append({"id": str(repasse_id), "resultado": "processado"})
            except Exception as exc:
                await session.rollback()
                resultados.append(
                    {
                        "id": str(repasse_id),
                        "resultado": exc.code if isinstance(exc, AppError) else type(exc).__name__,
                    }
                )
        print(json.dumps({"estados_atualizados": atualizados, "repasses": resultados}))
        return int(
            any(
                item["resultado"] not in {"processado", "PAYOUT_NOT_ELIGIBLE"}
                for item in resultados
            )
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--liberar", action="store_true")
    parser.add_argument("--admin-email")
    args = parser.parse_args()
    if args.liberar and not args.admin_email:
        parser.error("--liberar exige --admin-email de um administrador ativo")
    try:
        return await executar(liberar=args.liberar, admin_email=args.admin_email)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
