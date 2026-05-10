import duckdb
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "warehouse.duckdb"
EXPORTS_PATH = Path(__file__).parent.parent / "data" / "exports"


def build(con=None):
    close_after = con is None
    if con is None:
        log.info("Conectando ao warehouse: %s", DB_PATH)
        con = duckdb.connect(str(DB_PATH))

    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    con.execute("DROP TABLE IF EXISTS gold.top_authors")
    con.execute("DROP TABLE IF EXISTS gold.top_books")
    con.execute("DROP TABLE IF EXISTS gold.books_by_language")

    con.execute("""
        CREATE TABLE gold.top_authors AS
        SELECT
            authors,
            COUNT(*)                                        AS total_books,
            ROUND(AVG(average_rating), 2)                  AS avg_rating,
            SUM(ratings_count)                             AS total_ratings,
            SUM(text_reviews_count)                        AS total_reviews,
            MIN(publication_date)                          AS first_publication,
            MAX(publication_date)                          AS last_publication
        FROM silver.books
        WHERE authors IS NOT NULL
        GROUP BY authors
        ORDER BY total_ratings DESC
    """)

    rows = con.execute("SELECT * FROM gold.top_authors LIMIT 10").fetchall()
    cols = [d[0] for d in con.execute("DESCRIBE gold.top_authors").fetchall()]

    log.info("Top 10 autores por total de avaliações:")
    log.info("  %-40s %6s %10s %15s", "Autor", "Livros", "Avg Rating", "Total Ratings")
    log.info("  %s", "-" * 75)
    for row in rows:
        data = dict(zip(cols, row))
        log.info(
            "  %-40s %6d %10.2f %15s",
            data["authors"][:40],
            data["total_books"],
            data["avg_rating"] or 0,
            f'{data["total_ratings"] or 0:,}',
        )

    con.execute("""
        CREATE TABLE gold.top_books AS
        SELECT
            book_id,
            title,
            authors,
            average_rating,
            ratings_count,
            num_pages,
            publication_date,
            publisher
        FROM silver.books
        WHERE ratings_count >= 1000
        ORDER BY average_rating DESC, ratings_count DESC
    """)

    rows = con.execute("SELECT * FROM gold.top_books LIMIT 10").fetchall()
    cols = [d[0] for d in con.execute("DESCRIBE gold.top_books").fetchall()]

    log.info("Top 10 livros por rating (mín. 1000 avaliações):")
    log.info("  %-45s %10s %12s", "Título", "Avg Rating", "Avaliações")
    log.info("  %s", "-" * 70)
    for row in rows:
        data = dict(zip(cols, row))
        log.info(
            "  %-45s %10.2f %12s",
            data["title"][:45],
            data["average_rating"] or 0,
            f'{data["ratings_count"] or 0:,}',
        )

    con.execute("""
        CREATE TABLE gold.books_by_language AS
        SELECT
            language_code,
            COUNT(*)                        AS total_books,
            ROUND(AVG(average_rating), 2)   AS avg_rating,
            SUM(ratings_count)              AS total_ratings
        FROM silver.books
        WHERE language_code IS NOT NULL
        GROUP BY language_code
        ORDER BY total_books DESC
    """)

    rows = con.execute("SELECT * FROM gold.books_by_language").fetchall()
    cols = [d[0] for d in con.execute("DESCRIBE gold.books_by_language").fetchall()]

    log.info("Livros por idioma:")
    log.info("  %-12s %8s %10s %15s", "Idioma", "Livros", "Avg Rating", "Total Ratings")
    log.info("  %s", "-" * 50)
    for row in rows:
        data = dict(zip(cols, row))
        log.info(
            "  %-12s %8d %10.2f %15s",
            data["language_code"],
            data["total_books"],
            data["avg_rating"] or 0,
            f'{data["total_ratings"] or 0:,}',
        )

    EXPORTS_PATH.mkdir(parents=True, exist_ok=True)
    for table in ("top_authors", "top_books", "books_by_language"):
        dest = (EXPORTS_PATH / f"{table}.csv").as_posix()
        con.execute(f"COPY gold.{table} TO '{dest}' (HEADER, DELIMITER ',')")
        log.info("Exportado: %s", dest)

    if close_after:
        con.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    build()
