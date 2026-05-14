from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "warehouse.duckdb"

st.set_page_config(page_title="Goodreads Dashboard", page_icon="📚", layout="wide")
st.title("📚 Goodreads Data Platform")

if not DB_PATH.exists():
    st.error(f"Warehouse não encontrado em `{DB_PATH}`. Execute `python pipeline.py` primeiro.")
    st.stop()


@st.cache_resource
def _connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data
def _top_authors() -> pd.DataFrame:
    return _connection().execute("SELECT * EXCLUDE (loaded_at) FROM gold.top_authors").df()


@st.cache_data
def _top_books() -> pd.DataFrame:
    return _connection().execute("SELECT * EXCLUDE (loaded_at) FROM gold.top_books").df()


@st.cache_data
def _books_by_language() -> pd.DataFrame:
    return _connection().execute("SELECT * EXCLUDE (loaded_at) FROM gold.books_by_language").df()


authors = _top_authors()
books = _top_books()
languages = _books_by_language()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Autores", f"{len(authors):,}")
c2.metric("Livros (top)", f"{len(books):,}")
c3.metric("Idiomas", f"{len(languages):,}")
c4.metric("Rating médio", f"{books['average_rating'].mean():.2f}")

st.divider()

tab_authors, tab_books, tab_lang = st.tabs(["Autores", "Livros", "Idiomas"])

with tab_authors:
    top20 = authors.head(20)
    fig = px.bar(
        top20,
        x="total_ratings",
        y="authors",
        orientation="h",
        color="avg_rating",
        color_continuous_scale="Blues",
        labels={
            "total_ratings": "Total de Avaliações",
            "authors": "Autor",
            "avg_rating": "Rating Médio",
        },
        title="Top 20 autores por número de avaliações",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(authors, use_container_width=True, hide_index=True)

with tab_books:
    min_r = st.slider("Rating mínimo", 0.0, 5.0, 4.0, 0.1)
    filtered = books[books["average_rating"] >= min_r]
    st.caption(f"{len(filtered):,} livros encontrados")
    fig2 = px.scatter(
        filtered.head(200),
        x="ratings_count",
        y="average_rating",
        hover_name="title",
        hover_data=["authors"],
        color="average_rating",
        color_continuous_scale="RdYlGn",
        labels={
            "ratings_count": "Nº de Avaliações",
            "average_rating": "Rating Médio",
        },
        title="Rating vs. popularidade",
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(filtered, use_container_width=True, hide_index=True)

with tab_lang:
    fig3 = px.bar(
        languages.head(15),
        x="language_code",
        y="total_books",
        color="avg_rating",
        color_continuous_scale="Viridis",
        labels={
            "language_code": "Idioma",
            "total_books": "Total de Livros",
            "avg_rating": "Rating Médio",
        },
        title="Top 15 idiomas por número de livros",
    )
    st.plotly_chart(fig3, use_container_width=True)
    st.dataframe(languages, use_container_width=True, hide_index=True)
