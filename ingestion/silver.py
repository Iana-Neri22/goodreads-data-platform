import logging
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "warehouse.duckdb"


def transform(con: duckdb.DuckDBPyConnection | None = None) -> None:
    close_after = con is None

    if con is None:
        log.info("Conectando ao warehouse: %s", DB_PATH)
        con = duckdb.connect(str(DB_PATH))

    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.execute("DROP TABLE IF EXISTS silver.books")

    con.execute(
        """
        CREATE TABLE silver.books AS
        SELECT
            CAST(bookid AS INTEGER) AS book_id,
            TRIM(title) AS title,
            TRIM(authors) AS authors,
            TRY_CAST(average_rating AS DOUBLE) AS average_rating,
            NULLIF(TRIM(isbn), 'N/A') AS isbn,
            NULLIF(TRIM(isbn13), 'N/A') AS isbn13,
            NULLIF(TRIM(language_code), '') AS language_code,
            TRY_CAST(num_pages AS INTEGER) AS num_pages,
            TRY_CAST(ratings_count AS INTEGER) AS ratings_count,
            TRY_CAST(text_reviews_count AS INTEGER) AS text_reviews_count,
            TRY_CAST(
                TRY_STRPTIME(TRIM(publication_date), '%m/%d/%Y')
                AS DATE
            ) AS publication_date,
            NULLIF(TRIM(publisher), '') AS publisher,
            CURRENT_TIMESTAMP::TIMESTAMP AS loaded_at
        FROM bronze.books_raw
        WHERE
            TRIM(title) IS NOT NULL
            AND TRIM(title) != ''
            AND TRY_CAST(bookid AS INTEGER) IS NOT NULL
            AND TRY_CAST(num_pages AS INTEGER) > 0
        """
    )

    row = con.execute("SELECT COUNT(*) FROM bronze.books_raw").fetchone()
    total_bronze = row[0] if row is not None else 0  # pragma: no branch

    row = con.execute("SELECT COUNT(*) FROM silver.books").fetchone()
    total_silver = row[0] if row is not None else 0  # pragma: no branch

    dropped = total_bronze - total_silver

    log.info(
        "Transformação concluída: %d linhas válidas (%d descartadas)",
        total_silver,
        dropped,
    )

    if dropped > 0:
        reasons = con.execute(
            """
            SELECT
                SUM(
                    CASE
                        WHEN TRIM(title) IS NULL
                             OR TRIM(title) = ''
                        THEN 1
                        ELSE 0
                    END
                ) AS titulo_vazio,

                SUM(
                    CASE
                        WHEN TRY_CAST(bookid AS INTEGER) IS NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS id_invalido,

                SUM(
                    CASE
                        WHEN TRY_CAST(num_pages AS INTEGER) <= 0
                             OR TRY_CAST(num_pages AS INTEGER) IS NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS paginas_invalidas
            FROM bronze.books_raw
            """
        ).fetchone()

        if reasons is not None:  # pragma: no branch
            log.info(
                "Motivos: título vazio=%d | id inválido=%d | páginas inválidas=%d",
                reasons[0],
                reasons[1],
                reasons[2],
            )

    if close_after:
        con.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    transform()
