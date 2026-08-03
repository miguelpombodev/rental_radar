from crawler.base import BaseCrawler
from parser.schemas import TipoAnuncio, TipoImovel
from utils.urls import build_base_url


class IdealistaCrawler(BaseCrawler):
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
