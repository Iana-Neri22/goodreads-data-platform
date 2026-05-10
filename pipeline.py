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


def run():
    steps = [
        ("bronze", bronze.ingest),
        ("silver", silver.transform),
        ("checks", checks.validate),
        ("gold",   gold.build),
    ]

    start_total = time.time()
    log.info("Conectando ao warehouse: %s", DB_PATH)
    with duckdb.connect(DB_PATH) as con:
        for name, fn in steps:
            log.info("=== Iniciando etapa: %s ===", name)
            t = time.time()
            fn(con)
            log.info("=== Etapa %s concluída em %.1fs ===", name, time.time() - t)

    log.info("Pipeline concluído em %.1fs", time.time() - start_total)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log.error("Pipeline falhou: %s", e)
        sys.exit(1)
