from __future__ import annotations

import logging
from decimal import Decimal

from telegram import Bot
from telegram.constants import ParseMode

from src.config import settings
from src.storage.models import ImovelORM

logger = logging.getLogger(__name__)


class TelegramAlertas:
    def __init__(self) -> None:
        self._bot = Bot(token=settings.telegram_token_str)
        self._chat_id = settings.telegram_chat_id

    async def novo_imovel(self, imovel: ImovelORM) -> None:
        preco = f"R$ {imovel.preco:,.0f}" if imovel.preco else "Sob consulta"
        texto = (
            f"🏠 *Novo imóvel encontrado!*\n\n"
            f"*{imovel.titulo}*\n"
            f"📍 {imovel.bairro}, {imovel.cidade}/{imovel.estado}\n"
            f"💰 {preco}\n"
            f"📐 {imovel.area_m2} m²  🛏 {imovel.quartos} quartos\n\n"
            f"[Ver anúncio]({imovel.url})"
        )
        # await self._enviar(texto)

    async def preco_alterado(self, imovel: ImovelORM) -> None:
        def fmt(v: Decimal | None) -> str:
            return f"R$ {v:,.0f}" if v else "?"

        variacao = ""
        if imovel.preco and imovel.preco_anterior:
            diff = imovel.preco - imovel.preco_anterior
            sinal = "📉" if diff < 0 else "📈"
            variacao = f"{sinal} {fmt(imovel.preco_anterior)} → {fmt(imovel.preco)}"

        texto = (
            f"💸 *Mudança de preço detectada!*\n\n"
            f"*{imovel.titulo}*\n"
            f"📍 {imovel.bairro}, {imovel.cidade}\n"
            f"{variacao}\n\n"
            f"[Ver anúncio]({imovel.url})"
        )
        # await self._enviar(texto)

    async def _enviar(self, texto: str) -> None:
        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=texto,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False,
            )
        except Exception as exc:
            logger.error("Falha ao enviar alerta Telegram: %s", exc)
