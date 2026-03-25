"""Tests for backend.db.connection using in-memory SQLite."""

import sqlite3

import pytest

from backend.db.connection import (
    close_connection,
    deploy_schema,
    get_connection,
    get_transaction,
)


@pytest.fixture()
def mem_db():
    """Provide an in-memory database with schema deployed."""
    deploy_schema(db_path=":memory:")
    conn = get_connection(db_path=":memory:")
    yield conn
    close_connection(db_path=":memory:")


class TestDeploySchema:
    def test_creates_all_tables(self, mem_db: sqlite3.Connection):
        tables = mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = sorted(r["name"] for r in tables)
        assert "comments" in table_names
        assert "posts" in table_names
        assert "subreddits" in table_names
        assert "sentiment_buckets" in table_names
        assert "keywords" in table_names

    def test_idempotent(self, mem_db: sqlite3.Connection):
        deploy_schema(db_path=":memory:")
        deploy_schema(db_path=":memory:")
        tables = mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert len(tables) >= 5

    def test_indexes_created(self, mem_db: sqlite3.Connection):
        indexes = mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()
        index_names = [r["name"] for r in indexes]
        assert "idx_posts_subreddit_time" in index_names
        assert "idx_posts_vader" in index_names
        assert "idx_comments_post_depth" in index_names
        assert "idx_buckets_subreddit_time" in index_names
        assert "idx_buckets_unique" in index_names


class TestGetConnection:
    def test_returns_connection(self, mem_db: sqlite3.Connection):
        assert isinstance(mem_db, sqlite3.Connection)

    def test_row_factory(self, mem_db: sqlite3.Connection):
        row = mem_db.execute("SELECT 1 AS val").fetchone()
        assert row["val"] == 1

    def test_foreign_keys_enabled(self, mem_db: sqlite3.Connection):
        fk = mem_db.execute("PRAGMA foreign_keys").fetchone()
        assert fk[0] == 1


class TestTransaction:
    def test_commit_on_success(self, mem_db: sqlite3.Connection):
        with get_transaction(db_path=":memory:") as conn:
            conn.execute(
                "INSERT INTO subreddits (name, display_name) VALUES (?, ?)",
                ("test_sub", "Test"),
            )
        row = mem_db.execute(
            "SELECT name FROM subreddits WHERE name = 'test_sub'"
        ).fetchone()
        assert row is not None

    def test_rollback_on_error(self, mem_db: sqlite3.Connection):
        with pytest.raises(sqlite3.IntegrityError):
            with get_transaction(db_path=":memory:") as conn:
                conn.execute(
                    "INSERT INTO subreddits (name, display_name) VALUES (?, ?)",
                    ("roll_sub", "Roll"),
                )
                # Duplicate name triggers UNIQUE violation
                conn.execute(
                    "INSERT INTO subreddits (name, display_name) VALUES (?, ?)",
                    ("roll_sub", "Roll2"),
                )
        row = mem_db.execute(
            "SELECT name FROM subreddits WHERE name = 'roll_sub'"
        ).fetchone()
        assert row is None
