from __future__ import annotations

import re
from typing import AsyncIterator
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from src.crawler.base import BaseCrawler
from src.parser.schemas import Imovel, TipoAnuncio, TipoImovel
from utils.urls import build_base_url


class OLXCrawler(BaseCrawler):
    """
    Crawler para OLX Imóveis Brasil.

    Coleta listagens de imóveis para venda/aluguel
    filtrando por estado, cidade e tipo.
    """

    def __init__(
        self,
        pais: str = "brazil",
        estado: str = "sp",
        cidade: str = "sao-paulo",
        tipo: TipoImovel = TipoImovel.APARTAMENTO,
        tipo_anuncio: TipoAnuncio = TipoAnuncio.VENDA,
        paginas: int = 5,
    ) -> None:
        super().__init__()
        self._fonte = "olx"
        self._estado = estado
        self._cidade = cidade
        self._tipo = tipo
        self._tipo_anuncio = tipo_anuncio
        self._paginas = paginas
        self._base_url = build_base_url(
            pais, self._tipo_anuncio, self._tipo, self._estado
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
        for card in soup.select("section.olx-adcard"):
            try:
                imovel = self._extrair_card(card)
                if imovel:
                    imoveis.append(imovel)
            except Exception:
                continue

        return imoveis

    def _extrair_card(self, card) -> Imovel | None:  # type: ignore[no-untyped-def]
        id_externo = card.get("data-lurker-detail", "")
        link_tag = card.select_one("a[data-testid=adcard-link]")
        if not link_tag:
            return None

        url = link_tag.get("href", "")
        titulo_tag = card.select_one("h2")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Sem título"

        preco_tag = card.select_one("[class*='price'], .fntzzx0")
        preco_raw = preco_tag.get_text(strip=True) if preco_tag else None

        if preco_raw == "" or None:
            return None

        # Extrai área, quartos, vagas de badges tipo "80 m² · 2 quartos · 1 vaga"
        area = card.select_one("[aria-label*='quadrados']").get_text(strip=True)
        quartos = card.select_one("[aria-label*='quartos']").get_text(strip=True)
        banheiros = card.select_one("[aria-label*='banheiros']").get_text(strip=True)
        vagas = card.select_one("[aria-label*='vagas de garagem']").get_text(strip=True)

        bairro_tag = card.select_one("[class*='olx-adcard__location']")
        bairro_raw = bairro_tag.findChild().get_text(strip=True) if bairro_tag else None
        cidade, bairro = self._split_localizacao(bairro_raw)

        return Imovel(
            id_externo=id_externo or url,
            fonte=self._fonte,
            url=url,  # type: ignore[arg-type]
            titulo=titulo,
            preco=preco_raw,
            tipo=self._parse_residence(titulo),
            tipo_anuncio=self._tipo_anuncio,
            area_m2=area,
            quartos=quartos,
            banheiros=banheiros,
            vagas=vagas,
            bairro=bairro,
            cidade=cidade or self._cidade,
            estado=self._estado.upper(),
        )

    def _parse_residence(self, title: str) -> TipoImovel:
        match title:
            case str() if "casa" in title.lower():
                return TipoImovel.CASA
            case str() if "residencia" in title.lower():
                return TipoImovel.CASA
            case str() if "apartamento" in title.lower():
                return TipoImovel.APARTAMENTO
            case str() if "cobertura" in title.lower():
                return TipoImovel.APARTAMENTO
            case _:
                return TipoImovel.OUTROS

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
