# goodreads-data-platform

Pipeline de dados em camadas (bronze → silver → gold) para análise do dataset de livros do Goodreads, usando DuckDB como warehouse local.

## Estrutura

```
goodreads-data-platform/
├── data/
│   └── books.csv          # Dataset fonte
├── ingestion/
│   ├── bronze.py          # Ingestão bruta do CSV
│   ├── silver.py          # Limpeza e tipagem dos dados
│   ├── checks.py          # Verificações de qualidade
│   └── gold.py            # Agregações analíticas
├── logs/
│   └── pipeline.log       # Histórico de execuções
├── pipeline.py            # Orquestrador do pipeline
└── warehouse.duckdb       # Banco local (gerado, não versionado)
```

## Camadas

| Camada | Tabela | Descrição |
|---|---|---|
| Bronze | `bronze.books_raw` | Dados brutos do CSV, todos como VARCHAR |
| Silver | `silver.books` | Dados limpos com tipos corretos, linhas inválidas removidas |
| Gold | `gold.top_authors` | Autores agregados por total de avaliações |
| Gold | `gold.top_books` | Livros mais bem avaliados (mín. 1.000 avaliações) |

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Uso

Executar o pipeline completo:

```bash
python pipeline.py
```

Os resultados são exportados automaticamente para `data/exports/`:
- `top_authors.csv`
- `top_books.csv`

Os logs ficam em `logs/pipeline.log` com rotação automática (máx. 1 MB, 5 arquivos).
