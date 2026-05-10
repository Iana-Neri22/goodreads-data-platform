import argparse
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import duckdb

from ingestion import bronze, checks, gold, silver

ROOT = Path(__file__).parent
DB_PATH = str(ROOT / "warehouse.duckdb")
LOG_PATH = ROOT / "logs" / "pipeline.log"

LOG_PATH.parent.mkdir(exist_ok=True)

FMT = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(FMT)
root_logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    LOG_PATH,
    maxBytes=1_000_000,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setFormatter(FMT)
root_logger.addHandler(file_handler)

log = logging.getLogger(__name__)

ALL_STEPS = {
    "bronze": bronze.ingest,
    "silver": silver.transform,
    "checks": checks.validate,
    "gold": gold.build,
}


def run(selected=None, csv_path=None, db_path=None):
    steps = {
        key: value
        for key, value in ALL_STEPS.items()
        if selected is None or key in selected
    }

    db = db_path or DB_PATH
    start_total = time.time()

    log.info("Etapas selecionadas: %s", ", ".join(steps))
    log.info("Conectando ao warehouse: %s", db)

    with duckdb.connect(db) as con:
        for name, fn in steps.items():
            log.info("=== Iniciando etapa: %s ===", name)

            start_step = time.time()

            if name == "bronze" and csv_path:
                fn(con, csv_path)
            else:
                fn(con)

            elapsed = time.time() - start_step
            log.info("=== Etapa %s concluída em %.1fs ===", name, elapsed)

        _print_summary(con, steps, time.time() - start_total)


def _count(con, query):
    try:
        return con.execute(query).fetchone()[0]
    except duckdb.CatalogException:
        return None


def _print_summary(con, steps, elapsed):
    log.info("")
    log.info("╔══════════════════════════════════╗")
    log.info("║         RESUMO DO PIPELINE       ║")
    log.info("╠══════════════════════════════════╣")

    bronze_count = None
    silver_count = None

    if "bronze" in steps:
        bronze_count = _count(
            con,
            "SELECT count(*) FROM bronze.books_raw",
        )
        log.info(
            "║  bronze.books_raw       %8s  ║",
            bronze_count if bronze_count is not None else "N/A",
        )

    if "silver" in steps:
        silver_count = _count(
            con,
            "SELECT count(*) FROM silver.books",
        )

        log.info(
            "║  silver.books           %8s  ║",
            silver_count if silver_count is not None else "N/A",
        )

        if bronze_count is not None and silver_count is not None:
            log.info(
                "║  linhas descartadas     %8d  ║",
                bronze_count - silver_count,
            )

    if "gold" in steps:
        log.info("╠══════════════════════════════════╣")

        tables = (
            ("gold.top_authors", "gold.top_authors"),
            ("gold.top_books", "gold.top_books"),
            ("gold.books_by_language", "gold.books_by_language"),
        )

        for label, table in tables:
            count = _count(con, f"SELECT count(*) FROM {table}")

            log.info(
                "║  %-24s %8s  ║",
                label,
                count if count is not None else "N/A",
            )

    log.info("╠══════════════════════════════════╣")
    log.info("║  tempo total          %9.2fs  ║", elapsed)
    log.info("╚══════════════════════════════════╝")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Goodreads data pipeline",
    )

    parser.add_argument(
        "--steps",
        help=(
            "Etapas a executar, separadas por vírgula. "
            f"Disponíveis: {', '.join(ALL_STEPS)}"
        ),
    )

    parser.add_argument(
        "--input",
        help="Caminho para o CSV de entrada (padrão: data/books.csv)",
    )

    parser.add_argument(
        "--db",
        help=f"Caminho para o banco DuckDB (padrão: {DB_PATH})",
    )

    args = parser.parse_args()

    selected = (
        [step.strip() for step in args.steps.split(",")]
        if args.steps
        else None
    )

    if selected:
        invalid = [step for step in selected if step not in ALL_STEPS]

        if invalid:
            print(
                (
                    f"Etapas inválidas: {', '.join(invalid)}. "
                    f"Disponíveis: {', '.join(ALL_STEPS)}"
                ),
            )
            sys.exit(1)

    try:
        run(selected, csv_path=args.input, db_path=args.db)

    except Exception as exc:
        log.exception("Pipeline falhou: %s", exc)
        sys.exit(1)
