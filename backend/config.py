"""Application configuration — pure defaults, no .env loading.

Secrets live in macOS Keychain via `keyring`. All other settings are
code defaults overridable only by editing this file or future CLI args.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


class IngestionConfig(BaseModel):
    subreddits: list[str] = ["nba"]
    poll_interval_minutes: int = 15
    rate_limit_requests_per_min: int = 80
    first_run_hot_limit: int = 500
    first_run_top_limit: int = 500
    incremental_new_limit: int = 200


class SentimentConfig(BaseModel):
    llm_escalation_enabled: bool = False
    llm_escalation_threshold: float = 0.05
    llm_escalation_cap: int = 50
    spike_threshold: float = 0.3
    bucket_hours: int = 6


class DatabaseConfig(BaseModel):
    db_dir: Path = Path.home() / "Library" / "Application Support" / "reddit-sentiment"
    db_name: str = "reddit_sentiment.db"

    @property
    def db_path(self) -> Path:
        return self.db_dir / self.db_name


class AppConfig(BaseModel):
    ingestion: IngestionConfig = IngestionConfig()
    sentiment: SentimentConfig = SentimentConfig()
    database: DatabaseConfig = DatabaseConfig()
    log_level: str = "INFO"
    user_agent: str = "reddit-sentiment-analyzer/0.1.0"


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig()


def configure_logging(config: AppConfig | None = None) -> None:
    cfg = config or get_config()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
