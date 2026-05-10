import argparse
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import duckdb
from ingestion import bronze, silver, checks, gold

ROOT = Path(__file__).parent
DB_PATH = str(ROOT / "warehouse.duckdb")
LOG_PATH = ROOT / "logs" / "pipeline.log"

LOG_PATH.parent.mkdir(exist_ok=True)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

logging.getLogger().setLevel(logging.INFO)

_console = logging.StreamHandler()
_console.setFormatter(_fmt)
logging.getLogger().addHandler(_console)

_file = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
_file.setFormatter(_fmt)
logging.getLogger().addHandler(_file)

log = logging.getLogger(__name__)


ALL_STEPS = {
    "bronze": bronze.ingest,
    "silver": silver.transform,
    "checks": checks.validate,
    "gold":   gold.build,
}


def run(selected=None, csv_path=None):
    steps = {k: v for k, v in ALL_STEPS.items() if selected is None or k in selected}

    start_total = time.time()
    log.info("Etapas selecionadas: %s", ", ".join(steps))
    log.info("Conectando ao warehouse: %s", DB_PATH)
    with duckdb.connect(DB_PATH) as con:
        for name, fn in steps.items():
            log.info("=== Iniciando etapa: %s ===", name)
            t = time.time()
            fn(con, csv_path) if name == "bronze" and csv_path else fn(con)
            log.info("=== Etapa %s concluída em %.1fs ===", name, time.time() - t)

        _print_summary(con, steps, time.time() - start_total)


def _count(con, query):
    try:
        return con.execute(query).fetchone()[0]
    except Exception:
        return None


def _print_summary(con, steps, elapsed):
    log.info("")
    log.info("╔══════════════════════════════════╗")
    log.info("║         RESUMO DO PIPELINE       ║")
    log.info("╠══════════════════════════════════╣")

    if "bronze" in steps:
        bronze = _count(con, "SELECT count(*) FROM bronze.books_raw")
        log.info("║  bronze.books_raw       %8s  ║", bronze if bronze is not None else "N/A")

    if "silver" in steps:
        silver = _count(con, "SELECT count(*) FROM silver.books")
        log.info("║  silver.books           %8s  ║", silver if silver is not None else "N/A")
        if "bronze" in steps and bronze is not None and silver is not None:
            log.info("║  linhas descartadas     %8d  ║", bronze - silver)

    if "gold" in steps:
        log.info("╠══════════════════════════════════╣")
        for label, table in (
            ("gold.top_authors      ", "gold.top_authors"),
            ("gold.top_books        ", "gold.top_books"),
            ("gold.books_by_language", "gold.books_by_language"),
        ):
            n = _count(con, f"SELECT count(*) FROM {table}")
            log.info("║  %s %8s  ║", label, n if n is not None else "N/A")

    log.info("╠══════════════════════════════════╣")
    log.info("║  tempo total          %9.2fs  ║", elapsed)
    log.info("╚══════════════════════════════════╝")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Goodreads data pipeline")
    parser.add_argument(
        "--steps",
        help=f"Etapas a executar, separadas por vírgula. Disponíveis: {', '.join(ALL_STEPS)}",
    )
    parser.add_argument(
        "--input",
        help="Caminho para o CSV de entrada (padrão: data/books.csv)",
    )
    args = parser.parse_args()

    selected = [s.strip() for s in args.steps.split(",")] if args.steps else None
    if selected:
        invalid = [s for s in selected if s not in ALL_STEPS]
        if invalid:
            print(f"Etapas inválidas: {', '.join(invalid)}. Disponíveis: {', '.join(ALL_STEPS)}")
            sys.exit(1)

    try:
        run(selected, csv_path=args.input)
    except Exception as e:
        log.error("Pipeline falhou: %s", e)
        sys.exit(1)
