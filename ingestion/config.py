from pathlib import Path

from pydantic import field_validator
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
    min_silver_retention_pct: float = 0.80

    @field_validator("min_ratings_for_top_books")
    @classmethod
    def _valid_min_ratings(cls, v: int) -> int:
        if v <= 0:
            msg = "min_ratings_for_top_books deve ser maior que 0"
            raise ValueError(msg)
        return v

    @field_validator("min_silver_retention_pct")
    @classmethod
    def _valid_retention(cls, v: float) -> float:
        if not 0 < v <= 1:
            msg = "min_silver_retention_pct deve estar entre 0 (exclusivo) e 1 (inclusivo)"
            raise ValueError(msg)
        return v


settings = Settings()
