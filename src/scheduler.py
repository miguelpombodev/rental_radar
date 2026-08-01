from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rich.logging import RichHandler

from src.alerts.telegram import TelegramAlertas
from src.crawler.olx import OLXCrawler
from src.parser.schemas import TipoAnuncio, TipoImovel
from src.storage.database import get_session
from src.storage.repository import ImovelRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger(__name__)


async def executar_coleta() -> None:
    logger.info("Iniciando coleta...")
    alertas = TelegramAlertas()

    async with (
        OLXCrawler(
            estado="sp",
            cidade="sao-paulo",
            tipo=TipoImovel.APARTAMENTO,
            tipo_anuncio=TipoAnuncio.VENDA,
            paginas=3,
        ) as crawler,
        get_session() as session,
    ):
        repo = ImovelRepository(session)
        novos = preco_mudou = 0

        async for imovel in crawler.coletar():
            orm, is_novo, mudou_preco = await repo.upsert(imovel)

            if is_novo:
                novos += 1
                await alertas.novo_imovel(orm)

            if mudou_preco:
                preco_mudou += 1
                await alertas.preco_alterado(orm)

    logger.info(
        "Coleta finalizada. Novos: %d | Preços alterados: %d", novos, preco_mudou
    )


async def main() -> None:  # <-- agora é async
    scheduler = AsyncIOScheduler()
    await executar_coleta()

    scheduler.add_job(
        executar_coleta,
        trigger="interval",
        minutes=30,
        id="coleta_imoveis",
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.start()  # chamado dentro do loop — funciona
    logger.info("Scheduler iniciado. Ctrl+C para parar.")

    try:
        await asyncio.Event().wait()  # bloqueia indefinidamente sem busy-wait
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())  # cria o loop e entra nele
