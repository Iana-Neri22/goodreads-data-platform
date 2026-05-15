import argparse
import logging
import sys
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from typing import cast

import duckdb

from ingestion import bronze, checks, gold, silver
from ingestion.config import settings

settings.log_path.parent.mkdir(exist_ok=True)

FMT = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(FMT)
root_logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    settings.log_path,
    maxBytes=settings.log_max_bytes,
    backupCount=settings.log_backup_count,
    encoding="utf-8",
)
file_handler.setFormatter(FMT)
root_logger.addHandler(file_handler)

log = logging.getLogger(__name__)

ALL_STEPS: dict[str, Callable[..., object]] = {
    "bronze": bronze.ingest,
    "silver": silver.transform,
    "checks": checks.validate,
    "gold": gold.build,
}


def run(
    selected: list[str] | None = None, csv_path: str | None = None, db_path: str | None = None
) -> None:
    steps = {key: value for key, value in ALL_STEPS.items() if selected is None or key in selected}

    db = db_path or str(settings.db_path)
    start_total = time.time()
    checks_summary: tuple[int, int] | None = None

    log.info("Etapas selecionadas: %s", ", ".join(steps))
    log.info("Conectando ao warehouse: %s", db)

    with duckdb.connect(db) as con:
        for name, fn in steps.items():
            log.info("=== Iniciando etapa: %s ===", name)

            start_step = time.time()

            if name == "bronze" and csv_path:
                fn(con, csv_path)
            elif name == "checks":
                checks_summary = cast("tuple[int, int]", fn(con))
            else:
                fn(con)

            elapsed = time.time() - start_step
            log.info("=== Etapa %s concluída em %.1fs ===", name, elapsed)

        _print_summary(con, steps, time.time() - start_total, checks_summary)


def _count(con: duckdb.DuckDBPyConnection, query: str) -> int | None:
    try:
        row = con.execute(query).fetchone()
        return row[0] if row is not None else None
    except duckdb.CatalogException:
        return None


def _print_summary(
    con: duckdb.DuckDBPyConnection,
    steps: dict[str, Callable[..., object]],
    elapsed: float,
    checks_summary: tuple[int, int] | None = None,
) -> None:
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

        for table in ("gold.top_authors", "gold.top_books", "gold.books_by_language"):
            count = _count(con, f"SELECT count(*) FROM {table}")
            log.info("║  %-24s %8s  ║", table, count if count is not None else "N/A")

    if "checks" in steps:
        log.info("╠══════════════════════════════════╣")
        if checks_summary is not None:
            passed, total = checks_summary
            log.info("║  verificações        %3d/%3d OK  ║", passed, total)
        else:
            log.info("║  verificações                OK  ║")

    log.info("╠══════════════════════════════════╣")
    log.info("║  tempo total          %9.2fs  ║", elapsed)
    log.info("╚══════════════════════════════════╝")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Goodreads data pipeline",
    )

    parser.add_argument(
        "--steps",
        help=(f"Etapas a executar, separadas por vírgula. Disponíveis: {', '.join(ALL_STEPS)}"),
    )

    parser.add_argument(
        "--input",
        help="Caminho para o CSV de entrada (padrão: data/books.csv)",
    )

    parser.add_argument(
        "--db",
        help=f"Caminho para o banco DuckDB (padrão: {settings.db_path})",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nível de logging (padrão: INFO)",
    )

    args = parser.parse_args()

    logging.getLogger().setLevel(args.log_level)

    selected = [step.strip() for step in args.steps.split(",")] if args.steps else None

    if selected:
        invalid = [step for step in selected if step not in ALL_STEPS]

        if invalid:
            log.error(
                "Etapas inválidas: %s. Disponíveis: %s",
                ", ".join(invalid),
                ", ".join(ALL_STEPS),
            )
            sys.exit(1)

    try:
        run(selected, csv_path=args.input, db_path=args.db)

    except Exception:
        log.exception("Pipeline falhou")
        sys.exit(1)
