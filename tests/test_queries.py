"""Tests for backend.db.queries against in-memory SQLite."""

import sqlite3

import pytest

from backend.db.connection import close_connection, deploy_schema, get_connection
from backend.db import queries


@pytest.fixture()
def db():
    deploy_schema(db_path=":memory:")
    conn = get_connection(db_path=":memory:")
    yield conn
    close_connection(db_path=":memory:")


def _make_post(post_id: str = "abc123", subreddit_id: int = 1, **overrides) -> dict:
    base = {
        "id": post_id,
        "subreddit_id": subreddit_id,
        "title": "Test post title",
        "body": "Test body",
        "author": "test_user",
        "score": 100,
        "upvote_ratio": 0.95,
        "num_comments": 10,
        "created_utc": 1710000000,
        "vader_compound": 0.5,
        "vader_pos": 0.3,
        "vader_neg": 0.1,
        "vader_neu": 0.6,
        "llm_sentiment": None,
        "llm_confidence": None,
        "llm_reasoning": None,
        "sentiment_source": "vader",
    }
    base.update(overrides)
    return base


def _make_comment(comment_id: str = "com1", post_id: str = "abc123", **overrides) -> dict:
    base = {
        "id": comment_id,
        "post_id": post_id,
        "parent_id": None,
        "depth": 0,
        "body": "Great comment",
        "author": "commenter",
        "score": 50,
        "created_utc": 1710000100,
        "vader_compound": 0.4,
        "vader_pos": 0.2,
        "vader_neg": 0.1,
        "vader_neu": 0.7,
    }
    base.update(overrides)
    return base


class TestSubreddits:
    def test_get_or_create(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        assert isinstance(sub_id, int)
        assert sub_id > 0

    def test_idempotent(self, db: sqlite3.Connection):
        id1 = queries.get_or_create_subreddit(db, "nba")
        id2 = queries.get_or_create_subreddit(db, "nba")
        assert id1 == id2

    def test_case_normalized(self, db: sqlite3.Connection):
        id1 = queries.get_or_create_subreddit(db, "NBA")
        id2 = queries.get_or_create_subreddit(db, "nba")
        assert id1 == id2

    def test_tracked(self, db: sqlite3.Connection):
        queries.get_or_create_subreddit(db, "nba")
        tracked = queries.get_tracked_subreddits(db)
        names = [r["name"] for r in tracked]
        assert "nba" in names

    def test_untrack(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        queries.set_subreddit_tracked(db, sub_id, False)
        tracked = queries.get_tracked_subreddits(db)
        names = [r["name"] for r in tracked]
        assert "nba" not in names


class TestPosts:
    def test_upsert_and_retrieve(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        post = _make_post(subreddit_id=sub_id)
        queries.upsert_post(db, post)
        db.commit()
        assert queries.post_exists(db, "abc123")

    def test_bulk_upsert(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        posts = [
            _make_post(post_id=f"post_{i}", subreddit_id=sub_id, created_utc=1710000000 + i)
            for i in range(5)
        ]
        count = queries.bulk_upsert_posts(db, posts)
        db.commit()
        assert count == 5
        assert queries.get_post_count(db, sub_id) == 5

    def test_bulk_upsert_empty(self, db: sqlite3.Connection):
        assert queries.bulk_upsert_posts(db, []) == 0

    def test_upsert_updates_score(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        post = _make_post(subreddit_id=sub_id, score=100)
        queries.upsert_post(db, post)
        db.commit()

        post["score"] = 200
        queries.upsert_post(db, post)
        db.commit()

        row = queries.get_post_by_id(db, "abc123")
        assert row["score"] == 200

    def test_latest_timestamp(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        assert queries.get_latest_post_timestamp(db, sub_id) is None

        queries.upsert_post(db, _make_post(post_id="p1", subreddit_id=sub_id, created_utc=100))
        queries.upsert_post(db, _make_post(post_id="p2", subreddit_id=sub_id, created_utc=200))
        db.commit()

        assert queries.get_latest_post_timestamp(db, sub_id) == 200

    def test_post_not_exists(self, db: sqlite3.Connection):
        assert queries.post_exists(db, "nonexistent") is False


class TestComments:
    def test_upsert_and_count(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        queries.upsert_post(db, _make_post(subreddit_id=sub_id))
        db.commit()

        queries.upsert_comment(db, _make_comment())
        db.commit()

        assert queries.get_comment_count(db, depth=0) == 1

    def test_bulk_upsert_comments(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        queries.upsert_post(db, _make_post(subreddit_id=sub_id))
        db.commit()

        comments = [_make_comment(comment_id=f"c{i}") for i in range(3)]
        count = queries.bulk_upsert_comments(db, comments)
        db.commit()

        assert count == 3
        assert queries.get_comment_count(db) == 3

    def test_get_comments_for_post(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "nba")
        queries.upsert_post(db, _make_post(subreddit_id=sub_id))
        db.commit()

        for i in range(3):
            queries.upsert_comment(db, _make_comment(comment_id=f"c{i}", score=i * 10))
        db.commit()

        rows = queries.get_comments_for_post(db, "abc123", limit=2)
        assert len(rows) == 2
        assert rows[0]["score"] >= rows[1]["score"]  # ordered by score DESC
