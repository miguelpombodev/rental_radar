from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.database import Base


class ImovelORM(Base):
    __tablename__ = "imoveis"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_externo: Mapped[str] = mapped_column(String(120), nullable=False)
    fonte: Mapped[str] = mapped_column(String(30), nullable=False)
    url: Mapped[str] = mapped_column(String(512))
    titulo: Mapped[str] = mapped_column(String(300))
    preco: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tipo: Mapped[str] = mapped_column(String(30))
    tipo_anuncio: Mapped[str] = mapped_column(String(20))
    area_m2: Mapped[float | None]
    quartos: Mapped[int | None]
    banheiros: Mapped[int | None]
    vagas: Mapped[int | None]
    bairro: Mapped[str | None] = mapped_column(String(120))
    cidade: Mapped[str | None] = mapped_column(String(120))
    estado: Mapped[str | None] = mapped_column(String(2))
    descricao: Mapped[str | None] = mapped_column(String(2000))
    coletado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Para detectar variação de preço ao longo do tempo
    preco_anterior: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        # Constraint de unicidade por fonte+id_externo
        Index("uq_imovel_fonte_externo", "fonte", "id_externo", unique=True),
        # Índices para queries frequentes no dashboard
        Index("ix_imovel_cidade_tipo", "cidade", "tipo"),
        Index("ix_imovel_preco", "preco"),
    )
