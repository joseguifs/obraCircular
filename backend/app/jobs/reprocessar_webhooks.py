import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from app.core.database import SessionLocal, engine
from app.services.webhook_mercado_pago import WebhookMercadoPagoService


def _json_padrao(valor: object) -> str:
    if isinstance(valor, datetime):
        return valor.isoformat()
    raise TypeError(f"Tipo não serializável: {type(valor).__name__}")


async def executar(*, evento_id: UUID | None, forcar: bool) -> int:
    async with SessionLocal() as session:
        servico = WebhookMercadoPagoService(session)
        if evento_id is not None:
            processados = int(await servico.reprocessar_evento(evento_id, forcar=forcar))
        else:
            processados = await servico.reprocessar_pendentes()
        resumo = await servico.obter_monitoramento()
        print(
            json.dumps(
                {"reprocessados": processados, **asdict(resumo)},
                ensure_ascii=False,
                default=_json_padrao,
            )
        )
    return 1 if resumo.status != "ok" else 0


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reprocessa webhooks pendentes/falhos com lease e backoff."
    )
    parser.add_argument("--event-id", type=UUID, help="Reprocessa somente este evento.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora o backoff/limite para uma tentativa manual do evento informado.",
    )
    argumentos = parser.parse_args()
    if argumentos.force and argumentos.event_id is None:
        parser.error("--force exige --event-id")
    try:
        return await executar(evento_id=argumentos.event_id, forcar=argumentos.force)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
