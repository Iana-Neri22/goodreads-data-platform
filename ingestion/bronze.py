import logging
from pathlib import Path

import duckdb

from ingestion.config import settings

log = logging.getLogger(__name__)


def ingest(
    con: duckdb.DuckDBPyConnection | None = None, csv_path: str | Path | None = None
) -> None:
    csv = Path(csv_path) if csv_path else settings.csv_path
    if not csv.exists():
        raise FileNotFoundError(f"CSV não encontrado: {csv}")
    close_after = con is None
    if con is None:
        log.info("Conectando ao warehouse: %s", settings.db_path)
        con = duckdb.connect(str(settings.db_path))

    log.info("Lendo CSV: %s", csv)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    con.execute("DROP TABLE IF EXISTS bronze.books_raw")
    con.execute(
        """
        CREATE TABLE bronze.books_raw AS
        SELECT *
        FROM read_csv(
            ?,
            header = true,
            all_varchar = true,
            normalize_names = true,
            ignore_errors = true
        )
    """,
        [csv.as_posix()],
    )

    row = con.execute("SELECT count(*) FROM bronze.books_raw").fetchone()
    count = row[0] if row is not None else 0  # pragma: no branch
    cols = con.execute("DESCRIBE bronze.books_raw").fetchall()

    log.info("Ingestão concluída: %d linhas carregadas", count)
    log.info("Colunas criadas:")
    for col in cols:
        log.info("  %-30s %s", col[0], col[1])

    if close_after:
        con.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ingest()
