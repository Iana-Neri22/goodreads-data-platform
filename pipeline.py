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


def run(selected=None):
    steps = {k: v for k, v in ALL_STEPS.items() if selected is None or k in selected}

    start_total = time.time()
    log.info("Etapas selecionadas: %s", ", ".join(steps))
    log.info("Conectando ao warehouse: %s", DB_PATH)
    with duckdb.connect(DB_PATH) as con:
        for name, fn in steps.items():
            log.info("=== Iniciando etapa: %s ===", name)
            t = time.time()
            fn(con)
            log.info("=== Etapa %s concluída em %.1fs ===", name, time.time() - t)

        _print_summary(con, time.time() - start_total)


def _print_summary(con, elapsed):
    bronze   = con.execute("SELECT count(*) FROM bronze.books_raw").fetchone()[0]
    silver   = con.execute("SELECT count(*) FROM silver.books").fetchone()[0]
    authors   = con.execute("SELECT count(*) FROM gold.top_authors").fetchone()[0]
    books     = con.execute("SELECT count(*) FROM gold.top_books").fetchone()[0]
    languages = con.execute("SELECT count(*) FROM gold.books_by_language").fetchone()[0]

    log.info("")
    log.info("╔══════════════════════════════════╗")
    log.info("║         RESUMO DO PIPELINE       ║")
    log.info("╠══════════════════════════════════╣")
    log.info("║  bronze.books_raw       %8d  ║", bronze)
    log.info("║  silver.books           %8d  ║", silver)
    log.info("║  linhas descartadas     %8d  ║", bronze - silver)
    log.info("╠══════════════════════════════════╣")
    log.info("║  gold.top_authors       %8d  ║", authors)
    log.info("║  gold.top_books         %8d  ║", books)
    log.info("║  gold.books_by_language %8d  ║", languages)
    log.info("╠══════════════════════════════════╣")
    log.info("║  tempo total          %9.2fs  ║", elapsed)
    log.info("╚══════════════════════════════════╝")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Goodreads data pipeline")
    parser.add_argument(
        "--steps",
        help=f"Etapas a executar, separadas por vírgula. Disponíveis: {', '.join(ALL_STEPS)}",
    )
    args = parser.parse_args()

    selected = [s.strip() for s in args.steps.split(",")] if args.steps else None
    if selected:
        invalid = [s for s in selected if s not in ALL_STEPS]
        if invalid:
            print(f"Etapas inválidas: {', '.join(invalid)}. Disponíveis: {', '.join(ALL_STEPS)}")
            sys.exit(1)

    try:
        run(selected)
    except Exception as e:
        log.error("Pipeline falhou: %s", e)
        sys.exit(1)
