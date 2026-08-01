# src/dashboard/app.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import settings
from src.storage.models import ImovelORM


def _sync_url() -> str:
    """
    Converte a URL async para síncrona.
    O engine do dashboard é independente do engine da aplicação.
    """
    return settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    ).replace("sqlite+aiosqlite://", "sqlite://")


# Engine síncrono — criado uma vez, reutilizado entre reruns do Streamlit
@st.cache_resource
def get_engine():
    return create_engine(_sync_url(), pool_pre_ping=True)


@st.cache_data(ttl=300)
def carregar_dados(cidade: str, preco_max: int, quartos_min: int) -> pd.DataFrame:
    stmt = select(ImovelORM)

    if cidade:
        stmt = stmt.where(ImovelORM.cidade.ilike(f"%{cidade}%"))
    if preco_max:
        stmt = stmt.where(ImovelORM.preco <= preco_max)
    if quartos_min:
        stmt = stmt.where(ImovelORM.quartos >= quartos_min)

    stmt = stmt.order_by(ImovelORM.coletado_em.desc()).limit(500)

    with Session(get_engine()) as session:
        rows = session.execute(stmt).scalars().all()

    return pd.DataFrame(
        [
            {
                "titulo": r.titulo,
                "preco": float(r.preco) if r.preco else None,
                "preco_anterior": float(r.preco_anterior) if r.preco_anterior else None,
                "area_m2": r.area_m2,
                "quartos": r.quartos,
                "banheiros": r.banheiros,
                "vagas": r.vagas,
                "bairro": r.bairro,
                "cidade": r.cidade,
                "tipo": r.tipo,
                "url": r.url,
                "coletado_em": r.coletado_em,
            }
            for r in rows
        ]
    )


# ── UI ─────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Imóveis Radar", page_icon="🏠", layout="wide")
st.title("🏠 Imóveis Radar — Dashboard")

with st.sidebar:
    st.header("Filtros")
    cidade = st.text_input("Cidade", value="São Paulo")
    preco_max = st.number_input("Preço máximo (R$)", value=1_000_000, step=50_000)
    quartos_min = st.slider("Quartos mínimos", 0, 5, 2)

df = carregar_dados(cidade, int(preco_max), quartos_min)

if df.empty:
    st.warning("Nenhum imóvel encontrado com esses filtros.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de imóveis", len(df))
col2.metric(
    "Preço médio", f"R$ {df['preco'].mean():,.0f}" if df["preco"].notna().any() else "—"
)
col3.metric(
    "Área média",
    f"{df['area_m2'].mean():.0f} m²" if df["area_m2"].notna().any() else "—",
)
col4.metric("Com variação de preço", int(df["preco_anterior"].notna().sum()))

st.divider()

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Distribuição de preços")
    fig = px.histogram(df, x="preco", nbins=40, labels={"preco": "Preço (R$)"})
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("Imóveis por bairro")
    top_bairros = df["bairro"].value_counts().head(15).reset_index()
    top_bairros.columns = ["bairro", "count"]
    fig2 = px.bar(top_bairros, x="bairro", y="count", labels={"count": "Qtd"})
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Listagem")
st.dataframe(
    df[["titulo", "preco", "preco_anterior", "area_m2", "quartos", "bairro", "url"]],
    use_container_width=True,
    hide_index=True,
)
