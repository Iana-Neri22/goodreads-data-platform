import duckdb
import pytest

from ingestion import bronze, silver, checks, gold


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
        (
            "SELECT count(*) FROM "
            "(SELECT book_id FROM silver.books "
            "GROUP BY book_id HAVING count(*) > 1)"
        )
    ).fetchone()[0]
    assert count == 0, f"{count} book_ids duplicados na silver"


def test_silver_types(con):
    cols = {row[0]: row[1] for row in con.execute("DESCRIBE silver.books").fetchall()}
    assert cols["book_id"] == "INTEGER"
    assert cols["average_rating"] == "DOUBLE"
    assert cols["num_pages"] == "INTEGER"
    assert cols["publication_date"] == "DATE"
    assert "TIMESTAMP" in cols["loaded_at"]


def test_quality_checks_pass(con):
    checks.validate(con)


def test_gold_top_authors(con):
    count = con.execute("SELECT count(*) FROM gold.top_authors").fetchone()[0]
    assert count > 0, "gold.top_authors está vazia"


def test_gold_top_books_min_ratings(con):
    count = con.execute(
        "SELECT count(*) FROM gold.top_books WHERE ratings_count < 1000"
    ).fetchone()[0]
    assert count == 0, "gold.top_books contém livros com menos de 1000 avaliações"


def test_bronze_rejects_missing_file():
    conn = duckdb.connect(":memory:")
    with pytest.raises(FileNotFoundError):
        bronze.ingest(conn, csv_path="nao_existe.csv")


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
