import duckdb
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
CSV_PATH = ROOT / "data" / "books.csv"
DB_PATH = ROOT / "warehouse.duckdb"


def ingest(con=None):
    close_after = con is None
    if con is None:
        log.info("Conectando ao warehouse: %s", DB_PATH)
        con = duckdb.connect(str(DB_PATH))

    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    con.execute("DROP TABLE IF EXISTS bronze.books_raw")
    con.execute(f"""
        CREATE TABLE bronze.books_raw AS
        SELECT *
        FROM read_csv(
            '{CSV_PATH.as_posix()}',
            header = true,
            all_varchar = true,
            normalize_names = true,
            ignore_errors = true
        )
    """)

    count = con.execute("SELECT count(*) FROM bronze.books_raw").fetchone()[0]
    cols = con.execute("DESCRIBE bronze.books_raw").fetchall()

    log.info("Ingestão concluída: %d linhas carregadas", count)
    log.info("Colunas criadas:")
    for col in cols:
        log.info("  %-30s %s", col[0], col[1])

    if close_after:
        con.close()


if __name__ == "__main__":
    ingest()
