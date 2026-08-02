from __future__ import annotations

import re
from typing import AsyncIterator
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from src.crawler.base import BaseCrawler
from src.parser.schemas import Imovel, TipoAnuncio, TipoImovel


class OLXCrawler(BaseCrawler):
    """
    Crawler para OLX Imóveis Brasil.

    Coleta listagens de imóveis para venda/aluguel
    filtrando por estado, cidade e tipo.
    """

    fonte = "olx"

    def __init__(
        self,
        estado: str = "sp",
        cidade: str = "sao-paulo",
        tipo: TipoImovel = TipoImovel.APARTAMENTO,
        tipo_anuncio: TipoAnuncio = TipoAnuncio.VENDA,
        paginas: int = 5,
    ) -> None:
        super().__init__()
        self._estado = estado
        self._cidade = cidade
        self._tipo = tipo
        self._tipo_anuncio = tipo_anuncio
        self._paginas = paginas
        self._base_url = (
            f"https://www.olx.com.br/imoveis/{tipo_anuncio.value}"
            f"/{tipo.value}/estado-{estado}"
        )

    async def _urls_para_coletar(self) -> AsyncIterator[str]:
        for pagina in range(1, self._paginas + 1):
            params = {"o": pagina}
            yield f"{self._base_url}?{urlencode(params)}"

    async def _parsear_pagina(self, html: str, url: str) -> list[Imovel]:
        soup = BeautifulSoup(html, "lxml")
        imoveis: list[Imovel] = []

        # OLX injeta os dados dos anúncios num <script> JSON — mais robusto que CSS
        # Fallback: seletores CSS caso o JSON não esteja presente
        for card in soup.select("a[data-testid=adcard-link]"):
            try:
                imovel = self._extrair_card(card)
                if imovel:
                    imoveis.append(imovel)
            except Exception:
                continue

        return imoveis

    def _extrair_card(self, card) -> Imovel | None:  # type: ignore[no-untyped-def]
        id_externo = card.get("data-lurker-detail", "")
        link_tag = card.select_one("a[data-lurker-detail]")
        if not link_tag:
            return None

        url = link_tag.get("href", "")
        titulo_tag = card.select_one("h2, .fnmrjs0")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Sem título"

        preco_tag = card.select_one("[class*='price'], .fntzzx0")
        preco_raw = preco_tag.get_text(strip=True) if preco_tag else None

        # Extrai área, quartos, vagas de badges tipo "80 m² · 2 quartos · 1 vaga"
        detalhes = card.get_text(" ", strip=True)
        area = self._extrair_numero(detalhes, r"(\d+)\s*m²")
        quartos = self._extrair_numero(detalhes, r"(\d+)\s*quarto")
        banheiros = self._extrair_numero(detalhes, r"(\d+)\s*banheiro")
        vagas = self._extrair_numero(detalhes, r"(\d+)\s*vaga")

        bairro_tag = card.select_one("[class*='location'], .fntzzx1")
        bairro_raw = bairro_tag.get_text(strip=True) if bairro_tag else None
        bairro, cidade = self._split_localizacao(bairro_raw)

        return Imovel(
            id_externo=id_externo or url,
            fonte=self.fonte,
            url=url,  # type: ignore[arg-type]
            titulo=titulo,
            preco=preco_raw,
            tipo=self._tipo,
            tipo_anuncio=self._tipo_anuncio,
            area_m2=area,
            quartos=quartos,
            banheiros=banheiros,
            vagas=vagas,
            bairro=bairro,
            cidade=cidade or self._cidade,
            estado=self._estado.upper(),
        )

    @staticmethod
    def _extrair_numero(texto: str, padrao: str) -> int | None:
        match = re.search(padrao, texto, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _split_localizacao(raw: str | None) -> tuple[str | None, str | None]:
        if not raw:
            return None, None
        partes = [p.strip() for p in raw.split(",")]
        bairro = partes[0] if partes else None
        cidade = partes[1] if len(partes) > 1 else None
        return bairro, cidade
