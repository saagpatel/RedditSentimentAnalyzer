"""Tests for API routes using FastAPI TestClient."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db.connection import close_connection, deploy_schema, get_connection
from backend.db import queries

# Use a temp file DB so it works across threads (TestClient uses a different thread)
_test_db = Path(tempfile.mkdtemp()) / "test.db"

import backend.db.connection as conn_module

_original_get_connection = conn_module.get_connection


def _test_get_connection(db_path=None):
    # Only redirect default (no explicit path) to temp file.
    # Explicit paths (e.g., ":memory:" from other test files) pass through.
    if db_path is not None:
        return _original_get_connection(db_path=db_path)
    return _original_get_connection(db_path=str(_test_db))


conn_module.get_connection = _test_get_connection

from backend.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Deploy schema and seed data for each test."""
    db = str(_test_db)
    deploy_schema(db_path=db)
    conn = get_connection(db_path=db)

    # Clean any prior data
    for table in ("sentiment_buckets", "comments", "posts", "keywords", "subreddits"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()

    # Seed a subreddit with posts and buckets
    sub_id = queries.get_or_create_subreddit(conn, "nba")
    base_ts = 1710000000

    for i in range(5):
        queries.upsert_post(conn, {
            "id": f"post_{i}",
            "subreddit_id": sub_id,
            "title": f"Test post {i}",
            "body": f"Body of post {i}",
            "author": f"user_{i}",
            "score": (i + 1) * 100,
            "upvote_ratio": 0.9,
            "num_comments": 10,
            "created_utc": base_ts + i * 21600,
            "vader_compound": -0.3 + i * 0.2,
            "vader_pos": 0.3,
            "vader_neg": 0.1,
            "vader_neu": 0.6,
            "llm_sentiment": None,
            "llm_confidence": None,
            "llm_reasoning": None,
            "sentiment_source": "vader",
        })

    # Add a comment
    queries.upsert_comment(conn, {
        "id": "com_1",
        "post_id": "post_0",
        "parent_id": None,
        "depth": 0,
        "body": "Great post!",
        "author": "commenter",
        "score": 50,
        "created_utc": base_ts + 100,
        "vader_compound": 0.6,
        "vader_pos": 0.4,
        "vader_neg": 0.0,
        "vader_neu": 0.6,
    })
    conn.commit()

    # Compute buckets
    queries.compute_sentiment_buckets(conn, sub_id)
    queries.detect_and_flag_spikes(conn, sub_id, threshold=0.3)

    yield


class TestHealth:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "tracked_subreddits" in data


class TestSentimentTimeseries:
    def test_happy_path(self):
        resp = client.get("/api/sentiment/timeseries", params={"subreddit": "nba"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["subreddit"] == "nba"
        assert isinstance(data["buckets"], list)
        assert len(data["buckets"]) > 0

    def test_with_time_range(self):
        resp = client.get("/api/sentiment/timeseries", params={
            "subreddit": "nba",
            "start": 1710000000,
            "end": 1710100000,
        })
        assert resp.status_code == 200

    def test_bucket_size_12h(self):
        resp = client.get("/api/sentiment/timeseries", params={
            "subreddit": "nba",
            "bucket_size": "12h",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["buckets"], list)

    def test_bucket_size_1d(self):
        resp = client.get("/api/sentiment/timeseries", params={
            "subreddit": "nba",
            "bucket_size": "1d",
        })
        assert resp.status_code == 200

    def test_subreddit_not_found(self):
        resp = client.get("/api/sentiment/timeseries", params={"subreddit": "nonexistent"})
        assert resp.status_code == 404

    def test_missing_subreddit_param(self):
        resp = client.get("/api/sentiment/timeseries")
        assert resp.status_code == 422


class TestSentimentCompare:
    def test_happy_path(self):
        resp = client.get("/api/sentiment/compare", params={"subreddits": "nba"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["series"]) == 1
        assert data["series"][0]["subreddit"] == "nba"

    def test_unknown_subreddit_skipped(self):
        resp = client.get("/api/sentiment/compare", params={"subreddits": "nba,fake_sub"})
        assert resp.status_code == 200
        data = resp.json()
        names = [s["subreddit"] for s in data["series"]]
        assert "nba" in names
        assert "fake_sub" not in names

    def test_empty_subreddits(self):
        resp = client.get("/api/sentiment/compare", params={"subreddits": ""})
        assert resp.status_code == 422


class TestTopPosts:
    def test_happy_path(self):
        resp = client.get("/api/posts/top", params={"subreddit": "nba"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["posts"]) > 0
        scores = [p["score"] for p in data["posts"]]
        assert scores == sorted(scores, reverse=True)

    def test_with_limit(self):
        resp = client.get("/api/posts/top", params={"subreddit": "nba", "limit": 2})
        assert resp.status_code == 200
        assert len(resp.json()["posts"]) == 2

    def test_url_field(self):
        resp = client.get("/api/posts/top", params={"subreddit": "nba"})
        post = resp.json()["posts"][0]
        assert "reddit.com" in post["url"]
        assert "nba" in post["url"]

    def test_subreddit_not_found(self):
        resp = client.get("/api/posts/top", params={"subreddit": "nonexistent"})
        assert resp.status_code == 404


class TestPostDetail:
    def test_happy_path(self):
        resp = client.get("/api/posts/post_0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "post_0"
        assert data["title"] == "Test post 0"
        assert isinstance(data["comments"], list)
        assert len(data["comments"]) >= 1

    def test_not_found(self):
        resp = client.get("/api/posts/nonexistent")
        assert resp.status_code == 404


class TestTerms:
    def test_happy_path(self):
        resp = client.get("/api/posts/terms", params={"subreddit": "nba"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["subreddit"] == "nba"
        assert isinstance(data["terms"], list)

    def test_with_limit(self):
        resp = client.get("/api/posts/terms", params={"subreddit": "nba", "limit": 3})
        assert resp.status_code == 200
        assert len(resp.json()["terms"]) <= 3

    def test_subreddit_not_found(self):
        resp = client.get("/api/posts/terms", params={"subreddit": "nonexistent"})
        assert resp.status_code == 404

    def test_term_structure(self):
        resp = client.get("/api/posts/terms", params={"subreddit": "nba"})
        data = resp.json()
        for term in data["terms"]:
            assert "term" in term
            assert "count" in term
            assert "avg_compound" in term
            assert isinstance(term["count"], int)


class TestSpikes:
    def test_happy_path(self):
        resp = client.get("/api/spikes", params={"subreddit": "nba"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["spikes"], list)

    def test_subreddit_not_found(self):
        resp = client.get("/api/spikes", params={"subreddit": "nonexistent"})
        assert resp.status_code == 404

    def test_spike_structure(self):
        resp = client.get("/api/spikes", params={
            "subreddit": "nba",
            "lookback_hours": 720,
        })
        data = resp.json()
        for spike in data["spikes"]:
            assert "bucket_start" in spike
            assert "delta_compound" in spike
            assert spike["direction"] in ("positive", "negative")
            assert isinstance(spike["top_posts"], list)
