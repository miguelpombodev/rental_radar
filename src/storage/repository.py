from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert  # upsert nativo SQLite
from sqlalchemy.ext.asyncio import AsyncSession

from src.parser.schemas import Imovel
from src.storage.models import ImovelORM


class ImovelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, imovel: Imovel) -> tuple[ImovelORM, bool, bool]:
        """
        Retorna (orm_obj, is_novo, preco_mudou).

        Usa INSERT OR IGNORE + UPDATE separado para:
        1. Inserir se não existir
        2. Atualizar preço se mudou — e guardar o preço anterior
        """
        # Verifica se já existe
        stmt = select(ImovelORM).where(
            ImovelORM.fonte == imovel.fonte,
            ImovelORM.id_externo == imovel.id_externo,
        )
        result = await self._session.execute(stmt)
        existente = result.scalar_one_or_none()

        if existente is None:
            novo = ImovelORM(**imovel.model_dump(exclude={"coletado_em"}))
            self._session.add(novo)
            await self._session.flush()
            return novo, True, False

        preco_mudou = (
            imovel.preco is not None
            and existente.preco is not None
            and imovel.preco != existente.preco
        )

        if preco_mudou:
            existente.preco_anterior = existente.preco
            existente.preco = imovel.preco
            existente.atualizado_em = datetime.utcnow()

        return existente, False, preco_mudou

    async def listar(
        self,
        cidade: str | None = None,
        preco_max: Decimal | None = None,
        quartos_min: int | None = None,
    ) -> list[ImovelORM]:
        stmt = select(ImovelORM)
        if cidade:
            stmt = stmt.where(ImovelORM.cidade.ilike(f"%{cidade}%"))
        if preco_max:
            stmt = stmt.where(ImovelORM.preco <= preco_max)
        if quartos_min:
            stmt = stmt.where(ImovelORM.quartos >= quartos_min)
        stmt = stmt.order_by(ImovelORM.coletado_em.desc()).limit(500)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
