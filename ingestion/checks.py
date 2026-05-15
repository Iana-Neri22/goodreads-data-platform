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


def validate(con: duckdb.DuckDBPyConnection | None = None) -> None:
    close_after = con is None

    if con is None:
        con = duckdb.connect(str(settings.db_path))

    log.info("Executando verificações de qualidade em silver.books...")

    failures = 0

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

    failures += _check(
        con,
        "publication_date futura",
        """
        SELECT COUNT(*)
        FROM silver.books
        WHERE publication_date > CURRENT_DATE
        """,
    )

    total = 6
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    validate()
