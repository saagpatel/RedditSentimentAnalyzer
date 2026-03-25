"""Tests for sentiment bucket aggregation and spike detection queries."""

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


def _seed_subreddit(conn: sqlite3.Connection, name: str = "nba") -> int:
    return queries.get_or_create_subreddit(conn, name)


def _insert_post(
    conn: sqlite3.Connection,
    post_id: str,
    subreddit_id: int,
    created_utc: int,
    vader_compound: float = 0.5,
    score: int = 100,
    upvote_ratio: float = 0.9,
) -> None:
    queries.upsert_post(conn, {
        "id": post_id,
        "subreddit_id": subreddit_id,
        "title": f"Post {post_id}",
        "body": "Body text",
        "author": "user",
        "score": score,
        "upvote_ratio": upvote_ratio,
        "num_comments": 5,
        "created_utc": created_utc,
        "vader_compound": vader_compound,
        "vader_pos": 0.3,
        "vader_neg": 0.1,
        "vader_neu": 0.6,
        "llm_sentiment": None,
        "llm_confidence": None,
        "llm_reasoning": None,
        "sentiment_source": "vader",
    })
    conn.commit()


# 6h = 21600 seconds
BUCKET_SIZE = 21600


class TestComputeSentimentBuckets:
    def test_single_bucket(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        base_ts = 1710000000
        _insert_post(db, "p1", sub_id, base_ts, vader_compound=0.5)
        _insert_post(db, "p2", sub_id, base_ts + 100, vader_compound=0.3)

        count = queries.compute_sentiment_buckets(db, sub_id)
        assert count >= 1

        buckets = queries.get_sentiment_buckets(db, sub_id)
        assert len(buckets) == 1
        assert buckets[0]["post_count"] == 2
        assert abs(buckets[0]["avg_compound"] - 0.4) < 0.01

    def test_multiple_buckets(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        # Two posts in different 6h windows
        _insert_post(db, "p1", sub_id, 1710000000, vader_compound=0.8)
        _insert_post(db, "p2", sub_id, 1710000000 + BUCKET_SIZE, vader_compound=-0.2)

        queries.compute_sentiment_buckets(db, sub_id)
        buckets = queries.get_sentiment_buckets(db, sub_id)
        assert len(buckets) == 2
        # First bucket is positive, second is negative
        assert buckets[0]["avg_compound"] > 0
        assert buckets[1]["avg_compound"] < 0

    def test_with_time_range_filter(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        _insert_post(db, "p1", sub_id, 1710000000)
        _insert_post(db, "p2", sub_id, 1710050000)

        count = queries.compute_sentiment_buckets(
            db, sub_id, start_ts=1710040000
        )
        assert count >= 1
        buckets = queries.get_sentiment_buckets(db, sub_id)
        # Only one post should be in the bucket (the one after 1710040000)
        found_recent = any(b["post_count"] == 1 for b in buckets)
        assert found_recent

    def test_empty_subreddit(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        count = queries.compute_sentiment_buckets(db, sub_id)
        assert count == 0


class TestDetectAndFlagSpikes:
    def test_spike_detected(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        base = 1710000000
        # Two buckets with large compound delta (>0.3)
        _insert_post(db, "p1", sub_id, base, vader_compound=-0.2)
        _insert_post(db, "p2", sub_id, base + BUCKET_SIZE, vader_compound=0.5)

        queries.compute_sentiment_buckets(db, sub_id)
        spike_count = queries.detect_and_flag_spikes(db, sub_id, threshold=0.3)
        assert spike_count >= 1

        buckets = queries.get_sentiment_buckets(db, sub_id)
        flagged = [b for b in buckets if b["spike_flag"]]
        assert len(flagged) >= 1

    def test_no_spike_small_delta(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        base = 1710000000
        # Two buckets with small delta
        _insert_post(db, "p1", sub_id, base, vader_compound=0.4)
        _insert_post(db, "p2", sub_id, base + BUCKET_SIZE, vader_compound=0.45)

        queries.compute_sentiment_buckets(db, sub_id)
        spike_count = queries.detect_and_flag_spikes(db, sub_id, threshold=0.3)
        assert spike_count == 0

    def test_spike_flag_reset_on_recompute(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        base = 1710000000
        _insert_post(db, "p1", sub_id, base, vader_compound=-0.3)
        _insert_post(db, "p2", sub_id, base + BUCKET_SIZE, vader_compound=0.5)

        queries.compute_sentiment_buckets(db, sub_id)
        queries.detect_and_flag_spikes(db, sub_id, threshold=0.3)
        # Re-detect with higher threshold — should clear flags
        queries.detect_and_flag_spikes(db, sub_id, threshold=0.99)

        buckets = queries.get_sentiment_buckets(db, sub_id)
        flagged = [b for b in buckets if b["spike_flag"]]
        assert len(flagged) == 0


class TestGetSentimentBuckets:
    def test_time_range_filter(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        _insert_post(db, "p1", sub_id, 1710000000)
        _insert_post(db, "p2", sub_id, 1710100000)

        queries.compute_sentiment_buckets(db, sub_id)
        all_buckets = queries.get_sentiment_buckets(db, sub_id)
        filtered = queries.get_sentiment_buckets(
            db, sub_id, start_ts=1710090000
        )
        assert len(filtered) <= len(all_buckets)

    def test_ordered_by_time(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        for i in range(5):
            _insert_post(db, f"p{i}", sub_id, 1710000000 + i * BUCKET_SIZE)

        queries.compute_sentiment_buckets(db, sub_id)
        buckets = queries.get_sentiment_buckets(db, sub_id)
        timestamps = [b["bucket_start"] for b in buckets]
        assert timestamps == sorted(timestamps)


class TestGetTopPostsInRange:
    def test_returns_sorted_by_score(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        _insert_post(db, "p1", sub_id, 1710000000, score=50)
        _insert_post(db, "p2", sub_id, 1710000001, score=200)
        _insert_post(db, "p3", sub_id, 1710000002, score=100)

        rows = queries.get_top_posts_in_range(db, sub_id, sort_by="score")
        scores = [r["score"] for r in rows]
        assert scores == [200, 100, 50]

    def test_limit(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        for i in range(10):
            _insert_post(db, f"p{i}", sub_id, 1710000000 + i)

        rows = queries.get_top_posts_in_range(db, sub_id, limit=3)
        assert len(rows) == 3

    def test_time_range_filter(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        _insert_post(db, "old", sub_id, 1710000000)
        _insert_post(db, "new", sub_id, 1710100000)

        rows = queries.get_top_posts_in_range(
            db, sub_id, start_ts=1710050000
        )
        assert len(rows) == 1
        assert rows[0]["id"] == "new"

    def test_sort_by_compound(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        _insert_post(db, "p1", sub_id, 1710000000, vader_compound=0.9)
        _insert_post(db, "p2", sub_id, 1710000001, vader_compound=0.1)

        rows = queries.get_top_posts_in_range(db, sub_id, sort_by="compound")
        assert rows[0]["vader_compound"] > rows[1]["vader_compound"]


class TestGetSubredditByName:
    def test_found(self, db: sqlite3.Connection):
        queries.get_or_create_subreddit(db, "nba")
        row = queries.get_subreddit_by_name(db, "nba")
        assert row is not None
        assert row["name"] == "nba"

    def test_case_insensitive(self, db: sqlite3.Connection):
        queries.get_or_create_subreddit(db, "nba")
        row = queries.get_subreddit_by_name(db, "NBA")
        assert row is not None

    def test_not_found(self, db: sqlite3.Connection):
        row = queries.get_subreddit_by_name(db, "nonexistent")
        assert row is None


class TestGetPostsInBucket:
    def test_returns_posts_in_window(self, db: sqlite3.Connection):
        sub_id = _seed_subreddit(db)
        bucket_start = (1710000000 // BUCKET_SIZE) * BUCKET_SIZE
        _insert_post(db, "in1", sub_id, bucket_start + 100)
        _insert_post(db, "in2", sub_id, bucket_start + 200)
        _insert_post(db, "out", sub_id, bucket_start + BUCKET_SIZE + 100)

        rows = queries.get_posts_in_bucket(db, sub_id, bucket_start)
        ids = [r["id"] for r in rows]
        assert "in1" in ids
        assert "in2" in ids
        assert "out" not in ids
