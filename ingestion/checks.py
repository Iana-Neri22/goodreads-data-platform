import logging

import duckdb

from ingestion.config import settings

log = logging.getLogger(__name__)


def _check(
    con: duckdb.DuckDBPyConnection,
    name: str,
    query: str,
) -> int:
    row = con.execute(query).fetchone()

    count: int = row[0] if row is not None else 0  # pragma: no branch

    if count > 0:
        log.warning(
            "  FALHOU %-35s → %d linhas problemáticas",
            name,
            count,
        )
    else:
        log.info("  OK     %s", name)

    return count


def validate(con: duckdb.DuckDBPyConnection | None = None) -> tuple[int, int]:
    close_after = con is None

    if con is None:
        con = duckdb.connect(str(settings.db_path))

    log.info("Executando verificações de qualidade em silver.books...")

    total = 0
    failures = 0

    # --- Integridade básica ---

    total += 1
    failures += _check(
        con,
        "silver.books vazia",
        "SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END FROM silver.books",
    )

    total += 1
    failures += _check(
        con,
        f"retenção silver < {settings.min_silver_retention_pct:.0%}",
        f"""
        SELECT CASE
            WHEN (SELECT COUNT(*) FROM bronze.books_raw) = 0 THEN 0
            WHEN COUNT(*) * 1.0 / (SELECT COUNT(*) FROM bronze.books_raw)
                 < {settings.min_silver_retention_pct}
            THEN 1
            ELSE 0
        END
        FROM silver.books
        """,
    )

    total += 1
    failures += _check(
        con,
        "book_id duplicado",
        """
        SELECT COUNT(*)
        FROM (
            SELECT book_id
            FROM silver.books
            GROUP BY book_id
            HAVING COUNT(*) > 1
        )
        """,
    )

    total += 1
    failures += _check(
        con,
        "title nulo ou vazio",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE title IS NULL
           OR TRIM(title) = ''
        """,
    )

    total += 1
    failures += _check(
        con,
        "authors nulo ou vazio",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE authors IS NULL
           OR TRIM(authors) = ''
        """,
    )

    # --- Ranges numéricos ---

    total += 1
    failures += _check(
        con,
        "average_rating fora de [0, 5]",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE average_rating IS NOT NULL
          AND average_rating NOT BETWEEN 0 AND 5
        """,
    )

    total += 1
    failures += _check(
        con,
        "num_pages <= 0",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE num_pages IS NOT NULL
          AND num_pages <= 0
        """,
    )

    total += 1
    failures += _check(
        con,
        "ratings_count negativo",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE ratings_count IS NOT NULL
          AND ratings_count < 0
        """,
    )

    # --- Consistência entre colunas ---

    total += 1
    failures += _check(
        con,
        "text_reviews_count > ratings_count",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE text_reviews_count IS NOT NULL
          AND ratings_count IS NOT NULL
          AND text_reviews_count > ratings_count
        """,
    )

    # --- Datas ---

    total += 1
    failures += _check(
        con,
        "publication_date futura",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE publication_date > CURRENT_DATE
        """,
    )

    # --- Formato ---

    total += 1
    failures += _check(
        con,
        "isbn13 comprimento inválido",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE isbn13 IS NOT NULL
          AND LENGTH(isbn13) != 13
        """,
    )

    passed = total - failures

    if failures == 0:
        log.info("%d/%d verificações passaram.", passed, total)
    else:
        log.warning(
            "%d/%d verificações com problemas.",
            failures,
            total,
        )

        msg = f"Qualidade de dados insuficiente: {failures}/{total} verificação(ões) falharam."

        raise ValueError(msg)

    if close_after:
        con.close()

    return passed, total


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    validate()
