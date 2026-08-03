from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from crawler.ideal import IdealistaCrawler
from crawler.olx import OLXCrawler


class Settings(BaseSettings):
    """
    Configurações centralizadas do imoveis-radar.

    Lidas automaticamente de:
    1. Variáveis de ambiente (maior prioridade)
    2. Arquivo .env na raiz do projeto
    3. Valores default definidos aqui
    """

    crawlers: dict[str, Any] = {"olx": OLXCrawler, "idealist": IdealistaCrawler}

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # DATABASE_URL == database_url
        extra="ignore",  # ignora vars desconhecidas no .env
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./imoveis.db",
        description="SQLAlchemy async URL. Ex: postgresql+asyncpg://user:pass@host/db",
    )

    telegram_token: SecretStr = Field(
        default=SecretStr(""),
        description="Token do bot obtido via @BotFather",
    )
    telegram_chat_id: str = Field(
        default="",
        description="Chat ID para onde os alertas serão enviados",
    )

    crawler_intervalo_minutos: int = Field(
        default=30,
        ge=5,
        description="Intervalo entre coletas em minutos (mínimo 5)",
    )
    crawler_paginas: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Número de páginas a coletar por execução",
    )
    crawler_concorrencia: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Requisições simultâneas máximas",
    )
    crawler_delay_segundos: float = Field(
        default=1.0,
        ge=0.5,
        description="Pausa entre batches de requisições (respeito ao servidor)",
    )

    debug: bool = Field(
        default=False,
        description="Ativa SQL echo e logs verbosos",
    )
    log_level: str = Field(default="INFO")

    @field_validator("telegram_token", mode="before")
    @classmethod
    def token_nao_vazio_se_alertas(cls, v: object) -> object:
        # Permite vazio — alertas simplesmente não serão enviados.
        # Validação mais rígida pode ser feita em runtime se necessário.
        return v

    @field_validator("log_level")
    @classmethod
    def log_level_valido(cls, v: str) -> str:
        validos = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in validos:
            raise ValueError(f"log_level deve ser um de {validos}")
        return upper

    @property
    def alertas_ativos(self) -> bool:
        """True se token e chat_id foram configurados."""
        return bool(self.telegram_token.get_secret_value() and self.telegram_chat_id)

    @property
    def telegram_token_str(self) -> str:
        """Retorna o token como string (use apenas onde necessário)."""
        return self.telegram_token.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Singleton via lru_cache.
    Toda a aplicação usa a mesma instância — sem re-leitura do .env a cada chamada.
    Em testes, invalide com: get_settings.cache_clear()
    """
    return Settings()


# Atalho conveniente — `from src.config import settings`
settings = get_settings()
