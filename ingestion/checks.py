import logging
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "warehouse.duckdb"


def _check(con, name, query):
    count = con.execute(query).fetchone()[0]

    if count > 0:
        log.warning("  FALHOU %-35s → %d linhas problemáticas", name, count)
    else:
        log.info("  OK     %s", name)

    return count


def validate(con=None):
    close_after = con is None

    if con is None:
        con = duckdb.connect(str(DB_PATH))

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

    if failures == 0:
        log.info("Todas as verificações passaram.")
    else:
        log.warning("%d verificação(ões) com problemas.", failures)

        raise ValueError(
            f"Qualidade de dados insuficiente: "
            f"{failures} verificação(ões) falharam."
        )

    if close_after:
        con.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    validate()
