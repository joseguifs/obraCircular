import asyncio
import logging

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.webhook_mercado_pago import WebhookMercadoPagoService

logger = logging.getLogger(__name__)


async def executar_worker_webhooks() -> None:
    """O lifespan supervisiona a tarefa; o banco coordena instâncias concorrentes."""
    settings = get_settings()
    while True:
        try:
            async with SessionLocal() as session:
                servico = WebhookMercadoPagoService(session)
                await servico.reprocessar_pendentes()
                resumo = await servico.obter_monitoramento()
                if resumo.status != "ok":
                    logger.warning(
                        "Webhooks exigem atenção: status=%s abandonados=%s falhas=%s",
                        resumo.status,
                        resumo.abandonados,
                        resumo.falhas_sem_retentativa,
                    )
        except Exception:
            logger.exception("Falha no ciclo do worker de webhooks; novo ciclo será executado.")
        await asyncio.sleep(settings.webhook_worker_interval_seconds)
