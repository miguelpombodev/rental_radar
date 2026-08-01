from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.parser.schemas import Imovel

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """
    Contrato base para todos os crawlers.

    Cada implementação concreta só precisa definir:
    - `fonte`: identificador string da fonte
    - `_urls_para_coletar()`: gerador de URLs a visitar
    - `_parsear_pagina()`: extração do HTML → lista de Imovel
    """

    fonte: str
    # Headers que imitam um browser real — reduz bloqueios básicos
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    _CONCORRENCIA = 5  # máximo de requisições simultâneas
    _DELAY_ENTRE_REQS = 1  # segundos de pausa entre batches (educado com o servidor)

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self._CONCORRENCIA)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseCrawler":
        self._client = httpx.AsyncClient(
            headers=self._HEADERS,
            follow_redirects=True,
            timeout=httpx.Timeout(15.0),
            http2=True,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()

    @abstractmethod
    def _urls_para_coletar(self) -> AsyncIterator[str]:
        """Gerador assíncrono de URLs a visitar."""
        ...

    @abstractmethod
    async def _parsear_pagina(self, html: str, url: str) -> list[Imovel]:
        """Extrai imóveis de uma página HTML."""
        ...

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
    )
    async def _buscar(self, url: str) -> str:
        """
        Busca uma URL com retry exponencial automático via tenacity.
        O semáforo garante que no máximo `_CONCORRENCIA` reqs rodem juntas.
        """
        async with self._semaphore:
            assert self._client is not None
            resp = await self._client.get(url)
            resp.raise_for_status()
            return resp.text

    async def coletar(self) -> AsyncIterator[Imovel]:
        """
        Método público: itera URLs, busca em paralelo controlado,
        parseia e faz yield de cada Imovel.
        """
        async for url in self._urls_para_coletar():
            try:
                html = await self._buscar(url)
                imoveis = await self._parsear_pagina(html, url)
                for imovel in imoveis:
                    yield imovel
                await asyncio.sleep(self._DELAY_ENTRE_REQS)
            except Exception as exc:
                logger.warning("Falha ao coletar %s: %s", url, exc)
