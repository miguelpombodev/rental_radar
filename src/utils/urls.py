from parser.schemas import TipoAnuncio, TipoImovel
from utils.countries import get_country_code_by_its_name


def build_base_url(
    country_name: str, tipo_anuncio: TipoAnuncio, tipo: TipoImovel, state: str
):
    country_code = get_country_code_by_its_name(country_name)

    return (
        f"https://www.olx.com.{country_code}/imoveis/{tipo_anuncio.value}"
        f"/{tipo.value}/estado-{state}"
    )
