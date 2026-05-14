.PHONY: lint format format-check type-check test run check clean install dashboard

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

clean:
	if exist warehouse.duckdb del /f /q warehouse.duckdb
	if exist logs rmdir /s /q logs
	if exist data\exports rmdir /s /q data\exports
