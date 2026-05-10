# goodreads-data-platform

[![CI](https://github.com/IanaNeri22/goodreads-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/IanaNeri22/goodreads-data-platform/actions/workflows/ci.yml)

Pipeline de dados em camadas (bronze → silver → gold) para análise do dataset de livros do Goodreads, usando DuckDB como warehouse local.

## Estrutura

```
goodreads-data-platform/
├── .github/
│   └── workflows/
│       └── ci.yml             # Pipeline de CI (lint, format, type-check, testes)
├── data/
│   ├── books.csv              # Dataset fonte
│   └── exports/               # CSVs exportados (gerados, não versionados)
├── ingestion/
│   ├── bronze.py              # Ingestão bruta do CSV
│   ├── silver.py              # Limpeza e tipagem dos dados
│   ├── checks.py              # Verificações de qualidade
│   ├── gold.py                # Agregações analíticas
│   └── py.typed               # Marcador PEP 561
├── logs/
│   └── pipeline.log           # Histórico de execuções (gerado, não versionado)
├── tests/
│   └── test_pipeline.py       # Testes automatizados
├── .pre-commit-config.yaml    # Hooks de pre-commit (ruff, mypy)
├── .python-version            # Versão do Python (3.11)
├── Makefile                   # Atalhos de comandos
├── pipeline.py                # Orquestrador do pipeline
├── pyproject.toml             # Configuração de ferramentas
├── requirements.txt           # Dependências
└── warehouse.duckdb           # Banco local (gerado, não versionado)
```

## Camadas

| Camada | Tabela | Descrição |
|---|---|---|
| Bronze | `bronze.books_raw` | Dados brutos do CSV, todos como VARCHAR |
| Silver | `silver.books` | Dados limpos com tipos corretos, linhas inválidas removidas |
| Gold | `gold.top_authors` | Autores agregados por total de avaliações |
| Gold | `gold.top_books` | Livros mais bem avaliados (mín. 1.000 avaliações) |
| Gold | `gold.books_by_language` | Distribuição de livros por idioma |

## Instalação

```bash
make install
```

Ou manualmente:

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
pre-commit install
```

## Uso

Executar o pipeline completo:

```bash
python pipeline.py
```

Executar etapas específicas:

```bash
python pipeline.py --steps bronze,silver
```

Usar um CSV diferente do padrão:

```bash
python pipeline.py --input caminho/para/outro.csv
```

Usar um banco DuckDB diferente do padrão:

```bash
python pipeline.py --db outro_warehouse.duckdb
```

Controlar o nível de logging:

```bash
python pipeline.py --log-level WARNING   # silencioso
python pipeline.py --log-level DEBUG     # verboso
```

Os argumentos podem ser combinados:

```bash
python pipeline.py --input outro.csv --db dev.duckdb --steps bronze,silver --log-level WARNING
```

Os resultados são exportados automaticamente para `data/exports/`:
- `top_authors.csv`
- `top_books.csv`
- `books_by_language.csv`

Os logs ficam em `logs/pipeline.log` com rotação automática (máx. 1 MB, 5 arquivos).

## Qualidade de código

Atalhos via `make`:

```bash
make install     # cria venv, instala dependências e configura pre-commit
make check       # lint + formato + type-check + testes (equivalente ao CI)
make test        # pytest com cobertura (mínimo 90%)
make lint        # ruff check .
make format      # ruff format .
make type-check  # mypy ingestion pipeline.py
make run         # python pipeline.py
make clean       # remove warehouse.duckdb, logs/ e data/exports/
```

Ou diretamente:

```bash
pytest
ruff check .
ruff format .
mypy ingestion pipeline.py
```

Lint, formato e type check são executados automaticamente no CI a cada push.
