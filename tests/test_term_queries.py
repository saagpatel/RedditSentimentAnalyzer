"""Tests for term frequency extraction."""

from __future__ import annotations

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


def _seed_posts(conn: sqlite3.Connection, sub_id: int) -> None:
    base_ts = 1710000000
    posts = [
        ("p1", "Warriors win championship game tonight", 0.8),
        ("p2", "Warriors lose terrible game against Lakers", -0.6),
        ("p3", "Championship parade downtown celebration", 0.9),
        ("p4", "Game highlights best plays tonight", 0.3),
        ("p5", "Trade rumors warriors players moving", -0.1),
    ]
    for pid, title, compound in posts:
        queries.upsert_post(conn, {
            "id": pid,
            "subreddit_id": sub_id,
            "title": title,
            "body": None,
            "author": "user",
            "score": 100,
            "upvote_ratio": 0.9,
            "num_comments": 5,
            "created_utc": base_ts,
            "vader_compound": compound,
            "vader_pos": 0.3,
            "vader_neg": 0.1,
            "vader_neu": 0.6,
            "llm_sentiment": None,
            "llm_confidence": None,
            "llm_reasoning": None,
            "sentiment_source": "vader",
        })
        base_ts += 100
    conn.commit()


class TestGetTermFrequency:
    def test_returns_terms(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        terms = queries.get_term_frequency(db, sub_id)
        assert len(terms) > 0

    def test_sorted_by_count_desc(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        terms = queries.get_term_frequency(db, sub_id)
        counts = [t["count"] for t in terms]
        assert counts == sorted(counts, reverse=True)

    def test_stopwords_filtered(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        terms = queries.get_term_frequency(db, sub_id)
        term_words = {t["term"] for t in terms}
        # Common stopwords should not appear
        assert "the" not in term_words
        assert "and" not in term_words
        assert "is" not in term_words

    def test_warriors_appears(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        terms = queries.get_term_frequency(db, sub_id)
        term_words = {t["term"] for t in terms}
        assert "warriors" in term_words

    def test_game_appears_multiple_times(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        terms = queries.get_term_frequency(db, sub_id)
        game_term = next((t for t in terms if t["term"] == "game"), None)
        assert game_term is not None
        assert game_term["count"] >= 2

    def test_avg_compound_in_range(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        terms = queries.get_term_frequency(db, sub_id)
        for t in terms:
            assert -1 <= t["avg_compound"] <= 1

    def test_limit_respected(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        terms = queries.get_term_frequency(db, sub_id, limit=3)
        assert len(terms) <= 3

    def test_time_range_filter(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        # Very narrow range should return fewer terms
        terms = queries.get_term_frequency(
            db, sub_id, start_ts=1710000000, end_ts=1710000050
        )
        # Only first post falls in this range
        assert len(terms) > 0

    def test_empty_subreddit(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "empty_sub")
        terms = queries.get_term_frequency(db, sub_id)
        assert terms == []

    def test_term_has_required_keys(self, db: sqlite3.Connection):
        sub_id = queries.get_or_create_subreddit(db, "warriors")
        _seed_posts(db, sub_id)
        terms = queries.get_term_frequency(db, sub_id)
        for t in terms:
            assert "term" in t
            assert "count" in t
            assert "avg_compound" in t
