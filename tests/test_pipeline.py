import duckdb
import pytest

from ingestion import bronze, checks, gold, silver


@pytest.fixture(scope="module")
def con():
    conn = duckdb.connect(":memory:")
    bronze.ingest(conn)
    silver.transform(conn)
    gold.build(conn)
    yield conn
    conn.close()


def test_bronze_loaded(con):
    count = con.execute("SELECT count(*) FROM bronze.books_raw").fetchone()[0]
    assert count > 0, "bronze.books_raw está vazia"


def test_silver_removes_invalid_rows(con):
    bronze_count = con.execute("SELECT count(*) FROM bronze.books_raw").fetchone()[0]
    silver_count = con.execute("SELECT count(*) FROM silver.books").fetchone()[0]
    assert silver_count < bronze_count, "silver deveria descartar linhas inválidas"
    assert silver_count > 0, "silver.books está vazia"


def test_silver_no_zero_pages(con):
    count = con.execute("SELECT count(*) FROM silver.books WHERE num_pages <= 0").fetchone()[0]
    assert count == 0, f"{count} livros com num_pages <= 0 na silver"


def test_silver_ratings_in_range(con):
    count = con.execute(
        "SELECT count(*) FROM silver.books WHERE average_rating NOT BETWEEN 0 AND 5"
    ).fetchone()[0]
    assert count == 0, f"{count} livros com average_rating fora de [0, 5]"


def test_silver_no_duplicate_book_ids(con):
    count = con.execute(
        "SELECT count(*) FROM "
        "(SELECT book_id FROM silver.books "
        "GROUP BY book_id HAVING count(*) > 1)"
    ).fetchone()[0]
    assert count == 0, f"{count} book_ids duplicados na silver"


def test_silver_types(con):
    cols = {row[0]: row[1] for row in con.execute("DESCRIBE silver.books").fetchall()}
    assert cols["book_id"] == "INTEGER"
    assert cols["average_rating"] == "DOUBLE"
    assert cols["num_pages"] == "INTEGER"
    assert cols["publication_date"] == "DATE"
    assert cols["loaded_at"] == "TIMESTAMP"


def test_quality_checks_pass(con):
    checks.validate(con)


def test_gold_top_authors(con):
    count = con.execute("SELECT count(*) FROM gold.top_authors").fetchone()[0]
    assert count > 0, "gold.top_authors está vazia"


def test_gold_types(con):
    for table in ("top_authors", "top_books", "books_by_language"):
        cols = {row[0]: row[1] for row in con.execute(f"DESCRIBE gold.{table}").fetchall()}
        assert cols["loaded_at"] == "TIMESTAMP", (
            f"gold.{table}.loaded_at deveria ser TIMESTAMP, é {cols['loaded_at']}"
        )


def test_gold_top_books_min_ratings(con):
    count = con.execute(
        "SELECT count(*) FROM gold.top_books WHERE ratings_count < 1000"
    ).fetchone()[0]
    assert count == 0, "gold.top_books contém livros com menos de 1000 avaliações"


def test_bronze_rejects_missing_file():
    conn = duckdb.connect(":memory:")
    with pytest.raises(FileNotFoundError):
        bronze.ingest(conn, csv_path="nao_existe.csv")


def test_bronze_standalone_mode(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setattr(bronze, "DB_PATH", db_path)
    bronze.ingest()

    conn = duckdb.connect(str(db_path))
    count = conn.execute("SELECT count(*) FROM bronze.books_raw").fetchone()[0]
    conn.close()
    assert count > 0, "bronze.books_raw está vazia no modo standalone"


def test_silver_standalone_mode(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    bronze.ingest(conn)
    conn.close()

    monkeypatch.setattr(silver, "DB_PATH", db_path)
    silver.transform()

    conn = duckdb.connect(str(db_path))
    count = conn.execute("SELECT count(*) FROM silver.books").fetchone()[0]
    conn.close()
    assert count > 0, "silver.books está vazia no modo standalone"


def test_gold_standalone_mode(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    bronze.ingest(conn)
    silver.transform(conn)
    conn.close()

    monkeypatch.setattr(gold, "DB_PATH", db_path)
    monkeypatch.setattr(gold, "EXPORTS_PATH", tmp_path / "exports")
    gold.build()

    conn = duckdb.connect(str(db_path))
    count = conn.execute("SELECT count(*) FROM gold.top_authors").fetchone()[0]
    conn.close()
    assert count > 0, "gold.top_authors está vazia no modo standalone"


def test_gold_exports_exclude_loaded_at(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    exports_path = tmp_path / "exports"
    conn = duckdb.connect(str(db_path))
    bronze.ingest(conn)
    silver.transform(conn)
    conn.close()

    monkeypatch.setattr(gold, "DB_PATH", db_path)
    monkeypatch.setattr(gold, "EXPORTS_PATH", exports_path)
    gold.build()

    for table in ("top_authors", "top_books", "books_by_language"):
        header = (
            (exports_path / f"{table}.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
        )
        assert "loaded_at" not in header, f"{table}.csv contém coluna loaded_at"


def test_checks_standalone_mode(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    bronze.ingest(conn)
    silver.transform(conn)
    conn.close()

    monkeypatch.setattr(checks, "DB_PATH", db_path)
    checks.validate()


def test_silver_no_rows_dropped_when_all_valid():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA bronze")
    conn.execute(
        """
        CREATE TABLE bronze.books_raw (
            bookid VARCHAR, title VARCHAR, authors VARCHAR, average_rating VARCHAR,
            isbn VARCHAR, isbn13 VARCHAR, language_code VARCHAR, num_pages VARCHAR,
            ratings_count VARCHAR, text_reviews_count VARCHAR,
            publication_date VARCHAR, publisher VARCHAR
        )
        """
    )
    conn.execute(
        """
        INSERT INTO bronze.books_raw VALUES
        ('1', 'Valid Book', 'Author', '4.5', '123', '9780123', 'eng', '300',
         '1000', '50', '01/01/2000', 'Publisher')
        """
    )
    silver.transform(conn)
    bronze_count = conn.execute("SELECT count(*) FROM bronze.books_raw").fetchone()[0]
    silver_count = conn.execute("SELECT count(*) FROM silver.books").fetchone()[0]
    assert bronze_count == silver_count
    conn.close()


def test_checks_fail_on_invalid_data():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA silver")
    conn.execute("""
        CREATE TABLE silver.books (
            book_id       INTEGER,
            title         VARCHAR,
            authors       VARCHAR,
            average_rating DOUBLE,
            num_pages     INTEGER,
            ratings_count INTEGER,
            publication_date DATE
        )
    """)
    conn.execute("""
        INSERT INTO silver.books VALUES (1, 'Test', 'Author', 10.0, 100, 50, '2020-01-01')
    """)
    with pytest.raises(ValueError):
        checks.validate(conn)
    conn.close()
