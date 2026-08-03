from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rich.logging import RichHandler

from src.alerts.telegram import TelegramAlerts
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


async def execute_collecting() -> None:
    logger.info("Iniciando coleta...")
    alerts = TelegramAlerts()

    async with (
        OLXCrawler(
            estado="rj",
            cidade="rio-de-janeiro",
            tipo=TipoImovel.APARTAMENTO,
            tipo_anuncio=TipoAnuncio.ALUGUEL,
            paginas=3,
        ) as crawler,
        get_session() as session,
    ):
        repo = ImovelRepository(session)
        new = price_changed = 0

        async for imovel in crawler.coletar():
            orm, is_new, new_price = await repo.upsert(imovel)

            if is_new:
                new += 1
                await alerts.novo_imovel(orm)

            if new_price:
                price_changed += 1
                await alerts.preco_alterado(orm)

        await session.commit()
        logger.info("Real Estates registered in database")

    logger.info(
        "Collecting finished. New states: %d | Prices has changed: %d",
        new,
        price_changed,
    )


async def main() -> None:
    scheduler = AsyncIOScheduler()
    await execute_collecting()

    scheduler.add_job(
        execute_collecting,
        trigger="interval",
        minutes=30,
        id="real_estates_collector",
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.start()
    logger.info("Scheduler iniciado. Ctrl+C para parar.")

    try:
        await asyncio.Event().wait()  # bloqueia indefinidamente sem busy-wait
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())  # cria o loop e entra nele
