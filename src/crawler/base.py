from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx
from playwright.async_api import async_playwright
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.parser.schemas import Imovel

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    fonte: str

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;"
            "q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
    }

    _CONCORRENCIA = 3  # reduzido — menos paralelo = menos suspeito
    _DELAY_MIN = 1.5
    _DELAY_MAX = 4.0

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self._CONCORRENCIA)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseCrawler":
        # Inicia o Playwright uma vez e reutiliza entre todas as URLs
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",  # evita crashes em ambientes com pouca memória
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=self._HEADERS["User-Agent"],
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={"width": 1366, "height": 768},
            # Bloqueia recursos desnecessários — mais rápido e menos trackers
            java_script_enabled=True,
        )
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        if self._client:
            await self._client.aclose()

    @abstractmethod
    def _urls_para_coletar(self) -> AsyncIterator[str]: ...

    @abstractmethod
    async def _parsear_pagina(self, html: str, url: str) -> list[Imovel]: ...

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=2, min=3, max=60),
        stop=stop_after_attempt(4),
    )
    async def _buscar(self, url: str, referer: str | None = None) -> str:
        headers: dict[str, str] = {}
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin"

        async with self._semaphore:
            assert self._client is not None
            resp = await self._client.get(url, headers=headers)

            if resp.status_code == 403:
                logger.warning("403 em %s — possível bloqueio anti-bot", url)
                # Levanta para o tenacity tentar novamente com backoff
                resp.raise_for_status()

            resp.raise_for_status()
            return resp.text

    async def _buscar_com_browser(self, url: str) -> str:
        page = await self._context.new_page()
        try:
            # Bloqueia recursos que causam o networkidle nunca chegar
            await page.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type
                    in {"image", "media", "font", "stylesheet"}
                    else route.continue_()
                ),
            )

            await page.goto(
                url,
                wait_until="domcontentloaded",  # <-- não espera networkidle
                timeout=45_000,  # 45s em vez de 30s
            )

            # Aguarda um elemento que indica que o conteúdo dos anúncios carregou
            # Ajuste o seletor conforme o HTML real da OLX
            await page.wait_for_selector(
                "a[data-testid=adcard-link]",
                timeout=15_000,
            )

            return await page.content()
        finally:
            await page.close()  # fecha a page mas mantém o context/browser

    async def coletar(self) -> AsyncIterator[Imovel]:
        referer: str | None = None
        async for url in self._urls_para_coletar():
            try:
                html = await self._buscar_com_browser(url)
                imoveis = await self._parsear_pagina(html, url)
                for imovel in imoveis:
                    yield imovel
                referer = url  # próxima página "veio de" esta
                delay = random.uniform(self._DELAY_MIN, self._DELAY_MAX)
                logger.debug("Aguardando %.1fs antes da próxima requisição", delay)
                await asyncio.sleep(delay)
            except Exception as exc:
                logger.warning("Falha ao coletar %s: %s", url, exc)
