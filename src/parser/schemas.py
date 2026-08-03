from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class TipoImovel(StrEnum):
    APARTAMENTO = "apartamento"
    CASA = "casa"
    COBERTURA = "cobertura"
    TERRENO = "terreno"
    COMERCIAL = "comercial"
    OUTROS = "outros"


class TipoAnuncio(StrEnum):
    VENDA = "venda"
    ALUGUEL = "aluguel"


class Imovel(BaseModel):
    """
    Schema canônico de um imóvel coletado.
    Agnóstico de fonte — cada crawler mapeia para este modelo.
    """

    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    id_externo: str = Field(..., description="ID único na fonte (OLX, ZAP, etc.)")
    fonte: str = Field(..., description="Identificador do crawler (ex: 'olx')")
    url: str
    titulo: str
    preco: Optional[Decimal] = None
    tipo: TipoImovel = TipoImovel.OUTROS
    tipo_anuncio: TipoAnuncio = TipoAnuncio.VENDA
    area_m2: Optional[float] = None
    quartos: Optional[int] = None
    banheiros: Optional[int] = None
    vagas: Optional[int] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    descricao: Optional[str] = None
    coletado_em: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("preco", mode="before")
    @classmethod
    def limpar_preco(cls, v: object) -> object:
        """
        Aceita strings como 'R$ 450.000' ou '450000.00'
        e converte para Decimal limpo.
        """
        if isinstance(v, str):
            limpo = v.replace("R$", "").replace(".", "").replace(",", ".").strip()
            return Decimal(limpo) if limpo else None
        return v

    @field_validator("area_m2", mode="before")
    @classmethod
    def limpar_area(cls, v: object) -> object:
        if isinstance(v, str):
            limpo = v.replace("m²", "").replace("m2", "").strip()
            return float(limpo) if limpo else None
        return v
