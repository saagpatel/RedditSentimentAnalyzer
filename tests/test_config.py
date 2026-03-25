"""Tests for backend.config."""

from backend.config import AppConfig, DatabaseConfig, IngestionConfig, SentimentConfig


class TestIngestionConfig:
    def test_defaults(self):
        cfg = IngestionConfig()
        assert cfg.subreddits == ["nba"]
        assert cfg.poll_interval_minutes == 15
        assert cfg.rate_limit_requests_per_min == 80
        assert cfg.first_run_hot_limit == 500
        assert cfg.first_run_top_limit == 500
        assert cfg.incremental_new_limit == 200

    def test_override(self):
        cfg = IngestionConfig(subreddits=["nfl", "nba"], poll_interval_minutes=5)
        assert cfg.subreddits == ["nfl", "nba"]
        assert cfg.poll_interval_minutes == 5


class TestSentimentConfig:
    def test_defaults(self):
        cfg = SentimentConfig()
        assert cfg.llm_escalation_enabled is False
        assert cfg.llm_escalation_threshold == 0.05
        assert cfg.llm_escalation_cap == 50
        assert cfg.spike_threshold == 0.3
        assert cfg.bucket_hours == 6


class TestDatabaseConfig:
    def test_db_path_property(self):
        cfg = DatabaseConfig()
        assert cfg.db_path == cfg.db_dir / cfg.db_name
        assert str(cfg.db_path).endswith("reddit_sentiment.db")
        assert "reddit-sentiment" in str(cfg.db_path)


class TestAppConfig:
    def test_nested_defaults(self):
        cfg = AppConfig()
        assert isinstance(cfg.ingestion, IngestionConfig)
        assert isinstance(cfg.sentiment, SentimentConfig)
        assert isinstance(cfg.database, DatabaseConfig)
        assert cfg.log_level == "INFO"
        assert "reddit-sentiment" in cfg.user_agent
