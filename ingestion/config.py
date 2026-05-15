from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOODREADS_", env_file=".env", extra="ignore")

    db_path: Path = _ROOT / "warehouse.duckdb"
    csv_path: Path = _ROOT / "data" / "books.csv"
    exports_path: Path = _ROOT / "data" / "exports"
    log_path: Path = _ROOT / "logs" / "pipeline.log"
    log_max_bytes: int = 1_000_000
    log_backup_count: int = 5
    min_ratings_for_top_books: int = 1_000


settings = Settings()
