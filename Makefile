.PHONY: lint format format-check type-check test run check clean install dashboard prefect prefect-run

install:
	python -m venv .venv
	.venv\Scripts\pip install -r requirements.txt
	.venv\Scripts\pre-commit install

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

type-check:
	mypy ingestion pipeline.py

test:
	pytest

run:
	python pipeline.py

dashboard:
	streamlit run dashboard/app.py

check: lint format-check type-check test

prefect:
	powershell -ExecutionPolicy Bypass -File scripts\prefect_start.ps1

prefect-run:
	powershell -NoProfile -Command "$$env:PYTHONUTF8='1'; $$env:PREFECT_API_URL='http://127.0.0.1:4200/api'; .venv\Scripts\prefect deployment run 'goodreads-pipeline/full-pipeline'"

clean:
	if exist warehouse.duckdb del /f /q warehouse.duckdb
	if exist logs rmdir /s /q logs
	if exist data\exports rmdir /s /q data\exports
