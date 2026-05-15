import argparse
import sys

import duckdb
from prefect import flow, task

from ingestion import bronze, checks, gold, silver
from ingestion.config import settings

ALL_STEPS = ["bronze", "silver", "checks", "gold"]


@task(name="bronze")
def ingest_bronze(csv_path: str | None = None, db_path: str | None = None) -> None:
    with duckdb.connect(db_path or str(settings.db_path)) as con:
        bronze.ingest(con, csv_path=csv_path)


@task(name="silver")
def transform_silver(db_path: str | None = None) -> None:
    with duckdb.connect(db_path or str(settings.db_path)) as con:
        silver.transform(con)


@task(name="checks")
def validate_checks(db_path: str | None = None) -> tuple[int, int]:
    with duckdb.connect(db_path or str(settings.db_path)) as con:
        return checks.validate(con)


@task(name="gold")
def build_gold(db_path: str | None = None) -> None:
    with duckdb.connect(db_path or str(settings.db_path)) as con:
        gold.build(con)


@flow(name="goodreads-pipeline", log_prints=True)
def pipeline(
    csv_path: str | None = None,
    db_path: str | None = None,
    steps: list[str] | None = None,
) -> None:
    selected = steps or ALL_STEPS

    invalid = [s for s in selected if s not in ALL_STEPS]
    if invalid:
        raise ValueError(
            f"Etapas inválidas: {', '.join(invalid)}. Disponíveis: {', '.join(ALL_STEPS)}"
        )

    if "bronze" in selected:
        ingest_bronze(csv_path=csv_path, db_path=db_path)
    if "silver" in selected:
        transform_silver(db_path=db_path)
    if "checks" in selected:
        validate_checks(db_path=db_path)
    if "gold" in selected:
        build_gold(db_path=db_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Goodreads pipeline (Prefect)")
    parser.add_argument(
        "--steps",
        help=f"Etapas separadas por vírgula. Disponíveis: {', '.join(ALL_STEPS)}",
    )
    parser.add_argument("--input", help="Caminho para o CSV de entrada (padrão: data/books.csv)")
    parser.add_argument("--db", help=f"Caminho para o banco DuckDB (padrão: {settings.db_path})")

    args = parser.parse_args()

    selected = [s.strip() for s in args.steps.split(",")] if args.steps else None

    if selected:
        invalid = [s for s in selected if s not in ALL_STEPS]
        if invalid:
            print(  # noqa: T201
                f"Etapas inválidas: {', '.join(invalid)}. Disponíveis: {', '.join(ALL_STEPS)}",
                file=sys.stderr,
            )
            sys.exit(1)

    pipeline(csv_path=args.input, db_path=args.db, steps=selected)
